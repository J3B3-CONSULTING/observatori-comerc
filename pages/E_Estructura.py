"""Pàgina: Trajectòria estructural del comerç (ES).

El DOBLE PINÇAMENT del comerç físic: la quota de béns sobre el consum de les
llars baixa (els serveis guanyen) i, dins dels béns, l'online en guanya quota.
Dues forces lentes i PERSISTENTS — i per això projectables (R²~0,9), a diferència
del soroll mensual. Llegeix data/cache/estructura_comerc.csv + meta (Eurostat
nama_10_fcs + e-commerce CNMC, processats al pipeline).
"""
import json
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset, read_dataset, signatura
from navegacio import tab_destinacio
from style import (inject_css, setup_lang, page_header, insight, intro, source,
                   fpct, apply_layout, PURPLE, GREEN, GRAY, RED,
                   inject_premium_page_css, kicker, action_title, deck)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"

_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
_META = os.path.join(_CACHE, "estructura_comerc_meta.json")


@st.cache_data(ttl=3600)
def load_estructura(sig):
    df = read_dataset("estructura_comerc")
    if df.empty:
        return df, {}
    meta = {}
    if os.path.exists(_META):
        try:
            with open(_META, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            meta = {}
    return df, meta


df, meta = load_estructura(signatura("estructura_comerc", "csv"))
preds = load_dataset("prediccions_estructura")

kicker("Tendència estructural · Béns i canal online" if _ca
       else "Tendencia estructural · Bienes y canal online")
action_title("El comerç físic viu un doble pinçament: menys béns, més online" if _ca
             else "El comercio físico vive un doble pinzamiento: menos bienes, más online")
deck("La quota de béns sobre el consum de les llars baixa i, dins dels béns, l'online en guanya. Dues forces lentes i persistents." if _ca
     else "La cuota de bienes sobre el consumo de los hogares baja y, dentro de los bienes, el online gana. Dos fuerzas lentas y persistentes.")

intro(
    ("El comerç al detall físic no s'enfonsa: el <strong>pincen dues forces lentes "
     "i persistents</strong>. Pel costat del consum, els <strong>serveis</strong> "
     "(oci, restauració, viatges, subscripcions) guanyen quota any rere any als "
     "<strong>béns</strong>. I dins dels béns, el <strong>comerç online</strong> en "
     "captura una part creixent. El resultat és una erosió gradual de la quota del "
     "comerç físic sobre la despesa de les llars. A diferència del soroll mensual, "
     "aquestes derives són prou regulars per <strong>projectar-les</strong>."
     if _ca else
     "El comercio minorista físico no se hunde: lo <strong>atenazan dos fuerzas "
     "lentas y persistentes</strong>. Por el lado del consumo, los <strong>servicios</strong> "
     "(ocio, restauración, viajes, suscripciones) ganan cuota año tras año a los "
     "<strong>bienes</strong>. Y dentro de los bienes, el <strong>comercio online</strong> "
     "captura una parte creciente. El resultado es una erosión gradual de la cuota "
     "del comercio físico sobre el gasto de los hogares. A diferencia del ruido "
     "mensual, estas derivas son lo bastante regulares para <strong>proyectarlas</strong>."))

if df.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

hist = df[df["tipus"] == "historic"].copy()
proj = df[df["tipus"] == "projeccio"].copy()
_ult = int(meta.get("ultim_any_real", hist["any"].max()))


def _proj_bridge(col):
    """Prepèn l'últim punt històric a la projecció perquè la línia discontínua
    connecti visualment amb la sòlida."""
    h = hist.dropna(subset=[col])
    if h.empty:
        return proj["any"], proj[col]
    last = h.iloc[-1]
    xs = pd.concat([pd.Series([last["any"]]), proj["any"]], ignore_index=True)
    ys = pd.concat([pd.Series([last[col]]), proj[col]], ignore_index=True)
    return xs, ys


def _line(fig, x, y, name, color, dash=None, width=3, hover=None):
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name, mode="lines",
        line=dict(color=color, width=width, dash=dash),
        hovertemplate=f"{hover or name}: %{{y:.1f}} %<extra></extra>"))


