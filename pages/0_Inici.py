"""Portada: la tesi de la setmana com a titular, el pols del consum, les xifres
estructurals, les dues lectures de la setmana, la tesi editorial i la radiografia.

Tractament editorial sec: cap requadre, cap ombra i cap fons de color. La
jerarquia surt de la mida del tipus, dels filets d'1 px i de l'aire entre blocs.

Tot el contingut editorial (titular, entradeta, xifra de la setmana i primer
paràgraf) surt de l'última edició del Pulso a data/newsletter/semana-*.md: la
mateixa font que L_Editorial, perquè home i butlletí no puguin divergir mai.
"""
import json
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset
from navegacio import DESTINS, anar_a, oblidar_destinacio
from style import (inject_css, inject_premium_page_css, inject_home_css,
                   setup_lang, page_header, fnum, fpct, page_meta,
                   newsletter_form, format_mes_any,
                   home_standfirst, home_hero, home_shock, home_stats,
                   home_section, home_exhibit, home_source, home_quote,
                   home_field, home_rule, home_space,
                   NAVY, OCRE, OCRE_DEEP, TEAL, TEAL_SOFT, G1_P, INK_P, LINE_P)

inject_css()
inject_premium_page_css()
inject_home_css()
setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"
_avui = date.today()
oblidar_destinacio()  # la pestanya forçada d'una novetat només val per a un salt
_NDIR = os.path.join(os.path.dirname(__file__), "..", "data", "newsletter")

# ─── DADES ─────────────────────────────────────────────────────


def load_data(name):
    return load_dataset(name, fmt="auto")


df_pib = load_data("pib_vab")
df_empreses = load_data("empreses")
df_ocupacio = load_data("ocupacio_comerc")
df_ecommerce = load_data("ecommerce")
df_cdmge = load_data("cdmge")
df_eu_m = load_data("europa_retail_mensual")
df_icm = load_data("icm")
df_lideres = load_data("lideres_empreses")
df_eas = load_data("subsectors_eas")


def _layout(height, ysuffix="", **kw):
    """Layout Plotly de la portada: fons transparent, graella finíssima, cap marc."""
    base = dict(
        height=height, showlegend=False,
        margin=dict(l=0, r=8, t=18, b=4),
        font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        separators=",.",
        hoverlabel=dict(bgcolor="white", bordercolor=LINE_P,
                        font=dict(family="Manrope, sans-serif", color=INK_P, size=12)),
        xaxis=dict(showgrid=False, showline=True, linecolor=LINE_P, linewidth=1,
                   tickfont=dict(size=11.5), ticks="outside", tickcolor=LINE_P),
        yaxis=dict(showgrid=True, gridcolor="#f0f3f6", gridwidth=1, zeroline=False,
                   showline=False, ticksuffix=ysuffix, tickfont=dict(size=11.5)),
    )
    base.update(kw)
    return base


# ─── L'EDICIÓ VIGENT DEL PULSO ─────────────────────────────────

