"""
Motor de fets: lectures deterministes sobre les sèries i els derivats.

Cada regla llegeix DuckDB per les claus comunes (geo_codi, cnae_codi) i escriu
fets amb l'enunciat ja redactat, el valor, la referència amb què es compara,
les sèries d'origen i els avisos de qualitat heretats. L'enunciat surt en català
(enunciat) i en castellà (enunciat_es), redactats per la mateixa regla amb les
mateixes xifres. El xatbot, la newsletter i les candidates a predicció llegeixen
la taula `fets`; cap d'ells torna a calcular res.

Regles:
  extrem           el darrer valor és el més alt o el més baix des de fa N anys
  ratxa            N períodes seguits amb el mateix signe
  inflexio         canvi de signe després d'una ratxa
  ranking          canvi de posició d'una CCAA (>= 3 llocs) i qui encapçala o tanca
  divergencia      dues fonts que s'separen per sobre d'un llindar
  quadrant_branca  creixement de vendes reals x marge, per branca
  saturacio        locals per habitant x vendes per habitant, per CCAA

migrate.py crida construeix(con) després dels derivats i desa el resultat sencer
(la taula es regenera a cada migració: un fet només viu mentre les dades el diuen).
"""
import re

import pandas as pd

from data.sql.dimensions import NOMS_ES_BRANCA, NOMS_ES_TERRITORI

_COLS = ["fet_id", "regla", "enunciat", "valor", "unitat", "comparacio",
         "valor_referencia", "data", "series", "geo_codi", "cnae_codi", "avis",
         "rellevancia", "enunciat_es"]
_LANGS = ("ca", "es")

# Ceuta i Melilla queden fora dels rànquings i de la saturació: amb 80.000
# habitants qualsevol ràtio per càpita surt als extrems i no diu res del comerç.
_FORA_RANKING = {"ccaa:18", "ccaa:19"}

_MESOS = {
    "ca": ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost",
           "setembre", "octubre", "novembre", "desembre"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"],
}
_ORDINALS = {"ca": {1: "1r", 2: "2n", 3: "3r", 4: "4t"},
             "es": {1: "1.er", 2: "2.º", 3: "3.er", 4: "4.º"}}
# Unitats: la clau és la catalana, que és la que es desa a la columna unitat.
_UNITATS_ES = {"euros de 2021": "euros de 2021", "persones": "personas",
               "empreses per 1.000 hab.": "empresas por 1.000 hab.", "punts": "puntos",
               "milers de persones": "miles de personas",
               "locals per 1.000 hab.": "locales por 1.000 hab."}
# Grups de l'IPC (dim_1 del deflactor), que arriben en català.
_DIM1_ES = {"Parament de la llar": "muebles y artículos del hogar",
            "Alimentació i begudes no alcohòliques": "alimentos y bebidas no alcohólicas",
            "Vestit i calçat": "vestido y calzado", "Índex general": "índice general"}
_SIGNE = {"ca": {1: "positiu", -1: "negatiu"}, "es": {1: "positivo", -1: "negativo"}}
_PER_ANY = {"monthly": 12, "quarterly": 4, "annual": 1}


# ─── Format ──────────────────────────────────────────────────────────────────

def _num(v, signe=False):
    """Una xifra decimal com a màxim, amb coma decimal i punt de milers."""
    dec = 0 if abs(v) >= 1000 else 1
    txt = f"{abs(v):,.{dec}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    if v < 0:
        return f"−{txt}"
    return f"+{txt}" if signe and v > 0 else txt


def _u(unitat, lang):
    return _UNITATS_ES.get(unitat, unitat) if lang == "es" else unitat


def _valor(v, fmt, unitat="", lang="ca"):
    if fmt == "pct":
        return f"{_num(v, signe=True)}%"
    return f"{_num(v)} {_u(unitat, lang)}".strip()


def _periode(d, freq, lang="ca"):
    d = pd.Timestamp(d)
    de = "del" if lang == "ca" else "de"
    if freq == "monthly":
        return f"{_MESOS[lang][d.month - 1]} {de} {d.year}"
    if freq == "quarterly":
        return f"{_ORDINALS[lang][d.quarter]} trimestre {de} {d.year}"
    return str(d.year)


_PREP_ES = {"a": "en", "des de": "desde", "fins a": "hasta"}


