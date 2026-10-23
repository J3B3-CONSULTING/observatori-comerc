"""Pàgina 2: Teixit Empresarial (CNAE 47) — disseny premium consultora"""
import streamlit as st
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, cagr, apply_layout, highlight_expander,
    kicker, action_title, deck, key_takeaways, shock_stat, exhibit_header,
    metrics_band, premium_plotly_layout, freshness_badge,
    NAVY, OCRE, RED, G1_P, PALETTE,
    load_geojson_spain_ccaa, canaries_inset_layers,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()
_ca = st.session_state.lang == "ca"

_CHART_CONFIG = {"displayModeBar": False, "responsive": True}


@st.cache_data
def load_geojson():
    return load_geojson_spain_ccaa(with_canaries_inset=True)


df = load_dataset("empreses")

kicker("Anàlisi estructural · Teixit empresarial" if _ca
       else "Análisis estructural · Tejido empresarial")

if df.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

# Separar CCAA del total nacional
ccaa_names = [t_name for t_name in df["territori"].unique() if t_name != "espanya"]
df_esp = df[df["territori"] == "espanya"].sort_values("any").copy()
df_ccaa = df[df["territori"].isin(ccaa_names)].copy()

# ─── Càlculs per a header, takeaways i shock stat ─────────────
first_esp = df_esp.iloc[0]
last_esp = df_esp.iloc[-1]
_fy = int(first_esp["any"])
_ly = int(last_esp["any"])
total_var = int(last_esp["empreses"]) - int(first_esp["empreses"])
pct_var = (total_var / int(first_esp["empreses"])) * 100
cagr_val = cagr(first_esp["empreses"], last_esp["empreses"], _ly - _fy)
peak = df_esp.loc[df_esp["empreses"].idxmax()]
_decreix = total_var < 0

# Densitat (per a takeaway 3, si existeix)
_d_first = _d_last = None
if "empreses_per_1000hab" in df_esp.columns:
    _dd = df_esp.dropna(subset=["empreses_per_1000hab"])
    if len(_dd) > 1:
        _d_first = _dd.iloc[0]["empreses_per_1000hab"]
        _d_last = _dd.iloc[-1]["empreses_per_1000hab"]

# ─── HEADER ──────────────────────────────────────────────────
if _decreix:
    if _ca:
        action_title(f"El nombre d'empreses del comerç al detall ha caigut un "
                     f"{fnum(abs(pct_var), 0)}% des del {_fy}")
        deck("El cens es redueix de manera gairebé ininterrompuda. La caiguda és "
             "coherent amb la concentració del sector, però no n'és prova suficient per si sola.")
    else:
        action_title(f"El número de empresas del comercio minorista ha caído un "
                     f"{fnum(abs(pct_var), 0)}% desde {_fy}")
        deck("El censo se reduce de manera casi ininterrumpida. La caída es "
             "coherente con la concentración del sector, pero no es prueba suficiente por sí sola.")
else:
    if _ca:
        action_title(f"El comerç guanya empreses respecte al {_fy}")
        deck("El teixit empresarial del comerç al detall s'amplia, "
             "coherent amb la recuperació del consum i els nous formats.")
    else:
        action_title(f"El comercio gana empresas respecto a {_fy}")
        deck("El tejido empresarial del comercio minorista se amplía, "
             "coherente con la recuperación del consumo y los nuevos formatos.")

if _ca:
    _takeaways = [
        f"Entre {_fy} i {_ly} el nombre d'empreses actives ha "
        f"{'caigut' if _decreix else 'crescut'} un <b>{fpct(pct_var, 1, sign=False)}</b> "
        f"({fnum(abs(total_var))} {'menys' if _decreix else 'més'}), un ritme del "
        f"<b>{fpct(cagr_val, 1)}</b> anual.",
        "La caiguda és gairebé ininterrompuda: el sector encadena retrocessos "
        f"pràcticament cada any des del {_fy}, sense recuperar el terreny perdut."
        if _decreix else
        "L'expansió és coherent amb l'aparició de nous formats de proximitat, "
        "franquícies i comerç electrònic pur.",
    ]
    if _d_first is not None:
        _takeaways.append(
            f"La densitat comercial passa de <b>{fnum(_d_first, 1)}</b> a "
            f"<b>{fnum(_d_last, 1)}</b> empreses per 1.000 habitants: "
            f"{'menys' if _d_last < _d_first else 'més'} comerç a prop del ciutadà."
        )
    _tk_label = "Conclusions clau"
