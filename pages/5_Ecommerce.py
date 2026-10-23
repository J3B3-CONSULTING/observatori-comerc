"""Pàgina 5: Digitalització del comerç (CNAE 47) — disseny premium consultora"""
import streamlit as st
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, cagr,
    kicker, action_title, deck, key_takeaways, shock_stat, exhibit_header,
    metrics_band, premium_plotly_layout, apply_layout, freshness_badge,
    NAVY, OCRE, RED, G1_P, G2_P,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"

_CHART_CONFIG = {"displayModeBar": False, "responsive": True}

df = load_dataset("ecommerce")
df_dig = load_dataset("digitalitzacio_comerc")

# ─── HEADER ──────────────────────────────────────────────────

kicker("Anàlisi estructural · Digitalització" if _ca
       else "Análisis estructural · Digitalización")

if df.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

df = df.sort_values("any")

# ─── Càlculs per a header, takeaways i shock stat ────────────
# Per evitar la distorsió de l'any parcial, els càlculs de capçalera
# es fan sobre l'últim any complet (penúltima fila si l'última és parcial).
_df_ec = df.dropna(subset=["ecommerce_cnae47_eur"]).copy()
_first_ec = _df_ec.iloc[0]

# Detectar any parcial (caiguda brusca del total respecte l'any anterior)
_partial = False
if len(_df_ec) >= 2:
    _r = _df_ec.iloc[-1]["ecommerce_total_eur"] / _df_ec.iloc[-2]["ecommerce_total_eur"]
    _partial = _r < 0.85

_full_ec = _df_ec.iloc[-2] if (_partial and len(_df_ec) >= 2) else _df_ec.iloc[-1]

_fy = int(_first_ec["any"])
_ly = int(_full_ec["any"])
_n_years = _ly - _fy
_mult = _full_ec["ecommerce_cnae47_eur"] / _first_ec["ecommerce_cnae47_eur"]
_cagr_ec = cagr(_first_ec["ecommerce_cnae47_eur"], _full_ec["ecommerce_cnae47_eur"], _n_years)
_vol_last = _full_ec["ecommerce_cnae47_eur"] / 1e9

_df_pes = df.dropna(subset=["pes_cnae47_ecommerce"]).copy()
_pes_first = _df_pes.iloc[0]["pes_cnae47_ecommerce"] * 100
# Pes sobre l'any complet
_pes_full = _df_pes[_df_pes["any"] == _ly]
_pes_last = (float(_pes_full.iloc[0]["pes_cnae47_ecommerce"]) * 100
             if not _pes_full.empty else _df_pes.iloc[-1]["pes_cnae47_ecommerce"] * 100)
_pes_drop_pp = _pes_first - _pes_last

# Adopció TIC (últim valor per tecnologia, ES vs UE-27) per als takeaways
_dig_ready = not df_dig.empty


def _last_tech(tech_ca, p):
    if df_dig.empty:
        return (None, None)
    s = df_dig[(df_dig["tech"] == tech_ca) & (df_dig["pais_codi"] == p)].sort_values("any")
    return (None, None) if s.empty else (int(s.iloc[-1]["any"]), float(s.iloc[-1]["pct"]))


if _dig_ready:
    _ec_es = _last_tech("Venda electrònica", "ES")[1]
    _ec_ue = _last_tech("Venda electrònica", "EU27_2020")[1]
    _cl_es = _last_tech("Núvol (cloud)", "ES")[1]
    _cl_ue = _last_tech("Núvol (cloud)", "EU27_2020")[1]
    _cl_gap = _cl_ue - _cl_es