def _md_a_html(text):
    """Converteix el marcatge mínim del butlletí (**negreta**) a HTML."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _destacar_final(titular):
    """Marca l'última frase del titular per al subratllat ocre del hero.

    Amb dues frases o més, destaca l'última sencera; amb una sola frase, les
    tres últimes paraules. És èmfasi tipogràfic: no toca ni reordena el text.
    """
    text = titular.strip()
    frases = re.split(r"(?<=[.!?])\s+", text)
    if len(frases) >= 2 and len(frases[-1]) >= 8:
        return " ".join(frases[:-1]) + f" <em>{frases[-1]}</em>"
    mots = text.split()
    if len(mots) > 4:
        return " ".join(mots[:-3]) + f" <em>{' '.join(mots[-3:])}</em>"
    return f"<em>{text}</em>"


def _retallar(text, maxlen=430):
    """Talla en el punt final més proper per no deixar frases a mitges."""
    if len(text) <= maxlen:
        return text
    tall = text[:maxlen]
    tall_pos = max(tall.rfind(". "), tall.rfind("? "), tall.rfind("! "))
    if tall_pos > 140:
        return tall[:tall_pos + 1]
    return tall.rstrip() + "…"


@st.cache_data(ttl=3600)
def load_edicio(sig=None):
    """Llegeix l'última edició del Pulso del mirall local i n'extreu els camps.

    `sig` (noms + mtime de les edicions) trenca la caché quan se'n publica o es
    corregeix una.
    """
    try:
        mds = sorted((f for f in os.listdir(_NDIR)
                      if f.startswith("semana-") and f.endswith(".md")),
                     reverse=True)
    except OSError:
        return None
    for fname in mds:
        mdate = re.match(r"semana-(\d{4}-\d{2}-\d{2})\.md$", fname)
        if not mdate:
            continue
        try:
            with open(os.path.join(_NDIR, fname), "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue

        def camp(patro):
            m = re.search(patro, text, re.M)
            return m.group(1).strip() if m else None

        titular = camp(r"^\*\*Titular:\*\*\s*(.+)$")
        if not titular:
            continue
        # El camp de la xifra protagonista ha canviat de nom entre edicions.
        cifra = camp(r"^\*\*(?:El dato|Cifra):\*\*\s*(.+)$")
        # Primer paràgraf de prosa després de la línia de font del bloc de la xifra.
        m_lede = re.search(r"^\*\*Fuente:\*\*.+?$\n+(.+?)(?:\n\n|\n\*\*)",
                           text, re.M | re.S)
        try:
            data_pub = date.fromisoformat(mdate.group(1))
        except ValueError:
            data_pub = None
        return {
            "titular": titular,
            "pre": camp(r"^\*\*Pre-header:\*\*\s*(.+)$"),
            "num": camp(r"^\*Núm\.\s*(\d+)"),
            "setmana": camp(r"^\*Núm\.\s*\d+\s*\|\s*(.+?)\*\s*$"),
            "cifra": cifra,
            "context": camp(r"^\*\*Contexto:\*\*\s*(.+)$"),
            "font": camp(r"^\*\*Fuente:\*\*\s*(.+)$"),
            "lede": " ".join(m_lede.group(1).split()) if m_lede else None,
            "data": data_pub,
        }
    return None


try:
    _sig = tuple(sorted(
        (f, int(os.path.getmtime(os.path.join(_NDIR, f))))
        for f in os.listdir(_NDIR)
        if f.startswith("semana-") and f.endswith(".md")
    ))
except OSError:
    _sig = ()
_ed = load_edicio(_sig) or {}

# ─── EL POLS DEL CONSUM ────────────────────────────────────────
# CDMGE diari si és fresc; si no, variació anual real de l'ICM mensual.

_pulse = None
if not df_cdmge.empty and "indicador" in df_cdmge.columns:
    _p = df_cdmge.copy()
    _p["data"] = pd.to_datetime(_p["data"], errors="coerce")
    _ta = (_p[_p["indicador"] == "tasa_anual"]
           .dropna(subset=["data", "valor"]).sort_values("data")
           .reset_index(drop=True))
    if len(_ta) > 30:
        _last_dt = _ta["data"].max()
        _plot = _ta[_ta["data"] >= _last_dt - pd.Timedelta(days=365)].copy()
        _plot["mm30"] = _plot["valor"].rolling(window=30, min_periods=8).mean()
        _pulse = {
            "last_dt": _last_dt,
            "avg_30": float(_ta.tail(30)["valor"].mean()),
            "avg_90": float(_ta.tail(90)["valor"].mean()),
            "lag_days": int((pd.Timestamp(_avui) - _last_dt).days),
            "plot": _plot,
        }

# El CDMGE és estadística experimental de l'INE amb publicació irregular: si
# l'última dada té més de 30 dies, deixa de ser un "darrers 30 dies" honest.
POLS_LAG_LLINDAR = 30
_pulse_fresc = _pulse is not None and _pulse["lag_days"] <= POLS_LAG_LLINDAR

_icm_hero = None
if not _pulse_fresc and not df_icm.empty and "ambit" in df_icm.columns:
    _s = df_icm[(df_icm["ambit"] == "nacional")
                & (df_icm["tipus"] == "real")
                & (df_icm["indicador"] == "var_anual")
                & (df_icm["branca"] == "Comercio al por menor, excepto de vehículos "
                                      "de motor y motocicletas")].dropna(subset=["valor"]).copy()
    if not _s.empty:
        _s["data"] = pd.to_datetime(_s["data"], errors="coerce")
        _s = _s.dropna(subset=["data"]).sort_values("data")
        if not _s.empty:
            _icm_hero = {
                "valor": float(_s.iloc[-1]["valor"]),
                "data": _s.iloc[-1]["data"],
                "serie": _s[_s["data"] >= _s["data"].max() - pd.DateOffset(years=3)],
            }

# ─── HERO: LA TESI DE LA SETMANA ───────────────────────────────

# Un sol focus a la primera pantalla: el titular. A sobre, la frase permanent
# que diu què és això (el visitant que arriba de fora no ha de deduir-ho del
# titular de la setmana); el número del pols baixa a la franja de sota, on no
# li roba escala.
home_standfirst(
    "<b>Radiografia del comerç al detall espanyol</b> (CNAE 47) a partir de dades "
    "oficials de l'INE, Eurostat i la CNMC. Les sèries s'actualitzen de forma "
    "automàtica; cada dilluns, una lectura editorial del que ha passat."
    if _ca else
    "<b>Radiografía del comercio minorista español</b> (CNAE 47) a partir de datos "
    "oficiales del INE, Eurostat y la CNMC. Las series se actualizan de forma "
    "automática; cada lunes, una lectura editorial de lo que ha pasado."
)
home_space("m")

if _ed.get("titular"):
    _data_fmt = _ed["data"].strftime("%d/%m/%Y") if _ed.get("data") else ""
    _num = f" · Núm. {_ed['num']}" if _ed.get("num") else ""
    home_hero(("Tesi de la setmana · " if _ca else "Tesis de la semana · ")
              + _data_fmt + _num,
              _destacar_final(_ed["titular"]), _ed.get("pre"))
else:
    home_hero(("Observatori del comerç" if _ca else "Observatorio del comercio"),
              ("Radiografia del comerç al detall espanyol" if _ca
               else "Radiografía del comercio minorista español"),
              ("Dades oficials del CNAE 47, actualitzades de forma automàtica."
               if _ca else
               "Datos oficiales del CNAE 47, actualizados de forma automática."))

home_space("s")
_c1, _c2, _c3 = st.columns([1.1, 1.1, 2.8])
with _c1:
    st.page_link("pages/L_Editorial.py",
                 label=("Llegir l'edició →" if _ca else "Leer la edición →"))
with _c2:
    st.page_link("pages/0b_ICM.py",
                 label=("Veure les dades →" if _ca else "Ver los datos →"))

home_rule(space_before=46, space_after=30)

# ─── EL POLS DEL CONSUM (franja sota el hero) ──────────────────

if _pulse_fresc:
    _accel = _pulse["avg_30"] - _pulse["avg_90"]
    if abs(_accel) < 0.5:
        _dir = ("estable respecte del trimestre" if _ca
                else "estable respecto al trimestre")
    elif _accel > 0:
        _dir = "en acceleració" if _ca else "en aceleración"
    else:
        _dir = "en desacceleració" if _ca else "en desaceleración"
    home_shock(
        fpct(_pulse["avg_30"], 1),
        (f"<b>Vendes diàries de les grans cadenes</b>, variació anual dels últims "
         f"30 dies · {_dir}" if _ca else
         f"<b>Ventas diarias de las grandes cadenas</b>, variación anual de los "
         f"últimos 30 días · {_dir}"),
        negative=_pulse["avg_30"] < 0, line=True,
    )
    _fig = go.Figure()
    _fig.add_trace(go.Scatter(
        x=_pulse["plot"]["data"], y=_pulse["plot"]["mm30"],
        mode="lines", line=dict(color=NAVY, width=2.4),
        fill="tozeroy", fillcolor="rgba(11,58,102,0.06)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}%<extra></extra>",
    ))
    # Punt final en ocre amb la lectura anotada: tanca la sèrie amb color.
    _mm_ok = _pulse["plot"].dropna(subset=["mm30"])
    if not _mm_ok.empty:
        _fig.add_trace(go.Scatter(
            x=[_mm_ok["data"].iloc[-1]], y=[_mm_ok["mm30"].iloc[-1]],
            mode="markers+text", marker=dict(color=OCRE, size=9,
                                             line=dict(color="white", width=2)),
            text=[f" {fpct(_mm_ok['mm30'].iloc[-1], 1)}"], textposition="middle right",
            textfont=dict(family="Manrope, sans-serif", size=13, color=OCRE_DEEP),
            hoverinfo="skip",
        ))
    _fig.add_hline(y=0, line=dict(color="#c9d2db", width=1))
    _fig.update_layout(**_layout(240, ysuffix="%", hovermode="x unified",
                                 margin=dict(l=0, r=64, t=18, b=4)))
    st.plotly_chart(_fig, use_container_width=True, config={"displayModeBar": False})
    home_source(
        (f"Mitjana mòbil de 30 dies · INE, CDMGE (experimental) · dades fins al "
         f"{_pulse['last_dt'].strftime('%d/%m/%Y')}, {_pulse['lag_days']} dies de "
         f"retard. La sèrie diària, amb els pics de campanya, és a la pàgina del "
         f"Pols diari." if _ca else
         f"Media móvil de 30 días · INE, CDMGE (experimental) · datos hasta el "
         f"{_pulse['last_dt'].strftime('%d/%m/%Y')}, {_pulse['lag_days']} días de "
         f"retraso. La serie diaria, con los picos de campaña, está en la página "
         f"del Pulso diario.")
    )
    home_rule(space_before=40, space_after=30)
elif _icm_hero is not None:
    home_shock(
        fpct(_icm_hero["valor"], 1),
        (f"<b>Xifra de negoci del comerç al detall</b>, variació anual real de "
         f"{format_mes_any(_icm_hero['data'], st.session_state.lang)}" if _ca else
         f"<b>Cifra de negocio del comercio minorista</b>, variación anual real de "
         f"{format_mes_any(_icm_hero['data'], st.session_state.lang)}"),
        negative=_icm_hero["valor"] < 0, line=True,
    )
    _fig = go.Figure()
    _fig.add_trace(go.Scatter(
        x=_icm_hero["serie"]["data"], y=_icm_hero["serie"]["valor"],
        mode="lines", line=dict(color=NAVY, width=2.2),
        fill="tozeroy", fillcolor="rgba(11,58,102,0.05)",
        hovertemplate="%{x|%m/%Y}<br>%{y:.1f}%<extra></extra>",
    ))
    _fig.add_hline(y=0, line=dict(color="#c9d2db", width=1))
    _fig.update_layout(**_layout(240, ysuffix="%"))
    st.plotly_chart(_fig, use_container_width=True, config={"displayModeBar": False})
    home_source("INE, Índex de Comerç al Detall · preus constants" if _ca
                else "INE, Índice de Comercio al por Menor · precios constantes")
    home_rule(space_before=40, space_after=30)

# ─── XIFRES ESTRUCTURALS ───────────────────────────────────────

_stats = []

if not df_pib.empty and "pes_cnae47" in df_pib.columns:
    _r = df_pib.dropna(subset=["pes_cnae47"]).sort_values("any")
    if len(_r) >= 2:
        _l, _pr = _r.iloc[-1], _r.iloc[-2]
        _stats.append((
            fnum(_l["pes_cnae47"] * 100, 1), "%",
            f"VAB sobre el PIB · {int(_l['any'])}",
            (f"{'des del' if _ca else 'desde el'} {fnum(_pr['pes_cnae47'] * 100, 1)}% "
             f"{'el' if _ca else 'en'} {int(_pr['any'])}"),
            "up" if _l["pes_cnae47"] > _pr["pes_cnae47"] else "down",
        ))

if not df_empreses.empty and "territori" in df_empreses.columns:
    _e = df_empreses[df_empreses["territori"] == "espanya"].dropna(
        subset=["empreses"]).sort_values("any")
    if len(_e) >= 2:
        _l, _pr = _e.iloc[-1], _e.iloc[-2]
        _var = (_l["empreses"] / _pr["empreses"] - 1) * 100
        _stats.append((
            fnum(int(_l["empreses"])), "",
            (f"Empreses actives · {int(_l['any'])}" if _ca
             else f"Empresas activas · {int(_l['any'])}"),
            f"{fpct(_var, 1)} vs {int(_pr['any'])}",
            "up" if _var > 0 else "down",
        ))

if not df_ocupacio.empty and "pais_codi" in df_ocupacio.columns:
    _o = df_ocupacio[(df_ocupacio["pais_codi"] == "ES")
                     & (df_ocupacio["sex"] == "T")].dropna(subset=["ocupats_milers"])
    _o = _o.groupby("any")["ocupats_milers"].sum().sort_index()
    if len(_o) >= 2:
        _var = (_o.iloc[-1] / _o.iloc[-2] - 1) * 100
        _stats.append((
            fnum(_o.iloc[-1] / 1000, 2), "M",
            (f"Persones ocupades · {int(_o.index[-1])}" if _ca
             else f"Personas ocupadas · {int(_o.index[-1])}"),
            f"{fpct(_var, 1)} vs {int(_o.index[-2])}",
            "up" if _var > 0 else "down",
        ))

if not df_ecommerce.empty and "ecommerce_cnae47_eur" in df_ecommerce.columns:
    _c = df_ecommerce.dropna(subset=["ecommerce_cnae47_eur"]).sort_values("any")
    if len(_c) >= 2:
        _l, _pr = _c.iloc[-1], _c.iloc[-2]
        _var = (_l["ecommerce_cnae47_eur"] / _pr["ecommerce_cnae47_eur"] - 1) * 100
        _stats.append((
            fnum(_l["ecommerce_cnae47_eur"] / 1e9, 1), "Md€",
            (f"Vendes online · {int(_l['any'])}" if _ca
             else f"Ventas online · {int(_l['any'])}"),
            f"{fpct(_var, 1)} vs {int(_pr['any'])}",
            "up" if _var > 0 else "down",
        ))

if _stats:
    _cifres_lab = "El sector en quatre xifres" if _ca else "El sector en cuatro cifras"
    _cifres_txt = (
        "Quatre magnituds per situar la mida del sector: què aporta a l'economia, "
        "quantes empreses i quantes persones hi treballen, i quant es ven per internet."
        if _ca else
        "Cuatro magnitudes para situar el tamaño del sector: qué aporta a la economía, "
        "cuántas empresas y cuántas personas trabajan en él, y cuánto se vende por internet."
    )
    st.markdown(
        f'<div class="h-sec-eyebrow" style="margin-bottom:8px;">{_cifres_lab}</div>'
        f'<div class="h-sec-p" style="margin-top:0;">{_cifres_txt}</div>',
        unsafe_allow_html=True,
    )
    home_space("s")
    home_stats(_stats)
    home_source(
        "INE (Comptabilitat Nacional, DIRCE), Eurostat (enquesta de forces de treball) "
        "i CNMC · cada xifra, a l'últim exercici tancat de la seva font" if _ca else
        "INE (Contabilidad Nacional, DIRCE), Eurostat (encuesta de fuerzas de trabajo) "
        "y CNMC · cada cifra, en el último ejercicio cerrado de su fuente"
    )
    home_rule(space_before=40, space_after=30)

# ─── NOVETATS DE DADES ─────────────────────────────────────────


@st.cache_data(ttl=600)
def load_updates_log():
    p = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "updates_log.json")
    if not os.path.exists(p):
        return {"events": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"events": []}


def _fmt_marker(marker, lang):
    """Formata el marcador de data d'un event (any / mes-any / data)."""
    parts = str(marker).split("-")
    if len(parts) == 1:
        return parts[0]
    try:
        if len(parts) == 2:
            return format_mes_any(date(int(parts[0]), int(parts[1]), 1), lang)
        if len(parts) == 3:
            return f"{int(parts[2]):02d}/{int(parts[1]):02d}/{parts[0]}"
    except (ValueError, TypeError):
        return str(marker)
    return str(marker)


