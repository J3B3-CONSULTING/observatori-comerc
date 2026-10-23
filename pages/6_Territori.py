"""Pàgina 6: Territori — Magnituds del CNAE 47 per CCAA i locals DIRCE per província i subsector"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, apply_layout, highlight_expander,
    kicker, action_title, deck, key_takeaways, exhibit_header,
    freshness_badge,
    NAVY, OCRE, OCRE_DEEP, G1_P, G2_P,
    load_geojson_spain_ccaa, load_geojson_spain_provincies, canaries_inset_layers,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()
_ca = st.session_state.lang == "ca"


@st.cache_data(ttl=3600)
def load_data():
    p = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "eee_ccaa.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()


@st.cache_data
def load_geojson():
    return load_geojson_spain_ccaa(with_canaries_inset=True)


@st.cache_data(ttl=3600)
def load_cache_csv(name):
    p = os.path.join(os.path.dirname(__file__), "..", "data", "cache", name)
    if os.path.exists(p):
        return pd.read_csv(p, dtype={"codi_geo": str, "codi_ccaa": str, "cnae": str})
    return pd.DataFrame()


@st.cache_data
def load_geojson_prov():
    return load_geojson_spain_provincies(with_canaries_inset=True)


df_eee = load_data()
df_lp = load_cache_csv("locals_provincia.csv")
df_lg = load_cache_csv("locals_ccaa_grups.csv")
df_emp = load_cache_csv("empreses.csv")

# Any del trencament de sèrie DIRCE: es llegeix del CSV, mai escrit a mà
_trenc = sorted(df_lp.loc[df_lp["travessa_trencament"] == True, "any"].unique()) if not df_lp.empty else []  # noqa: E712
_TB = int(_trenc[0]) if _trenc else None
_ESP = "Espanya" if _ca else "España"
_SRC_DIRCE = ("INE, Directori Central d'Empreses (DIRCE), locals" if _ca
              else "INE, Directorio Central de Empresas (DIRCE), locales")
_SRC_PADRO = ("Padró continu (taula 29005)" if _ca else "Padrón continuo (tabla 29005)")

kicker("Anàlisi territorial · Comerç al detall per CCAA i província" if _ca
       else "Análisis territorial · Comercio minorista por CCAA y provincia")

_tabs_lbl = [
    ("Magnituds per CCAA" if _ca else "Magnitudes por CCAA"),
    ("Locals per província" if _ca else "Locales por provincia"),
    ("Locals per subsector" if _ca else "Locales por subsector"),
]
tab_mag, tab_prov, tab_grup = st.tabs(_tabs_lbl, default=tab_destinacio("pages/6_Territori.py", _tabs_lbl))

# ════════════════════════════════════════════════════════════
# TAB 1: MAGNITUDS PER CCAA (Estadística Estructural + Eurostat)
# ════════════════════════════════════════════════════════════
with tab_mag:
    if df_eee.empty:
        st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    else:
        geojson = load_geojson()
        df_ccaa = df_eee[df_eee["territori"] != "espanya"].copy()
        df_esp = df_eee[df_eee["territori"] == "espanya"].copy()
        _tots_anys = sorted(df_ccaa["any"].dropna().unique())
        if "pes_cnae47_pib" in df_ccaa.columns:
            anys = sorted(df_ccaa.dropna(subset=["pes_cnae47_pib"])["any"].unique())
        else:
            anys = _tots_anys
        if not anys:
            anys = _tots_anys

        # ─── Càlculs per a header i takeaways (últim any disponible) ──
        _ly = int(max(anys))

        _d_hdr = df_ccaa[df_ccaa["any"] == _ly].dropna(subset=["pes_cnae47_pib"]).copy()
        _d_hdr["_pct"] = _d_hdr["pes_cnae47_pib"] * 100
        _d_hdr = _d_hdr.sort_values("_pct")
        _hdr_top = _d_hdr.iloc[-1]
        _hdr_bot = _d_hdr.iloc[0]
        _hdr_ratio = _hdr_top["_pct"] / _hdr_bot["_pct"] if _hdr_bot["_pct"] else 0

        _esp_hdr = df_esp[df_esp["any"] == _ly]
        _esp_pes_hdr = None
        if not _esp_hdr.empty and pd.notna(_esp_hdr.iloc[0].get("pes_cnae47_pib")):
            _esp_pes_hdr = _esp_hdr.iloc[0]["pes_cnae47_pib"] * 100

        # Productivitat per al takeaway
        _dp_hdr = df_ccaa[df_ccaa["any"] == _ly].copy()
        _prod_top = _prod_bot = _prod_ratio = None
        if "xifra_negoci" in _dp_hdr.columns and "personal_ocupat" in _dp_hdr.columns:
            _dp_hdr["_prod"] = _dp_hdr["xifra_negoci"] / _dp_hdr["personal_ocupat"]
            _dp_hdr = _dp_hdr.dropna(subset=["_prod"]).sort_values("_prod")
            if not _dp_hdr.empty:
                _prod_top = _dp_hdr.iloc[-1]
                _prod_bot = _dp_hdr.iloc[0]
                _prod_ratio = _prod_top["_prod"] / _prod_bot["_prod"]

        # ─── HEADER ──────────────────────────────────────────────────
        if _ca:
            action_title(
                f"El pes del comerç sobre el PIB regional oscil·la entre el "
                f"{fpct(_hdr_top['_pct'], 1, sign=False)} i el {fpct(_hdr_bot['_pct'], 1, sign=False)}")
            deck("El comerç al detall pesa molt més a les economies orientades al consum "
                 "i al turisme que a les industrials o de serveis avançats.")
        else:
            action_title(
                f"El peso del comercio sobre el PIB regional oscila entre el "
                f"{fpct(_hdr_top['_pct'], 1, sign=False)} y el {fpct(_hdr_bot['_pct'], 1, sign=False)}")
            deck("El comercio minorista pesa mucho más en las economías orientadas al "
                 "consumo y al turismo que en las industriales o de servicios avanzados.")

        if _ca:
            _takeaways = [
                f"El {_ly}, <b>{_hdr_top['territori']}</b> destina el "
                f"<b>{fpct(_hdr_top['_pct'], 1, sign=False)}</b> del seu PIB al comerç al detall, "
                f"<b>{fnum(_hdr_ratio, 1)}</b> vegades el de <b>{_hdr_bot['territori']}</b> "
                f"({fpct(_hdr_bot['_pct'], 1, sign=False)}).",
            ]
            if _esp_pes_hdr is not None:
                _above = int((_d_hdr["_pct"] >= _esp_pes_hdr).sum())
                _below = int((_d_hdr["_pct"] < _esp_pes_hdr).sum())
                _takeaways.append(
                    f"<b>{_above}</b> comunitats superen la mitjana espanyola "
                    f"(<b>{fpct(_esp_pes_hdr, 1, sign=False)}</b> del PIB) i <b>{_below}</b> hi queden per sota.")
            if _prod_ratio is not None:
                _takeaways.append(
                    f"La facturació per ocupat varia <b>{fnum(_prod_ratio, 1)}</b> vegades entre "
                    f"<b>{_prod_top['territori']}</b> ({fnum(_prod_top['_prod']/1000, 0)} k EUR) "
                    f"i <b>{_prod_bot['territori']}</b> ({fnum(_prod_bot['_prod']/1000, 0)} k EUR).")
            _tk_label = "Conclusions clau"
        else:
            _takeaways = [
                f"En {_ly}, <b>{_hdr_top['territori']}</b> destina el "
                f"<b>{fpct(_hdr_top['_pct'], 1, sign=False)}</b> de su PIB al comercio minorista, "
                f"<b>{fnum(_hdr_ratio, 1)}</b> veces el de <b>{_hdr_bot['territori']}</b> "
                f"({fpct(_hdr_bot['_pct'], 1, sign=False)}).",
            ]
            if _esp_pes_hdr is not None:
                _above = int((_d_hdr["_pct"] >= _esp_pes_hdr).sum())
                _below = int((_d_hdr["_pct"] < _esp_pes_hdr).sum())
                _takeaways.append(
                    f"<b>{_above}</b> comunidades superan la media española "
                    f"(<b>{fpct(_esp_pes_hdr, 1, sign=False)}</b> del PIB) y <b>{_below}</b> quedan por debajo.")
            if _prod_ratio is not None:
                _takeaways.append(
                    f"La facturación por ocupado varía <b>{fnum(_prod_ratio, 1)}</b> veces entre "
                    f"<b>{_prod_top['territori']}</b> ({fnum(_prod_top['_prod']/1000, 0)} k EUR) "
                    f"y <b>{_prod_bot['territori']}</b> ({fnum(_prod_bot['_prod']/1000, 0)} k EUR).")
            _tk_label = "Conclusiones clave"

        key_takeaways(_takeaways, label=_tk_label)
        freshness_badge("eee_ccaa", st.session_state.lang)

        # ─── Nota metodològica (mètode híbrid top-down + bottom-up) ──
        _lbl_metode = ("Nota metodològica: com s'estima el VAB del comerç per CCAA"
                       if _ca else "Nota metodológica: cómo se estima el VAB del comercio por CCAA")
        with highlight_expander(_lbl_metode, expanded=False):
            if _ca:
                st.markdown(
                    "La Comptabilitat Regional de l'INE no desglossa el CNAE 47 per comunitats autònomes. "
                    "Per estimar el VAB del comerç al detall per CCAA combinem dues fonts: "
                    "la **comptabilitat regional d'Eurostat** (VAB de la secció G-I: comerç, transport i hostaleria) "
                    "i la **xifra de negoci per CCAA** de l'Enquesta Estructural d'Empreses de l'INE. "
                    "El mètode híbrid distribueix el VAB nacional del CNAE 47 entre CCAA ponderant "
                    "les quotes regionals de G-I (top-down) amb les quotes de facturació (bottom-up), "
                    "garantint que la suma coincideixi amb el total nacional d'Eurostat.")
            else:
                st.markdown(
                    "La Contabilidad Regional del INE no desglosa el CNAE 47 por comunidades autónomas. "
                    "Para estimar el VAB del comercio minorista por CCAA combinamos dos fuentes: "
                    "la **contabilidad regional de Eurostat** (VAB de la sección G-I: comercio, transporte y hostelería) "
                    "y la **cifra de negocio por CCAA** de la Encuesta Estructural de Empresas del INE. "
                    "El método híbrido distribuye el VAB nacional del CNAE 47 entre CCAA ponderando "
                    "las cuotas regionales de G-I (top-down) con las cuotas de facturación (bottom-up), "
                    "garantizando que la suma coincida con el total nacional de Eurostat.")

        # ─── Selector d'any ──────────────────────────────────────────

        any_sel = st.select_slider(
            t("emp_ccaa_year"),
            options=anys,
            value=max(anys),
        )

        # ─── KPIs ────────────────────────────────────────────────────

        VAB_COL = "vab_eurostat" if "vab_eurostat" in df_eee.columns else "vab_estimat"

        d_yr_esp = df_esp[df_esp["any"] == any_sel]
        if not d_yr_esp.empty:
            row = d_yr_esp.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            if pd.notna(row.get("pes_cnae47_pib")):
                c1.metric(
                    f"{'Pes CNAE 47 / PIB' if _ca else 'Peso CNAE 47 / PIB'} ({int(any_sel)})",
                    fpct(row["pes_cnae47_pib"] * 100, 1, sign=False))
            if "xifra_negoci" in row and pd.notna(row.get("xifra_negoci")):
                c2.metric(t("eee_ccaa_xn") + " (M EUR)", fnum(row["xifra_negoci"] / 1e6))
            if "personal_ocupat" in row and pd.notna(row.get("personal_ocupat")):
                c3.metric(t("eee_ccaa_personal"), fnum(row["personal_ocupat"]))
            if "locals" in row and pd.notna(row.get("locals")):
                c4.metric("Locals (Estadística Estructural)" if _ca else "Locales (Estadística Estructural)",
                          fnum(row["locals"]),
                          help=("Estadística Estructural d'Empreses de l'INE. No coincideix amb els locals del "
                                "DIRCE de les altres pestanyes: són dues fonts amb mètodes diferents." if _ca else
                                "Estadística Estructural de Empresas del INE. No coincide con los locales del "
                                "DIRCE de las otras pestañas: son dos fuentes con métodos distintos."))

        # ─── Exhibit 1: pes del CNAE 47 sobre el PIB per CCAA ────────

        if "pes_cnae47_pib" in df_ccaa.columns:
            d_pes = df_ccaa[df_ccaa["any"] == any_sel].dropna(subset=["pes_cnae47_pib"]).copy()
            d_pes = d_pes.sort_values("pes_cnae47_pib", ascending=True)

            if not d_pes.empty:
                d_pes["_pct"] = d_pes["pes_cnae47_pib"] * 100

                esp_pes_row = df_esp[df_esp["any"] == any_sel]
                esp_pes = None
                if not esp_pes_row.empty and pd.notna(esp_pes_row.iloc[0].get("pes_cnae47_pib")):
                    esp_pes = esp_pes_row.iloc[0]["pes_cnae47_pib"] * 100

                _ex1_top = d_pes.iloc[-1]
                if _ca:
                    exhibit_header(
                        1, f"{_ex1_top['territori']} encapçala el pes del comerç sobre el PIB "
                           f"({fpct(_ex1_top['_pct'], 1, sign=False)}) el {int(any_sel)}",
                        note="Les barres navy marquen comunitats per sobre de la mitjana espanyola; "
                             "les clares, per sota.",
                    )
                else:
                    exhibit_header(
                        1, f"{_ex1_top['territori']} encabeza el peso del comercio sobre el PIB "
                           f"({fpct(_ex1_top['_pct'], 1, sign=False)}) en {int(any_sel)}",
                        note="Las barras navy marcan comunidades por encima de la media española; "
                             "las claras, por debajo.",
                    )

                colors_pes = []
                for _, r in d_pes.iterrows():
                    if esp_pes is not None and r["_pct"] >= esp_pes:
                        colors_pes.append(NAVY)
                    else:
                        colors_pes.append(G2_P)

                fig_pes = go.Figure()
                fig_pes.add_trace(go.Bar(
                    y=d_pes["territori"], x=d_pes["_pct"],
                    orientation="h",
                    marker_color=colors_pes,
                    text=[fpct(v, 1, sign=False) for v in d_pes["_pct"]],
                    textposition="outside",
                    textfont=dict(size=11, color=G1_P),
                ))

                if esp_pes is not None:
                    fig_pes.add_vline(
                        x=esp_pes, line_dash="dash", line_color=OCRE, line_width=2,
                        annotation_text=f"{'Espanya' if _ca else 'España'}: {fpct(esp_pes, 1, sign=False)}",
                        annotation_position="top right",
                    )

                apply_layout(fig_pes,
                    xaxis_title="% PIB",
                    height=max(450, len(d_pes) * 32 + 100),
                    margin=dict(l=200, r=100, t=50, b=50),
                )
                st.plotly_chart(fig_pes, use_container_width=True)
                if _ca:
                    source(
                        "Eurostat (comptabilitat regional G-I, <i>nama_10r_3gva</i> + VAB G47 nacional, <i>nama_10_a64</i>) "
                        "i INE (xifra de negoci CNAE 47 per CCAA, taula 76817). "
                        "Mètode: distribució proporcional híbrida (mitjana de quotes G-I i XN) "
                        "restringida al total nacional Eurostat"
                    )
                else:
                    source(
                        "Eurostat (contabilidad regional G-I, <i>nama_10r_3gva</i> + VAB G47 nacional, <i>nama_10_a64</i>) "
                        "e INE (cifra de negocio CNAE 47 por CCAA, tabla 76817). "
                        "Método: distribución proporcional híbrida (media de cuotas G-I y XN) "
                        "restringida al total nacional Eurostat"
                    )

                # Insight pes/PIB
                _top1 = d_pes.iloc[-1]
                _bot1 = d_pes.iloc[0]
                _above = d_pes[d_pes["_pct"] >= esp_pes] if esp_pes else d_pes
                _below = d_pes[d_pes["_pct"] < esp_pes] if esp_pes else pd.DataFrame()
                _spread = _top1["_pct"] - _bot1["_pct"]
                if _ca:
                    _txt_pes = (
                        f"<strong>{_top1['territori']}</strong> lidera amb un {fpct(_top1['_pct'], 1, sign=False)} del seu PIB "
                        f"dedicat al comerç al detall, gairebé el doble que <strong>{_bot1['territori']}</strong> "
                        f"({fpct(_bot1['_pct'], 1, sign=False)}). "
                    )
                    if esp_pes:
                        _txt_pes += (
                            f"<strong>{len(_above)}</strong> comunitats superen la mitjana nacional ({fpct(esp_pes, 1, sign=False)}) "
                            f"i <strong>{len(_below)}</strong> queden per sota. "
                        )
                    _txt_pes += (
                        "Les CCAA amb més pes del retail solen tenir economies orientades al consum final i al turisme, "
                        "mentre que les de menor pes tenen estructures més industrials o de serveis avancats."
                    )
                else:
                    _txt_pes = (
                        f"<strong>{_top1['territori']}</strong> lidera con un {fpct(_top1['_pct'], 1, sign=False)} de su PIB "
                        f"dedicado al comercio minorista, casi el doble que <strong>{_bot1['territori']}</strong> "
                        f"({fpct(_bot1['_pct'], 1, sign=False)}). "
                    )
                    if esp_pes:
                        _txt_pes += (
                            f"<strong>{len(_above)}</strong> comunidades superan la media nacional ({fpct(esp_pes, 1, sign=False)}) "
                            f"y <strong>{len(_below)}</strong> quedan por debajo. "
                        )
                    _txt_pes += (
                        "Las CCAA con mas peso del retail suelen tener economias orientadas al consumo final y al turismo, "
                        "mientras que las de menor peso tienen estructuras mas industriales o de servicios avanzados."
                    )
                insight(_txt_pes)

            # ── Mapa del pes ──
            d_map = df_ccaa[df_ccaa["any"] == any_sel].dropna(subset=["pes_cnae47_pib"]).copy()
            d_map["_pct"] = d_map["pes_cnae47_pib"] * 100

            if not d_map.empty:
                if _ca:
                    exhibit_header(2, f"Mapa del pes del comerç sobre el PIB per comunitat ({int(any_sel)})")
                else:
                    exhibit_header(2, f"Mapa del peso del comercio sobre el PIB por comunidad ({int(any_sel)})")
                fig_map = go.Figure(go.Choroplethmap(
                    geojson=geojson,
                    locations=d_map["territori"],
                    featureidkey="properties.territori",
                    z=d_map["_pct"],
                    zmin=d_map["_pct"].min() * 0.9,
                    zmax=d_map["_pct"].max() * 1.05,
                    colorscale=[
                        [0, "#ffffff"], [0.25, "#dde7f0"], [0.5, "#6985a8"],
                        [0.75, "#1f487a"], [1, "#003366"],
                    ],
                    colorbar=dict(title="% PIB", thickness=15),
                    marker=dict(line=dict(width=1.5, color="white")),
                    text=d_map["territori"],
                    hovertemplate="<b>%{text}</b><br>Pes CNAE 47: %{z:.1f}%<extra></extra>",
                ))
                fig_map.update_layout(
                    map=dict(
                        style="white-bg",
                        center=dict(lat=38.7, lon=-4.0),
                        zoom=4.55,
                        layers=canaries_inset_layers(),
                    ),
                    height=700, margin=dict(l=0, r=0, t=10, b=10),
                    dragmode=False,
                    annotations=[dict(
                        text="<b>CANÀRIES</b>" if _ca else "<b>CANARIAS</b>",
                        xref="paper", yref="paper",
                        x=0.18, y=0.18,
                        showarrow=False,
                        font=dict(size=10, color="#003366", family="Inter, sans-serif"),
                    )],
                )
                st.plotly_chart(fig_map, use_container_width=True,
                                config={"scrollZoom": False, "doubleClick": False, "displayModeBar": False})

        # ─── Exhibit 3: productivitat per CCAA ───────────────────────

        d_derived = df_ccaa[df_ccaa["any"] == any_sel].copy()
        if "xifra_negoci" in d_derived.columns and "personal_ocupat" in d_derived.columns:
            d_derived["prod_xn_ocupat"] = d_derived["xifra_negoci"] / d_derived["personal_ocupat"]
            d_prod = d_derived.dropna(subset=["prod_xn_ocupat"]).sort_values("prod_xn_ocupat", ascending=True)

            if not d_prod.empty:
                _pr_top = d_prod.iloc[-1]
                if _ca:
                    exhibit_header(
                        3, f"{_pr_top['territori']} lidera la facturació per ocupat "
                           f"({fnum(_pr_top['prod_xn_ocupat']/1000, 0)} k EUR) el {int(any_sel)}",
                        note="La línia ocre marca la mitjana espanyola.",
                    )
                else:
                    exhibit_header(
                        3, f"{_pr_top['territori']} lidera la facturación por ocupado "
                           f"({fnum(_pr_top['prod_xn_ocupat']/1000, 0)} k EUR) en {int(any_sel)}",
                        note="La línea ocre marca la media española.",
                    )

                fig_prod = go.Figure()
                fig_prod.add_trace(go.Bar(
                    y=d_prod["territori"], x=d_prod["prod_xn_ocupat"] / 1000,
                    orientation="h", marker_color=NAVY,
                    text=[f"{fnum(v/1000, 1)} k" for v in d_prod["prod_xn_ocupat"]],
                    textposition="outside", textfont=dict(size=11, color=G1_P),
                ))

                esp_row = df_esp[df_esp["any"] == any_sel]
                if not esp_row.empty and "xifra_negoci" in esp_row.columns:
                    esp_p = esp_row["xifra_negoci"].values[0] / esp_row["personal_ocupat"].values[0]
                    fig_prod.add_vline(
                        x=esp_p / 1000, line_dash="dash", line_color=OCRE, line_width=2,
                        annotation_text=f"{'Espanya' if _ca else 'España'}: {fnum(esp_p/1000, 1)} k",
                        annotation_position="top right",
                    )

                apply_layout(fig_prod,
                    xaxis_title=("Milers EUR / ocupat" if _ca else "Miles EUR / ocupado"),
                    height=max(450, len(d_prod) * 32 + 100),
                    margin=dict(l=200, r=100, t=50, b=50),
                )
                st.plotly_chart(fig_prod, use_container_width=True)
                source("INE, Enquesta Estructural d'Empreses. Calcul propi" if _ca
                       else "INE, Encuesta Estructural de Empresas. Calculo propio")

                # Insight productivitat
                _p_top = d_prod.iloc[-1]
                _p_bot = d_prod.iloc[0]
                _p_ratio = _p_top["prod_xn_ocupat"] / _p_bot["prod_xn_ocupat"]
                if _ca:
                    _txt_prod = (
                        f"La productivitat per ocupat varia un <strong>x{fnum(_p_ratio, 1)}</strong> entre "
                        f"<strong>{_p_top['territori']}</strong> ({fnum(_p_top['prod_xn_ocupat']/1000, 1)} k EUR) "
                        f"i <strong>{_p_bot['territori']}</strong> ({fnum(_p_bot['prod_xn_ocupat']/1000, 1)} k EUR). "
                        "Aquesta diferència reflecteix el tiquet mitja (producte de més o menys valor), "
                        "la presencia de grans cadenes (mes eficients en facturacio per treballador) "
                        "i el cost de vida de cada regio."
                    )
                else:
                    _txt_prod = (
                        f"La productividad por ocupado varia un <strong>x{fnum(_p_ratio, 1)}</strong> entre "
                        f"<strong>{_p_top['territori']}</strong> ({fnum(_p_top['prod_xn_ocupat']/1000, 1)} k EUR) "
                        f"y <strong>{_p_bot['territori']}</strong> ({fnum(_p_bot['prod_xn_ocupat']/1000, 1)} k EUR). "
                        "Esta diferencia refleja el ticket medio (producto de mas o menos valor), "
                        "la presencia de grandes cadenas (mas eficientes en facturacion por trabajador) "
                        "y el coste de vida de cada region."
                    )
                insight(_txt_prod)

# ════════════════════════════════════════════════════════════
# TAB 2: LOCALS PER PROVÍNCIA (DIRCE, taula 301)
# ════════════════════════════════════════════════════════════
with tab_prov:
    if df_lp.empty:
        st.info("No hi ha dades de locals per província." if _ca
                else "No hay datos de locales por provincia.")
    else:
        _lp_esp = df_lp[df_lp["nivell_geo"] == "espanya"].sort_values("any")
        _lp_prov = df_lp[df_lp["nivell_geo"] == "provincia"].copy()
        _anys_lp = sorted(int(a) for a in _lp_prov["any"].unique())
        _ly_lp = max(_anys_lp)
        _esp_ly = _lp_esp[_lp_esp["any"] == _ly_lp].iloc[0]

        # Empreses del mateix any, per no confondre locals amb empreses
        _emp_ly = None
        if not df_emp.empty and "empreses" in df_emp.columns:
            _e = df_emp[(df_emp["territori"] == "espanya") & (df_emp["any"] == _ly_lp)]
            if not _e.empty:
                _emp_ly = int(_e.iloc[0]["empreses"])

        # Variació des del trencament fins a l'últim any (comparable)
        _a0_hdr = _TB if _TB and _TB < _ly_lp else _anys_lp[0]
        _v = _lp_prov[_lp_prov["any"].isin([_a0_hdr, _ly_lp])].pivot_table(
            index="provincia", columns="any", values="locals_cnae47")
        _v["_pct"] = (_v[_ly_lp] / _v[_a0_hdr] - 1) * 100
        _v = _v.sort_values("_pct")
        _e0 = _lp_esp[_lp_esp["any"] == _a0_hdr].iloc[0]["locals_cnae47"]
        _esp_pct = (_esp_ly["locals_cnae47"] / _e0 - 1) * 100

        if _ca:
            action_title(f"{_ESP} compta {fnum(_esp_ly['locals_cnae47'])} locals de comerç al detall el {_ly_lp}")
            deck("Un local és un establiment físic: una cadena amb cent botigues compta cent locals"
                 + (f" i una sola empresa ({fnum(_emp_ly)} empreses el {_ly_lp})." if _emp_ly else "."))
            _tk = [
                f"Entre el {_a0_hdr} i el {_ly_lp}, {_ESP} passa de <b>{fnum(_e0)}</b> a "
                f"<b>{fnum(_esp_ly['locals_cnae47'])}</b> locals ({fpct(_esp_pct, 1)}).",
                f"Les províncies que més en perden són <b>{_v.index[0]}</b> ({fpct(_v['_pct'].iloc[0], 1)}), "
                f"<b>{_v.index[1]}</b> ({fpct(_v['_pct'].iloc[1], 1)}) i <b>{_v.index[2]}</b> "
                f"({fpct(_v['_pct'].iloc[2], 1)}).",
                f"Les que menys: <b>{_v.index[-1]}</b> ({fpct(_v['_pct'].iloc[-1], 1)}), "
                f"<b>{_v.index[-2]}</b> ({fpct(_v['_pct'].iloc[-2], 1)}) i <b>{_v.index[-3]}</b> "
                f"({fpct(_v['_pct'].iloc[-3], 1)}).",
            ]
            key_takeaways(_tk, label="Conclusions clau")
        else:
            action_title(f"{_ESP} cuenta con {fnum(_esp_ly['locals_cnae47'])} locales de comercio minorista en {_ly_lp}")
            deck("Un local es un establecimiento físico: una cadena con cien tiendas cuenta cien locales"
                 + (f" y una sola empresa ({fnum(_emp_ly)} empresas en {_ly_lp})." if _emp_ly else "."))
            _tk = [
                f"Entre {_a0_hdr} y {_ly_lp}, {_ESP} pasa de <b>{fnum(_e0)}</b> a "
                f"<b>{fnum(_esp_ly['locals_cnae47'])}</b> locales ({fpct(_esp_pct, 1)}).",
                f"Las provincias que más pierden son <b>{_v.index[0]}</b> ({fpct(_v['_pct'].iloc[0], 1)}), "
                f"<b>{_v.index[1]}</b> ({fpct(_v['_pct'].iloc[1], 1)}) y <b>{_v.index[2]}</b> "
                f"({fpct(_v['_pct'].iloc[2], 1)}).",
                f"Las que menos: <b>{_v.index[-1]}</b> ({fpct(_v['_pct'].iloc[-1], 1)}), "
                f"<b>{_v.index[-2]}</b> ({fpct(_v['_pct'].iloc[-2], 1)}) y <b>{_v.index[-3]}</b> "
                f"({fpct(_v['_pct'].iloc[-3], 1)}).",
            ]
            key_takeaways(_tk, label="Conclusiones clave")
        st.page_link("pages/2_Empreses.py",
                     label=("Veure el nombre d'empreses →" if _ca else "Ver el número de empresas →"))
        if _TB:
            st.caption(
                f"El DIRCE canvia de mètode el {_TB}: la variació {_TB - 1}→{_TB} no és comparable "
                f"i els nivells anteriors al {_TB} no es poden enfrontar directament als posteriors." if _ca else
                f"El DIRCE cambia de método en {_TB}: la variación {_TB - 1}→{_TB} no es comparable "
                f"y los niveles anteriores a {_TB} no pueden enfrentarse directamente a los posteriores.")

        sub_map, sub_rank, sub_evo = st.tabs([
            "Mapa",
            ("Rànquing" if _ca else "Ranking"),
            ("Evolució" if _ca else "Evolución"),
        ])

        # ── Mapa de densitat ──
        with sub_map:
            _any_map = st.select_slider(
                ("Any" if _ca else "Año"), options=_anys_lp, value=_ly_lp, key="terr_prov_any_map")
            _metric = st.radio(
                ("Mètrica" if _ca else "Métrica"), ["density", "absolute"],
                format_func=lambda x: (
                    ("Locals / 1.000 hab." if _ca else "Locales / 1.000 hab.") if x == "density"
                    else ("Locals (absolut)" if _ca else "Locales (absoluto)")),
                horizontal=True, key="terr_prov_metric")
            if _TB and _any_map < _TB:
                st.warning(
                    f"Any anterior al trencament de sèrie del {_TB}: aquests nivells no són comparables "
                    f"amb els del {_TB} i posteriors." if _ca else
                    f"Año anterior a la ruptura de serie de {_TB}: estos niveles no son comparables "
                    f"con los de {_TB} y posteriores.")
            _dm = _lp_prov[_lp_prov["any"] == _any_map].copy()
            if _metric == "density":
                _col, _lbl, _fmt = "locals_per_1000hab", ("Locals / 1.000 hab." if _ca else "Locales / 1.000 hab."), ".1f"
            else:
                _col, _lbl, _fmt = "locals_cnae47", ("Locals" if _ca else "Locales"), ",.0f"
            exhibit_header(
                1, (f"Locals de comerç al detall per província ({_any_map})" if _ca
                    else f"Locales de comercio minorista por provincia ({_any_map})"))
            fig_pm = go.Figure(go.Choroplethmap(
                geojson=load_geojson_prov(),
                locations=_dm["codi_geo"],
                featureidkey="properties.codi_prov",
                z=_dm[_col],
                colorscale=[
                    [0, "#ffffff"], [0.25, "#dde7f0"], [0.5, "#6985a8"],
                    [0.75, "#1f487a"], [1, "#003366"]],
                colorbar=dict(title=_lbl, thickness=15),
                marker=dict(line=dict(width=0.8, color="white")),
                text=_dm["provincia"],
                hovertemplate="<b>%{text}</b><br>" + f"{_lbl}: " + "%{z:" + _fmt + "}<extra></extra>",
            ))
            fig_pm.update_layout(
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
            st.plotly_chart(fig_pm, use_container_width=True,
                            config={"scrollZoom": False, "doubleClick": False, "displayModeBar": False})
            st.caption(
                "Ceuta i Melilla hi són, però a aquesta escala gairebé no es veuen: les seves xifres són al rànquing i a l'evolució." if _ca
                else "Ceuta y Melilla están incluidas, pero a esta escala apenas se ven: sus cifras están en el ranking y en la evolución.")
            source(f"{_SRC_DIRCE} (taula 301) i {_SRC_PADRO}. Mapa: © Instituto Geográfico Nacional (CC BY 4.0). "
                   + ("Càlcul propi" if _ca else "Cálculo propio"))

        # ── Rànquing de variació ──
        with sub_rank:
            _def0 = _TB if _TB and _TB < _ly_lp else _anys_lp[0]
            _a0, _a1 = st.select_slider(
                ("Període" if _ca else "Periodo"), options=_anys_lp,
                value=(_def0, _ly_lp), key="terr_prov_periode")
            if _a0 == _a1:
                st.info("Tria dos anys diferents." if _ca else "Elige dos años distintos.")
            else:
                _cross = bool(_TB and _a0 < _TB <= _a1)
                _r = _lp_prov[_lp_prov["any"].isin([_a0, _a1])].pivot_table(
                    index="provincia", columns="any", values="locals_cnae47")
                _r["_abs"] = _r[_a1] - _r[_a0]
                _r["_pct"] = (_r[_a1] / _r[_a0] - 1) * 100
                _r = _r.sort_values("_pct", ascending=True)
                if _cross:
                    st.warning(
                        f"El període travessa el trencament de sèrie del {_TB}: la variació barreja el canvi real "
                        f"amb el canvi de mètode i no s'ha de llegir com a evolució." if _ca else
                        f"El periodo cruza la ruptura de serie de {_TB}: la variación mezcla el cambio real "
                        f"con el cambio de método y no debe leerse como evolución.")
                exhibit_header(
                    2, (f"Variació dels locals per província, {_a0}-{_a1}" if _ca
                        else f"Variación de los locales por provincia, {_a0}-{_a1}"),
                    note=("Percentatge i diferència absoluta de locals." if _ca
                          else "Porcentaje y diferencia absoluta de locales."))
                _bar_col = G2_P if _cross else [NAVY if p < 0 else OCRE for p in _r["_pct"]]
                fig_rk = go.Figure(go.Bar(
                    y=_r.index, x=_r["_pct"], orientation="h",
                    marker_color=_bar_col,
                    hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
                ))
                # Etiquetes com a anotacions amb fons blanc: tapen la línia d'Espanya
                # quan la barra acaba a prop seu, en lloc de quedar-hi travessades.
                for _prov, p, a in zip(_r.index, _r["_pct"], _r["_abs"]):
                    fig_rk.add_annotation(
                        x=p, y=_prov, showarrow=False,
                        xanchor="right" if p < 0 else "left", xshift=-3 if p < 0 else 3,
                        text=f"{fpct(p, 1)} ({'+' if a > 0 else '−' if a < 0 else ''}{fnum(abs(a))})",
                        font=dict(size=10, color=G1_P), bgcolor="#ffffff", borderpad=1)
                _e_a0 = _lp_esp[_lp_esp["any"] == _a0].iloc[0]["locals_cnae47"]
                _e_a1 = _lp_esp[_lp_esp["any"] == _a1].iloc[0]["locals_cnae47"]
                _e_pct = (_e_a1 / _e_a0 - 1) * 100
                fig_rk.add_vline(x=_e_pct, line_dash="dash", line_color=OCRE, line_width=2,
                                 layer="below")
                fig_rk.add_annotation(
                    x=_e_pct, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                    text=f"{_ESP}: {fpct(_e_pct, 1)}", font=dict(size=11, color=OCRE))
                # Marge a banda i banda perquè les etiquetes de fora de la barra no es tallin
                _span = max(_r["_pct"].max(), 0) - min(_r["_pct"].min(), 0)
                apply_layout(fig_rk,
                    xaxis_title="%",
                    xaxis_range=[min(_r["_pct"].min(), 0) - _span * 0.25,
                                 max(_r["_pct"].max(), 0) + _span * 0.25],
                    height=max(600, len(_r) * 22 + 120),
                    margin=dict(l=190, r=40, t=60, b=50))
                st.plotly_chart(fig_rk, use_container_width=True)
                source(f"{_SRC_DIRCE} (taula 301). " + ("Càlcul propi" if _ca else "Cálculo propio"))

        # ── Evolució ──
        with sub_evo:
            _opts = [_ESP] + sorted(_lp_prov["provincia"].unique())
            _terr = st.selectbox(("Territori" if _ca else "Territorio"), _opts, key="terr_prov_evo")
            _s = (_lp_esp if _terr == _ESP else _lp_prov[_lp_prov["provincia"] == _terr]).sort_values("any")
            exhibit_header(
                3, (f"Evolució dels locals de comerç al detall: {_terr}" if _ca
                    else f"Evolución de los locales de comercio minorista: {_terr}"),
                note=(f"La línia discontínua uneix els dos anys del trencament de sèrie ({_TB - 1}-{_TB})." if _ca
                      else f"La línea discontinua une los dos años de la ruptura de serie ({_TB - 1}-{_TB}).") if _TB else None)
            _ce1, _ce2 = st.columns(2)
            for _cont, _col, _ttl, _fmt in (
                (_ce1, "locals_cnae47", ("Locals" if _ca else "Locales"), ",.0f"),
                (_ce2, "locals_per_1000hab", ("Locals / 1.000 hab." if _ca else "Locales / 1.000 hab."), ".1f"),
            ):
                fig_ev = go.Figure()
                _segs = ([_s[_s["any"] < _TB], _s[_s["any"] >= _TB]] if _TB else [_s])
                for _seg in _segs:
                    fig_ev.add_trace(go.Scatter(
                        x=_seg["any"], y=_seg[_col], mode="lines+markers",
                        line=dict(color=NAVY, width=2.5), marker=dict(size=5),
                        hovertemplate="%{x}: %{y:" + _fmt + "}<extra></extra>", showlegend=False))
                if _TB:
                    _pont = _s[_s["any"].isin([_TB - 1, _TB])]
                    fig_ev.add_trace(go.Scatter(
                        x=_pont["any"], y=_pont[_col], mode="lines",
                        line=dict(color=NAVY, width=2, dash="dash"),
                        hoverinfo="skip", showlegend=False))
                apply_layout(fig_ev, title=_ttl, height=380, margin=dict(l=60, r=20, t=50, b=40))
                _cont.plotly_chart(fig_ev, use_container_width=True)
            source(f"{_SRC_DIRCE} (taula 301) i {_SRC_PADRO}. " + ("Càlcul propi" if _ca else "Cálculo propio"))

# ════════════════════════════════════════════════════════════
# TAB 3: LOCALS PER SUBSECTOR (DIRCE, taula 294)
# ════════════════════════════════════════════════════════════
_GRUP_LBL = {
    "ca": {"47": "Total CNAE 47", "471": "471 No especialitzats", "472": "472 Alimentació",
           "473": "473 Carburants", "474": "474 Equips TIC", "475": "475 Llar",
           "476": "476 Cultura i lleure", "477": "477 Moda i altres", "478": "478 Mercadillos",
           "479": "479 Fora d'establiment"},
    "es": {"47": "Total CNAE 47", "471": "471 No especializados", "472": "472 Alimentación",
           "473": "473 Carburantes", "474": "474 Equipos TIC", "475": "475 Hogar",
           "476": "476 Cultura y ocio", "477": "477 Moda y otros", "478": "478 Mercadillos",
           "479": "479 Fuera de establecimiento"},
}
_MIN_LOCALS = 200

with tab_grup:
    if df_lg.empty:
        st.info("No hi ha dades de locals per subsector." if _ca
                else "No hay datos de locales por subsector.")
    else:
        _lbl_g = _GRUP_LBL["ca" if _ca else "es"]
        _anys_lg = sorted(int(a) for a in df_lg["any"].unique())
        _any_g = st.select_slider(("Any" if _ca else "Año"), options=_anys_lg,
                                  value=max(_anys_lg), key="terr_grup_any")
        _g = df_lg[df_lg["any"] == _any_g].copy()
        _g["_p100k"] = _g["locals"] / _g["poblacio"] * 1e5
        _g_esp = _g[_g["nivell_geo"] == "espanya"].set_index("cnae")["_p100k"]
        _g = _g[_g["nivell_geo"] != "espanya"]
        _g["_idx"] = _g.apply(lambda r: r["_p100k"] / _g_esp.get(r["cnae"]) * 100, axis=1)
        _g["_petit"] = _g["locals"] < _MIN_LOCALS

        _cols = [c for c in _lbl_g if c in set(_g["cnae"])]
        _rows = sorted(_g["ccaa"].unique(), reverse=True)
        _piv = lambda c: _g.pivot_table(index="ccaa", columns="cnae", values=c, aggfunc="first").reindex(index=_rows, columns=_cols)
        _idx, _p100k, _loc, _petit = _piv("_idx"), _piv("_p100k"), _piv("locals"), _piv("_petit").astype(bool)
        _idx_ok = _idx.where(~_petit)

        _vals = _idx_ok.stack()
        _mx, _mn = _vals.idxmax(), _vals.idxmin()
        if _ca:
            action_title(f"On pesa més cada tipus de botiga: densitat de locals per CCAA i subsector ({_any_g})")
            deck(f"Cada casella compara els locals per 100.000 habitants amb la mitjana d'{_ESP} "
                 "del mateix subsector (índex 100). Així es poden comparar subsectors de mida molt diferent.")
        else:
            action_title(f"Dónde pesa más cada tipo de tienda: densidad de locales por CCAA y subsector ({_any_g})")
            deck(f"Cada casilla compara los locales por 100.000 habitantes con la media de {_ESP} "
                 "del mismo subsector (índice 100). Así se pueden comparar subsectores de tamaño muy distinto.")

        exhibit_header(
            1, (f"Índex de densitat de locals per CCAA i subsector, {_ESP} = 100 ({_any_g})" if _ca
                else f"Índice de densidad de locales por CCAA y subsector, {_ESP} = 100 ({_any_g})"),
            note=(f"En gris, les caselles amb menys de {_MIN_LOCALS} locals: massa petites per comparar-les, "
                  "i fora del màxim i el mínim." if _ca else
                  f"En gris, las casillas con menos de {_MIN_LOCALS} locales: demasiado pequeñas para compararlas, "
                  "y fuera del máximo y el mínimo."))
        _x = [_lbl_g[c] for c in _cols]
        _hover = [[
            (f"<b>{r}</b><br>{_lbl_g[c]}<br>"
             + (f"Locals: {fnum(_loc.loc[r, c])}<br>" if _ca else f"Locales: {fnum(_loc.loc[r, c])}<br>")
             + f"{fnum(_p100k.loc[r, c], 1)} / 100.000 hab.<br>"
             + (f"Índex: {fnum(_idx.loc[r, c], 0)}" if not _petit.loc[r, c]
                else (f"Menys de {_MIN_LOCALS} locals" if _ca else f"Menos de {_MIN_LOCALS} locales")))
            for c in _cols] for r in _rows]
        fig_hm = go.Figure()
        fig_hm.add_trace(go.Heatmap(
            z=_idx_ok.values, x=_x, y=_rows,
            # Escala fixa 50-150: els extrems (mercadillos a Ceuta i Melilla) no aixafen la resta
            zmin=50, zmax=150, zmid=100,
            colorscale=[[0, OCRE_DEEP], [0.5, "#ffffff"], [1, NAVY]],
            colorbar=dict(title=("Índex" if _ca else "Índice"), thickness=15,
                          tickvals=[50, 75, 100, 125, 150], ticktext=["≤50", "75", "100", "125", "≥150"]),
            text=[[("" if _petit.loc[r, c] else fnum(_idx.loc[r, c], 0)) for c in _cols] for r in _rows],
            texttemplate="%{text}", textfont=dict(size=10),
            customdata=_hover, hovertemplate="%{customdata}<extra></extra>", xgap=2, ygap=2))
        fig_hm.add_trace(go.Heatmap(
            z=_petit.where(_petit).astype(float).values, x=_x, y=_rows,
            colorscale=[[0, "#b9c0c8"], [1, "#b9c0c8"]], showscale=False,
            customdata=_hover, hovertemplate="%{customdata}<extra></extra>", xgap=2, ygap=2))
        apply_layout(fig_hm, height=max(560, len(_rows) * 30 + 140),
                     margin=dict(l=210, r=40, t=120, b=30))
        fig_hm.update_xaxes(side="top", tickangle=-35)
        st.plotly_chart(fig_hm, use_container_width=True)
        source(f"{_SRC_DIRCE} (taula 294) i {_SRC_PADRO}. " + ("Càlcul propi" if _ca else "Cálculo propio"))

        if _ca:
            insight(
                f"La densitat relativa més alta és la de <strong>{_mx[0]}</strong> a "
                f"<strong>{_lbl_g[_mx[1]]}</strong> (índex {fnum(_vals.max(), 0)}); la més baixa, "
                f"la de <strong>{_mn[0]}</strong> a <strong>{_lbl_g[_mn[1]]}</strong> (índex {fnum(_vals.min(), 0)}).")
        else:
            insight(
                f"La densidad relativa más alta es la de <strong>{_mx[0]}</strong> en "
                f"<strong>{_lbl_g[_mx[1]]}</strong> (índice {fnum(_vals.max(), 0)}); la más baja, "
                f"la de <strong>{_mn[0]}</strong> en <strong>{_lbl_g[_mn[1]]}</strong> (índice {fnum(_vals.min(), 0)}).")

# ─── Taula ────────────────────────────────────────────────────

with st.expander(t("download_data")):
    for _df_dl, _nom, _fitxer in (
        (df_eee, ("Magnituds per CCAA (Estadística Estructural)" if _ca
                  else "Magnitudes por CCAA (Estadística Estructural)"), "territori_cnae47.csv"),
        (df_lp, ("Locals per província (DIRCE)" if _ca else "Locales por provincia (DIRCE)"), "locals_provincia.csv"),
        (df_lg, ("Locals per CCAA i subsector (DIRCE)" if _ca else "Locales por CCAA y subsector (DIRCE)"), "locals_ccaa_grups.csv"),
    ):
        if _df_dl.empty:
            continue
        st.markdown(f"**{_nom}**")
        st.dataframe(_df_dl, use_container_width=True)
        st.download_button("CSV", _df_dl.to_csv(index=False).encode("utf-8"),
                           _fitxer, "text/csv", key=f"dl_{_fitxer}")

page_meta("INE (Estadística Estructural, DIRCE i Padró) + Eurostat. Càlcul propi" if _ca
          else "INE (Estadística Estructural, DIRCE y Padrón) + Eurostat. Cálculo propio", st.session_state.lang)