# ─── Titular + deck + takeaways ──────────────────────────────
if _ca:
    action_title(
        "El comerç ven online com mai, però perd quota i va lent en tecnologia de fons"
    )
    deck(
        "El volum d'e-commerce del comerç al detall s'ha multiplicat, però guanya menys "
        "terreny que la resta de l'economia digital i s'endarrereix en infraestructura."
    )
    _takeaways = [
        f"El volum d'e-commerce del CNAE 47 s'ha multiplicat per "
        f"<b>x{fnum(_mult, 0)}</b> entre {_fy} i {_ly} (CAGR {fpct(_cagr_ec, 1)}), "
        f"fins als <b>{fnum(_vol_last, 1)} Md€</b>.",
        f"Tot i això, el pes del detall sobre tot l'e-commerce baixa del "
        f"<b>{fpct(_pes_first, 1, sign=False)}</b> al <b>{fpct(_pes_last, 1, sign=False)}</b> "
        f"({fnum(_pes_drop_pp, 1)} pp): serveis i turisme creixen encara més de pressa al canal digital.",
    ]
    if _dig_ready:
        _takeaways.append(
            f"En vendre online Espanya supera la UE (<b>{fpct(_ec_es, 1, sign=False)}</b> "
            f"vs {fpct(_ec_ue, 1, sign=False)}), però en <b>núvol</b> queda "
            f"{fnum(_cl_gap, 0)} punts per sota ({fpct(_cl_es, 1, sign=False)} vs {fpct(_cl_ue, 1, sign=False)}): "
            f"sap vendre, però li falta tecnologia de fons."
        )
    _tk_label = "Conclusions clau"
else:
    action_title(
        "El comercio vende online como nunca, pero pierde cuota y va lento en tecnología de fondo"
    )
    deck(
        "El volumen de e-commerce del comercio minorista se ha multiplicado, pero gana menos "
        "terreno que el resto de la economía digital y se rezaga en infraestructura."
    )
    _takeaways = [
        f"El volumen de e-commerce del CNAE 47 se ha multiplicado por "
        f"<b>x{fnum(_mult, 0)}</b> entre {_fy} y {_ly} (CAGR {fpct(_cagr_ec, 1)}), "
        f"hasta los <b>{fnum(_vol_last, 1)} Md€</b>.",
        f"Aun así, el peso del minorista sobre todo el e-commerce baja del "
        f"<b>{fpct(_pes_first, 1, sign=False)}</b> al <b>{fpct(_pes_last, 1, sign=False)}</b> "
        f"({fnum(_pes_drop_pp, 1)} pp): servicios y turismo crecen aún más rápido en el canal digital.",
    ]
    if _dig_ready:
        _takeaways.append(
            f"En vender online España supera a la UE (<b>{fpct(_ec_es, 1, sign=False)}</b> "
            f"vs {fpct(_ec_ue, 1, sign=False)}), pero en <b>nube</b> queda "
            f"{fnum(_cl_gap, 0)} puntos por debajo ({fpct(_cl_es, 1, sign=False)} vs {fpct(_cl_ue, 1, sign=False)}): "
            f"sabe vender, pero le falta tecnología de fondo."
        )
    _tk_label = "Conclusiones clave"

key_takeaways(_takeaways, label=_tk_label)
freshness_badge(["ecommerce", "digitalitzacio_comerc"], st.session_state.lang)

# ─── TABS ────────────────────────────────────────────────────
_tabs_lbl = [
    "E-commerce",
    ("Digitalització" if _ca else "Digitalización"),
]
tab_ec, tab_dig = st.tabs(_tabs_lbl, default=tab_destinacio("pages/5_Ecommerce.py", _tabs_lbl))