_NOVETATS_DIES = 14
_recents = []
for _ev in load_updates_log().get("events", []):
    try:
        _det = date.fromisoformat(_ev.get("detected_at", ""))
    except (TypeError, ValueError):
        continue
    _ago = (_avui - _det).days
    if 0 <= _ago <= _NOVETATS_DIES:
        _recents.append((_ev, _ago))

if _recents:
    # Fila amb enllaç: el filet passa de la fila de text al contenidor sencer, i el
    # botó es pinta com un enllaç de text (l'estil global dels botons li posa caixa).
    st.markdown(
        '<style>'
        '[class*="st-key-novrow_"] { border-bottom: 1px solid #f2f4f7; gap: 0; }'
        '[class*="st-key-novrow_"] .h-upd-row { border-bottom: none; }'
        '[class*="st-key-novlink_"] { padding-top: 6px; }'
        '[class*="st-key-novlink_"] button { border: none !important; background: none !important;'
        ' box-shadow: none !important; padding: 0 !important; min-height: 0 !important; }'
        '[class*="st-key-novlink_"] button p { font-family: Manrope, system-ui, sans-serif !important;'
        ' font-size: 13px !important; font-weight: 700 !important; color: #0b3a66 !important;'
        ' text-transform: none !important; letter-spacing: 0 !important; white-space: nowrap; }'
        '[class*="st-key-novlink_"] button:hover p { color: #b07d2b !important; }'
        '</style>'
        f'<div class="h-sec-eyebrow" style="margin-bottom:6px;">'
        f'{"Novetats" if _ca else "Novedades"}</div>',
        unsafe_allow_html=True,
    )
    for _i, (_ev, _ago) in enumerate(_recents):
        _ds = _ev.get("dataset", "")
        _lbl = _ev.get("label_ca" if _ca else "label_es", _ds)
        _marker = _fmt_marker(_ev.get("last_data", ""), st.session_state.lang)
        if _ago == 0:
            _when = "avui" if _ca else "hoy"
        elif _ago == 1:
            _when = "ahir" if _ca else "ayer"
        else:
            _when = f"fa {_ago} dies" if _ca else f"hace {_ago} días"
        _verb = "actualitzat amb dades de" if _ca else "actualizado con datos de"
        _row = (f'<div class="h-upd-row"><span class="l"><b>{_lbl}</b> {_verb} '
                f'<span class="m">{_marker}</span></span>'
                f'<span class="r">{_when}</span></div>')
        if _ds in DESTINS:
            with st.container(key=f"novrow_{_i}"):
                _c_txt, _c_link = st.columns([9, 1], vertical_alignment="center", gap="small")
                with _c_txt:
                    st.markdown(_row, unsafe_allow_html=True)
                with _c_link:
                    if st.button(("Veure →" if _ca else "Ver →"), key=f"novlink_{_i}_{_ds}",
                                 type="tertiary"):
                        anar_a(_ds)
        else:
            st.markdown(_row, unsafe_allow_html=True)

