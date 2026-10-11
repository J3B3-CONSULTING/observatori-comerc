"""
Capa de consulta pel chatbot de retail: 9 funcions deterministes sobre
observatori.duckdb (esquema a schema.sql, migració a migrate.py).

Principis:
  - Cap SQL cru des del prompt — nomes parametres tipats via aquestes funcions.
  - Tota resposta amb dades porta "metadata" (name/description/source/unit/
    is_derived) — la citacio viatja amb les dades, no depen que el model
    se'n recordi.
  - serie_id o dimensio inexistent -> {"error": ..., "suggestions": [...]},
    mai una excepcio crua ni un resultat buit silencios.
  - get_series i compare_dimension porten "limit" (per defecte 100) i sempre
    retornen "total_available" perque el model sapiga si ha rebut el
    conjunt complet o un tall (series denses com cdmge tenen ~2.700 files).
"""
import os
import re
import difflib
import duckdb

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "observatori.duckdb")

# source_table NO es columna de series_metadata (nomes d'observations, per fila)
# — _get_metadata() l'afegeix amb una consulta petita addicional.
_METADATA_COLS = ["serie_id", "name", "description", "source",
                   "frequency", "date_start", "date_end", "is_critical", "is_derived",
                   "nota_trencament", "formula", "fonts_origen"]


def _connect(db_path=None):
    return duckdb.connect(db_path or DB_PATH, read_only=True)


def _iso(d):
    if d is None:
        return None
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _normalize_date(d):
    """Admet 'YYYY', 'YYYY-MM' o 'YYYY-MM-DD'; sempre retorna 'YYYY-MM-DD'."""
    if d is None:
        return None
    d = str(d)
    if re.fullmatch(r"\d{4}", d):
        return f"{d}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}", d):
        return f"{d}-01"
    return d


def _all_serie_ids(con):
    return [r[0] for r in con.execute("SELECT serie_id FROM series_metadata").fetchall()]


def _suggest_series_ids(con, bad_id, n=5):
    return difflib.get_close_matches(bad_id, _all_serie_ids(con), n=n, cutoff=0.3)


def _get_metadata(con, serie_id):
    row = con.execute(f"""
        SELECT {", ".join(_METADATA_COLS)} FROM series_metadata WHERE serie_id = ?
    """, [serie_id]).fetchone()
    if row is None:
        return None
    meta = dict(zip(_METADATA_COLS, row))
    meta["date_start"] = _iso(meta["date_start"])
    meta["date_end"] = _iso(meta["date_end"])
    tbl = con.execute(
        "SELECT source_table FROM observations WHERE serie_id = ? LIMIT 1", [serie_id]
    ).fetchone()
    meta["source_table"] = tbl[0] if tbl else None
    # Avisos de qualitat presents a la sèrie, amb el text: viatgen amb les dades.
    meta["avisos"] = [dict(codi=c, text=t) for c, t in con.execute("""
        SELECT DISTINCT a.avis_codi, a.text
        FROM (SELECT DISTINCT unnest(string_split(avis, ',')) AS codi
              FROM observations WHERE serie_id = ? AND avis IS NOT NULL) o
        JOIN dim_avis a ON a.avis_codi = o.codi
        ORDER BY 1
    """, [serie_id]).fetchall()]
    return meta


def _dim_clauses(dim_1=None, dim_2=None, dim_3=None, start_idx=1):
    clauses, params = [], []
    for i, v in enumerate([dim_1, dim_2, dim_3], start=1):
        if v is not None:
            clauses.append(f"dim_{i} = ?")
            params.append(v)
    return clauses, params


def _points(con, serie_id, date_start=None, date_end=None, dims=None, limit=500):
    """Helper intern (usat per get_epa_indicators/get_macro_context): llista
    simple de {date, value} sense metadata, per no repetir SQL 8 cops."""
    clauses = ["serie_id = ?"]
    params = [serie_id]
    if date_start:
        clauses.append("date >= ?")
        params.append(_normalize_date(date_start))
    if date_end:
        clauses.append("date <= ?")
        params.append(_normalize_date(date_end))
    for k, v in (dims or {}).items():
        clauses.append(f"{k} = ?")
        params.append(v)
    where = " AND ".join(clauses)
    rows = con.execute(f"""
        SELECT date, value FROM observations WHERE {where} ORDER BY date LIMIT ?
    """, params + [limit]).fetchall()
    return [{"date": _iso(r[0]), "value": r[1]} for r in rows]


# ─── 1. Descobriment de series ───────────────────────────────────────────────