else:
    _takeaways = [
        f"Entre {_fy} y {_ly} el número de empresas activas ha "
        f"{'caído' if _decreix else 'crecido'} un <b>{fpct(pct_var, 1, sign=False)}</b> "
        f"({fnum(abs(total_var))} {'menos' if _decreix else 'más'}), un ritmo del "
        f"<b>{fpct(cagr_val, 1)}</b> anual.",
        "La caída es casi ininterrumpida: el sector encadena retrocesos "
        f"prácticamente cada año desde {_fy}, sin recuperar el terreno perdido."
        if _decreix else
        "La expansión es coherente con la aparición de nuevos formatos de proximidad, "
        "franquicias y comercio electrónico puro.",
    ]
    if _d_first is not None:
        _takeaways.append(
            f"La densidad comercial pasa de <b>{fnum(_d_first, 1)}</b> a "
            f"<b>{fnum(_d_last, 1)}</b> empresas por 1.000 habitantes: "
            f"{'menos' if _d_last < _d_first else 'más'} comercio cerca del ciudadano."
        )
    _tk_label = "Conclusiones clave"

key_takeaways(_takeaways, label=_tk_label)
freshness_badge("empreses", st.session_state.lang)

# ─── TABS ────────────────────────────────────────────────────
_tabs_lbl = [
    ("Espanya" if _ca else "España"),
    ("Comunitats autònomes" if _ca else "Comunidades autónomas"),
]
tab_esp, tab_ccaa = st.tabs(_tabs_lbl, default=tab_destinacio("pages/2_Empreses.py", _tabs_lbl))