home_rule(space_before=44, space_after=0, strong=True)
home_space("m")

# ─── LES LECTURES DE LA SETMANA ────────────────────────────────

home_section(
    ("Les lectures de la setmana" if _ca else "Las lecturas de la semana"),
    ("Dos senyals: on se situa Espanya i qui captura el creixement" if _ca
     else "Dos señales: dónde se sitúa España y quién captura el crecimiento"),
    ("La primera diu si el sector va més ràpid o més lent que el seu entorn. La "
     "segona, si el creixement es reparteix o es concentra." if _ca else
     "La primera dice si el sector va más rápido o más lento que su entorno. La "
     "segunda, si el crecimiento se reparte o se concentra."),
)
home_space("m")

# ── Espanya vs zona euro, per trimestres complets ──
_panel_a = None
_serie_q = None
if not df_eu_m.empty and {"pais_codi", "periode", "yoy"} <= set(df_eu_m.columns):
    _q = df_eu_m[df_eu_m["pais_codi"].isin(["ES", "EA20"])].dropna(subset=["yoy"]).copy()
    if not _q.empty:
        _q["trim"] = pd.PeriodIndex(pd.to_datetime(_q["periode"] + "-01"), freq="Q")
        # Només trimestres complets (3 mesos publicats per als dos àmbits).
        _cnt = _q.groupby(["trim", "pais_codi"]).size().unstack(fill_value=0)
        _plens = (_cnt[(_cnt["ES"] == 3) & (_cnt["EA20"] == 3)].index
                  if {"ES", "EA20"} <= set(_cnt.columns) else [])
        _serie_q = (_q[_q["trim"].isin(_plens)]
                    .pivot_table(index="trim", columns="pais_codi", values="yoy",
                                 aggfunc="mean").sort_index())
        if len(_serie_q) >= 2 and {"ES", "EA20"} <= set(_serie_q.columns):
            _panel_a = _serie_q.tail(8)