def list_series(keyword=None, is_critical=None, is_derived=None):
    """Cerca a series_metadata per nom/descripcio/serie_id i/o flags.
    Necessari perque el model no pot memoritzar els ~97 serie_id — aquesta es
    la manera de descobrir-los abans de cridar la resta de funcions."""
    con = _connect()
    try:
        clauses, params = [], []
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(name ILIKE ? OR description ILIKE ? OR serie_id ILIKE ?)")
            params += [like, like, like]
        if is_critical is not None:
            clauses.append("is_critical = ?")
            params.append(is_critical)
        if is_derived is not None:
            clauses.append("is_derived = ?")
            params.append(is_derived)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = con.execute(f"""
            SELECT {", ".join(_METADATA_COLS)} FROM series_metadata
            {where}
            ORDER BY serie_id
        """, params).fetchall()
        results = []
        for r in rows:
            d = dict(zip(_METADATA_COLS, r))
            d["date_start"] = _iso(d["date_start"])
            d["date_end"] = _iso(d["date_end"])
            results.append(d)
        return {"series": results, "count": len(results)}
    finally:
        con.close()


# ─── 2. Evolucio temporal d'una metrica ──────────────────────────────────────

def get_series(serie_id, date_start=None, date_end=None, dim_1=None, dim_2=None,
                dim_3=None, limit=100):
    """Retorna l'evolucio temporal d'una serie, opcionalment filtrada per
    dimensio i rang de dates.

    Si NO s'especifica cap rang de dates: retorna les 'limit' observacions
    MES RECENTS (ordre cronologic a la resposta) — es el comportament util
    per "com ha evolucionat X" sense mes context. Si es dona un rang: retorna
    les primeres 'limit' dins d'aquest rang, en ordre cronologic.
    'total_available' indica sempre el total real (abans del tall)."""
    con = _connect()
    try:
        meta = _get_metadata(con, serie_id)
        if meta is None:
            return {"error": f"serie_id desconegut: {serie_id}",
                    "suggestions": _suggest_series_ids(con, serie_id)}

        clauses = ["serie_id = ?"]
        params = [serie_id]
        if date_start:
            clauses.append("date >= ?")
            params.append(_normalize_date(date_start))
        if date_end:
            clauses.append("date <= ?")
            params.append(_normalize_date(date_end))
        dim_cl, dim_params = _dim_clauses(dim_1, dim_2, dim_3)
        clauses += dim_cl
        params += dim_params
        where = " AND ".join(clauses)

        total = con.execute(f"SELECT count(*) FROM observations WHERE {where}", params).fetchone()[0]

        if date_start or date_end:
            order = "date ASC"
        else:
            order = "date DESC"
        rows = con.execute(f"""
            SELECT date, value, dim_1, dim_2, dim_3 FROM observations
            WHERE {where} ORDER BY {order} LIMIT ?
        """, params + [limit]).fetchall()
        if order == "date DESC":
            rows = list(reversed(rows))

        points = [{"date": _iso(r[0]), "value": r[1], "dim_1": r[2], "dim_2": r[3], "dim_3": r[4]}
                  for r in rows]
        return {"serie_id": serie_id, "points": points, "total_available": total,
                "returned": len(points), "metadata": meta}
    finally:
        con.close()


# ─── 3. Creixement d'una branca/sector en un periode ─────────────────────────

def get_growth(serie_id, date_start, date_end, dim_1=None, dim_2=None, dim_3=None):
    """Creixement entre dues dates. Si la data exacta no existeix (freqüencies
    diferents), agafa l'observacio disponible mes propera ANTERIOR o igual a
    la data demanada (mai interpola ni inventa)."""
    con = _connect()
    try:
        meta = _get_metadata(con, serie_id)
        if meta is None:
            return {"error": f"serie_id desconegut: {serie_id}",
                    "suggestions": _suggest_series_ids(con, serie_id)}

        dim_cl, dim_params = _dim_clauses(dim_1, dim_2, dim_3)

        def _nearest(target):
            clauses = ["serie_id = ?", "date <= ?"] + dim_cl
            params = [serie_id, _normalize_date(target)] + dim_params
            return con.execute(f"""
                SELECT date, value FROM observations
                WHERE {" AND ".join(clauses)} ORDER BY date DESC LIMIT 1
            """, params).fetchone()

        row_start = _nearest(date_start)
        row_end = _nearest(date_end)
        if row_start is None or row_end is None:
            return {"error": "no hi ha observacions disponibles per al rang/dimensions demanades",
                    "metadata": meta}

        value_start, value_end = row_start[1], row_end[1]
        abs_change = value_end - value_start
        pct_change = (abs_change / value_start * 100) if value_start else None

        return {
            "serie_id": serie_id,
            "date_start_actual": _iso(row_start[0]), "date_end_actual": _iso(row_end[0]),
            "value_start": value_start, "value_end": value_end,
            "absolute_change": abs_change, "pct_change": pct_change,
            "metadata": meta,
        }
    finally:
        con.close()