_tabs_lbl = [
    ("El doble pinçament" if _ca else "El doble pinzamiento"),
    ("Béns → serveis" if _ca else "Bienes → servicios"),
    ("Penetració online" if _ca else "Penetración online"),
]
tab_sint, tab_bs, tab_on = st.tabs(_tabs_lbl, default=tab_destinacio("pages/E_Estructura.py", _tabs_lbl))

# ════════════════════════════════════════════ TAB 1 · SÍNTESI
with tab_sint:
    _f24 = hist.dropna(subset=["comerc_fisic_share"])
    _v_ult = float(_f24.iloc[-1]["comerc_fisic_share"]) if not _f24.empty else None
    _p30 = proj[proj["any"] == 2030]["comerc_fisic_share"]
    _p35 = proj[proj["any"] == 2035]["comerc_fisic_share"]

    c1, c2, c3 = st.columns(3)
    if _v_ult is not None:
        c1.metric(f"Comerç físic / consum ({_ult})" if _ca
                  else f"Comercio físico / consumo ({_ult})", fpct(_v_ult, 1, sign=False))
    if len(_p30):
        c2.metric("Projecció 2030" if _ca else "Proyección 2030",
                  fpct(float(_p30.iloc[0]), 1, sign=False))
    if len(_p35):
        c3.metric("Projecció 2035" if _ca else "Proyección 2035",
                  fpct(float(_p35.iloc[0]), 1, sign=False))

    fig = go.Figure()
    _line(fig, _f24["any"], _f24["comerc_fisic_share"],
          "Comerç físic (històric)" if _ca else "Comercio físico (histórico)", PURPLE)
    bx, by = _proj_bridge("comerc_fisic_share")
    _line(fig, bx, by, "Projecció" if _ca else "Proyección", PURPLE, dash="dash")
    apply_layout(fig, yaxis_title=("% del consum de les llars" if _ca
                                   else "% del consumo de los hogares"), height=460)
    st.plotly_chart(fig, use_container_width=True)
    source("Elaboració pròpia · Eurostat (nama_10_fcs) + CNMC (e-commerce). "
           "Projecció = ajust lineal excloent COVID 2020-22."
           if _ca else
           "Elaboración propia · Eurostat (nama_10_fcs) + CNMC (e-commerce). "
           "Proyección = ajuste lineal excluyendo COVID 2020-22.")

    insight(
        ("<strong>Aquesta és la tesi de l'Observatori, amb dades.</strong> El comerç "
         "físic perd quota de manera lenta però sostinguda: no per una crisi, sinó "
         "per un canvi d'hàbits (béns→serveis) i de canal (botiga→online) que avancen "
         "a la vegada. És el contrari del soroll mensual: aquí el senyal és tan regular "
         "que es projecta amb confiança. El sector no desapareix —segueix sent enorme— "
         "però qui hi competeix ho fa en un espai que s'estreny cada any."
         if _ca else
         "<strong>Esta es la tesis del Observatorio, con datos.</strong> El comercio "
         "físico pierde cuota de forma lenta pero sostenida: no por una crisis, sino "
         "por un cambio de hábitos (bienes→servicios) y de canal (tienda→online) que "
         "avanzan a la vez. Es lo contrario del ruido mensual: aquí la señal es tan "
         "regular que se proyecta con confianza. El sector no desaparece —sigue siendo "
         "enorme— pero quien compite en él lo hace en un espacio que se estrecha cada año."))