if _panel_a is not None:
    _last_q = _panel_a.index[-1]
    _es_v, _ea_v = float(_panel_a["ES"].iloc[-1]), float(_panel_a["EA20"].iloc[-1])
    _per_damunt = _es_v > _ea_v
    # Ratxa de trimestres per damunt (o, si ara està per sota, la que s'acaba de
    # trencar), sobre la sèrie completa i no només les vuit barres del gràfic.
    _ratxa = 0
    for _t in reversed(_serie_q.index if _per_damunt else _serie_q.index[:-1]):
        if _serie_q.loc[_t, "ES"] > _serie_q.loc[_t, "EA20"]:
            _ratxa += 1
        else:
            break
    _qlbl = f"{str(_last_q)[-1]}T {str(_last_q)[:4]}"

    if _per_damunt:
        _titol_a = (f"Espanya creix per damunt de la zona euro {_ratxa} trimestres seguits"
                    if _ca else
                    f"España crece por encima de la zona euro {_ratxa} trimestres seguidos")
    else:
        _titol_a = (f"Espanya cau per sota de la zona euro després de {_ratxa} trimestres "
                    f"per damunt" if _ca else
                    f"España cae por debajo de la zona euro tras {_ratxa} trimestres "
                    f"por encima")
    home_exhibit(
        ("Dinàmica recent · Eurostat" if _ca else "Dinámica reciente · Eurostat"),
        _titol_a,
        (f"{_qlbl}: {fpct(_es_v, 1)} Espanya i {fpct(_ea_v, 1)} zona euro, un "
         f"diferencial de {fnum(abs(_es_v - _ea_v), 1)}%. Volum de vendes, variació "
         f"interanual mitjana del trimestre." if _ca else
         f"{_qlbl}: {fpct(_es_v, 1)} España y {fpct(_ea_v, 1)} zona euro, un "
         f"diferencial de {fnum(abs(_es_v - _ea_v), 1)}%. Volumen de ventas, variación "
         f"interanual media del trimestre."),
        legend=[(NAVY, "Espanya" if _ca else "España"),
                (OCRE, "Zona euro" if _ca else "Zona euro")],
    )
    _labels = [f"{str(p)[-1]}T {str(p)[2:4]}" for p in _panel_a.index]
    _fig_a = go.Figure()
    _fig_a.add_trace(go.Bar(
        x=_labels, y=_panel_a["ES"], marker_color=NAVY,
        hovertemplate="%{x}<br>%{y:.1f}%<extra>"
                      + ("Espanya" if _ca else "España") + "</extra>",
    ))
    _fig_a.add_trace(go.Bar(
        x=_labels, y=_panel_a["EA20"], marker_color=OCRE,
        hovertemplate="%{x}<br>%{y:.1f}%<extra>Zona euro</extra>",
    ))
    _fig_a.add_hline(y=0, line=dict(color="#c9d2db", width=1))
    _fig_a.update_layout(**_layout(300, ysuffix="%", barmode="group",
                                   bargap=0.34, bargroupgap=0.06))
    st.plotly_chart(_fig_a, use_container_width=True, config={"displayModeBar": False})
    home_source(
        "Eurostat (sts_trtu_m) · volum de vendes corregit d'estacionalitat i "
        "calendari · només trimestres complets" if _ca else
        "Eurostat (sts_trtu_m) · volumen de ventas corregido de estacionalidad y "
        "calendario · solo trimestres completos"
    )
    home_space("l")