# ════════════════════════════════════════════════════════════
# TAB 1: E-COMMERCE (volum de negoci online, CNMC)
# ════════════════════════════════════════════════════════════
with tab_ec:

    # ─── Nota metodològica any parcial ───────────────────
    if len(df) >= 2:
        _last_yr = df.iloc[-1]
        _prev_yr = df.iloc[-2]
        if "ecommerce_total_eur" in df.columns:
            _ratio = _last_yr["ecommerce_total_eur"] / _prev_yr["ecommerce_total_eur"]
            if _ratio < 0.85:
                _any_parcial = int(_last_yr["any"])
                if _ca:
                    st.warning(
                        f"**Nota metodològica:** Les dades de {_any_parcial} són provisionals i corresponen "
                        f"a un any incomplet (dades publicades fins al moment per la CNMC). "
                        f"La caiguda aparent respecte a {_any_parcial - 1} reflecteix la manca de dades dels últims trimestres, "
                        f"no una reducció real del volum de negoci."
                    )
                else:
                    st.warning(
                        f"**Nota metodológica:** Los datos de {_any_parcial} son provisionales y corresponden "
                        f"a un año incompleto (datos publicados hasta el momento por la CNMC). "
                        f"La caída aparente respecto a {_any_parcial - 1} refleja la falta de datos de los últimos trimestres, "
                        f"no una reducción real del volumen de negocio."
                    )

    # ─── Exhibit 1: Volum e-commerce ──────────────────────
    if _ca:
        exhibit_header(
            1, f"L'e-commerce del comerç al detall arriba als {fnum(_vol_last, 1)} Md€ el {_ly}",
            note="Les barres comparen el volum online del sector amb el total de "
                 "l'e-commerce a Espanya: el detall n'és una part que creix, però minoritària.",
        )
    else:
        exhibit_header(
            1, f"El e-commerce del comercio minorista alcanza los {fnum(_vol_last, 1)} Md€ en {_ly}",
            note="Las barras comparan el volumen online del sector con el total del "
                 "e-commerce en España: el minorista es una parte que crece, pero minoritaria.",
        )

    fig = go.Figure()
    if "ecommerce_total_eur" in df.columns:
        fig.add_trace(go.Bar(
            x=df["any"], y=df["ecommerce_total_eur"] / 1e9,
            name=t("ec_total"), marker_color=G2_P,
            hovertemplate="%{x}: <b>%{y:,.1f} Md€</b><extra>" + t("ec_total") + "</extra>",
        ))
    if "ecommerce_cnae47_eur" in df.columns:
        fig.add_trace(go.Bar(
            x=df["any"], y=df["ecommerce_cnae47_eur"] / 1e9,
            name=t("ec_cnae47"), marker_color=NAVY,
            hovertemplate="%{x}: <b>%{y:,.1f} Md€</b><extra>" + t("ec_cnae47") + "</extra>",
        ))
    _layout = premium_plotly_layout(
        height=450, margin_right=30,
        ytitle=("Milers de milions EUR" if _ca else "Miles de millones EUR"))
    _layout["barmode"] = "group"
    _layout["showlegend"] = True
    _layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(**_layout)
    st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)
    source("CNMC, Comerç electrònic a Espanya" if _ca
           else "CNMC, Comercio electrónico en España")

    # ─── Exhibit 2: Pes CNAE 47 sobre total ───────────────
    if "pes_cnae47_ecommerce" in df.columns:
        if _ca:
            exhibit_header(
                2, f"El detall perd {fnum(_pes_drop_pp, 1)} punts de quota dins l'e-commerce des del {_fy}",
                note="Si el pes baixa, vol dir que altres sectors —serveis, turisme, "
                     "continguts— han crescut encara més de pressa al canal digital.",
            )
        else:
            exhibit_header(
                2, f"El minorista pierde {fnum(_pes_drop_pp, 1)} puntos de cuota dentro del e-commerce desde {_fy}",
                note="Si el peso baja, significa que otros sectores —servicios, turismo, "
                     "contenidos— han crecido aún más rápido en el canal digital.",
            )

        _dp = df.dropna(subset=["pes_cnae47_ecommerce"]).sort_values("any")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=_dp["any"], y=_dp["pes_cnae47_ecommerce"] * 100,
            mode="lines", name=("Pes" if _ca else "Peso"),
            line=dict(color=NAVY, shape="spline", smoothing=0.5, width=3),
            fill="tozeroy", fillcolor="rgba(11,58,102,0.06)",
            hovertemplate="%{x}: <b>%{y:.1f}%</b><extra></extra>",
        ))
        _px_last = int(_dp["any"].iloc[-1])
        _py_last = float(_dp["pes_cnae47_ecommerce"].iloc[-1]) * 100
        fig2.add_trace(go.Scatter(
            x=[_px_last], y=[_py_last], mode="markers",
            showlegend=False, hoverinfo="skip",
            marker=dict(color=NAVY, size=10, line=dict(color="white", width=2)),
        ))
        _layout2 = premium_plotly_layout(
            height=400, margin_right=110,
            ytitle=("% sobre total e-commerce" if _ca else "% sobre total e-commerce"))
        _layout2["yaxis"]["rangemode"] = "normal"
        _layout2["yaxis"]["range"] = [0, float(_dp["pes_cnae47_ecommerce"].max() * 100) * 1.2]
        _layout2["yaxis"]["tickformat"] = ".1f"
        _layout2["annotations"] = [dict(
            x=_px_last, y=_py_last, xanchor="left", xshift=14, showarrow=False,
            align="left", text=f"<b>{fpct(_py_last, 1, sign=False)}</b><br>"
                               f"<span style='color:{G1_P}'>{_px_last}</span>",
            font=dict(color=NAVY, size=13),
        )]
        fig2.update_layout(**_layout2)
        st.plotly_chart(fig2, use_container_width=True, config=_CHART_CONFIG)
        source("CNMC. Càlcul propi" if _ca else "CNMC. Cálculo propio")

    # ─── Exhibit 3: Creixement interanual ─────────────────
    if "ecommerce_cnae47_eur" in df.columns and len(df) > 1:
        df["creix_ec"] = df["ecommerce_cnae47_eur"].pct_change() * 100
        df_creix = df.dropna(subset=["creix_ec"])
        if _ca:
            exhibit_header(
                3, "El creixement de l'e-commerce es modera després del salt de la pandèmia",
                note="Les barres blaves marquen anys de creixement; les vermelles, de "
                     "retrocés (inclou l'any parcial més recent).",
            )
        else:
            exhibit_header(
                3, "El crecimiento del e-commerce se modera tras el salto de la pandemia",
                note="Las barras azules marcan años de crecimiento; las rojas, de "
                     "retroceso (incluye el año parcial más reciente).",
            )
        colors = [NAVY if v >= 0 else RED for v in df_creix["creix_ec"]]
        fig3 = go.Figure(go.Bar(
            x=df_creix["any"], y=df_creix["creix_ec"],
            marker_color=colors,
            text=[fpct(v) for v in df_creix["creix_ec"]],
            textposition="outside",
            textfont=dict(size=10, color=G1_P, family="Manrope, system-ui, sans-serif"),
            hovertemplate="%{x}: <b>%{y:.1f}%</b><extra></extra>",
        ))
        _layout3 = premium_plotly_layout(
            height=400, margin_right=30,
            ytitle=("Variació interanual (%)" if _ca else "Variación interanual (%)"))
        _layout3["yaxis"]["rangemode"] = "normal"
        _layout3["yaxis"]["tickformat"] = ".1f"
        fig3.update_layout(**_layout3)
        fig3.add_hline(y=0, line_dash="dash", line_color="rgba(0,0,0,0.15)")
        st.plotly_chart(fig3, use_container_width=True, config=_CHART_CONFIG)
        source("CNMC. Càlcul propi" if _ca else "CNMC. Cálculo propio")

    # ─── Insight e-commerce ──────────────────────────────
    if "ecommerce_cnae47_eur" in df.columns and "pes_cnae47_ecommerce" in df.columns:
        pes_first = _pes_first
        pes_last = _pes_last
        pes_var = pes_last - pes_first
        multiplicador = _mult
        n_years = _n_years
        cagr_ec = _cagr_ec
        if _ca:
            txt = (
                f"El comerç electrònic del CNAE 47 ha multiplicat el seu volum per <strong>x{fnum(multiplicador)}</strong> "
                f"en {n_years} anys, amb un CAGR del <strong>{fpct(cagr_ec)}</strong>. "
                f"El pes del detall sobre el total d'e-commerce "
                f"ha passat del {fpct(pes_first, 1, sign=False)} al {fpct(pes_last, 1, sign=False)} ({fpct(pes_var)})."
            )
            if pes_var < 0:
                txt += (
                    "Això indica que <strong>altres sectors han crescut encara més ràpidament</strong> en el canal digital. "
                    "El comerç al detall, tot i ser un adoptant significatiu, "
                    "perd quota relativa davant serveis, turisme i sectors amb major marge digital. "
                    "La digitalització del sector ha estat reactiva (accelerada per la pandèmia) "
                    "més que proactiva, cosa que explica la pèrdua de quota relativa."
                )
            else:
                txt += (
                    "Això indica que <strong>el comerç al detall guanya quota en el canal digital</strong> "
                    "per sobre d'altres sectors, consolidant la seva posició en l'ecosistema d'e-commerce."
                )
        else:
            txt = (
                f"El comercio electrónico del CNAE 47 ha multiplicado su volumen por <strong>x{fnum(multiplicador)}</strong> "
                f"en {n_years} años, con un CAGR del <strong>{fpct(cagr_ec)}</strong>. "
                f"El peso del minorista sobre el total de e-commerce "
                f"ha pasado del {fpct(pes_first, 1, sign=False)} al {fpct(pes_last, 1, sign=False)} ({fpct(pes_var)})."
            )
            if pes_var < 0:
                txt += (
                    "Esto indica que <strong>otros sectores han crecido aún más rápidamente</strong> en el canal digital. "
                    "El comercio minorista, aun siendo un adoptante significativo, "
                    "pierde cuota relativa frente a servicios, turismo y sectores con mayor margen digital. "
                    "La digitalización del sector ha sido reactiva (acelerada por la pandemia) "
                    "más que proactiva, lo que explica la pérdida de cuota relativa."
                )
            else:
                txt += (
                    "Esto indica que <strong>el minorista gana cuota en el canal digital</strong> "
                    "por encima de otros sectores, consolidando su posición en el ecosistema de e-commerce."
                )
        insight(txt)

    # ─── Shock stat ───────────────────────────────────────────
    if _ca:
        shock_stat(
            f"x{fnum(_mult, 0)}", "",
            f"ha multiplicat el seu volum l'e-commerce del comerç al detall entre {_fy} i {_ly}, "
            f"i tot i això perd {fnum(_pes_drop_pp, 1)} punts de quota dins del total digital: "
            f"creix molt, però la resta de l'economia digital encara creix més.",
            sub="Créixer no és el mateix que guanyar quota",
        )
    else:
        shock_stat(
            f"x{fnum(_mult, 0)}", "",
            f"ha multiplicado su volumen el e-commerce del comercio minorista entre {_fy} y {_ly}, "
            f"y aun así pierde {fnum(_pes_drop_pp, 1)} puntos de cuota dentro del total digital: "
            f"crece mucho, pero el resto de la economía digital crece todavía más.",
            sub="Crecer no es lo mismo que ganar cuota",
        )

    # ─── Banda de mètriques (resum e-commerce) ────────────
    metrics_band([
        (fnum(_vol_last, 1), "Md€", f"E-commerce CNAE 47 ({_ly})"),
        (f"x{fnum(_mult, 0)}", "", f"Multiplicador {_fy}–{_ly}"),
        (fnum(_cagr_ec, 1), "%", "CAGR anual"),
        (fnum(_pes_last, 1), "%", "Pes sobre total e-commerce" if _ca else "Peso sobre total e-commerce"),
    ])

    with st.expander(t("download_data")):
        st.dataframe(df, use_container_width=True)
        st.download_button("CSV", df.to_csv(index=False).encode("utf-8"),
                           "ecommerce_cnae47.csv", "text/csv")