def _amb(prep, d, freq, lang="ca"):
    """Període amb preposició: 'a l'agost del 2026', 'des del 2024' / 'en agosto de
    2026', 'desde 2024', 'hasta el 2.º trimestre de 2026'. prep és la catalana."""
    txt = _periode(d, freq, lang)
    if lang == "es":
        return f"{_PREP_ES[prep]} {'el ' if freq == 'quarterly' else ''}{txt}"
    if freq == "monthly" and txt[0] in "aeiou":
        return f"{prep} l'{txt}"
    # a + el = al, de + el = del; 'fins a' i 'des de' acaben igual
    return f"{prep}l {txt}"


def _de(txt, lang="ca"):
    if lang == "es":
        return f"de {txt}"
    return f"d'{txt}" if txt[0] in "aeiouàèéíòóú" else f"de {txt}"


def _periodes(n, freq, lang="ca"):
    unitat = {"ca": {"monthly": ("mes", "mesos"), "quarterly": ("trimestre", "trimestres"),
                     "annual": ("any", "anys")},
              "es": {"monthly": ("mes", "meses"), "quarterly": ("trimestre", "trimestres"),
                     "annual": ("año", "años")}}[lang][freq]
    return f"{n} {unitat[0] if n == 1 else unitat[1]}"


def _seguits(n, freq, signe, lang):
    """'8 mesos seguits en positiu' / '8 meses seguidos en positivo'."""
    s = "seguits" if lang == "ca" else "seguidos"
    return f"{_periodes(n, freq, lang)} {s} en {_SIGNE[lang][signe]}"


def _cap(txt):
    return txt[0].upper() + txt[1:]


# ─── Lectura ─────────────────────────────────────────────────────────────────

def _obs(con, serie_id, **filtres):
    where = "".join(f" AND {k} = ?" for k in filtres)
    df = con.execute(f"""
        SELECT date, value, dim_1, dim_2, dim_3, geo_codi, cnae_codi, avis
        FROM observations WHERE serie_id = ?{where}
    """, [serie_id, *filtres.values()]).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _uneix_avis(vals, extra=()):
    codis = set(extra)
    for v in vals:
        if isinstance(v, str) and v:
            codis.update(v.split(","))
    return ",".join(sorted(codis)) or None


def _fet(**kw):
    kw["data"] = pd.Timestamp(kw["data"]).date()
    kw["series"] = ",".join(kw["series"])
    return {c: (None if c in kw and not isinstance(kw[c], str) and pd.isna(kw[c])
                else kw.get(c)) for c in _COLS}


class _Noms:
    """Noms de territoris i branques: en català de dim_territori i dim_branca, en
    castellà de dimensions.NOMS_ES_* (si no hi són, el català)."""

    def __init__(self, con):
        self.geo = dict(con.execute("SELECT geo_codi, nom FROM dim_territori").fetchall())
        self.cnae = dict(con.execute("SELECT cnae_codi, nom FROM dim_branca").fetchall())
        self.freq = dict(con.execute("SELECT serie_id, frequency FROM series_metadata").fetchall())

    def territori(self, codi, lang="ca"):
        nom = self.geo.get(codi, codi)
        return NOMS_ES_TERRITORI.get(codi, nom) if lang == "es" else nom

    def nom_branca(self, codi, lang="ca"):
        nom = self.cnae.get(codi, codi)
        return NOMS_ES_BRANCA.get(codi, nom) if lang == "es" else nom

    def branca(self, codi, lang="ca"):
        if codi in ("47", None):
            return "comerç al detall" if lang == "ca" else "comercio minorista"
        # Fora la composició de les agrupacions de l'ICM: "Alimentació (4711+472)".
        nom = re.sub(r" \([\d+]+\)$", "", self.nom_branca(codi, lang))
        return nom[0].lower() + nom[1:]


# ─── Sèries vigilades (extrem, ratxa, inflexió) ──────────────────────────────

# tipus 'variacio': el signe té sentit (ratxes i inflexions); 'nivell': només extrems.
_BRANQUES_ICM = ["47", "47_SENSE473", "47_ALIM", "47_EQPERS", "47_EQLLAR", "47_SALUT",
                 "47_RESTA", "4791"]