# ── Qui captura el creixement: quotes sobre el sector ──
_panel_b = None
if not df_lideres.empty and not df_eas.empty and "ing_2024" in df_lideres.columns:
    # El codi de branca ve com a text al parquet i com a enter al CSV: comparar en text.
    _s47 = (df_eas[df_eas["codi"].astype(str) == "47"]
            .dropna(subset=["xifra_negoci"]).sort_values("any"))
    if not _s47.empty:
        _sec_any = int(_s47.iloc[-1]["any"])
        _sec_meur = float(_s47.iloc[-1]["xifra_negoci"]) / 1e6
        _lid = df_lideres.dropna(subset=["ing_2024"]).sort_values("ing_2024", ascending=False)
        if not _lid.empty and _sec_meur > 0:
            _top = _lid.head(5)
            _quotes = [(r["nombre"], r["ing_2024"] / 1000 / _sec_meur * 100)
                       for _, r in _top.iterrows()]
            _bloc_pct = _lid["ing_2024"].sum() / 1000 / _sec_meur * 100
            # Mateix bloc d'empreses quatre anys abans: s'ha mogut el repartiment?
            _bloc_ant = _any_ant = _bloc_ara_sub = _n_ambdos = None
            if "ing_2020" in _lid.columns:
                _sub = _lid.dropna(subset=["ing_2020"])
                _s_ant = _s47[_s47["any"] == 2020]
                if not _sub.empty and not _s_ant.empty:
                    _any_ant = 2020
                    _n_ambdos = len(_sub)
                    _bloc_ant = (_sub["ing_2020"].sum() / 1000
                                 / (float(_s_ant.iloc[0]["xifra_negoci"]) / 1e6) * 100)
                    _bloc_ara_sub = _sub["ing_2024"].sum() / 1000 / _sec_meur * 100
            _panel_b = {
                "quotes": _quotes, "altres_n": len(_lid) - len(_top),
                "altres_pct": _lid.iloc[5:]["ing_2024"].sum() / 1000 / _sec_meur * 100,
                "resta_pct": 100 - _bloc_pct, "bloc_pct": _bloc_pct, "n": len(_lid),
                "sec_any": _sec_any, "bloc_ant": _bloc_ant, "any_ant": _any_ant,
                "bloc_ara_sub": _bloc_ara_sub, "n_ambdos": _n_ambdos,
                "no_2024": int((_lid["snapshot_any"] != 2024).sum())
                if "snapshot_any" in _lid.columns else 0,
            }