# ════════════════════════════════════════════ TAB 2 · BÉNS vs SERVEIS
with tab_bs:
    _bh = hist.dropna(subset=["bens_share"])
    _b0 = _bh.iloc[0]
    _b1 = _bh.iloc[-1]
    _slope = meta.get("bens_slope_pp_any")
    _r2 = meta.get("bens_r2")

    c1, c2, c3 = st.columns(3)
    c1.metric(f"Quota de béns {int(_b0['any'])}", fpct(float(_b0["bens_share"]), 1, sign=False))
    c2.metric(f"Quota de béns {int(_b1['any'])}", fpct(float(_b1["bens_share"]), 1, sign=False),
              delta=f"{float(_b1['bens_share']) - float(_b0['bens_share']):+.1f} pp")
    if _slope is not None:
        c3.metric("Tendència" if _ca else "Tendencia",
                  f"{_slope:+.2f} pp/any" if _ca else f"{_slope:+.2f} pp/año",
                  delta=(f"R² {_r2:.2f}" if _r2 is not None else None), delta_color="off")

    fig = go.Figure()
    _line(fig, _bh["any"], _bh["bens_share"],
          "Béns" if _ca else "Bienes", PURPLE)
    bx, by = _proj_bridge("bens_share")
    _line(fig, bx, by, "Béns (proj.)" if _ca else "Bienes (proy.)", PURPLE, dash="dash",
          hover="Béns, projecció" if _ca else "Bienes, proyección")
    _sh = hist.dropna(subset=["serveis_share"])
    _line(fig, _sh["any"], _sh["serveis_share"],
          "Serveis" if _ca else "Servicios", GRAY, width=2)
    # Prediccions registrades i datades (P011-P014) com a marcadors amb banda
    if not preds.empty:
        fig.add_trace(go.Scatter(
            x=preds["horitzo"], y=preds["valor"], mode="markers",
            name=("Predicció" if _ca else "Predicción"),
            marker=dict(color=RED, size=10, symbol="diamond"),
            customdata=preds["banda"],
            error_y=dict(type="data", array=preds["banda"], visible=True,
                         color=RED, thickness=1.5, width=6),
            hovertemplate=(
                "Predicció registrada: %{y:.1f} % ± %{customdata:.1f}<extra></extra>"
                if _ca else
                "Predicción registrada: %{y:.1f} % ± %{customdata:.1f}<extra></extra>")))
    # Anotació del bot COVID
    _covid = hist[hist["any"] == 2020]
    if not _covid.empty:
        fig.add_annotation(x=2020, y=float(_covid.iloc[0]["bens_share"]),
                           text="COVID", showarrow=True, arrowhead=2,
                           ay=-30, font=dict(size=11, color=GRAY))
    apply_layout(fig, yaxis_title="% del consum" if _ca else "% del consumo", height=460)
    st.plotly_chart(fig, use_container_width=True)
    source("Eurostat, nama_10_fcs (despesa en consum final de les llars per durabilitat). "
           "Béns = duradors + semiduradors + no duradors."
           if _ca else
           "Eurostat, nama_10_fcs (gasto en consumo final de los hogares por durabilidad). "
           "Bienes = duraderos + semiduraderos + no duraderos.")

    insight(
        ("Des de 1995 els <strong>serveis</strong> no han parat de guanyar quota al "
         "consum de les llars: els béns han passat de gairebé la meitat a poc més d'un "
         "terç. El 2020-21 és l'única excepció —el confinament va suprimir el consum de "
         "serveis i va inflar el de béns temporalment—, i per això s'exclou de l'ajust. "
         "Un cop normalitzat, la deriva reprèn exactament on era."
         if _ca else
         "Desde 1995 los <strong>servicios</strong> no han dejado de ganar cuota al "
         "consumo de los hogares: los bienes han pasado de casi la mitad a algo más de "
         "un tercio. El 2020-21 es la única excepción —el confinamiento suprimió el "
         "consumo de servicios e infló el de bienes temporalmente—, y por eso se excluye "
         "del ajuste. Una vez normalizado, la deriva retoma justo donde estaba."))

    if not preds.empty:
        st.divider()
        st.markdown("**Predicció registrada i falsable**" if _ca
                    else "**Predicción registrada y falsable**")
        _flat = float(preds["benchmark_flat"].iloc[0])
        _mesos = (["gener", "febrer", "març", "abril", "maig", "juny", "juliol",
                   "agost", "setembre", "octubre", "novembre", "desembre"] if _ca else
                  ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                   "agosto", "septiembre", "octubre", "noviembre", "diciembre"])
        try:
            _y, _m, _d = preds["data_prediccio"].iloc[0].split("-")
            _dpred = f"{int(_d)} de {_mesos[int(_m) - 1]} de {_y}"
        except (ValueError, IndexError):
            _dpred = preds["data_prediccio"].iloc[0]
        st.caption(
            (f"**Què vol dir això?** El {_dpred}, abans de saber com aniria, vam deixar "
             f"per escrit quant esperem que pesin els béns dins la despesa de les llars "
             f"el 2026, 2027, 2030 i 2035 (els rombes vermells del gràfic, cadascun amb "
             f"el seu marge). Cada any, quan Eurostat publiqui la xifra real, podràs "
             f"comprovar aquí si vam encertar. I la prova és exigent: només comptarà com "
             f"a encert si la realitat segueix la **baixada** que anticipem, no la sortida "
             f"fàcil que tot es quedi com avui ({_flat:.1f} %)."
             if _ca else
             f"**¿Qué significa esto?** El {_dpred}, antes de saber cómo iría, dejamos "
             f"por escrito cuánto esperamos que pesen los bienes en el gasto de los "
             f"hogares en 2026, 2027, 2030 y 2035 (los rombos rojos del gráfico, cada "
             f"uno con su margen). Cada año, cuando Eurostat publique la cifra real, "
             f"podrás comprobar aquí si acertamos. Y la prueba es exigente: solo contará "
             f"como acierto si la realidad sigue la **bajada** que anticipamos, no la "
             f"salida fácil de que todo se quede como hoy ({_flat:.1f} %)."),
        )
        _disp = pd.DataFrame({
            ("Any" if _ca else "Año"): preds["horitzo"].astype(int),
            ("Predicció" if _ca else "Predicción"):
                preds.apply(lambda r: f"{r['valor']:.1f} % ± {r['banda']:.1f}", axis=1),
            ("Estat" if _ca else "Estado"): preds["estat"],
            ("Valor real" if _ca else "Valor real"):
                preds["valor_real"].apply(lambda v: "—" if pd.isna(v) else f"{float(v):.1f} %"),
        })
        st.dataframe(_disp, hide_index=True, use_container_width=True)