# ════════════════════════════════════════════════════════════
# TAB 1: ESPANYA
# ════════════════════════════════════════════════════════════
with tab_esp:

    # ─── Exhibit 1: evolució del nombre d'empreses ───
    if _ca:
        exhibit_header(
            1, f"El cens cau de {fnum(first_esp['empreses'])} a "
               f"{fnum(last_esp['empreses'])} empreses entre {_fy} i {_ly}",
            note="El màxim de la sèrie és l'any inicial; des d'aleshores el cens "
                 "no ha tornat a aquell nivell.",
        )
    else:
        exhibit_header(
            1, f"El censo cae de {fnum(first_esp['empreses'])} a "
               f"{fnum(last_esp['empreses'])} empresas entre {_fy} y {_ly}",
            note="El máximo de la serie es el año inicial; desde entonces el censo "
                 "no ha vuelto a ese nivel.",
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_esp["any"], y=df_esp["empreses"],
        mode="lines", name=t("spain"),
        line=dict(color=NAVY, shape="spline", smoothing=0.5, width=3),
        fill="tozeroy", fillcolor="rgba(11,58,102,0.06)",
        hovertemplate="<b>%{y:,.0f}</b><extra></extra>",
    ))
    _x_last = int(df_esp["any"].iloc[-1])
    _y_last = float(df_esp["empreses"].iloc[-1])
    fig.add_trace(go.Scatter(
        x=[_x_last], y=[_y_last], mode="markers",
        showlegend=False, hoverinfo="skip",
        marker=dict(color=NAVY, size=10, line=dict(color="white", width=2)),
    ))
    _layout = premium_plotly_layout(
        height=440, margin_right=120,
        ytitle=("Empreses" if _ca else "Empresas"))
    _layout["yaxis"]["rangemode"] = "normal"
    _layout["yaxis"]["range"] = [
        float(df_esp["empreses"].min()) * 0.92,
        float(df_esp["empreses"].max()) * 1.04,
    ]
    _layout["annotations"] = [dict(
        x=_x_last, y=_y_last, xanchor="left", xshift=14, showarrow=False,
        align="left", text=f"<b>{fnum(_y_last)}</b><br>"
                           f"<span style='color:{G1_P}'>{_ly}</span>",
        font=dict(color=NAVY, size=13),
    )]
    fig.update_layout(**_layout)
    st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)
    source("INE, Directori Central d'Empreses (DIRCE)" if _ca
           else "INE, Directorio Central de Empresas (DIRCE)")

    # ─── Shock stat ───
    if _decreix:
        if _ca:
            shock_stat(
                fnum(abs(total_var)), " empreses",
                f"menys que el {_fy}. El cens del comerç al detall encadena "
                f"{_ly - _fy} anys de contracció i no ha recuperat el nivell de partida.",
                sub="Contracció sostinguda del cens empresarial",
            )
        else:
            shock_stat(
                fnum(abs(total_var)), " empresas",
                f"menos que en {_fy}. El censo del comercio minorista encadena "
                f"{_ly - _fy} años de contracción y no ha recuperado el nivel de partida.",
                sub="Contracción sostenida del censo empresarial",
            )

    # ─── Exhibit 2: taxa de variació anual ───
    if len(df_esp) > 1:
        df_esp["var_pct"] = df_esp["empreses"].pct_change() * 100
        df_var = df_esp.dropna(subset=["var_pct"])
        _n_neg = int((df_var["var_pct"] < 0).sum())
        if _ca:
            exhibit_header(
                2, f"La variació anual és negativa en {_n_neg} dels {len(df_var)} exercicis",
                note="Les barres vermelles marquen anys de destrucció neta d'empreses; "
                     "les blaves, de creació neta.",
            )
        else:
            exhibit_header(
                2, f"La variación anual es negativa en {_n_neg} de los {len(df_var)} ejercicios",
                note="Las barras rojas marcan años de destrucción neta de empresas; "
                     "las azules, de creación neta.",
            )
        colors = [NAVY if v >= 0 else RED for v in df_var["var_pct"]]
        fig2 = go.Figure(go.Bar(
            x=df_var["any"], y=df_var["var_pct"], marker_color=colors,
            text=[fpct(v) for v in df_var["var_pct"]],
            textposition="outside",
            textfont=dict(size=10, color=G1_P, family="Manrope, system-ui, sans-serif"),
            hovertemplate="%{x}: <b>%{y:.1f}%</b><extra></extra>",
        ))
        _layout2 = premium_plotly_layout(height=380, margin_right=30, ytitle="%")
        _layout2["yaxis"]["rangemode"] = "normal"
        _layout2["yaxis"]["tickformat"] = ".1f"
        fig2.update_layout(**_layout2)
        fig2.add_hline(y=0, line_dash="dash", line_color="rgba(0,0,0,0.15)")
        st.plotly_chart(fig2, use_container_width=True, config=_CHART_CONFIG)
        source("INE, DIRCE. Càlcul propi" if _ca else "INE, DIRCE. Cálculo propio")

    # ─── Insight dinàmic ───
    if not df_esp.empty and len(df_esp) > 1:
        if _ca:
            diff_lbl = "menys" if _decreix else "més"
            cagr_lbl = "destrucció neta" if _decreix else "creació neta"
            tendencia = (
                "La tendència reflecteix la concentració del sector i la pressió del "
                "comerç electrònic. Malgrat la reducció del nombre d'empreses, la "
                "dimensió mitjana creix: les empreses supervivents absorbeixen quota "
                "de mercat i guanyen escala operativa."
                if _decreix else
                "L'expansió del nombre d'empreses és coherent amb la recuperació del "
                "consum i l'aparició de nous formats de proximitat, e-commerce pur i "
                "franquícies emergents."
            )
            txt = (
                f"El comerç al detall espanyol comptava amb <strong>{fnum(last_esp['empreses'])} empreses</strong> "
                f"el {_ly}, <strong>{fnum(abs(total_var))} {diff_lbl}</strong> "
                f"que el {_fy} ({fpct(pct_var)}). "
                f"El màxim es va registrar el {int(peak['any'])} amb {fnum(peak['empreses'])} empreses. "
                f"Això suposa una {cagr_lbl} anual mitjana (CAGR) del <strong>{fpct(cagr_val, 1)}</strong>. "
                f"{tendencia}"
            )
        else:
            diff_lbl = "menos" if _decreix else "más"
            cagr_lbl = "destrucción neta" if _decreix else "creación neta"
            tendencia = (
                "La tendencia refleja la concentración del sector y la presión del "
                "comercio electrónico. Pese a la reducción del número de empresas, "
                "la dimensión media crece: las empresas supervivientes absorben cuota "
                "de mercado y ganan escala operativa."
                if _decreix else
                "La expansión del número de empresas es coherente con la recuperación "
                "del consumo y la aparición de nuevos formatos de proximidad, e-commerce "
                "puro y franquicias emergentes."
            )
            txt = (
                f"El comercio minorista español contaba con <strong>{fnum(last_esp['empreses'])} empresas</strong> "
                f"en {_ly}, <strong>{fnum(abs(total_var))} {diff_lbl}</strong> "
                f"que en {_fy} ({fpct(pct_var)}). "
                f"El máximo se registró en {int(peak['any'])} con {fnum(peak['empreses'])} empresas. "
                f"Esto supone una {cagr_lbl} anual media (CAGR) del <strong>{fpct(cagr_val, 1)}</strong>. "
                f"{tendencia}"
            )
        insight(txt)

    # ─── Densitat comercial (secundari) ───
    if _d_first is not None:
        _lbl_dens_exp = ("Veure densitat comercial (empreses / 1.000 hab.)"
                         if _ca else "Ver densidad comercial (empresas / 1.000 hab.)")
        with highlight_expander(_lbl_dens_exp, expanded=False):
            df_dens = df_esp.dropna(subset=["empreses_per_1000hab"])
            var_dens = ((_d_last / _d_first) - 1) * 100
            _dens_baixa = var_dens < 0
            if _ca:
                exhibit_header(
                    3, f"La densitat comercial cau un {fnum(abs(var_dens), 1)}% "
                       f"des del {int(df_dens.iloc[0]['any'])}"
                    if _dens_baixa else
                    f"La densitat comercial puja un {fnum(var_dens, 1)}% "
                    f"des del {int(df_dens.iloc[0]['any'])}",
                )
            else:
                exhibit_header(
                    3, f"La densidad comercial cae un {fnum(abs(var_dens), 1)}% "
                       f"desde {int(df_dens.iloc[0]['any'])}"
                    if _dens_baixa else
                    f"La densidad comercial sube un {fnum(var_dens, 1)}% "
                    f"desde {int(df_dens.iloc[0]['any'])}",
                )
            fig_dens = go.Figure(go.Scatter(
                x=df_dens["any"], y=df_dens["empreses_per_1000hab"],
                mode="lines",
                line=dict(color=OCRE, shape="spline", smoothing=0.5, width=3),
                fill="tozeroy", fillcolor="rgba(176,125,43,0.07)",
                hovertemplate="%{x}: <b>%{y:.1f}</b> emp/1.000 hab<extra></extra>",
            ))
            _ld = premium_plotly_layout(
                height=360, margin_right=30,
                ytitle=("Empreses / 1.000 hab." if _ca else "Empresas / 1.000 hab."))
            _ld["yaxis"]["rangemode"] = "normal"
            _ld["yaxis"]["range"] = [
                float(df_dens["empreses_per_1000hab"].min()) * 0.85,
                float(df_dens["empreses_per_1000hab"].max()) * 1.05,
            ]
            _ld["yaxis"]["tickformat"] = ".1f"
            fig_dens.update_layout(**_ld)
            st.plotly_chart(fig_dens, use_container_width=True, config=_CHART_CONFIG)
            source("INE, DIRCE i Padrón Municipal. Càlcul propi" if _ca
                   else "INE, DIRCE y Padrón Municipal. Cálculo propio")

    # ─── Banda de mètriques (resum Espanya) ───
    _m_var = ("+" if pct_var >= 0 else "") + fnum(pct_var, 1)
    _m_cagr = ("+" if cagr_val >= 0 else "") + fnum(cagr_val, 1)
    if _ca:
        metrics_band([
            (fnum(last_esp["empreses"]), "", f"Empreses ({_ly})"),
            (_m_var, "%", f"Variació {_fy}–{_ly}"),
            (fnum(abs(total_var)), "", "Empreses perdudes" if _decreix else "Empreses guanyades"),
            (_m_cagr, "%", "Ritme anual (CAGR)"),
        ])
    else:
        metrics_band([
            (fnum(last_esp["empreses"]), "", f"Empresas ({_ly})"),
            (_m_var, "%", f"Variación {_fy}–{_ly}"),
            (fnum(abs(total_var)), "", "Empresas perdidas" if _decreix else "Empresas ganadas"),
            (_m_cagr, "%", "Ritmo anual (CAGR)"),
        ])