VIGILADES = [
    dict(serie_id="icm_real", filtres=dict(geo_codi="pais:ES", dim_3="var_anual"),
         cnae=_BRANQUES_ICM, tipus="variacio", fmt="pct",
         etiqueta="vendes reals ({branca}), variació interanual",
         etiqueta_es="ventas reales ({branca}), variación interanual"),
    dict(serie_id="icm_real", filtres=dict(dim_3="var_anual", cnae_codi="47"),
         nivell_geo="ccaa", tipus="variacio", fmt="pct",
         etiqueta="vendes reals del comerç al detall ({territori}), variació interanual",
         etiqueta_es="ventas reales del comercio minorista ({territori}), variación interanual"),
    dict(serie_id="icm_ocupacio", filtres=dict(geo_codi="pais:ES", dim_3="var_anual",
                                               cnae_codi="47"),
         tipus="variacio", fmt="pct",
         etiqueta="ocupació del comerç al detall (ICM), variació interanual",
         etiqueta_es="empleo del comercio minorista (ICM), variación interanual"),
    dict(serie_id="der_icm_productivitat_var_anual",
         filtres=dict(geo_codi="pais:ES", cnae_codi="47"), tipus="variacio", fmt="pct",
         etiqueta="vendes reals per persona ocupada, variació interanual",
         etiqueta_es="ventas reales por persona ocupada, variación interanual"),
    # Eurostat (CVEC, base 2021): alimentació contra no alimentari; l'internet ja el porta l'ICM.
    dict(serie_id="europa_retail_branques_yoy", filtres=dict(geo_codi="pais:ES"),
         cnae=["47_STS_ALIM", "47_STS_NOALIM"], tipus="variacio", fmt="pct",
         etiqueta="volum de vendes, {branca}, variació interanual",
         etiqueta_es="volumen de ventas, {branca}, variación interanual"),
    dict(serie_id="targetes_tpv_var_import", filtres={}, tipus="variacio", fmt="pct",
         etiqueta="import pagat amb targeta en TPV, variació interanual",
         etiqueta_es="importe pagado con tarjeta en TPV, variación interanual"),
    dict(serie_id="der_tpv_menys_icm", filtres={}, tipus="variacio", fmt="pct",
         etiqueta="diferència entre la targeta i les vendes nominals del comerç",
         etiqueta_es="diferencia entre la tarjeta y las ventas nominales del comercio"),
    dict(serie_id="der_icm_deflactor_vs_ipc", filtres=dict(geo_codi="pais:ES"),
         per_dim_1=True, tipus="variacio", fmt="pct",
         etiqueta="preus de venda del comerç contra l'IPC ({dim_1})",
         etiqueta_es="precios de venta del comercio frente al IPC ({dim_1})"),
    dict(serie_id="confianza_consumidor_index_confianca", filtres={}, tipus="nivell",
         fmt="nivell", unitat="punts",
         etiqueta="indicador de confiança del consumidor",
         etiqueta_es="indicador de confianza del consumidor"),
    dict(serie_id="epa_retail_ocupats", filtres=dict(dim_1="total"), tipus="nivell",
         fmt="nivell", unitat="milers de persones",
         etiqueta="persones ocupades al comerç al detall (EPA)",
         etiqueta_es="personas ocupadas en el comercio minorista (EPA)"),
]

# Un extrem només és fet si la darrera vegada que es va superar fa com a mínim
# dos anys; una ratxa, si dura com a mínim mig any (o tres anys en sèries anuals).
_MIN_ANYS_EXTREM = 2
_MIN_RATXA = {"monthly": 6, "quarterly": 3, "annual": 3}
_MIN_RATXA_PREVIA = {"monthly": 3, "quarterly": 2, "annual": 2}
# Un canvi de signe per sota de mig punt és soroll, no una inflexió.
_MIN_INFLEXIO = 0.5


def _grups_vigilats(con, noms, v):
    df = _obs(con, v["serie_id"], **v["filtres"])
    if v.get("cnae"):
        df = df[df["cnae_codi"].isin(v["cnae"])]
    if v.get("nivell_geo") == "ccaa":
        df = df[df["geo_codi"].str.startswith("ccaa:") & ~df["geo_codi"].isin(_FORA_RANKING)]
    claus = ["geo_codi", "cnae_codi"] + (["dim_1"] if v.get("per_dim_1") else [])
    for clau, g in df.groupby(claus, dropna=False):
        g = g.sort_values("date").reset_index(drop=True)
        clau = tuple(None if pd.isna(c) else c for c in clau)
        geo, cnae = clau[0], clau[1]
        dim_1 = clau[2] if len(clau) > 2 else None
        etiquetes = {}
        for lang in _LANGS:
            d1 = (_DIM1_ES.get(dim_1, dim_1) if lang == "es" else dim_1) or ""
            etiquetes[lang] = v["etiqueta" if lang == "ca" else "etiqueta_es"].format(
                branca=noms.branca(cnae, lang), territori=noms.territori(geo, lang),
                dim_1=d1.lower())
        yield geo, cnae, dim_1, etiquetes, g