# ─── 4. Comparativa branques/CCAA, ranking, comparativa europea ─────────────

def compare_dimension(serie_id, date, dim_to_compare="dim_1", fixed_dims=None,
                       ascending=False, limit=100):
    """Tots els valors d'una dimensio en una data (mes propera ANTERIOR o
    igual), ordenats i amb 'rank'. Serveix per comparatives (branques, CCAA,
    paisos europeus) i per rankings — es la mateixa operacio: slice d'una
    serie per una dimensio en un instant. 'fixed_dims' fixa altres dimensions
    (p.ex. {"dim_2": "index"} a l'ICM abans de comparar branques)."""
    con = _connect()
    try:
        meta = _get_metadata(con, serie_id)
        if meta is None:
            return {"error": f"serie_id desconegut: {serie_id}",
                    "suggestions": _suggest_series_ids(con, serie_id)}
        if dim_to_compare not in ("dim_1", "dim_2", "dim_3"):
            return {"error": "dim_to_compare ha de ser 'dim_1', 'dim_2' o 'dim_3'"}

        clauses = ["serie_id = ?", "date <= ?"]
        params = [serie_id, _normalize_date(date)]
        for k, v in (fixed_dims or {}).items():
            if k not in ("dim_1", "dim_2", "dim_3"):
                return {"error": f"clau de fixed_dims no valida: {k}"}
            clauses.append(f"{k} = ?")
            params.append(v)
        where = " AND ".join(clauses)

        # Per cada valor de dim_to_compare, ens quedem amb l'observacio mes
        # recent <= date (QUALIFY row_number == 1 per grup).
        base_sql = f"""
            SELECT {dim_to_compare} AS dim_value, value, date
            FROM observations
            WHERE {where}
            QUALIFY row_number() OVER (PARTITION BY {dim_to_compare} ORDER BY date DESC) = 1
        """
        total = con.execute(f"SELECT count(*) FROM ({base_sql})", params).fetchone()[0]
        order_dir = "ASC" if ascending else "DESC"
        rows = con.execute(f"""
            SELECT * FROM ({base_sql}) ORDER BY value {order_dir} LIMIT ?
        """, params + [limit]).fetchall()

        items = [{"dim_value": r[0], "value": r[1], "date_actual": _iso(r[2]), "rank": i + 1}
                 for i, r in enumerate(rows)]
        return {"serie_id": serie_id, "items": items, "total_available": total,
                "returned": len(items), "metadata": meta}
    finally:
        con.close()


# ─── 5. Marges per branca ────────────────────────────────────────────────────

def get_margins(any_=None, branca=None):
    """Marges (EBE/vendes) per branca CNAE 47. Sense any_, agafa l'ultim
    disponible. Wrapper dedicat sobre marges_branca_ine — evita que el model
    hagi de deduir que ha de cridar compare_dimension amb aquest serie_id."""
    con = _connect()
    try:
        serie_id = "marges_branca_ine"
        meta = _get_metadata(con, serie_id)
        if meta is None:
            return {"error": f"serie_id '{serie_id}' no trobat"}

        if any_ is not None:
            target_date = _normalize_date(any_)
        else:
            target_date = con.execute(
                "SELECT max(date) FROM observations WHERE serie_id = ?", [serie_id]
            ).fetchone()[0]
            if target_date is None:
                return {"error": "no hi ha dades de marges_branca_ine", "metadata": meta}
            target_date = _iso(target_date)

        clauses = ["serie_id = ?", "date = ?"]
        params = [serie_id, target_date]
        if branca is not None:
            clauses.append("dim_1 = ?")
            params.append(branca)
        where = " AND ".join(clauses)

        rows = con.execute(f"""
            SELECT dim_1, value FROM observations WHERE {where} ORDER BY value DESC
        """, params).fetchall()
        if not rows:
            return {"error": f"cap dada de marges per any={any_}, branca={branca}", "metadata": meta}

        items = [{"branca": r[0], "marge_vendes_pct": r[1]} for r in rows]
        return {"any": int(target_date[:4]), "items": items, "metadata": meta}
    finally:
        con.close()


# ─── 6. Indicadors d'ocupacio retail (EPA) ───────────────────────────────────