# ════════════════════════════════════════════ TAB 3 · ONLINE
with tab_on:
    _oh = hist.dropna(subset=["online_pen"])
    _o0 = _oh.iloc[0]
    _o1 = _oh.iloc[-1]
    _osl = meta.get("online_slope_pp_any")
    _or2 = meta.get("online_r2")

    c1, c2, c3 = st.columns(3)
    c1.metric(f"Online / béns {int(_o0['any'])}", fpct(float(_o0["online_pen"]), 1, sign=False))
    c2.metric(f"Online / béns {int(_o1['any'])}", fpct(float(_o1["online_pen"]), 1, sign=False),
              delta=f"{float(_o1['online_pen']) - float(_o0['online_pen']):+.1f} pp")
    if _osl is not None:
        c3.metric("Tendència" if _ca else "Tendencia",
                  f"{_osl:+.2f} pp/any" if _ca else f"{_osl:+.2f} pp/año",
                  delta=(f"R² {_or2:.2f}" if _or2 is not None else None), delta_color="off")

    fig = go.Figure()
    _line(fig, _oh["any"], _oh["online_pen"],
          "Penetració online" if _ca else "Penetración online", GREEN)
    bx, by = _proj_bridge("online_pen")
    _line(fig, bx, by, "Projecció" if _ca else "Proyección", GREEN, dash="dash")
    apply_layout(fig, yaxis_title=("% dels béns comprats online" if _ca
                                   else "% de los bienes comprados online"), height=460)
    st.plotly_chart(fig, use_container_width=True)
    source("Elaboració pròpia · e-commerce CNAE 47 (CNMC) sobre consum de béns "
           "(Eurostat). Proxy: numerador i denominador de fonts diferents; el que "
           "importa és la tendència. El salt COVID és permanent."
           if _ca else
           "Elaboración propia · e-commerce CNAE 47 (CNMC) sobre consumo de bienes "
           "(Eurostat). Proxy: numerador y denominador de fuentes distintas; lo que "
           "importa es la tendencia. El salto COVID es permanente.")

    insight(
        ("La compra de béns per internet ha passat de testimonial a una de cada catorze "
         "euros de béns, i puja amb una regularitat notable. El salt del 2020 no va "
         "revertir: es va consolidar. És la segona mossegada del pinçament — i la que "
         "actua <strong>dins</strong> del territori que encara és dels béns."
         if _ca else
         "La compra de bienes por internet ha pasado de testimonial a uno de cada "
         "catorce euros de bienes, y sube con una regularidad notable. El salto de 2020 "
         "no revirtió: se consolidó. Es el segundo mordisco del pinzamiento — y el que "
         "actúa <strong>dentro</strong> del territorio que todavía es de los bienes."))