def _extrem(g, freq):
    """(sentit, data de l'anterior més extrem o None, períodes entremig) o None."""
    darrer = g["value"].iloc[-1]
    abans = g.iloc[:-1]
    for sentit, supera in (("max", abans["value"] > darrer), ("min", abans["value"] < darrer)):
        previs = abans[supera]
        if previs.empty:
            n = len(abans)
            ref = None
        else:
            n = len(abans) - previs.index[-1] - 1
            ref = previs["date"].iloc[-1]
        if n / _PER_ANY[freq] >= _MIN_ANYS_EXTREM:
            return sentit, ref, n
    return None


def _signe(x):
    return int(x > 0) - int(x < 0)


def _ratxa(valors):
    """Longitud de la ratxa final amb el mateix signe (0 si el darrer és 0)."""
    s = _signe(valors[-1])
    n = 0
    for x in reversed(valors):
        if s == 0 or _signe(x) != s:
            break
        n += 1
    return n


def _regles_vigilades(con, noms):
    fets = []
    for v in VIGILADES:
        freq = noms.freq[v["serie_id"]]
        for geo, cnae, dim_1, etiquetes, g in _grups_vigilats(con, noms, v):
            if len(g) < 3:
                continue
            d = g["date"].iloc[-1]
            x = g["value"].iloc[-1]
            unitat = v.get("unitat", "")
            val = {lang: _valor(x, v["fmt"], unitat, lang) for lang in _LANGS}
            base = dict(series=[v["serie_id"]], geo_codi=geo, cnae_codi=cnae, data=d,
                        valor=x, unitat=v.get("unitat") or "%")
            clau = f"{v['serie_id']}:{geo}:{cnae or ''}:{dim_1 or ''}"
            cap = {lang: _cap(etiquetes[lang]) for lang in _LANGS}

            ext = _extrem(g, freq)
            if ext:
                sentit, ref, n = ext
                adj = {"ca": "més alt" if sentit == "max" else "més baix",
                       "es": "más alto" if sentit == "max" else "más bajo"}
                enun = {}
                if ref is None:
                    inici = g["date"].iloc[0]
                    comp = f"tota la sèrie, que comença {_amb('a', inici, freq)}"
                    comp_es = f"toda la serie, que empieza {_amb('a', inici, freq, 'es')}"
                    for lang, c in (("ca", comp), ("es", comp_es)):
                        enun[lang] = (f"{cap[lang]}: {val[lang]} {_amb('a', d, freq, lang)}, "
                                      f"el valor {adj[lang]} de {c}.")
                    vref = None
                else:
                    comp = _amb("des de", ref, freq)
                    vref = float(g.loc[g["date"] == ref, "value"].iloc[0])
                    for lang in _LANGS:
                        enun[lang] = (f"{cap[lang]}: {val[lang]} {_amb('a', d, freq, lang)}, "
                                      f"el valor {adj[lang]} {_amb('des de', ref, freq, lang)} "
                                      f"({_valor(vref, v['fmt'], unitat, lang)}).")
                finestra = g.iloc[-(n + 2):] if ref is not None else g
                fets.append(_fet(fet_id=f"extrem_{sentit}:{clau}", regla="extrem",
                                 enunciat=enun["ca"], enunciat_es=enun["es"],
                                 comparacio=comp, valor_referencia=vref,
                                 avis=_uneix_avis(finestra["avis"]),
                                 rellevancia=min(n / _PER_ANY[freq], 10), **base))

            if v["tipus"] != "variacio":
                continue
            valors = g["value"].tolist()
            n = _ratxa(valors)
            signe = 1 if valors[-1] > 0 else -1
            if n == 1:
                n_prev = _ratxa(valors[:-1])
                if (n_prev >= _MIN_RATXA_PREVIA[freq] and _signe(valors[-2]) == -_signe(x)
                        and abs(x) >= _MIN_INFLEXIO):
                    previ = 1 if valors[-2] > 0 else -1
                    despres = {"ca": "després de", "es": "tras"}
                    passa = {"ca": "passa a", "es": "pasa a"}
                    enun = {lang: (f"{cap[lang]}: {passa[lang]} {_SIGNE[lang][signe]} "
                                   f"{_amb('a', d, freq, lang)} ({val[lang]}) {despres[lang]} "
                                   f"{_seguits(n_prev, freq, previ, lang)}.")
                            for lang in _LANGS}
                    fets.append(_fet(
                        fet_id=f"inflexio:{clau}", regla="inflexio",
                        enunciat=enun["ca"], enunciat_es=enun["es"],
                        comparacio=_seguits(n_prev, freq, previ, "ca"),
                        valor_referencia=float(valors[-2]),
                        avis=_uneix_avis(g["avis"].iloc[-(n_prev + 1):]),
                        rellevancia=min(n_prev / _PER_ANY[freq] * 2, 10), **base))
            elif n >= _MIN_RATXA[freq]:
                enun = {lang: (f"{cap[lang]}: {_seguits(n, freq, signe, lang)}, "
                               f"{_amb('fins a', d, freq, lang)} ({val[lang]}).")
                        for lang in _LANGS}
                fets.append(_fet(
                    fet_id=f"ratxa:{clau}", regla="ratxa",
                    enunciat=enun["ca"], enunciat_es=enun["es"],
                    comparacio=_seguits(n, freq, signe, "ca"), valor_referencia=None,
                    avis=_uneix_avis(g["avis"].iloc[-n:]),
                    rellevancia=min(n / _PER_ANY[freq], 10), **base))
    return fets