_EPA_SERIES = {
    "ocupats_cnae47_milers": "epa_retail_ocupats",
    "aturats_seccio_g_milers": "epa_retail_aturats",
    "hores_setmana_seccio_g": "epa_retail_hores",
}
_EPA_CAVEAT = (
    "Aturats i hores inclouen tota la secció G (comerç a l'engròs + al detall + "
    "reparació de vehicles de motor), no només CNAE 47 (comerç al detall). "
    "Ocupats sí que és CNAE 47 net. L'INE no publica aturats/hores desglossats "
    "a nivell CNAE 47."
)


def get_epa_indicators(date_start=None, date_end=None, sexe=None):
    """Ocupats/aturats/hores del comerç (EPA), per trimestre i sexe, en una
    sola crida. El 'caveat' de secció G viatja sempre a la resposta.

    Clau interna (date, sexe): sense aixo, si no es filtra per sexe, les
    files de homes/dones/total es sobreescriurien entre elles en comptes
    de conviure com a files separades."""
    con = _connect()
    try:
        by_key = {}
        metas = {}
        for field, sid in _EPA_SERIES.items():
            meta = _get_metadata(con, sid)
            if meta is None:
                continue
            metas[field] = meta

            clauses = ["serie_id = ?"]
            params = [sid]
            if date_start:
                clauses.append("date >= ?")
                params.append(_normalize_date(date_start))
            if date_end:
                clauses.append("date <= ?")
                params.append(_normalize_date(date_end))
            if sexe:
                clauses.append("dim_1 = ?")
                params.append(sexe)
            where = " AND ".join(clauses)

            rows = con.execute(f"""
                SELECT date, dim_1, value FROM observations
                WHERE {where} ORDER BY date
            """, params).fetchall()
            for d, sx, v in rows:
                key = (_iso(d), sx)
                entry = by_key.setdefault(key, {"periode": _iso(d), "sexe": sx})
                entry[field] = v

        points = sorted(by_key.values(), key=lambda p: (p["periode"], p["sexe"] or ""))
        return {"points": points, "caveat": _EPA_CAVEAT, "metadata": metas}
    finally:
        con.close()


# ─── 7. Context macro (IPC, confianca del consumidor) ────────────────────────

_CONFIANZA_SERIES = {
    "index_confianca": "confianza_consumidor_index_confianca",
    "situacio_actual_financera": "confianza_consumidor_situacio_actual_financera",
    "situacio_actual_economica": "confianza_consumidor_situacio_actual_economica",
    "expectatives_financera": "confianza_consumidor_expectatives_financera",
    "expectatives_economica": "confianza_consumidor_expectatives_economica",
}
_IPC_COICOP_GRUPS = {
    "alimentacio": "Alimentació i begudes no alcohòliques",
    "vestit": "Vestit i calçat",
    "llar": "Parament de la llar",
}


def get_macro_context(date_start=None, date_end=None):
    """IPC (general + grups rellevants) i confiança del consumidor per a un
    periode, en una sola crida — el context macro habitual per interpretar
    l'evolucio del comerç."""
    con = _connect()
    try:
        ipc = {"general": _points(con, "ipc", date_start, date_end)}
        for key, grup in _IPC_COICOP_GRUPS.items():
            ipc[key] = _points(con, "ipc_coicop", date_start, date_end, dims={"dim_1": grup})

        confianza = {
            "index_confianca": _points(con, _CONFIANZA_SERIES["index_confianca"], date_start, date_end),
            "situacio_actual": {
                "financera": _points(con, _CONFIANZA_SERIES["situacio_actual_financera"], date_start, date_end),
                "economica": _points(con, _CONFIANZA_SERIES["situacio_actual_economica"], date_start, date_end),
            },
            "expectatives": {
                "financera": _points(con, _CONFIANZA_SERIES["expectatives_financera"], date_start, date_end),
                "economica": _points(con, _CONFIANZA_SERIES["expectatives_economica"], date_start, date_end),
            },
        }

        metadata = {sid: _get_metadata(con, sid)
                    for sid in ["ipc", "ipc_coicop"] + list(_CONFIANZA_SERIES.values())}
        return {"ipc": ipc, "confianza": confianza, "metadata": metadata}
    finally:
        con.close()


# ─── 8. Fets (motor de fets, data/sql/fets.py) ───────────────────────────────

_FET_COLS = ["fet_id", "regla", "enunciat", "valor", "unitat", "comparacio",
             "valor_referencia", "data", "series", "geo_codi", "cnae_codi", "avis",
             "rellevancia"]