# ════════════════════════════════════════════════════════════
# TAB 2: COMUNITATS AUTÒNOMES (mapa + rànquing + anàlisi)
# ════════════════════════════════════════════════════════════
with tab_ccaa:
    if df_ccaa.empty:
        st.info("No hi ha dades de CCAA disponibles." if _ca
                else "No hay datos de CCAA disponibles.")
    else:
        geojson = load_geojson()
        any_sel = st.select_slider(
            t("emp_ccaa_year"),
            options=sorted(df_ccaa["any"].dropna().unique()),
            value=max(df_ccaa["any"].dropna().unique()))
        df_map = df_ccaa[df_ccaa["any"] == any_sel].copy()

        tab_map, tab_rank = st.tabs([
            "Mapa" if _ca else "Mapa",
            "Rànquing" if _ca else "Ranking",
        ])

        with tab_map:
            map_metric = st.radio(
                "Mètrica" if _ca else "Métrica",
                ["density", "absolute"],
                format_func=lambda x: (
                    ("Empreses / 1.000 hab." if _ca else "Empresas / 1.000 hab.") if x == "density"
                    else ("Empreses (absolut)" if _ca else "Empresas (absoluto)")),
                horizontal=True)

            if map_metric == "density" and "empreses_per_1000hab" in df_map.columns:
                col_val = "empreses_per_1000hab"
                lbl_legend = "Emp. / 1.000 hab."
                fmt = ".1f"
                zmin = df_ccaa["empreses_per_1000hab"].min()
                zmax = df_ccaa["empreses_per_1000hab"].max()
            else:
                col_val = "empreses"
                lbl_legend = "Empreses" if _ca else "Empresas"
                fmt = ",.0f"
                zmin = df_ccaa["empreses"].min()
                zmax = df_ccaa["empreses"].max()

            fig_map = go.Figure(go.Choroplethmap(
                geojson=geojson,
                locations=df_map["territori"],
                featureidkey="properties.territori",
                z=df_map[col_val], zmin=zmin, zmax=zmax,
                colorscale=[
                    [0, "#ffffff"], [0.25, "#dde7f0"], [0.5, "#6985a8"],
                    [0.75, "#1f487a"], [1, "#003366"]],
                colorbar=dict(title=lbl_legend, thickness=15),
                marker=dict(line=dict(width=1.5, color="white")),
                text=df_map["territori"],
                hovertemplate=(
                    "<b>%{text}</b><br>" +
                    f"{lbl_legend}: " + "%{z:" + fmt + "}<extra></extra>")))
            fig_map.update_layout(
                map=dict(
                    style="white-bg",
                    center=dict(lat=38.7, lon=-4.0),
                    zoom=4.55,
                    layers=canaries_inset_layers()),
                height=800,
                margin=dict(l=0, r=0, t=10, b=10),
                dragmode=False,
                annotations=[dict(
                    text="<b>CANÀRIES</b>" if _ca else "<b>CANARIAS</b>",
                    xref="paper", yref="paper", x=0.18, y=0.18, showarrow=False,
                    font=dict(size=10, color="#003366", family="Inter, sans-serif"))])
            st.plotly_chart(fig_map, use_container_width=True,
                            config={"scrollZoom": False, "doubleClick": False, "displayModeBar": False})
            source("INE, DIRCE i Padrón Municipal. Càlcul propi" if _ca
                   else "INE, DIRCE y Padrón Municipal. Cálculo propio")

        with tab_rank:
            df_any = df_ccaa[df_ccaa["any"] == any_sel].sort_values("empreses", ascending=True)
            total_esp_val = df_esp[df_esp["any"] == any_sel]["empreses"].values
            total_val = total_esp_val[0] if len(total_esp_val) > 0 else df_any["empreses"].sum()

            if _ca:
                exhibit_header(1, f"Distribució d'empreses per comunitat ({int(any_sel)})")
            else:
                exhibit_header(1, f"Distribución de empresas por comunidad ({int(any_sel)})")

            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                y=df_any["territori"], x=df_any["empreses"], orientation="h",
                marker_color=NAVY,
                text=[f"{fnum(v)}  ({fpct(v / total_val * 100, 1, sign=False)})" for v in df_any["empreses"]],
                textposition="outside", textfont=dict(size=11, color=G1_P)))
            n_ccaa = len(df_any)
            if n_ccaa > 0:
                avg_emp = total_val / n_ccaa
                fig3.add_vline(
                    x=avg_emp, line_dash="dash", line_color=OCRE, line_width=2,
                    annotation_text=f"{'Mitjana' if _ca else 'Media'}: {fnum(avg_emp)}",
                    annotation_position="top right")
            apply_layout(fig3,
                xaxis_title=t("emp_count"),
                height=max(450, len(df_any) * 32 + 100),
                margin=dict(l=200, r=120, t=30, b=50))
            st.plotly_chart(fig3, use_container_width=True)
            source("INE, DIRCE")

            if "empreses_per_1000hab" in df_ccaa.columns:
                df_dens_ccaa = df_ccaa[df_ccaa["any"] == any_sel].dropna(subset=["empreses_per_1000hab"])
                if not df_dens_ccaa.empty:
                    if _ca:
                        exhibit_header(2, f"Densitat comercial per comunitat ({int(any_sel)})")
                    else:
                        exhibit_header(2, f"Densidad comercial por comunidad ({int(any_sel)})")
                    df_dens_ccaa = df_dens_ccaa.sort_values("empreses_per_1000hab", ascending=True)
                    esp_dens = df_esp[df_esp["any"] == any_sel]["empreses_per_1000hab"].values
                    avg_dens = esp_dens[0] if len(esp_dens) > 0 else None

                    fig_dens_ccaa = go.Figure()
                    fig_dens_ccaa.add_trace(go.Bar(
                        y=df_dens_ccaa["territori"], x=df_dens_ccaa["empreses_per_1000hab"],
                        orientation="h", marker_color=OCRE,
                        text=[f"{v:.1f}".replace(".", ",") for v in df_dens_ccaa["empreses_per_1000hab"]],
                        textposition="outside", textfont=dict(size=11, color=G1_P)))
                    if avg_dens:
                        fig_dens_ccaa.add_vline(
                            x=avg_dens, line_dash="dash", line_color=NAVY, line_width=2,
                            annotation_text=f"{'Espanya' if _ca else 'España'}: {avg_dens:.1f}".replace(".", ","),
                            annotation_position="top right")
                    apply_layout(fig_dens_ccaa,
                        xaxis_title=("Empreses / 1.000 hab." if _ca else "Empresas / 1.000 hab."),
                        height=max(450, len(df_dens_ccaa) * 32 + 100),
                        margin=dict(l=200, r=100, t=30, b=50))
                    st.plotly_chart(fig_dens_ccaa, use_container_width=True)
                    source("INE, DIRCE i Padrón Municipal. Càlcul propi" if _ca
                           else "INE, DIRCE y Padrón Municipal. Cálculo propio")

        # Anàlisi addicional per CCAA (variació acumulada + evolució)
        _lbl_ccaa_exp = ("Veure anàlisi addicional per CCAA"
                         if _ca else "Ver análisis adicional por CCAA")
        with highlight_expander(_lbl_ccaa_exp, expanded=False):
            first_year = df_ccaa["any"].min()
            last_year = df_ccaa["any"].max()
            df_first = df_ccaa[df_ccaa["any"] == first_year][["territori", "empreses"]].rename(columns={"empreses": "emp_first"})
            df_last = df_ccaa[df_ccaa["any"] == last_year][["territori", "empreses"]].rename(columns={"empreses": "emp_last"})
            df_var_ccaa = df_first.merge(df_last, on="territori")
            df_var_ccaa["var_pct"] = ((df_var_ccaa["emp_last"] / df_var_ccaa["emp_first"]) - 1) * 100
            df_var_ccaa = df_var_ccaa.sort_values("var_pct", ascending=True)

            if _ca:
                exhibit_header(3, f"Variació acumulada del cens per comunitat ({int(first_year)}–{int(last_year)})")
            else:
                exhibit_header(3, f"Variación acumulada del censo por comunidad ({int(first_year)}–{int(last_year)})")
            fig_var = go.Figure()
            colors_var = [NAVY if v >= 0 else RED for v in df_var_ccaa["var_pct"]]
            fig_var.add_trace(go.Bar(
                y=df_var_ccaa["territori"], x=df_var_ccaa["var_pct"], orientation="h",
                marker_color=colors_var,
                text=[fpct(v) for v in df_var_ccaa["var_pct"]],
                textposition="outside", textfont=dict(size=11, color=G1_P), name="",
                hovertemplate="<b>%{y}</b><br>" +
                              ("Variació acumulada" if _ca else "Variación acumulada") +
                              ": %{x:+.1f}%<extra></extra>"))
            apply_layout(fig_var,
                xaxis_title=("Variació acumulada (%)" if _ca else "Variación acumulada (%)"),
                height=max(450, len(df_var_ccaa) * 32 + 100),
                margin=dict(l=200, r=80, t=30, b=50))
            fig_var.add_vline(x=0, line_dash="dash", line_color="rgba(0,0,0,0.2)")
            st.plotly_chart(fig_var, use_container_width=True)
            source("INE, DIRCE. Càlcul propi" if _ca else "INE, DIRCE. Cálculo propio")

            st.subheader(t("emp_ccaa_evolution"))
            default_ccaa = [c for c in ["Cataluña", "Madrid (Comunidad de)", "Andalucía",
                                        "Comunitat Valenciana"] if c in ccaa_names]
            sel_ccaa = st.multiselect(t("emp_ccaa_select"), sorted(ccaa_names), default=default_ccaa)
            if sel_ccaa:
                fig4 = go.Figure()
                for i, ccaa in enumerate(sel_ccaa):
                    df_c = df_ccaa[df_ccaa["territori"] == ccaa].sort_values("any")
                    fig4.add_trace(go.Scatter(
                        x=df_c["any"], y=df_c["empreses"],
                        mode="lines+markers", name=ccaa,
                        line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
                        marker=dict(size=5)))
                apply_layout(fig4, yaxis_title=t("emp_count"), height=450)
                st.plotly_chart(fig4, use_container_width=True)
                source("INE, DIRCE")

# ─── Descàrrega ───
with st.expander(t("download_data")):
    st.dataframe(df, use_container_width=True)
    st.download_button("CSV", df.to_csv(index=False).encode("utf-8"), "empreses_cnae47.csv", "text/csv")

page_meta("INE, Directori Central d'Empreses (DIRCE)" if _ca
          else "INE, Directorio Central de Empresas (DIRCE)", st.session_state.lang)