# ─── Rànquing de CCAA ────────────────────────────────────────────────────────

RANKINGS = [
    dict(serie_id="der_vendes_per_habitant_real", unitat="euros de 2021",
         etiqueta="vendes del comerç al detall per habitant",
         etiqueta_es="ventas del comercio minorista por habitante"),
    dict(serie_id="der_vendes_per_local_real", unitat="euros de 2021",
         etiqueta="vendes per local",
         etiqueta_es="ventas por local"),
    dict(serie_id="der_vendes_per_ocupat_real", unitat="euros de 2021",
         etiqueta="vendes per persona ocupada",
         etiqueta_es="ventas por persona ocupada"),
    dict(serie_id="der_ocupats_per_local", unitat="persones",
         etiqueta="persones ocupades per local",
         etiqueta_es="personas ocupadas por local"),
    dict(serie_id="empreses_per_1000hab", unitat="empreses per 1.000 hab.",
         etiqueta="empreses de comerç al detall per 1.000 habitants",
         etiqueta_es="empresas de comercio minorista por 1.000 habitantes"),
    # Una variació anual canvia molt de posició d'un any a l'altre: pesa la meitat
    # i demana un salt més gran (les CCAA s'apilen a poques dècimes).
    dict(serie_id="der_icm_real_var_anual", fmt="pct", unitat="%", pes=0.5,
         min_salt=5, etiqueta="creixement de les vendes reals",
         etiqueta_es="crecimiento de las ventas reales"),
]
_MIN_SALT = 3
# Qui encapçala o tanca igual que l'any anterior no és notícia: queda al fons.
_RELL_CAP_CUA_REPETIT = 0.25