# ════════════════════════════════════════════════════════════
# TAB 2: DIGITALITZACIÓ (adopció TIC: e-commerce, IA, núvol — Eurostat)
# ════════════════════════════════════════════════════════════
with tab_dig:
    if df_dig.empty:
        st.info("Sense dades de digitalització disponibles." if _ca
                else "Sin datos de digitalización disponibles.")
    else:
        # (tech_ca, tech_es, color) en ordre de presentació
        _TECHS = [
            ("Venda electrònica", "Venta electrónica", NAVY),
            ("Intel·ligència artificial", "Inteligencia artificial", OCRE),
            ("Núvol (cloud)", "Nube (cloud)", G1_P),
        ]

        def _last(tech_ca, p):
            s = df_dig[(df_dig["tech"] == tech_ca) & (df_dig["pais_codi"] == p)].sort_values("any")
            return (None, None) if s.empty else (int(s.iloc[-1]["any"]), float(s.iloc[-1]["pct"]))

        if _ca:
            exhibit_header(
                4, "Espanya lidera en vendre online, però s'endarrereix en núvol i IA",
                note="Quantes empreses del sector tenen cada capacitat digital, comparat "
                     "amb la UE-27. És la cara de l'oferta: capacitat instal·lada, no vendes. "
                     "Nota: IA i núvol cobreixen empreses de 10 o més ocupats.",
            )
        else:
            exhibit_header(
                4, "España lidera en vender online, pero se rezaga en nube e IA",
                note="Cuántas empresas del sector tienen cada capacidad digital, comparado "
                     "con la UE-27. Es la cara de la oferta: capacidad instalada, no ventas. "
                     "Nota: IA y nube cubren empresas de 10 o más ocupados.",
            )

        _sub_comp, _sub_evo = st.tabs([
            ("Comparativa ES vs UE-27" if _ca else "Comparativa ES vs UE-27"),
            ("Evolució a Espanya" if _ca else "Evolución en España"),
        ])

        with _sub_comp:
            _labels = [(_tca if _ca else _tes) for _tca, _tes, _ in _TECHS]
            figb = go.Figure()
            figb.add_trace(go.Bar(
                x=_labels, y=[_last(t2[0], "ES")[1] for t2 in _TECHS],
                name=("Espanya" if _ca else "España"), marker_color=NAVY,
                hovertemplate="%{x}: <b>%{y:.1f}%</b><extra>" + ("Espanya" if _ca else "España") + "</extra>"))
            figb.add_trace(go.Bar(
                x=_labels, y=[_last(t2[0], "EU27_2020")[1] for t2 in _TECHS],
                name="UE-27", marker_color=OCRE,
                hovertemplate="%{x}: <b>%{y:.1f}%</b><extra>UE-27</extra>"))
            apply_layout(figb, yaxis_title="% d'empreses" if _ca else "% de empresas",
                         height=380, barmode="group")
            st.plotly_chart(figb, use_container_width=True, config=_CHART_CONFIG)
            source("Eurostat, enquesta TIC (isoc_ec_eseln2 · isoc_eb_ain2 · isoc_cicce_usen2), CNAE G47")

        with _sub_evo:
            figl = go.Figure()
            for _tca, _tes, _c in _TECHS:
                _d = df_dig[(df_dig["tech"] == _tca) & (df_dig["pais_codi"] == "ES")].sort_values("any")
                figl.add_trace(go.Scatter(
                    x=_d["any"], y=_d["pct"], mode="lines+markers", name=(_tca if _ca else _tes),
                    line=dict(color=_c, width=2.5), marker=dict(size=5)))
            _layoutl = premium_plotly_layout(
                height=380, margin_right=30,
                ytitle="% d'empreses" if _ca else "% de empresas")
            _layoutl["showlegend"] = True
            _layoutl["yaxis"]["rangemode"] = "tozero"
            _layoutl["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            figl.update_layout(**_layoutl)
            st.plotly_chart(figl, use_container_width=True, config=_CHART_CONFIG)
            source("Eurostat, enquesta TIC, CNAE G47")

        _ec_es, _ec_ue = _last("Venda electrònica", "ES")[1], _last("Venda electrònica", "EU27_2020")[1]
        _ai_es, _ai_ue = _last("Intel·ligència artificial", "ES")[1], _last("Intel·ligència artificial", "EU27_2020")[1]
        _ai_0 = df_dig[(df_dig["tech"] == "Intel·ligència artificial") & (df_dig["pais_codi"] == "ES")].sort_values("any")
        _ai_first = (None, None) if _ai_0.empty else (int(_ai_0.iloc[0]["any"]), float(_ai_0.iloc[0]["pct"]))
        _cl_es, _cl_ue = _last("Núvol (cloud)", "ES")[1], _last("Núvol (cloud)", "EU27_2020")[1]
        insight(
            (f"La digitalització del comerç espanyol és <strong>desigual</strong>. En <strong>venda electrònica</strong> "
             f"Espanya supera la UE ({fpct(_ec_es, 1, sign=False)} vs {fpct(_ec_ue, 1, sign=False)}): el canal de venda "
             f"es va digitalitzar aviat. Però en la <strong>infraestructura</strong> queda enrere: el "
             f"<strong>núvol</strong> ({fpct(_cl_es, 1, sign=False)}) està molt per sota de la UE ({fpct(_cl_ue, 1, sign=False)}). "
             f"La <strong>IA</strong> irromp de pressa —del {fpct(_ai_first[1], 1, sign=False)} ({_ai_first[0]}) al "
             f"{fpct(_ai_es, 1, sign=False)} ({_last('Intel·ligència artificial', 'ES')[0]})—, encara just per sota de la UE "
             f"({fpct(_ai_ue, 1, sign=False)}). Lectura: el comerç espanyol sap <em>vendre</em> online, però va més lent "
             f"a adoptar la <em>tecnologia de fons</em> que decideix qui competeix en els canals nous."
             if _ca else
             f"La digitalización del comercio español es <strong>desigual</strong>. En <strong>venta electrónica</strong> "
             f"España supera a la UE ({fpct(_ec_es, 1, sign=False)} vs {fpct(_ec_ue, 1, sign=False)}): el canal de venta "
             f"se digitalizó pronto. Pero en la <strong>infraestructura</strong> se queda atrás: la "
             f"<strong>nube</strong> ({fpct(_cl_es, 1, sign=False)}) está muy por debajo de la UE ({fpct(_cl_ue, 1, sign=False)}). "
             f"La <strong>IA</strong> irrumpe rápido —del {fpct(_ai_first[1], 1, sign=False)} ({_ai_first[0]}) al "
             f"{fpct(_ai_es, 1, sign=False)} ({_last('Intel·ligència artificial', 'ES')[0]})—, aún justo por debajo de la UE "
             f"({fpct(_ai_ue, 1, sign=False)}). Lectura: el comercio español sabe <em>vender</em> online, pero va más lento "
             f"en adoptar la <em>tecnología de fondo</em> que decide quién compite en los canales nuevos.")
        )

        # ─── Banda de mètriques (resum adopció TIC) ───────
        _yr_ec = _last("Venda electrònica", "ES")[0]
        metrics_band([
            (fnum(_ec_es, 1), "%", f"Venda electrònica · UE-27 {fnum(_ec_ue, 1)}%" if _ca
             else f"Venta electrónica · UE-27 {fnum(_ec_ue, 1)}%"),
            (fnum(_cl_es, 1), "%", f"Núvol · UE-27 {fnum(_cl_ue, 1)}%" if _ca
             else f"Nube · UE-27 {fnum(_cl_ue, 1)}%"),
            (fnum(_ai_es, 1), "%", f"IA · UE-27 {fnum(_ai_ue, 1)}%"),
        ])

        with st.expander(t("download_data")):
            st.dataframe(df_dig, use_container_width=True)
            st.download_button("CSV", df_dig.to_csv(index=False).encode("utf-8"),
                               "digitalitzacio_comerc.csv", "text/csv", key="dl_dig")

page_meta("CNMC + Eurostat (enquesta TIC)" if _ca
          else "CNMC + Eurostat (encuesta TIC)", st.session_state.lang)