def get_facts(regla=None, geo_codi=None, cnae_codi=None, serie_id=None, limit=20):
    """Fets ja redactats pel motor, ordenats per rellevància. Cada fet porta les
    sèries d'on surt (amb nom i font) i el text dels avisos de qualitat: el model
    els ha de citar tal com venen, sense recalcular-los.
    Filtres: regla (extrem, ratxa, inflexio, ranking, divergencia,
    quadrant_branca, saturacio), geo_codi ('ccaa:09'), cnae_codi ('477'),
    serie_id (fets que fan servir aquesta sèrie)."""
    con = _connect()
    try:
        clauses, params = [], []
        for col, v in (("regla", regla), ("geo_codi", geo_codi), ("cnae_codi", cnae_codi)):
            if v is not None:
                clauses.append(f"{col} = ?")
                params.append(v)
        if serie_id is not None:
            clauses.append("list_contains(string_split(series, ','), ?)")
            params.append(serie_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = con.execute(f"SELECT count(*) FROM fets {where}", params).fetchone()[0]
        if total == 0:
            regles = [r[0] for r in con.execute(
                "SELECT DISTINCT regla FROM fets ORDER BY 1").fetchall()]
            return {"error": "cap fet amb aquests filtres", "regles_disponibles": regles,
                    "facts": [], "total_available": 0}
        rows = con.execute(f"""
            SELECT {", ".join(_FET_COLS)} FROM fets {where}
            ORDER BY rellevancia DESC, data DESC, fet_id LIMIT ?
        """, params + [limit]).fetchall()

        textos_avis = dict(con.execute("SELECT avis_codi, text FROM dim_avis").fetchall())
        fonts = {r[0]: {"serie_id": r[0], "name": r[1], "source": r[2]} for r in con.execute(
            "SELECT serie_id, name, source FROM series_metadata").fetchall()}
        facts = []
        for r in rows:
            f = dict(zip(_FET_COLS, r))
            f["data"] = _iso(f["data"])
            f["fonts"] = [fonts[s] for s in f.pop("series").split(",") if s in fonts]
            codis = f.pop("avis")
            f["avisos"] = [dict(codi=c, text=textos_avis[c])
                           for c in (codis.split(",") if codis else [])]
            facts.append(f)
        return {"facts": facts, "total_available": total, "returned": len(facts)}
    finally:
        con.close()


# ─── 9. Indicadors derivats per clau comuna ──────────────────────────────────

def get_derived(serie_id=None, geo_codi=None, cnae_codi=None, limit=100):
    """Sense serie_id: catàleg dels indicadors derivats (fórmula, sèries d'origen,
    unitat). Amb serie_id: els valors filtrats per les claus comunes geo_codi i
    cnae_codi (no per etiquetes de text), les 'limit' observacions més recents,
    amb la metadata i els avisos."""
    con = _connect()
    try:
        if serie_id is None:
            cols = ["serie_id", "name", "description", "formula", "fonts_origen",
                    "frequency", "date_start", "date_end"]
            rows = con.execute(f"""
                SELECT {", ".join(cols)} FROM series_metadata
                WHERE is_derived AND formula IS NOT NULL ORDER BY serie_id
            """).fetchall()
            derivats = [dict(zip(cols, r)) for r in rows]
            for d in derivats:
                d["date_start"], d["date_end"] = _iso(d["date_start"]), _iso(d["date_end"])
            return {"derived": derivats, "count": len(derivats)}

        meta = _get_metadata(con, serie_id)
        if meta is None or not meta["is_derived"] or not meta["formula"]:
            return {"error": f"no és un indicador derivat: {serie_id}",
                    "suggestions": difflib.get_close_matches(
                        serie_id, [s for s in _all_serie_ids(con) if s.startswith("der_")],
                        n=5, cutoff=0.3)}
        clauses, params = ["serie_id = ?"], [serie_id]
        for col, v in (("geo_codi", geo_codi), ("cnae_codi", cnae_codi)):
            if v is not None:
                clauses.append(f"{col} = ?")
                params.append(v)
        where = " AND ".join(clauses)
        total = con.execute(f"SELECT count(*) FROM observations WHERE {where}",
                            params).fetchone()[0]
        rows = con.execute(f"""
            SELECT date, value, geo_codi, cnae_codi, dim_1, avis FROM observations
            WHERE {where} ORDER BY date DESC, geo_codi, cnae_codi LIMIT ?
        """, params + [limit]).fetchall()
        points = [{"date": _iso(r[0]), "value": r[1], "geo_codi": r[2], "cnae_codi": r[3],
                   "dim_1": r[4], "avis": r[5]} for r in reversed(rows)]
        return {"serie_id": serie_id, "points": points, "total_available": total,
                "returned": len(points), "metadata": meta}
    finally:
        con.close()