def _regla_ranking(con, noms):
    fets = []
    for r in RANKINGS:
        df = _obs(con, r["serie_id"], cnae_codi="47")
        esp = df[df["geo_codi"] == "pais:ES"].set_index("date")
        df = df[df["geo_codi"].str.startswith("ccaa:") & ~df["geo_codi"].isin(_FORA_RANKING)]
        dates = sorted(df["date"].unique())
        if len(dates) < 2:
            continue
        d0, d1 = dates[-2], dates[-1]
        n_ccaa = df[df["date"] == d1]["geo_codi"].nunique()
        pos = {}
        for d in (d0, d1):
            t = df[df["date"] == d].sort_values("value", ascending=False).reset_index(drop=True)
            pos[d] = {row.geo_codi: (i + 1, row.value, row.avis) for i, row in t.iterrows()}
        fmt = r.get("fmt", "nivell")
        a0, a1 = _periode(d0, "annual"), _periode(d1, "annual")
        for geo, (p1, v1, av1) in pos[d1].items():
            if geo not in pos[d0]:
                continue
            p0, v0, av0 = pos[d0][geo]
            avis = _uneix_avis([av0, av1])
            base = dict(series=[r["serie_id"]], geo_codi=geo, cnae_codi="47", data=d1,
                        valor=v1, unitat=r["unitat"], avis=avis)
            nom = {lang: noms.territori(geo, lang) for lang in _LANGS}
            etq = {"ca": r["etiqueta"], "es": r["etiqueta_es"]}
            val = {lang: _valor(v1, fmt, r["unitat"], lang) for lang in _LANGS}
            if abs(p1 - p0) >= r.get("min_salt", _MIN_SALT):
                puja = p1 < p0
                enun = {
                    "ca": (f"{nom['ca']} {'puja' if puja else 'baixa'} de la posició {p0} a "
                           f"la {p1} de {n_ccaa} comunitats en {etq['ca']} entre el {a0} i "
                           f"el {a1} ({val['ca']})."),
                    "es": (f"{nom['es']} {'sube' if puja else 'baja'} del puesto {p0} al "
                           f"{p1} de {n_ccaa} comunidades en {etq['es']} entre {a0} y {a1} "
                           f"({val['es']})."),
                }
                fets.append(_fet(
                    fet_id=f"ranking:{r['serie_id']}:{geo}", regla="ranking",
                    enunciat=enun["ca"], enunciat_es=enun["es"],
                    comparacio=f"posició {p0} el {a0}", valor_referencia=float(p0),
                    rellevancia=abs(p1 - p0) / 2 * r.get("pes", 1), **base))
            if p1 in (1, n_ccaa):
                vesp = esp["value"].get(d1)
                comp = {lang: (f"{noms.territori('pais:ES', lang)}: "
                               f"{_valor(vesp, fmt, r['unitat'], lang)}"
                               if vesp is not None else None) for lang in _LANGS}
                lloc = {"ca": "encapçala" if p1 == 1 else "tanca",
                        "es": "encabeza" if p1 == 1 else "cierra"}
                enun = {
                    "ca": f"{nom['ca']} {lloc['ca']} el rànquing {_de(etq['ca'])} el {a1}: ",
                    "es": f"{nom['es']} {lloc['es']} el ranking {_de(etq['es'], 'es')} en {a1}: ",
                }
                enun = {lang: enun[lang] + val[lang]
                        + (f" ({comp[lang]})." if comp[lang] else ".") for lang in _LANGS}
                fets.append(_fet(
                    fet_id=f"ranking_{'cap' if p1 == 1 else 'cua'}:{r['serie_id']}",
                    regla="ranking", enunciat=enun["ca"], enunciat_es=enun["es"],
                    comparacio=comp["ca"], valor_referencia=vesp,
                    rellevancia=_RELL_CAP_CUA_REPETIT if p0 == p1 else 1.0, **base))
    return fets


# ─── Divergències entre fonts ────────────────────────────────────────────────

DIVERGENCIES = [
    dict(serie_id="der_tpv_menys_icm", llindar=5.0, filtres={},
         positiu="l'import pagat amb targeta creix {v} més que les vendes nominals del comerç",
         negatiu="l'import pagat amb targeta creix {v} menys que les vendes nominals del comerç",
         positiu_es="el importe pagado con tarjeta crece {v} más que las ventas nominales del comercio",
         negatiu_es="el importe pagado con tarjeta crece {v} menos que las ventas nominales del comercio"),
    dict(serie_id="der_icm_deflactor_vs_ipc", llindar=2.0, filtres=dict(geo_codi="pais:ES"),
         per_dim_1=True,
         positiu="els preus del que ven el comerç ({dim_1}) pugen {v} més que l'IPC del grup",
         negatiu="els preus del que ven el comerç ({dim_1}) pugen {v} menys que l'IPC del grup",
         positiu_es="los precios de lo que vende el comercio ({dim_1}) suben {v} más que el IPC del grupo",
         negatiu_es="los precios de lo que vende el comercio ({dim_1}) suben {v} menos que el IPC del grupo"),
]