if _panel_b is not None:
    _b = _panel_b
    _lider_nom, _lider_pct = _b["quotes"][0]
    if _b["bloc_ant"] is not None:
        _nota_b = (f"I el repartiment gairebé no s'ha mogut: les {_b['n_ambdos']} societats "
                   f"amb comptes dipositats dels dos exercicis passen del "
                   f"{fnum(_b['bloc_ant'], 1)}% ({_b['any_ant']}) al "
                   f"{fnum(_b['bloc_ara_sub'], 1)}% ({_b['sec_any']}) de la xifra de negoci "
                   f"del sector." if _ca else
                   f"Y el reparto apenas se ha movido: las {_b['n_ambdos']} sociedades con "
                   f"cuentas depositadas de los dos ejercicios pasan del "
                   f"{fnum(_b['bloc_ant'], 1)}% ({_b['any_ant']}) al "
                   f"{fnum(_b['bloc_ara_sub'], 1)}% ({_b['sec_any']}) de la cifra de negocio "
                   f"del sector.")
    else:
        _nota_b = (f"Els {_b['n']} grans sumen el {fnum(_b['bloc_pct'], 1)}% de la xifra de "
                   f"negoci del sector; la resta es reparteix entre desenes de milers "
                   f"d'empreses." if _ca else
                   f"Los {_b['n']} grandes suman el {fnum(_b['bloc_pct'], 1)}% de la cifra "
                   f"de negocio del sector; el resto se reparte entre decenas de miles de "
                   f"empresas.")
    home_exhibit(
        ("Estructura de mercat · Registre Mercantil i INE" if _ca
         else "Estructura de mercado · Registro Mercantil e INE"),
        (f"Un sol operador val el {fnum(_lider_pct, 1)}% del sector; els {_b['n']} grans, "
         f"el {fnum(_b['bloc_pct'], 1)}%" if _ca else
         f"Un solo operador vale el {fnum(_lider_pct, 1)}% del sector; los {_b['n']} "
         f"grandes, el {fnum(_b['bloc_pct'], 1)}%"),
        _nota_b,
    )
    _noms = [n for n, _ in _b["quotes"]]
    _vals = [v for _, v in _b["quotes"]]
    _noms += [(f"Els altres {_b['altres_n']} grans" if _ca
               else f"Los otros {_b['altres_n']} grandes"),
              ("Resta del sector" if _ca else "Resto del sector")]
    _vals += [_b["altres_pct"], _b["resta_pct"]]
    # Navy per als grans, teal per a la resta del teixit: el contrast de color
    # és el propi argument del gràfic (cap concentrat vs base fragmentada).
    _fig_b = go.Figure(go.Bar(
        x=_vals, y=_noms, orientation="h",
        marker_color=[NAVY] + ["#2b5f8f"] * 4 + [TEAL, TEAL_SOFT],
        text=[f"{fnum(v, 1)}%" for v in _vals], textposition="outside",
        textfont=dict(family="Manrope, sans-serif", size=12.5, color=INK_P),
        hovertemplate="%{y}<br>%{x:.1f}%<extra></extra>",
    ))
    _fig_b.update_layout(**_layout(
        296,
        xaxis=dict(visible=False, range=[0, max(_vals) * 1.16]),
        yaxis=dict(autorange="reversed", showgrid=False,
                   tickfont=dict(size=13, color=INK_P)),
        margin=dict(l=0, r=48, t=6, b=0),
    ))
    st.plotly_chart(_fig_b, use_container_width=True, config={"displayModeBar": False})
    _nota_snap = ""
    if _b["no_2024"]:
        _nota_snap = (f" · {_b['no_2024']} societats amb l'últim exercici dipositat "
                      f"anterior al {_b['sec_any']}" if _ca else
                      f" · {_b['no_2024']} sociedades con el último ejercicio depositado "
                      f"anterior a {_b['sec_any']}")
    home_source(
        (f"Comptes del Registre Mercantil i Enquesta Estructural d'Empreses (INE), "
         f"exercici {_b['sec_any']}{_nota_snap}" if _ca else
         f"Cuentas del Registro Mercantil y Encuesta Estructural de Empresas (INE), "
         f"ejercicio {_b['sec_any']}{_nota_snap}")
    )
    home_space("s")
    st.page_link("pages/D_Lideres.py",
                 label=("Anatomia de la concentració →" if _ca
                        else "Anatomía de la concentración →"))

home_rule(space_before=48, space_after=0, strong=True)
home_space("m")

# ─── LA TESI EDITORIAL ─────────────────────────────────────────

if _ed.get("cifra") or _ed.get("lede"):
    _tesi_l, _tesi_r = st.columns([1, 1], gap="large")
    with _tesi_l:
        _src_bits = []
        if _ed.get("setmana"):
            _src_bits.append(f'<span class="d">{_ed["setmana"]}</span>')
        _src_bits.append("El Pulso de la semana")
        if _ed.get("font"):
            _src_bits.append(_ed["font"])
        home_quote(
            _md_a_html(_ed.get("cifra") or _ed["lede"].split(". ")[0] + "."),
            " · ".join(_src_bits),
        )
    with _tesi_r:
        _paras = ""
        if _ed.get("context"):
            _paras += f'<div class="ctx">{_md_a_html(_ed["context"])}</div>'
        if _ed.get("lede"):
            _paras += f'<p>{_md_a_html(_retallar(_ed["lede"]))}</p>'
        st.markdown(f'<div class="h-aside">{_paras}</div>', unsafe_allow_html=True)
        home_space("s")
        st.page_link("pages/L_Editorial.py",
                     label=("Llegir l'edició completa →" if _ca
                            else "Leer la edición completa →"))
    home_rule(space_before=48, space_after=0, strong=True)
    home_space("m")

