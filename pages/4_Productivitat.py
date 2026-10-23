"""Pàgina 4: Productivitat, distribució del VAB i marges (CNAE 47) — disseny premium consultora"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, cagr, highlight_expander,
    kicker, action_title, deck, key_takeaways, exhibit_header,
    metrics_band, premium_plotly_layout, freshness_badge,
    NAVY, OCRE, OCRE_DEEP, RED, G1_P, G2_P,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_CHART_CONFIG = {"displayModeBar": False, "responsive": True}


df = load_dataset("productivitat")
df_mb = load_dataset("marges_branca_ine")

_ca = st.session_state.lang == "ca"

# Noms complets (sense abreviatures)
_lbl_va = "Valor Afegit/hora" if _ca else "Valor Añadido/hora"
_lbl_xn = "Xifra de Negoci/hora" if _ca else "Cifra de Negocio/hora"
_lbl_va_short = "VA/hora"
_lbl_xn_short = "Xifra Negoci/hora" if _ca else "Cifra Negocio/hora"

kicker("Anàlisi estructural · Productivitat i marges" if _ca
       else "Análisis estructural · Productividad y márgenes")

if df.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

df = df.sort_values("any").reset_index(drop=True)

# ─── Càlculs per a header i takeaways ─────────────────────────
_df_h = df.dropna(subset=["productivitat_va_hora",
                          "valor_afegit_constants", "xifra_negoci_constants",
                          "gastos_personal_constants"]).copy()
_h_first = _df_h.iloc[0]
_h_last = _df_h.iloc[-1]
_h_fy = int(_h_first["any"])
_h_ly = int(_h_last["any"])
_h_n = _h_ly - _h_fy

_prod_var = (_h_last["productivitat_va_hora"] / _h_first["productivitat_va_hora"] - 1) * 100
_prod_cagr = cagr(_h_first["productivitat_va_hora"], _h_last["productivitat_va_hora"], _h_n)
_prod_last = _h_last["productivitat_va_hora"]

_df_h["marge_brut_pct"] = _df_h["marge_brut"] * 100 if "marge_brut" in _df_h.columns else None
_df_h["marge_op_h"] = (_df_h["valor_afegit_constants"] - _df_h["gastos_personal_constants"]) \
    / _df_h["xifra_negoci_constants"] * 100
_mb_last = float(_df_h["marge_brut_pct"].iloc[-1]) if "marge_brut" in df.columns else None
_op_min = float(_df_h["marge_op_h"].min())
_op_max = float(_df_h["marge_op_h"].max())

if _ca:
    _takeaways = [
        f"La productivitat (valor afegit per hora treballada) ha crescut un "
        f"<b>{fpct(_prod_var, 1, sign=False)}</b> entre {_h_fy} i {_h_ly} "
        f"(CAGR {fpct(_prod_cagr, 1)}): un ritme modest que manté el sector "
        f"<b>per sota de la productivitat mitjana</b> de l'economia espanyola.",
        f"El marge brut comercial és <b>estructuralment estable</b> al voltant del "
        f"<b>{fnum(_mb_last, 1)}%</b>: la mercaderia comprada per revendre és el cost "
        f"que marca el sostre del sector i amb prou feines es mou.",
        f"El marge operatiu (≈ EBITDA) oscil·la entre el <b>{fnum(_op_min, 1)}%</b> "
        f"i el <b>{fnum(_op_max, 1)}%</b> de les vendes: amb marges fins, l'única "
        f"palanca real de rendibilitat és la <b>rotació</b> i l'eficiència operativa.",
    ]
    _tk_label = "Conclusions clau"
else:
    _takeaways = [
        f"La productividad (valor añadido por hora trabajada) ha crecido un "
        f"<b>{fpct(_prod_var, 1, sign=False)}</b> entre {_h_fy} y {_h_ly} "
        f"(CAGR {fpct(_prod_cagr, 1)}): un ritmo modesto que mantiene al sector "
        f"<b>por debajo de la productividad media</b> de la economía española.",
        f"El margen bruto comercial es <b>estructuralmente estable</b> en torno al "
        f"<b>{fnum(_mb_last, 1)}%</b>: la mercancía comprada para revender es el coste "
        f"que marca el techo del sector y apenas se mueve.",
        f"El margen operativo (≈ EBITDA) oscila entre el <b>{fnum(_op_min, 1)}%</b> "
        f"y el <b>{fnum(_op_max, 1)}%</b> de las ventas: con márgenes finos, la única "
        f"palanca real de rentabilidad es la <b>rotación</b> y la eficiencia operativa.",
    ]
    _tk_label = "Conclusiones clave"

if _ca:
    action_title(
        f"La productivitat creix un {fnum(_prod_var, 0)}% en {_h_n} anys, "
        f"amb marges fins i la rotació com a palanca"
    )
    deck(
        "El comerç al detall genera poc valor afegit per hora i opera amb marges "
        "estructuralment ajustats. La rendibilitat depèn de vendre molt, no de marges amples."
    )
else:
    action_title(
        f"La productividad crece un {fnum(_prod_var, 0)}% en {_h_n} años, "
        f"con márgenes finos y la rotación como palanca"
    )
    deck(
        "El comercio minorista genera poco valor añadido por hora y opera con márgenes "
        "estructuralmente ajustados. La rentabilidad depende de vender mucho, no de márgenes amplios."
    )

key_takeaways(_takeaways, label=_tk_label)
freshness_badge("productivitat", st.session_state.lang)

# ─── TABS ────────────────────────────────────────────────────

_tabs_lbl = [
    ("Productivitat" if _ca else "Productividad"),
    ("Distribució del Valor Afegit" if _ca else "Distribución del Valor Añadido"),
    ("Marges i rendibilitat" if _ca else "Márgenes y rentabilidad"),
]
tab1, tab2, tab3 = st.tabs(_tabs_lbl, default=tab_destinacio("pages/4_Productivitat.py", _tabs_lbl))

# ============================================================
# TAB 1: PRODUCTIVITAT
# ============================================================
with tab1:
    if _ca:
        st.markdown(
            f"<div class='intro-box' style='margin-top:8px'>"
            f"La <strong>productivitat</strong> mesura l'eficiència del sector dividint el resultat econòmic "
            f"entre les hores treballades. Es presenten dues mètriques complementàries:<br>"
            f"• <strong>{_lbl_va}</strong>: quant valor net genera cada hora de treball, "
            f"descomptant els costos intermedis (compres, subministraments). És la mesura d'eficiència pura.<br>"
            f"• <strong>{_lbl_xn}</strong>: quant factura cada hora de treball. "
            f"Inclou tant el valor afegit com els costos intermedis.<br>"
            f"Si el {_lbl_va_short} creix més que el {_lbl_xn_short}, els <strong>marges milloren</strong> (el sector reté "
            f"més valor de cada euro facturat). Si passa al revés, hi ha <strong>compressió de marges</strong>."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='intro-box' style='margin-top:8px'>"
            f"La <strong>productividad</strong> mide la eficiencia del sector dividiendo el resultado económico "
            f"entre las horas trabajadas. Se presentan dos métricas complementarias:<br>"
            f"• <strong>{_lbl_va}</strong>: cuánto valor neto genera cada hora de trabajo, "
            f"descontando los costes intermedios (compras, suministros). Es la medida de eficiencia pura.<br>"
            f"• <strong>{_lbl_xn}</strong>: cuánto factura cada hora de trabajo. "
            f"Incluye tanto el valor añadido como los costes intermedios.<br>"
            f"Si el {_lbl_va_short} crece más que el {_lbl_xn_short}, los <strong>márgenes mejoran</strong> (el sector retiene "
            f"más valor de cada euro facturado). Si ocurre al revés, hay <strong>compresión de márgenes</strong>."
            f"</div>",
            unsafe_allow_html=True,
        )

    # ─── KPIs superiors ──────────────────────────────────────────
    if "productivitat_va_hora" in df.columns:
        first = df.dropna(subset=["productivitat_va_hora"]).iloc[0]
        last = df.dropna(subset=["productivitat_va_hora"]).iloc[-1]
        var = ((last["productivitat_va_hora"] / first["productivitat_va_hora"]) - 1) * 100
        cagr_prod = cagr(first["productivitat_va_hora"], last["productivitat_va_hora"],
                         int(last["any"]) - int(first["any"]))

        any_first = int(first["any"])
        any_last = int(last["any"])
        n_anys = any_last - any_first

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(f"{_lbl_va_short} ({any_last})",
                    f"{fnum(last['productivitat_va_hora'], 1)} {t('prod_eur_h')}")
        col2.metric(f"{_lbl_va_short} ({any_first})",
                    f"{fnum(first['productivitat_va_hora'], 1)} {t('prod_eur_h')}")
        col3.metric(f"{'Variació' if _ca else 'Variación'} {any_first}–{any_last}",
                    fpct(var))
        with col4:
            st.metric(f"CAGR {any_first}–{any_last}", fpct(cagr_prod, 1))
            with st.popover("Què és el CAGR?" if _ca else "¿Qué es el CAGR?"):
                if _ca:
                    st.markdown(
                        f"**CAGR** (*Compound Annual Growth Rate*) és la taxa de creixement anual compost.\n\n"
                        f"Indica quant ha crescut la productivitat **cada any de mitjana** si el creixement "
                        f"hagués estat constant entre {any_first} i {any_last} ({n_anys} anys).\n\n"
                        f"Un CAGR del **{fpct(cagr_prod, 1)}** vol dir que, de mitjana, la productivitat "
                        f"ha augmentat un {fpct(cagr_prod, 1)} cada any durant aquest període."
                    )
                else:
                    st.markdown(
                        f"**CAGR** (*Compound Annual Growth Rate*) es la tasa de crecimiento anual compuesto.\n\n"
                        f"Indica cuánto ha crecido la productividad **cada año de media** si el crecimiento "
                        f"hubiese sido constante entre {any_first} y {any_last} ({n_anys} años).\n\n"
                        f"Un CAGR del **{fpct(cagr_prod, 1)}** significa que, de media, la productividad "
                        f"ha aumentado un {fpct(cagr_prod, 1)} cada año durante este período."
                    )

    # ─── Gràfic: Índex base 100 ──────────────────────────────────
    if _ca:
        exhibit_header(
            1, "La facturació per hora puja més que el valor afegit per hora",
            note=("Quatre magnituds en índex base 100. Quan la xifra de negoci per hora "
                  "creix més que el valor afegit per hora, els marges es comprimeixen."),
        )
    else:
        exhibit_header(
            1, "La facturación por hora sube más que el valor añadido por hora",
            note=("Cuatro magnitudes en índice base 100. Cuando la cifra de negocio por hora "
                  "crece más que el valor añadido por hora, los márgenes se comprimen."),
        )

    df_idx = df.copy()
    cols_idx = []
    labels_idx = {}
    colors_idx = {}

    if "productivitat_va_hora" in df_idx.columns:
        base = df_idx["productivitat_va_hora"].dropna().iloc[0]
        df_idx["idx_va_hora"] = (df_idx["productivitat_va_hora"] / base) * 100
        cols_idx.append("idx_va_hora")
        labels_idx["idx_va_hora"] = _lbl_va_short
        colors_idx["idx_va_hora"] = NAVY

    if "productivitat_xn_hora" in df_idx.columns:
        base = df_idx["productivitat_xn_hora"].dropna().iloc[0]
        df_idx["idx_xn_hora"] = (df_idx["productivitat_xn_hora"] / base) * 100
        cols_idx.append("idx_xn_hora")
        labels_idx["idx_xn_hora"] = _lbl_xn_short
        colors_idx["idx_xn_hora"] = OCRE

    if "personal_ocupat" in df_idx.columns:
        base = df_idx["personal_ocupat"].dropna().iloc[0]
        df_idx["idx_personal"] = (df_idx["personal_ocupat"] / base) * 100
        cols_idx.append("idx_personal")
        labels_idx["idx_personal"] = "Personal ocupat" if _ca else "Personal ocupado"
        colors_idx["idx_personal"] = G1_P

    if "hores_treballades" in df_idx.columns:
        base = df_idx["hores_treballades"].dropna().iloc[0]
        df_idx["idx_hores"] = (df_idx["hores_treballades"] / base) * 100
        cols_idx.append("idx_hores")
        labels_idx["idx_hores"] = "Hores treballades" if _ca else "Horas trabajadas"
        colors_idx["idx_hores"] = G2_P

    fig_idx = go.Figure()
    for col in cols_idx:
        fig_idx.add_trace(go.Scatter(
            x=df_idx["any"], y=df_idx[col],
            mode="lines+markers",
            name=labels_idx[col],
            line=dict(color=colors_idx[col], width=2.5),
            marker=dict(size=5),
        ))

    fig_idx.add_hline(y=100, line_dash="dash", line_color="rgba(0,0,0,0.15)")
    _layout_idx = premium_plotly_layout(height=450, margin_right=30,
        ytitle=f"{'Índex' if _ca else 'Índice'} (base 100 = {int(df_idx['any'].min())})")
    _layout_idx["showlegend"] = True
    _layout_idx["yaxis"]["rangemode"] = "normal"
    _layout_idx["yaxis"]["tickformat"] = ".0f"
    _layout_idx["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
        bgcolor="rgba(0,0,0,0)",
    )
    fig_idx.update_layout(**_layout_idx)
    st.plotly_chart(fig_idx, use_container_width=True, config=_CHART_CONFIG)
    source("INE, Estadística Estructural d'Empreses Sector Comerç. Càlcul propi" if _ca
           else "INE, Estadística Estructural de Empresas Sector Comercio. Cálculo propio")

    # ─── Insight productivitat ────────────────────────────────────
    if "productivitat_va_hora" in df.columns and len(df) >= 4:
        df_i = df.dropna(subset=["personal_ocupat", "hores_treballades", "valor_afegit_constants", "xifra_negoci_constants"])
        if len(df_i) >= 4:
            df_i = df_i.copy()
            df_i["marge"] = df_i["valor_afegit_constants"] / df_i["xifra_negoci_constants"] * 100

            base_yr = df_i.iloc[0]
            last_yr = df_i.iloc[-1]
            any_first = int(df_i["any"].iloc[0])
            any_last = int(df_i["any"].iloc[-1])
            n_anys = any_last - any_first
            prod_last = last_yr["valor_afegit_constants"] / last_yr["hores_treballades"]
            prod_first = base_yr["valor_afegit_constants"] / base_yr["hores_treballades"]
            var_prod = ((prod_last / prod_first) - 1) * 100

            if _ca:
                txt = (
                    f"<strong>Marges volàtils.</strong> "
                    f"El 2021 va ser excepcional: els ERTOs van reduir costos laborals mentre el consum "
                    f"post-confinament disparava el valor afegit, generant marges artificials "
                    f"({fnum(df_i[df_i['any']==2021]['marge'].iloc[0], 1)}% de valor afegit sobre xifra de negoci). "
                    f"El 2022, la inflació va comprimir marges fins al {fnum(df_i[df_i['any']==2022]['marge'].iloc[0], 1)}%. "
                    f"El 2023 es va estancar, i el 2024 els recupera ({fnum(df_i[df_i['any']==2024]['marge'].iloc[0], 1)}%). "
                    f"Aquesta <strong>volatilitat dels marges</strong> explica la cautela del sector a l'hora de contractar "
                    f"durant 2022-23: sense certesa de marges estables, les empreses van preferir augmentar hores "
                    f"abans que assumir nous costos fixos de personal."
                    f"<br><br>"
                    f"<strong>Un sector productiu?</strong> "
                    f"Amb {fnum(prod_last, 1)} EUR de valor afegit per hora treballada, "
                    f"el comerç al detall se situa <strong>per sota de la productivitat mitjana</strong> "
                    f"del conjunt de l'economia espanyola. "
                    f"Malgrat la creixent <strong>tecnificació</strong> del sector — impulsada pel comerç electrònic, "
                    f"la digitalització de la cadena de subministrament i l'automatització de processos —, "
                    f"el marge sobre facturació segueix sent estructuralment ajustat: "
                    f"el {int(last_yr['any'])}, el valor afegit va representar el {fnum(last_yr['marge'], 1)}% "
                    f"de la xifra de negoci. "
                    f"La productivitat ha crescut un {fpct(var_prod)} en {n_anys} anys, "
                    f"un ritme modest però positiu. El repte del sector és "
                    f"<strong>retenir més valor</strong> de cada euro venut, millorant marges "
                    f"a través de la diferenciació, el servei i la reducció de costos intermedis."
                )
            else:
                txt = (
                    f"<strong>Márgenes volátiles.</strong> "
                    f"2021 fue excepcional: los ERTEs redujeron costes laborales mientras el consumo "
                    f"post-confinamiento disparaba el valor añadido, generando márgenes artificiales "
                    f"({fnum(df_i[df_i['any']==2021]['marge'].iloc[0], 1)}% de valor añadido sobre cifra de negocio). "
                    f"En 2022, la inflación comprimió márgenes hasta el {fnum(df_i[df_i['any']==2022]['marge'].iloc[0], 1)}%. "
                    f"2023 se estancó, y 2024 los recupera ({fnum(df_i[df_i['any']==2024]['marge'].iloc[0], 1)}%). "
                    f"Esta <strong>volatilidad de márgenes</strong> explica la cautela del sector al contratar "
                    f"durante 2022-23: sin certeza de márgenes estables, las empresas prefirieron aumentar horas "
                    f"antes que asumir nuevos costes fijos de personal."
                    f"<br><br>"
                    f"<strong>¿Un sector productivo?</strong> "
                    f"Con {fnum(prod_last, 1)} EUR de valor añadido por hora trabajada, "
                    f"el comercio minorista se sitúa <strong>por debajo de la productividad media</strong> "
                    f"del conjunto de la economía española. "
                    f"Pese a la creciente <strong>tecnificación</strong> del sector — impulsada por el comercio electrónico, "
                    f"la digitalización de la cadena de suministro y la automatización de procesos —, "
                    f"el margen sobre facturación sigue siendo estructuralmente ajustado: "
                    f"en {int(last_yr['any'])}, el valor añadido representó el {fnum(last_yr['marge'], 1)}% "
                    f"de la cifra de negocio. "
                    f"La productividad ha crecido un {fpct(var_prod)} en {n_anys} años, "
                    f"un ritmo modesto pero positivo. El reto del sector es "
                    f"<strong>retener más valor</strong> de cada euro vendido, mejorando márgenes "
                    f"a través de la diferenciación, el servicio y la reducción de costes intermedios."
                )
            insight(txt)

    # ─── Banda de mètriques (resum productivitat) ─────────────
    _m_va = ("+" if _prod_cagr >= 0 else "") + fnum(_prod_cagr, 1)
    if _ca:
        metrics_band([
            (fnum(_prod_last, 1), "EUR/h", f"Valor afegit per hora ({_h_ly})"),
            (("+" if _prod_var >= 0 else "") + fnum(_prod_var, 1), "%",
             f"Variació {_h_fy}–{_h_ly}"),
            (_m_va, "%", f"Creixement anual (CAGR) · {_h_n} anys"),
        ])
    else:
        metrics_band([
            (fnum(_prod_last, 1), "EUR/h", f"Valor añadido por hora ({_h_ly})"),
            (("+" if _prod_var >= 0 else "") + fnum(_prod_var, 1), "%",
             f"Variación {_h_fy}–{_h_ly}"),
            (_m_va, "%", f"Crecimiento anual (CAGR) · {_h_n} años"),
        ])

# ============================================================
# TAB 2: DISTRIBUCIÓ DEL VAB
# ============================================================
with tab2:
    if "quota_salarial" in df.columns and "excedent_brut" in df.columns:
        if _ca:
            st.markdown(
                "<div class='intro-box' style='margin-top:8px'>"
                "El Valor Afegit que genera el sector es reparteix entre dos grans components: "
                "la <strong>remuneració dels treballadors</strong> (gastos de personal) i "
                "l'<strong>excedent brut d'explotació</strong> (beneficis empresarials, amortitzacions i impostos). "
                "La <strong>quota salarial</strong> (% del VA destinat a salaris) és un indicador clau de com "
                "es distribueix la riquesa generada.<br>"
                "El <strong>cost laboral per ocupat</strong> mostra l'evolució de la remuneració mitjana, "
                "a preus constants per eliminar l'efecte de la inflació."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='intro-box' style='margin-top:8px'>"
                "El Valor Añadido que genera el sector se reparte entre dos grandes componentes: "
                "la <strong>remuneración de los trabajadores</strong> (gastos de personal) y "
                "el <strong>excedente bruto de explotación</strong> (beneficios empresariales, amortizaciones e impuestos). "
                "La <strong>cuota salarial</strong> (% del VA destinado a salarios) es un indicador clave de cómo "
                "se distribuye la riqueza generada.<br>"
                "El <strong>coste laboral por ocupado</strong> muestra la evolución de la remuneración media, "
                "a precios constantes para eliminar el efecto de la inflación."
                "</div>",
                unsafe_allow_html=True,
            )

        df_dist = df.dropna(subset=["gastos_personal_constants", "excedent_brut"])

        if not df_dist.empty:
            if _ca:
                exhibit_header(
                    1, "El Valor Afegit es reparteix entre salaris i excedent brut",
                    note="La major part del VAB es destina a remuneració dels treballadors; "
                         "la resta és excedent brut (beneficis, amortitzacions i impostos).",
                )
            else:
                exhibit_header(
                    1, "El Valor Añadido se reparte entre salarios y excedente bruto",
                    note="La mayor parte del VAB se destina a remuneración de los trabajadores; "
                         "el resto es excedente bruto (beneficios, amortizaciones e impuestos).",
                )
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Scatter(
                x=df_dist["any"], y=df_dist["gastos_personal_constants"] / 1e9,
                mode="lines",
                name=("Remuneració treballadors" if _ca else "Remuneración trabajadores"),
                line=dict(width=0), fillcolor="rgba(11,58,102,0.55)",
                stackgroup="one",
            ))
            fig_dist.add_trace(go.Scatter(
                x=df_dist["any"], y=df_dist["excedent_brut"] / 1e9,
                mode="lines",
                name=("Excedent brut" if _ca else "Excedente bruto"),
                line=dict(width=0), fillcolor="rgba(176,125,43,0.55)",
                stackgroup="one",
            ))
            _layout_dist = premium_plotly_layout(height=400, margin_right=30,
                ytitle=("Milers M EUR" if _ca else "Miles M EUR"))
            _layout_dist["showlegend"] = True
            _layout_dist["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            fig_dist.update_layout(**_layout_dist)
            st.plotly_chart(fig_dist, use_container_width=True, config=_CHART_CONFIG)
            source("INE, Estadística Estructural d'Empreses. Preus constants. Càlcul propi" if _ca
                   else "INE, Estadística Estructural de Empresas. Precios constantes. Cálculo propio")

        _lbl_lab_exp = ("Veure quota salarial i cost laboral per ocupat"
                       if _ca else
                       "Ver cuota salarial y coste laboral por ocupado")
        with highlight_expander(_lbl_lab_exp, expanded=False):
            df_qs = df.dropna(subset=["quota_salarial"])
            if not df_qs.empty:
                st.subheader("Quota salarial" if _ca else "Cuota salarial")
                fig_qs = go.Figure()
                fig_qs.add_trace(go.Scatter(
                    x=df_qs["any"], y=df_qs["quota_salarial"] * 100,
                    mode="lines+markers",
                    name=("Quota salarial" if _ca else "Cuota salarial"),
                    line=dict(color=NAVY, width=3),
                    marker=dict(size=8),
                    text=[f"{v:.1f}%".replace(".", ",") for v in df_qs["quota_salarial"] * 100],
                    textposition="top center",
                    textfont=dict(size=10, color=G1_P),
                ))
                _layout_qs = premium_plotly_layout(height=380, margin_right=30,
                    ytitle=("% del Valor Afegit" if _ca else "% del Valor Añadido"))
                _layout_qs["yaxis"]["rangemode"] = "normal"
                _layout_qs["yaxis"]["tickformat"] = ".0f"
                fig_qs.update_layout(**_layout_qs)
                st.plotly_chart(fig_qs, use_container_width=True, config=_CHART_CONFIG)
                source("INE, Estadística Estructural d'Empreses. Càlcul propi" if _ca
                       else "INE, Estadística Estructural de Empresas. Cálculo propio")

            if "cost_laboral_per_ocupat" in df.columns:
                df_cl = df.dropna(subset=["cost_laboral_per_ocupat"])
                if not df_cl.empty:
                    st.subheader("Cost laboral per ocupat (preus constants)" if _ca
                                 else "Coste laboral por ocupado (precios constantes)")

                    fig_cl = go.Figure()
                    fig_cl.add_trace(go.Bar(
                        x=df_cl["any"], y=df_cl["cost_laboral_per_ocupat"],
                        marker_color=NAVY,
                        text=[f"{fnum(v, 0)} EUR" for v in df_cl["cost_laboral_per_ocupat"]],
                        textposition="outside",
                        textfont=dict(size=11, color=G1_P),
                    ))
                    _layout_cl = premium_plotly_layout(height=380, margin_right=30,
                        ytitle=("EUR / ocupat" if _ca else "EUR / ocupado"))
                    fig_cl.update_layout(**_layout_cl)
                    st.plotly_chart(fig_cl, use_container_width=True, config=_CHART_CONFIG)
                    source("INE, Estadística Estructural d'Empreses. Preus constants. Càlcul propi" if _ca
                           else "INE, Estadística Estructural de Empresas. Precios constantes. Cálculo propio")

        if not df_qs.empty:
            qs_first = df_qs.iloc[0]
            qs_last = df_qs.iloc[-1]
            var_qs = (qs_last["quota_salarial"] - qs_first["quota_salarial"]) * 100

            if _ca:
                txt_dist = (
                    f"La quota salarial del comerç al detall ha passat del "
                    f"<strong>{fpct(qs_first['quota_salarial'] * 100, 1, sign=False)}</strong> "
                    f"({int(qs_first['any'])}) al "
                    f"<strong>{fpct(qs_last['quota_salarial'] * 100, 1, sign=False)}</strong> "
                    f"({int(qs_last['any'])}). "
                )
                if var_qs < -2:
                    txt_dist += (
                        f"La caiguda de <strong>{fpct(abs(var_qs), 1, sign=False)}</strong> indica que "
                        f"l'excedent brut (beneficis + amortitzacions) ha crescut més que la remuneració: "
                        f"el sector <strong>reté més valor per als propietaris</strong> en detriment dels salaris relatius. "
                        f"Això és coherent amb la concentració empresarial: les grans cadenes generen més excedent "
                        f"per les economies d'escala i el seu poder de negociació amb proveïdors."
                    )
                elif var_qs > 2:
                    txt_dist += (
                        f"L'augment de <strong>{fpct(abs(var_qs), 1, sign=False)}</strong> indica que "
                        f"els salaris han absorbit una proporció creixent del valor generat: "
                        f"els <strong>treballadors capten més valor</strong>, cosa que pot reflectir millores salarials "
                        f"o reducció de marges empresarials."
                    )
                else:
                    txt_dist += (
                        "La distribució entre salaris i excedent brut s'ha mantingut <strong>relativament estable</strong>, "
                        "cosa que suggereix un equilibri entre la pressió salarial i la capacitat del sector "
                        "de mantenir els seus marges."
                    )
            else:
                txt_dist = (
                    f"La cuota salarial del comercio minorista ha pasado del "
                    f"<strong>{fpct(qs_first['quota_salarial'] * 100, 1, sign=False)}</strong> "
                    f"({int(qs_first['any'])}) al "
                    f"<strong>{fpct(qs_last['quota_salarial'] * 100, 1, sign=False)}</strong> "
                    f"({int(qs_last['any'])}). "
                )
                if var_qs < -2:
                    txt_dist += (
                        f"La caída de <strong>{fpct(abs(var_qs), 1, sign=False)}</strong> indica que "
                        f"el excedente bruto (beneficios + amortizaciones) ha crecido más que la remuneración: "
                        f"el sector <strong>retiene más valor para los propietarios</strong> en detrimento de los salarios relativos. "
                        f"Esto es coherente con la concentración empresarial: las grandes cadenas generan más excedente "
                        f"por las economías de escala y su poder de negociación con proveedores."
                    )
                elif var_qs > 2:
                    txt_dist += (
                        f"El aumento de <strong>{fpct(abs(var_qs), 1, sign=False)}</strong> indica que "
                        f"los salarios han absorbido una proporción creciente del valor generado: "
                        f"los <strong>trabajadores captan más valor</strong>, lo que puede reflejar mejoras salariales "
                        f"o reducción de márgenes empresariales."
                    )
                else:
                    txt_dist += (
                        "La distribución entre salarios y excedente bruto se ha mantenido <strong>relativamente estable</strong>, "
                        "lo que sugiere un equilibrio entre la presión salarial y la capacidad del sector "
                        "de mantener sus márgenes."
                    )
            insight(txt_dist)

# ============================================================
# TAB 3: MARGES I RENDIBILITAT (NOU)
# ============================================================
with tab3:
    cols_req = ["xifra_negoci_constants", "valor_afegit_constants",
                "gastos_personal_constants", "excedent_brut"]
    df_m = df.dropna(subset=[c for c in cols_req if c in df.columns]).copy()

    if df_m.empty or any(c not in df_m.columns for c in cols_req):
        st.info("No hi ha dades suficients per calcular marges." if _ca else "Sin datos suficientes para calcular márgenes.")
    else:
        # Marge brut comptable: (Vendes - COGS) / Vendes — el "gross margin" del retail
        if "marge_brut" in df_m.columns:
            df_m["marge_brut_pct"] = df_m["marge_brut"] * 100
        # Marge sobre VAB: % de la xifra de negoci que es manté com a valor afegit (despres TOTS els costos intermedis)
        df_m["marge_vab"] = df_m["valor_afegit_constants"] / df_m["xifra_negoci_constants"] * 100
        # Cost laboral unitari: % de la xifra de negoci que va a salaris
        df_m["clu"] = df_m["gastos_personal_constants"] / df_m["xifra_negoci_constants"] * 100
        # Marge operatiu (proxy EBITDA): % de la xifra de negoci que queda despres TOTS els costos intermedis i personal
        df_m["marge_op"] = (df_m["valor_afegit_constants"] - df_m["gastos_personal_constants"]) / df_m["xifra_negoci_constants"] * 100

        has_brut = "marge_brut_pct" in df_m.columns and df_m["marge_brut_pct"].notna().any()

        if _ca:
            st.markdown(
                "<div class='intro-box' style='margin-top:8px'>"
                "Aquesta secció descompon la <strong>cadena de valor</strong> de cada euro facturat al "
                "comerç al detall en quatre marges, ordenats de més brut a més net:<br>"
                "• <strong>Marge brut sobre vendes</strong> = (Vendes − Cost de mercaderia venuda) / Vendes. "
                "El marge típic del comerç al detall (~25-35%): el que queda després de pagar la "
                "<em>mercaderia comprada per revendre</em>. <em>Font: INE, Compte de resultats de "
                "l'Enquesta Estructural d'Empreses Sector Comerç (taula 36199).</em><br>"
                "• <strong>Valor Afegit sobre vendes</strong> = Valor Afegit / Vendes. El que queda "
                "després de pagar <em>tots els intermedis</em> (mercaderia + lloguers + subministraments "
                "+ serveis externs). Sempre inferior al marge brut.<br>"
                "• <strong>Cost laboral unitari</strong> = Despeses de personal / Vendes. Quina part del preu "
                "es destina a <em>salaris i cotitzacions</em>.<br>"
                "• <strong>Marge operatiu</strong> (≈ EBITDA) = Excedent Brut / Vendes. El que queda després "
                "d'intermedis i personal — disponible per <em>amortitzacions, impostos, interessos i "
                "benefici net</em>."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='intro-box' style='margin-top:8px'>"
                "Esta sección descompone la <strong>cadena de valor</strong> de cada euro facturado en el "
                "comercio minorista en cuatro márgenes, ordenados de más bruto a más neto:<br>"
                "• <strong>Margen bruto sobre ventas</strong> = (Ventas − Coste de mercancía vendida) / Ventas. "
                "El margen típico del comercio minorista (~25-35%): lo que queda tras pagar la "
                "<em>mercancía comprada para revender</em>. <em>Fuente: INE, Cuenta de resultados de la "
                "Encuesta Estructural de Empresas Sector Comercio (tabla 36199).</em><br>"
                "• <strong>Valor Añadido sobre ventas</strong> = Valor Añadido / Ventas. Lo que queda "
                "tras pagar <em>todos los intermedios</em> (mercancía + alquileres + suministros + "
                "servicios externos). Siempre inferior al margen bruto.<br>"
                "• <strong>Coste laboral unitario</strong> = Gastos de personal / Ventas. Qué parte del precio "
                "se destina a <em>salarios y cotizaciones</em>.<br>"
                "• <strong>Margen operativo</strong> (≈ EBITDA) = Excedente Bruto / Ventas. Lo que queda tras "
                "intermedios y personal — disponible para <em>amortizaciones, impuestos, intereses y "
                "beneficio neto</em>."
                "</div>",
                unsafe_allow_html=True,
            )

        # ─── KPIs ──────────────────────────────────────────────
        first_m = df_m.iloc[0]
        last_m = df_m.iloc[-1]
        any_first = int(first_m["any"])
        any_last = int(last_m["any"])

        delta_marge_vab = last_m["marge_vab"] - first_m["marge_vab"]
        delta_clu = last_m["clu"] - first_m["clu"]
        delta_marge_op = last_m["marge_op"] - first_m["marge_op"]

        # ─── HERO: Marge brut comercial (la xifra clau del retail) ────
        if has_brut:
            mb_first = first_m["marge_brut_pct"]
            mb_last = last_m["marge_brut_pct"]
            delta_marge_brut = mb_last - mb_first
            delta_color_brut = OCRE_DEEP if delta_marge_brut >= 0 else RED
            delta_arrow = "▲" if delta_marge_brut >= 0 else "▼"

            mb_value_str = f"{mb_last:.1f}".replace(".", ",")
            delta_str = f"{abs(delta_marge_brut):.1f}".replace(".", ",")

            with st.container(border=True):
                col_num, col_txt = st.columns([1, 2])
                with col_num:
                    st.markdown(
                        f"<div style='font-family:Manrope,system-ui,sans-serif;font-size:11px;"
                        f"font-weight:700;letter-spacing:.08em;text-transform:uppercase;"
                        f"color:{OCRE};margin-bottom:4px;'>"
                        f"{'Any' if _ca else 'Año'} {any_last}</div>"
                        f"<div style='font-size:3.4rem;line-height:1;color:{NAVY};"
                        f"font-weight:800;font-family:Manrope,system-ui,sans-serif;"
                        f"letter-spacing:-.02em;'>{mb_value_str}%</div>"
                        f"<div style='font-size:14px;color:{delta_color_brut};font-weight:700;"
                        f"margin-top:8px;font-family:Manrope,system-ui,sans-serif;'>"
                        f"{delta_arrow} {delta_str}% vs {any_first}</div>",
                        unsafe_allow_html=True,
                    )
                with col_txt:
                    st.markdown(
                        f"### {'Marge brut comercial' if _ca else 'Margen bruto comercial'}"
                    )
                    if _ca:
                        st.markdown(
                            f"De cada 100 € venuts, **{mb_value_str} €** són marge brut "
                            f"(després de pagar la mercaderia comprada per revendre). "
                            f"Els altres **{100 - mb_last:.1f} €** són cost de la mercaderia.".replace(".", ",")
                        )
                        st.caption("Càlcul: (Vendes − Cost de mercaderia venuda) / Vendes")
                    else:
                        st.markdown(
                            f"De cada 100 € vendidos, **{mb_value_str} €** son margen bruto "
                            f"(tras pagar la mercancía comprada para revender). "
                            f"Los otros **{100 - mb_last:.1f} €** son coste de la mercancía.".replace(".", ",")
                        )
                        st.caption("Cálculo: (Ventas − Coste de mercancía vendida) / Ventas")

            st.caption(
                "Indicadors complementaris (anàlisi més detallada):" if _ca
                else "Indicadores complementarios (análisis más detallado):"
            )

        # KPIs secundaris (3 mètriques d'anàlisi)
        col1, col2, col3 = st.columns(3)
        col1.metric(
            ("Cost laboral unitari" if _ca else "Coste laboral unitario") + f" ({any_last})",
            fpct(last_m["clu"], 1, sign=False),
            delta=fpct(delta_clu, 1) + (f" vs {any_first}"),
            delta_color="inverse",
            help=("Despeses de personal / Vendes" if _ca else "Gastos de personal / Ventas"),
        )
        col2.metric(
            ("Marge operatiu (≈ EBITDA)" if _ca else "Margen operativo (≈ EBITDA)") + f" ({any_last})",
            fpct(last_m["marge_op"], 1, sign=False),
            delta=fpct(delta_marge_op, 1) + (f" vs {any_first}"),
            help=("Excedent Brut / Vendes" if _ca else "Excedente Bruto / Ventas"),
        )
        col3.metric(
            ("Valor Afegit sobre vendes" if _ca else "Valor Añadido sobre ventas") + f" ({any_last})",
            fpct(last_m["marge_vab"], 1, sign=False),
            delta=fpct(delta_marge_vab, 1) + (f" vs {any_first}"),
            help=("Valor Afegit / Vendes — concepte de comptabilitat nacional, vendes net "
                  "de TOTS els intermedis (mercaderia + lloguers + serveis externs)" if _ca else
                  "Valor Añadido / Ventas — concepto de contabilidad nacional, ventas netas "
                  "de TODOS los intermedios (mercancía + alquileres + servicios externos)"),
        )

        # ─── Gràfic 1: Evolució dels marges sobre vendes ─────────
        if _ca:
            exhibit_header(
                1, "Del marge brut al marge operatiu: cada esglaó descompta un cost",
                note="El marge brut és estable; el marge operatiu, més estret, absorbeix els "
                     "xocs de cost en intermedis i salaris.",
            )
        else:
            exhibit_header(
                1, "Del margen bruto al margen operativo: cada escalón descuenta un coste",
                note="El margen bruto es estable; el margen operativo, más estrecho, absorbe los "
                     "shocks de coste en intermedios y salarios.",
            )

        fig_marges = go.Figure()
        if has_brut:
            fig_marges.add_trace(go.Scatter(
                x=df_m["any"], y=df_m["marge_brut_pct"],
                mode="lines+markers",
                name=("Marge brut sobre vendes" if _ca else "Margen bruto sobre ventas"),
                line=dict(color=NAVY, width=3),
                marker=dict(size=8),
                hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
            ))
        fig_marges.add_trace(go.Scatter(
            x=df_m["any"], y=df_m["marge_vab"],
            mode="lines+markers",
            name=("Valor Afegit sobre vendes" if _ca else "Valor Añadido sobre ventas"),
            line=dict(color=OCRE, width=2.8),
            marker=dict(size=7),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
        fig_marges.add_trace(go.Scatter(
            x=df_m["any"], y=df_m["clu"],
            mode="lines+markers",
            name=("Cost laboral unitari" if _ca else "Coste laboral unitario"),
            line=dict(color=G1_P, width=2.5, dash="dot"),
            marker=dict(size=6),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
        fig_marges.add_trace(go.Scatter(
            x=df_m["any"], y=df_m["marge_op"],
            mode="lines+markers",
            name=("Marge operatiu (≈ EBITDA)" if _ca else "Margen operativo (≈ EBITDA)"),
            line=dict(color=RED, width=2.8),
            marker=dict(size=7),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
        _layout_marges = premium_plotly_layout(height=420, margin_right=30,
            ytitle=("% sobre xifra de negoci" if _ca else "% sobre cifra de negocios"))
        _layout_marges["showlegend"] = True
        _layout_marges["yaxis"]["rangemode"] = "normal"
        _layout_marges["yaxis"]["tickformat"] = ".0f"
        _layout_marges["legend"] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
            bgcolor="rgba(0,0,0,0)",
        )
        fig_marges.update_layout(**_layout_marges)
        st.plotly_chart(fig_marges, use_container_width=True, config=_CHART_CONFIG)
        source("INE, Enquesta Estructural d'Empreses Sector Comerç (taules 36194 + 36199). Càlcul propi" if _ca
               else "INE, Encuesta Estructural de Empresas Sector Comercio (tablas 36194 + 36199). Cálculo propio")

        _lbl_stack_exp = ("Veure descomposició de la xifra de negoci"
                          if _ca else
                          "Ver descomposición de la cifra de negocios")
        with highlight_expander(_lbl_stack_exp, expanded=False):
            # ─── Gràfic 2: Composició de cada euro venut (waterfall implicit) ──
            if _ca:
                exhibit_header(2, "On va cada euro facturat: mercaderia, intermedis, personal i excedent")
            else:
                exhibit_header(2, "Adónde va cada euro facturado: mercancía, intermedios, personal y excedente")

            df_w = df_m.copy()
            if has_brut and "cogs" in df_w.columns:
                # Descomposicio completa: COGS + altres intermedis + personal + excedent
                df_w["pct_cogs"] = df_w["cogs"] / df_w["xifra_negoci_constants"] * 100 * (df_w["xifra_negoci_constants"] / df_w["xifra_negoci_constants"])
                # Recalcular sobre xifra a preus corrents per consistencia (el ratio es invariant)
                # Aprofitem que tenim cogs (corrents) i xifra negoci constants? millor calcular el ratio
                # CGS / Xifra a preus corrents = ratio invariant
                df_w["pct_cogs"] = (1 - df_w["marge_brut"]) * 100  # = COGS / Vendes
                # Altres intermedis = (Vendes - VA - COGS) / Vendes = marge_brut*100 - marge_vab
                df_w["pct_altres_int"] = df_w["pct_cogs"] - 0  # placeholder
                # En realitat: 100 = COGS_pct + AltresInt_pct + VA_pct
                # AltresInt_pct = 100 - COGS_pct - VA_pct = marge_brut_pct - marge_vab
                df_w["pct_altres_int"] = df_w["marge_brut_pct"] - df_w["marge_vab"]
                df_w["pct_personal"] = df_w["clu"]
                df_w["pct_excedent"] = df_w["marge_op"]

                fig_stack = go.Figure()
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["pct_cogs"],
                    name=("Cost de mercaderia (COGS)" if _ca else "Coste de mercancía (COGS)"),
                    marker_color="#9aa6b2",
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["pct_altres_int"],
                    name=("Altres intermedis (lloguer, energia, serveis)" if _ca
                          else "Otros intermedios (alquiler, energía, servicios)"),
                    marker_color="#cdd5dd",
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["pct_personal"],
                    name=("Personal" if _ca else "Personal"),
                    marker_color=NAVY,
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["pct_excedent"],
                    name=("Excedent brut (≈ EBITDA)" if _ca else "Excedente bruto (≈ EBITDA)"),
                    marker_color=OCRE,
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
            else:
                # Fallback sense COGS
                df_w["resta_intermedis"] = 100 - df_w["marge_vab"]
                df_w["resta_personal"] = df_w["clu"]
                df_w["resta_excedent"] = df_w["marge_op"]

                fig_stack = go.Figure()
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["resta_intermedis"],
                    name=("Costos intermedis" if _ca else "Costes intermedios"),
                    marker_color="#cdd5dd",
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["resta_personal"],
                    name=("Personal" if _ca else "Personal"),
                    marker_color=NAVY,
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_stack.add_trace(go.Bar(
                    x=df_w["any"], y=df_w["resta_excedent"],
                    name=("Excedent brut (≈ EBITDA)" if _ca else "Excedente bruto (≈ EBITDA)"),
                    marker_color=OCRE,
                    hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>",
                ))

            _layout_stack = premium_plotly_layout(height=420, margin_right=30,
                ytitle=("% de cada euro facturat" if _ca else "% de cada euro facturado"))
            _layout_stack["showlegend"] = True
            _layout_stack["barmode"] = "stack"
            _layout_stack["yaxis"]["rangemode"] = "normal"
            _layout_stack["yaxis"]["tickformat"] = ".0f"
            _layout_stack["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            fig_stack.update_layout(**_layout_stack)
            st.plotly_chart(fig_stack, use_container_width=True, config=_CHART_CONFIG)
            source("INE, Enquesta Estructural d'Empreses Sector Comerç (taules 36194 + 36199). Càlcul propi" if _ca
                   else "INE, Encuesta Estructural de Empresas Sector Comercio (tablas 36194 + 36199). Cálculo propio")

        # ─── Insight rendibilitat ────────────────────────────────
        marge_op_std = df_m["marge_op"].std()
        marge_op_mean = df_m["marge_op"].mean()
        cv = (marge_op_std / marge_op_mean * 100) if marge_op_mean else 0

        idx_max = df_m["marge_op"].idxmax()
        idx_min = df_m["marge_op"].idxmin()
        any_max = int(df_m.loc[idx_max, "any"])
        any_min = int(df_m.loc[idx_min, "any"])
        marge_max = df_m.loc[idx_max, "marge_op"]
        marge_min = df_m.loc[idx_min, "marge_op"]

        # Variacio del marge brut
        if has_brut:
            mb_first = first_m["marge_brut_pct"]
            mb_last = last_m["marge_brut_pct"]
            mb_delta = mb_last - mb_first

        if _ca:
            txt = ""
            if has_brut:
                txt += (
                    f"<strong>Marge brut comercial ({any_last}): {fnum(last_m['marge_brut_pct'], 1)}%.</strong> "
                    f"De cada 100 € venuts, "
                    f"<strong>{100 - last_m['marge_brut_pct']:.1f} €</strong>".replace(".", ",")
                    + f" se'n van directament a pagar la mercaderia comprada per revendre — el cost més "
                    f"important del sector. Aquest marge brut és <strong>estructuralment estable</strong> "
                    f"per al comerç al detall espanyol "
                    + (f"(va passar del {fnum(mb_first, 1)}% al {fnum(mb_last, 1)}%, una variació de "
                       f"<strong>{fpct(mb_delta, 1)}</strong> en {any_last - any_first} anys), "
                       f"reflectint el fet que els marges entre cost i preu de venda de la mercaderia "
                       f"són una variable difícil de moure: depèn del poder de negociació amb proveïdors, "
                       f"del posicionament de marca i de la categoria de producte.")
                    + f"<br><br>"
                )
            txt += (
                f"<strong>Estructura de cada euro facturat ({any_last}):</strong> "
                f"de cada 100 € que entra a caixa, el sector paga "
            )
            if has_brut:
                txt += (
                    f"<strong>{100 - last_m['marge_brut_pct']:.1f} €</strong>".replace(".", ",")
                    + f" als <strong>proveïdors de mercaderia</strong>, "
                    f"<strong>{last_m['marge_brut_pct'] - last_m['marge_vab']:.1f} €</strong>".replace(".", ",")
                    + f" a <strong>altres intermedis</strong> (lloguers, energia, serveis externs), "
                )
            else:
                txt += (
                    f"<strong>{100 - last_m['marge_vab']:.1f} €</strong>".replace(".", ",")
                    + f" als proveïdors (mercaderia + intermedis), "
                )
            txt += (
                f"<strong>{last_m['clu']:.1f} €</strong>".replace(".", ",")
                + f" als <strong>treballadors</strong>, i només queden "
                f"<strong>{last_m['marge_op']:.1f} €</strong>".replace(".", ",")
                + f" d'<strong>excedent brut</strong> per cobrir amortitzacions, impostos, "
                f"interessos i benefici net. El benefici net després d'impostos sol ser només "
                f"una fracció modesta d'aquests {last_m['marge_op']:.1f} €.".replace(".", ",")
                + f"<br><br>"
                f"<strong>Volatilitat estructural:</strong> el marge operatiu ha oscil·lat entre el "
                f"<strong>{fnum(marge_min, 1)}%</strong> ({any_min}) i el "
                f"<strong>{fnum(marge_max, 1)}%</strong> ({any_max}), amb un coeficient de variació del "
                f"<strong>{fnum(cv, 1)}%</strong>. "
                + (f"Aquesta volatilitat és <strong>elevada</strong> per a un sector madur: "
                   f"el marge operatiu fluctua molt més que el marge brut, perquè absorbeix de cop "
                   f"els xocs d'inflació en intermedis i salaris."
                   if cv > 8 else
                   f"Aquesta volatilitat és <strong>moderada</strong>, suggerint que el sector ha "
                   f"absorbit relativament bé els xocs de cost dels darrers anys.")
                + f"<br><br>"
                f"<strong>Lectura del benchmark:</strong> el comerç al detall espanyol opera amb un "
                f"marge brut comercial al voltant del <strong>28-29%</strong> i un marge operatiu "
                f"d'un sol dígit. El múltiple més rellevant per al sector no és el marge sinó la "
                f"<strong>rotació</strong>: facturar molt amb marges fins. Per això un dèficit de "
                f"productivitat (vegeu pestanya Productivitat) és tan crític: amb marges curts, "
                f"l'única palanca real és l'eficiència operativa."
            )
            insight(txt)
        else:
            txt = ""
            if has_brut:
                txt += (
                    f"<strong>Margen bruto comercial ({any_last}): {fnum(last_m['marge_brut_pct'], 1)}%.</strong> "
                    f"De cada 100 € vendidos, "
                    f"<strong>{100 - last_m['marge_brut_pct']:.1f} €</strong>".replace(".", ",")
                    + f" se van directamente a pagar la mercancía comprada para revender — el coste "
                    f"más importante del sector. Este margen bruto es <strong>estructuralmente "
                    f"estable</strong> en el comercio minorista español "
                    + (f"(pasó del {fnum(mb_first, 1)}% al {fnum(mb_last, 1)}%, una variación de "
                       f"<strong>{fpct(mb_delta, 1)}</strong> en {any_last - any_first} años), "
                       f"reflejando que los márgenes entre coste y precio de venta de la mercancía "
                       f"son una variable difícil de mover: depende del poder de negociación con "
                       f"proveedores, del posicionamiento de marca y de la categoría de producto.")
                    + f"<br><br>"
                )
            txt += (
                f"<strong>Estructura de cada euro facturado ({any_last}):</strong> "
                f"de cada 100 € que entra en caja, el sector paga "
            )
            if has_brut:
                txt += (
                    f"<strong>{100 - last_m['marge_brut_pct']:.1f} €</strong>".replace(".", ",")
                    + f" a los <strong>proveedores de mercancía</strong>, "
                    f"<strong>{last_m['marge_brut_pct'] - last_m['marge_vab']:.1f} €</strong>".replace(".", ",")
                    + f" a <strong>otros intermedios</strong> (alquileres, energía, servicios externos), "
                )
            else:
                txt += (
                    f"<strong>{100 - last_m['marge_vab']:.1f} €</strong>".replace(".", ",")
                    + f" a los proveedores (mercancía + intermedios), "
                )
            txt += (
                f"<strong>{last_m['clu']:.1f} €</strong>".replace(".", ",")
                + f" a los <strong>trabajadores</strong>, y solo quedan "
                f"<strong>{last_m['marge_op']:.1f} €</strong>".replace(".", ",")
                + f" de <strong>excedente bruto</strong> para cubrir amortizaciones, impuestos, "
                f"intereses y beneficio neto. El beneficio neto después de impuestos suele ser solo "
                f"una fracción modesta de esos {last_m['marge_op']:.1f} €.".replace(".", ",")
                + f"<br><br>"
                f"<strong>Volatilidad estructural:</strong> el margen operativo ha oscilado entre el "
                f"<strong>{fnum(marge_min, 1)}%</strong> ({any_min}) y el "
                f"<strong>{fnum(marge_max, 1)}%</strong> ({any_max}), con un coeficiente de variación del "
                f"<strong>{fnum(cv, 1)}%</strong>. "
                + (f"Esta volatilidad es <strong>elevada</strong> para un sector maduro: el margen "
                   f"operativo fluctúa mucho más que el margen bruto, porque absorbe de golpe los "
                   f"shocks de inflación en intermedios y salarios."
                   if cv > 8 else
                   f"Esta volatilidad es <strong>moderada</strong>, sugiriendo que el sector ha "
                   f"absorbido relativamente bien los shocks de coste de los últimos años.")
                + f"<br><br>"
                f"<strong>Lectura del benchmark:</strong> el comercio minorista español opera con un "
                f"margen bruto comercial alrededor del <strong>28-29%</strong> y un margen operativo "
                f"de un solo dígito. El múltiplo más relevante para el sector no es el margen sino la "
                f"<strong>rotación</strong>: facturar mucho con márgenes finos. Por eso un déficit de "
                f"productividad (ver pestaña Productividad) es tan crítico: con márgenes cortos, "
                f"la única palanca real es la eficiencia operativa."
            )
            insight(txt)

        # ─── Gràfic 3: Marge operatiu per branca (INE T=76818) ───
        if not df_mb.empty:
            _mb_lbl = {
                471: ("Súper i hiper (no especialitzats)" if _ca
                      else "Súper e híper (no especializados)"),
                472: ("Alimentació especialitzada" if _ca
                      else "Alimentación especializada"),
                473: ("Estacions de servei" if _ca else "Estaciones de servicio"),
                474: ("Equips informàtics i telecomunicacions" if _ca
                      else "Equipos informáticos y telecomunicaciones"),
                475: ("Equipament de la llar" if _ca else "Equipamiento del hogar"),
                476: ("Cultura i lleure" if _ca else "Cultura y ocio"),
                477: ("Moda, calçat, farmàcia i altres" if _ca
                      else "Moda, calzado, farmacia y otros"),
                479: ("Venda fora d'establiment (internet i altres)" if _ca
                      else "Venta fuera de establecimiento (internet y otros)"),
            }
            _mb = df_mb.dropna(subset=["marge_vendes_pct"]).copy()
            _mb["cnae"] = pd.to_numeric(_mb["cnae"], errors="coerce")
            _mb_y1 = int(_mb["any"].max())
            _mb_y0 = int(_mb["any"].min())
            _mb_p = (_mb.pivot_table(index="cnae", columns="any",
                                     values="marge_vendes_pct", aggfunc="first")
                     .dropna(subset=[_mb_y1]).sort_values(_mb_y1))
            _mb_p["label"] = [_mb_lbl.get(int(c), str(int(c))) for c in _mb_p.index]
            _c_max, _c_min = _mb_p[_mb_y1].idxmax(), _mb_p[_mb_y1].idxmin()

            _v_min = fnum(_mb_p.loc[_c_min, _mb_y1], 1)
            _v_max = fnum(_mb_p.loc[_c_max, _mb_y1], 1)
            if _ca:
                exhibit_header(
                    3, f"Segons la branca, el marge operatiu va d'un {_v_min}% a un {_v_max}% "
                       f"de les vendes",
                    note=f"Excedent brut d'explotació sobre xifra de negoci per branca del "
                         f"comerç al detall, {_mb_y0} i {_mb_y1}.",
                )
            else:
                exhibit_header(
                    3, f"Según la rama, el margen operativo va de un {_v_min}% a un {_v_max}% "
                       f"de las ventas",
                    note=f"Excedente bruto de explotación sobre cifra de negocios por rama del "
                         f"comercio minorista, {_mb_y0} y {_mb_y1}.",
                )

            fig_mb = go.Figure()
            # Línia que uneix els dos anys de cada branca
            for _c, _r in _mb_p.iterrows():
                if pd.notna(_r.get(_mb_y0)):
                    fig_mb.add_trace(go.Scatter(
                        x=[_r[_mb_y0], _r[_mb_y1]], y=[_r["label"], _r["label"]],
                        mode="lines", line=dict(color="#cdd5dd", width=3),
                        showlegend=False, hoverinfo="skip"))
            fig_mb.add_trace(go.Scatter(
                x=_mb_p[_mb_y0], y=_mb_p["label"], mode="markers", name=str(_mb_y0),
                marker=dict(color=G2_P, size=11),
                hovertemplate=f"<b>%{{y}}</b><br>{_mb_y0}: %{{x:.1f}}%<extra></extra>"))
            fig_mb.add_trace(go.Scatter(
                x=_mb_p[_mb_y1], y=_mb_p["label"], mode="markers", name=str(_mb_y1),
                marker=dict(color=NAVY, size=13),
                hovertemplate=f"<b>%{{y}}</b><br>{_mb_y1}: %{{x:.1f}}%<extra></extra>"))
            # Etiqueta del darrer any a la dreta del punt més extern, perquè no la tapi el de l'any inicial
            fig_mb.add_trace(go.Scatter(
                x=_mb_p[[_mb_y0, _mb_y1]].max(axis=1) + 0.25, y=_mb_p["label"], mode="text",
                text=[fnum(v, 1) + "%" for v in _mb_p[_mb_y1]],
                textposition="middle right", showlegend=False, hoverinfo="skip",
                textfont=dict(size=12, color=NAVY, family="Manrope, system-ui, sans-serif")))
            _layout_mb = premium_plotly_layout(height=max(380, len(_mb_p) * 46 + 90),
                                               margin_right=60,
                                               ytitle="")
            _layout_mb["showlegend"] = True
            _layout_mb["hovermode"] = "closest"
            _layout_mb["xaxis"].update(
                title=dict(text=("% sobre xifra de negoci" if _ca else "% sobre cifra de negocios"),
                           font=dict(color=G2_P, size=12)),
                rangemode="tozero", tickformat=".0f", dtick=2,
                showspikes=False, showgrid=True, gridcolor="#eef1f4")
            _layout_mb["yaxis"].update(type="category", showgrid=False, automargin=True)
            _layout_mb["yaxis"].pop("tickformat", None)
            _layout_mb["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            fig_mb.update_layout(**_layout_mb)
            st.plotly_chart(fig_mb, use_container_width=True, config=_CHART_CONFIG)
            source(("INE, Estadística Estructural d'Empreses Sector Comerç (taula 76818). "
                    "Sense la branca 478 (parades i mercats ambulants): amb menys d'una persona "
                    "ocupada per empresa, l'excedent hi inclou la remuneració del titular") if _ca else
                   ("INE, Estadística Estructural de Empresas Sector Comercio (tabla 76818). "
                    "Sin la rama 478 (puestos y mercadillos): con menos de una persona "
                    "ocupada por empresa, el excedente incluye la remuneración del titular"))

            _mb_d = (_mb_p[_mb_y1] - _mb_p[_mb_y0]).dropna().round(1)
            _n_puja = int((_mb_d > 0).sum())
            _ratio = _mb_p.loc[_c_max, _mb_y1] / _mb_p.loc[_c_min, _mb_y1]

            def _llista(codis, conj):
                noms = [f"«{_mb_lbl[int(c)].lower()}»" for c in codis]
                return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + f" {conj} " + noms[-1]

            _up = _mb_d[_mb_d == _mb_d.max()].index
            _dn = _mb_d[_mb_d == _mb_d.min()].index
            _pt = lambda v: f"{v:+.1f}".replace(".", ",")
            if _ca:
                insight(
                    f"El {_mb_y1}, el marge operatiu oscil·la entre un <strong>{_v_min}%</strong> "
                    f"({_mb_lbl[int(_c_min)].lower()}) i un <strong>{_v_max}%</strong> "
                    f"({_mb_lbl[int(_c_max)].lower()}), {fnum(_ratio, 1)} vegades més. "
                    f"Entre {_mb_y0} i {_mb_y1} el marge puja a <strong>{_n_puja} de {len(_mb_d)}</strong> branques. "
                    f"{'Les que més guanyen són' if len(_up) > 1 else 'La que més guanya és'} "
                    f"{_llista(_up, 'i')} ({_pt(_mb_d.max())} punts), i "
                    f"{'les que més perden,' if len(_dn) > 1 else 'la que més perd,'} "
                    f"{_llista(_dn, 'i')} ({_pt(_mb_d.min())} punts)."
                )
            else:
                insight(
                    f"En {_mb_y1}, el margen operativo oscila entre un <strong>{_v_min}%</strong> "
                    f"({_mb_lbl[int(_c_min)].lower()}) y un <strong>{_v_max}%</strong> "
                    f"({_mb_lbl[int(_c_max)].lower()}), {fnum(_ratio, 1)} veces más. "
                    f"Entre {_mb_y0} y {_mb_y1} el margen sube en <strong>{_n_puja} de {len(_mb_d)}</strong> ramas. "
                    f"{'Las que más ganan son' if len(_up) > 1 else 'La que más gana es'} "
                    f"{_llista(_up, 'y')} ({_pt(_mb_d.max())} puntos), y "
                    f"{'las que más pierden,' if len(_dn) > 1 else 'la que más pierde,'} "
                    f"{_llista(_dn, 'y')} ({_pt(_mb_d.min())} puntos)."
                )

        # ─── Avis metodologic ─────────────────────────────────────
        if _ca:
            st.caption(
                "**Limitacions metodològiques.** El **marge brut sobre vendes** s'extreu directament "
                "del Compte de resultats publicat per l'INE (T=36199, variable *Consumo de bienes y "
                "servicios para reventa*). En canvi, el **marge operatiu** és una aproximació a "
                "l'EBITDA: l'INE no publica directament l'amortització, el resultat financer ni els "
                "impostos al detall sectorial. Per al càlcul de **ROE / ROA** caldria informació de "
                "balanç (fons propis, actius totals) que no es publica per CNAE 47 al nivell "
                "estructural — la millor font seria la **Central de Balances del Banco de España** "
                "(que NO té API estructurada per a aquest desglossament: cal extreure-la dels informes "
                "anuals)."
            )
        else:
            st.caption(
                "**Limitaciones metodológicas.** El **margen bruto sobre ventas** se extrae "
                "directamente de la Cuenta de resultados publicada por el INE (T=36199, variable "
                "*Consumo de bienes y servicios para reventa*). En cambio, el **margen operativo** es "
                "una aproximación al EBITDA: el INE no publica directamente la amortización, el "
                "resultado financiero ni los impuestos al detalle sectorial. Para el cálculo de "
                "**ROE / ROA** se requeriría información de balance (fondos propios, activos totales) "
                "que no se publica para CNAE 47 a nivel estructural — la mejor fuente sería la "
                "**Central de Balances del Banco de España** (que NO tiene API estructurada para este "
                "desglose: hay que extraerla de los informes anuales)."
            )

# ─── Descàrrega ──────────────────────────────────────────────

with st.expander(t("download_data")):
    st.dataframe(df, use_container_width=True)
    st.download_button("CSV", df.to_csv(index=False).encode("utf-8"), "productivitat_cnae47.csv", "text/csv")

page_meta("INE, Estadística Estructural d'Empreses Sector Comerç" if _ca
          else "INE, Estadística Estructural de Empresas Sector Comercio", st.session_state.lang)