def _regla_divergencia(con, noms):
    fets = []
    for dv in DIVERGENCIES:
        freq = noms.freq[dv["serie_id"]]
        df = _obs(con, dv["serie_id"], **dv["filtres"])
        claus = ["dim_1"] if dv.get("per_dim_1") else ["geo_codi"]
        for clau, g in df.groupby(claus, dropna=False):
            darrer = g.sort_values("date").iloc[-1]
            x = darrer["value"]
            if abs(x) < dv["llindar"]:
                continue
            dim_1 = clau[0] if dv.get("per_dim_1") else ""
            clau_txt = "positiu" if x > 0 else "negatiu"
            enun = {}
            for lang in _LANGS:
                d1 = (_DIM1_ES.get(dim_1, dim_1) if lang == "es" else dim_1) or ""
                txt = dv[clau_txt if lang == "ca" else f"{clau_txt}_es"].format(
                    v=f"{_num(abs(x))}%", dim_1=d1.lower())
                enun[lang] = f"{_periode(darrer['date'], freq, lang).capitalize()}: {txt}."
            comp = f"llindar de {_num(dv['llindar'])}%"
            fets.append(_fet(
                fet_id=f"divergencia:{dv['serie_id']}:{dim_1}", regla="divergencia",
                enunciat=enun["ca"], enunciat_es=enun["es"],
                valor=x, unitat="%", comparacio=comp, valor_referencia=dv["llindar"],
                data=darrer["date"], series=[dv["serie_id"]], geo_codi=darrer["geo_codi"],
                cnae_codi=darrer["cnae_codi"], avis=_uneix_avis([darrer["avis"]]),
                rellevancia=abs(x) / dv["llindar"]))
    return fets


# ─── Quadrant creixement x marge per branca ──────────────────────────────────

def _costat(x, ref, tol):
    """+1 per sobre, -1 per sota, 0 dins de la banda de tolerància."""
    return 0 if abs(x - ref) < tol else (1 if x > ref else -1)


# Per sota de mig punt de diferència amb la mediana, la branca hi és a prop:
# dir que creix "més" per una dècima seria un qualificador que no aguanta.
_TOL_QUADRANT = 0.5
_CREIX = {"ca": {1: "creix més que", 0: "creix com", -1: "creix menys que"},
          "es": {1: "crece más que", 0: "crece como", -1: "crece menos que"}}
_MARGE = {"ca": {1: "té més marge", 0: "té un marge semblant", -1: "té menys marge"},
          "es": {1: "tiene más margen", 0: "tiene un margen similar", -1: "tiene menos margen"}}


def _regla_quadrant(con, noms):
    cre = _obs(con, "der_icm_real_var_anual", geo_codi="pais:ES")
    mar = _obs(con, "marges_branca_ine", geo_codi="pais:ES")
    df = cre.merge(mar, on=["date", "cnae_codi"], suffixes=("_cre", "_mar"))
    if df.empty:
        return []
    d = df["date"].max()
    t = df[df["date"] == d]
    med_cre, med_mar = t["value_cre"].median(), t["value_mar"].median()
    any_ = _periode(d, "annual")
    comp = (f"mediana de {len(t)} branques el {any_}: vendes reals "
            f"{_valor(med_cre, 'pct')}, marge {_num(med_mar)}%")
    fets = []
    for row in t.itertuples():
        c = _costat(row.value_cre, med_cre, _TOL_QUADRANT)
        m = _costat(row.value_mar, med_mar, _TOL_QUADRANT)
        cre, mar = _valor(row.value_cre, "pct"), _num(row.value_mar)
        enun = {
            "ca": (f"{noms.nom_branca(row.cnae_codi)} ({row.cnae_codi}), {any_}: vendes reals "
                   f"{cre} i marge (EBE sobre vendes) de {mar}%; {_CREIX['ca'][c]} la "
                   f"mediana de branques i {_MARGE['ca'][m]}."),
            "es": (f"{noms.nom_branca(row.cnae_codi, 'es')} ({row.cnae_codi}), {any_}: ventas "
                   f"reales {cre} y margen (EBE sobre ventas) del {mar}%; {_CREIX['es'][c]} "
                   f"la mediana de ramas y {_MARGE['es'][m]}."),
        }
        fets.append(_fet(
            fet_id=f"quadrant_branca:{row.cnae_codi}", regla="quadrant_branca",
            enunciat=enun["ca"], enunciat_es=enun["es"],
            valor=row.value_cre, unitat="%", comparacio=comp, valor_referencia=med_cre,
            data=d, series=["der_icm_real_var_anual", "marges_branca_ine"],
            geo_codi="pais:ES", cnae_codi=row.cnae_codi,
            avis=_uneix_avis([row.avis_cre, row.avis_mar]),
            rellevancia=1.0 + (abs(c) + abs(m)) / 2))
    return fets


# ─── Saturació per CCAA ──────────────────────────────────────────────────────

# Diferències de menys del 3% amb Espanya es llegeixen com a semblants.
_TOL_SATURACIO = 0.03
_LOCALS = {"ca": {1: "més locals per habitant", 0: "una densitat de locals semblant",
                  -1: "menys locals per habitant"},
           "es": {1: "más locales por habitante", 0: "una densidad de locales similar",
                  -1: "menos locales por habitante"}}