# ─── LA RADIOGRAFIA ────────────────────────────────────────────

home_section(
    ("La radiografia" if _ca else "La radiografía"),
    ("Vuit dimensions del comerç al detall" if _ca
     else "Ocho dimensiones del comercio minorista"),
    ("Sèries oficials verificades i actualitzades de forma automàtica des de la font."
     if _ca else
     "Series oficiales verificadas y actualizadas de forma automática desde la fuente."),
)
home_space("s")

_DIMENSIONS = [
    ("01", "PIB i VAB", "PIB y VAB",
     "Pes del comerç a l'economia i trajectòria del seu valor afegit.",
     "Peso del comercio en la economía y trayectoria de su valor añadido.",
     "pages/1_PIB_i_VAB.py"),
    ("02", "Empreses", "Empresas",
     "Demografia empresarial: cens, densitat territorial i mida mitjana.",
     "Demografía empresarial: censo, densidad territorial y tamaño medio.",
     "pages/2_Empreses.py"),
    ("03", "Ocupació", "Empleo",
     "Ocupats, perfil de qui treballa al sector i pes al mercat laboral.",
     "Ocupados, perfil de quien trabaja en el sector y peso en el mercado laboral.",
     "pages/3_Ocupació.py"),
    ("04", "Productivitat", "Productividad",
     "Valor afegit per hora, marges i repartiment de cada euro venut.",
     "Valor añadido por hora, márgenes y reparto de cada euro vendido.",
     "pages/4_Productivitat.py"),
    ("05", "E-commerce", "E-commerce",
     "Volum online del sector i adopció de tecnologia de fons.",
     "Volumen online del sector y adopción de tecnología de fondo.",
     "pages/5_Ecommerce.py"),
    ("06", "Territori", "Territorio",
     "Distribució per comunitats autònomes i densitat comercial.",
     "Distribución por comunidades autónomas y densidad comercial.",
     "pages/6_Territori.py"),
    ("07", "Subsectors", "Subsectores",
     "Estructura, activitat i demanda de cada branca del CNAE 47.",
     "Estructura, actividad y demanda de cada rama del CNAE 47.",
     "pages/9_Subsectors.py"),
    ("08", "Comparativa Europa", "Comparativa Europa",
     "El comerç espanyol davant la UE-27 en estructura i dinàmica.",
     "El comercio español frente a la UE-27 en estructura y dinámica.",
     "pages/7_Comparativa_Europa.py"),
]

_col_esq, _col_dre = st.columns(2, gap="large")
for _i, (_n, _t_ca, _t_es, _d_ca, _d_es, _path) in enumerate(_DIMENSIONS):
    with (_col_esq if _i % 2 == 0 else _col_dre):
        home_field(_n, _t_ca if _ca else _t_es, _d_ca if _ca else _d_es)
        st.page_link(_path, label="Explorar →")

home_space("m")

# ─── SOBRE L'OBSERVATORI ───────────────────────────────────────

with st.expander(
    "Què és l'Observatori del Comerç" if _ca else "Qué es el Observatorio del Comercio",
    expanded=False,
):
    if _ca:
        st.markdown(
            "El **comerç al detall** (CNAE 47) és un dels pilars de l'economia "
            "espanyola: dona feina a més de **2 milions** de persones, genera uns "
            "**72.000 M€** de valor afegit i articula el consum de les famílies a tot "
            "el territori. Aquest observatori ofereix una **radiografia actualitzada** "
            "del sector a partir de dades oficials (INE, Eurostat, CNMC), organitzada "
            "en vuit dimensions. Les sèries anuals s'actualitzen de forma **trimestral "
            "automàtica** i el pols diari i mensual es refresca de continu."
        )
    else:
        st.markdown(
            "El **comercio minorista** (CNAE 47) es uno de los pilares de la economía "
            "española: da empleo a más de **2 millones** de personas, genera unos "
            "**72.000 M€** de valor añadido y articula el consumo de las familias en "
            "todo el territorio. Este observatorio ofrece una **radiografía "
            "actualizada** del sector a partir de datos oficiales (INE, Eurostat, "
            "CNMC), organizada en ocho dimensiones. Las series anuales se actualizan de "
            "forma **trimestral automática** y el pulso diario y mensual se refresca de "
            "continuo."
        )

# ─── BUTLLETÍ ──────────────────────────────────────────────────

home_space("m")
newsletter_form(st.session_state.lang)

# ─── META ──────────────────────────────────────────────────────

# newsletter=False: la portada ja porta el bloc gran d'alta just a sobre.
page_meta("INE, Eurostat, CNMC", st.session_state.lang, newsletter=False)