_VENDES = {"ca": {1: "més vendes per habitant", 0: "unes vendes per habitant semblants",
                  -1: "menys vendes per habitant"},
           "es": {1: "más ventas por habitante", 0: "unas ventas por habitante similares",
                  -1: "menos ventas por habitante"}}
_LECTURA = {"ca": {(1, -1): ": senyal de saturació",
                   (-1, 1): ": poca densitat de locals per a les vendes que hi ha"},
            "es": {(1, -1): ": señal de saturación",
                   (-1, 1): ": poca densidad de locales para las ventas que hay"}}


def _regla_saturacio(con, noms):
    loc = _obs(con, "locals_ccaa_grup", cnae_codi="47")[["date", "geo_codi", "value", "avis"]]
    pob = _obs(con, "empreses_poblacio")[["date", "geo_codi", "value", "avis"]]
    ven = _obs(con, "der_vendes_per_habitant_real", cnae_codi="47")[
        ["date", "geo_codi", "value", "avis"]]
    df = (loc.merge(pob, on=["date", "geo_codi"], suffixes=("_loc", "_pob"))
             .merge(ven.rename(columns={"value": "ven", "avis": "avis_ven"}),
                    on=["date", "geo_codi"]))
    if df.empty:
        return []
    d = df["date"].max()
    t = df[df["date"] == d].set_index("geo_codi")
    t["densitat"] = t["value_loc"] / t["value_pob"] * 1000
    if "pais:ES" not in t.index:
        return []
    esp = t.loc["pais:ES"]
    any_ = _periode(d, "annual")
    comp = (f"Espanya el {any_}: {_num(esp['densitat'])} locals per 1.000 habitants i "
            f"{_num(esp['ven'])} euros de 2021 de vendes per habitant")
    fets = []
    for geo, row in t.iterrows():
        if not geo.startswith("ccaa:") or geo in _FORA_RANKING:
            continue
        loc_c = _costat(row["densitat"] / esp["densitat"], 1, _TOL_SATURACIO)
        ven_c = _costat(row["ven"] / esp["ven"], 1, _TOL_SATURACIO)
        rell = {(1, -1): 2.0, (-1, 1): 1.5}.get((loc_c, ven_c), 1.0)
        dens, ven = _num(row["densitat"]), _num(row["ven"])
        enun = {
            "ca": (f"{noms.territori(geo)}, {any_}: {dens} locals de comerç al detall per "
                   f"1.000 habitants i {ven} euros de 2021 de vendes per habitant; respecte "
                   f"de la mitjana espanyola, {_LOCALS['ca'][loc_c]} i {_VENDES['ca'][ven_c]}"
                   f"{_LECTURA['ca'].get((loc_c, ven_c), '')}."),
            "es": (f"{noms.territori(geo, 'es')}, {any_}: {dens} locales de comercio minorista "
                   f"por 1.000 habitantes y {ven} euros de 2021 de ventas por habitante; "
                   f"respecto a la media española, {_LOCALS['es'][loc_c]} y "
                   f"{_VENDES['es'][ven_c]}{_LECTURA['es'].get((loc_c, ven_c), '')}."),
        }
        fets.append(_fet(
            fet_id=f"saturacio:{geo}", regla="saturacio",
            enunciat=enun["ca"], enunciat_es=enun["es"],
            valor=row["densitat"], unitat="locals per 1.000 hab.", comparacio=comp,
            valor_referencia=float(esp["densitat"]), data=d,
            series=["locals_ccaa_grup", "empreses_poblacio", "der_vendes_per_habitant_real"],
            geo_codi=geo, cnae_codi="47",
            avis=_uneix_avis([row["avis_loc"], row["avis_pob"], row["avis_ven"]],
                             extra=["lloc_de_venda"]),
            rellevancia=rell))
    return fets


# ─── Entrada ─────────────────────────────────────────────────────────────────

REGLES = [_regles_vigilades, _regla_ranking, _regla_divergencia, _regla_quadrant,
          _regla_saturacio]


def construeix(con):
    noms = _Noms(con)
    fets = [f for regla in REGLES for f in regla(con, noms)]
    df = pd.DataFrame(fets, columns=_COLS)
    if df["fet_id"].duplicated().any():
        dup = df.loc[df["fet_id"].duplicated(), "fet_id"].tolist()
        raise ValueError(f"fet_id duplicats: {dup[:5]}")
    return df
