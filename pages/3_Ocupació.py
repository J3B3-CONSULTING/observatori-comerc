"""Pàgina 3: Ocupació (CNAE 47) — volum/intensitat, salaris i perfil (sexe/edat)"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset, read_dataset
from navegacio import tab_destinacio
from style import (inject_css, inject_premium_page_css, setup_lang, page_header,
                   insight, intro, source, page_meta,
                   fnum, fpct, apply_layout, highlight_expander,
                   kicker, action_title, deck, key_takeaways, shock_stat,
                   exhibit_header, metrics_band, premium_plotly_layout, freshness_badge,
                   NAVY, OCRE, OCRE_DEEP, G1_P, G2_P)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"

@st.cache_data(ttl=3600)
def load_epa():
    d = read_dataset("epa_retail")
    if d.empty:
        return d
    # Inici de trimestre com a data, per a l'eix i per creuar amb l'any anterior
    d["data"] = pd.to_datetime(
        d["any"].astype(str) + "-" + ((d["trimestre"] - 1) * 3 + 1).astype(str) + "-01")
    return d.sort_values(["sexe", "data"])


df_prod = load_dataset("productivitat")
df_emp = load_dataset("empreses")
df_eaes = load_dataset("eaes")
df_epa = load_epa()
df_ocu = load_dataset("ocupacio_comerc")

kicker("Anàlisi estructural · Ocupació" if _ca else "Análisis estructural · Empleo")

# ─── Càlculs per a header, takeaways i shock stat ────────────
# Volum i intensitat (EEE)
_hd_ok = (not df_prod.empty and "personal_ocupat" in df_prod.columns
          and "hores_treballades" in df_prod.columns)
if _hd_ok:
    _hd = df_prod.sort_values("any")
    _hd_oc = _hd.dropna(subset=["personal_ocupat"])
    _hd_h = _hd.dropna(subset=["hores_treballades"])
    _hd_fy = int(_hd_oc.iloc[0]["any"])
    _hd_ly = int(_hd_oc.iloc[-1]["any"])
    _hd_var_oc = (_hd_oc.iloc[-1]["personal_ocupat"] / _hd_oc.iloc[0]["personal_ocupat"] - 1) * 100
    _hd_var_h = (_hd_h.iloc[-1]["hores_treballades"] / _hd_h.iloc[0]["hores_treballades"] - 1) * 100
    _hd_hpt_f = _hd_h.iloc[0]["hores_treballades"] / _hd_oc.iloc[0]["personal_ocupat"]
    _hd_hpt_l = _hd_h.iloc[-1]["hores_treballades"] / _hd_oc.iloc[-1]["personal_ocupat"]
    _hd_gap = _hd_var_h - _hd_var_oc  # punts: quant més creixen les hores que els caps

# Salaris (EAES)
_hd_sal_ok = False
if not df_eaes.empty:
    _hd_yr = int(df_eaes["any"].max())
    _hd_e = df_eaes[df_eaes["any"] == _hd_yr]
    _ST = "Industria, construcción y servicios (excepto actividades de los hogares como empleadores y de organizaciones y organismos extraterritoriales)"
    _SC = "Comercio al por mayor y al por menor; reparación de vehículos de motor y motocicletas"
    _hd_t = _hd_e[_hd_e["sector"] == _ST]
    _hd_c = _hd_e[_hd_e["sector"] == _SC]
    if not _hd_t.empty and not _hd_c.empty:
        _hd_vt = float(_hd_t["valor"].iloc[0])
        _hd_vc = float(_hd_c["valor"].iloc[0])
        _hd_sal_pct = (_hd_vc - _hd_vt) / _hd_vt * 100
        _hd_sal_ok = True

# Perfil: edat (Eurostat EU-LFS)
_hd_perf_ok = False
if not df_ocu.empty:
    _hd_pu = int(df_ocu["any"].max())
    _hd_pf = int(df_ocu["any"].min())

    def _hd_sen(p, y):
        a = df_ocu[(df_ocu["sexe"] == "Total") & (df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
        s = a.groupby("edat")["ocupats_milers"].sum()
        if not s.sum():
            return None
        return (s.get("50-59", 0) + s.get("60-64", 0) + s.get("65+", 0)) / s.sum() * 100

    def _hd_jove(p, y):
        a = df_ocu[(df_ocu["sexe"] == "Total") & (df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
        s = a.groupby("edat")["ocupats_milers"].sum()
        return (s.get("15-24", 0) / s.sum() * 100) if s.sum() else None

    def _hd_dones(p, y):
        b = df_ocu[(df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
        tot = b[b["sexe"] == "Total"]["ocupats_milers"].sum()
        don = b[b["sexe"] == "Dones"]["ocupats_milers"].sum()
        return (don / tot * 100) if tot else None

    _hd_sen_f = _hd_sen("ES", _hd_pf)
    _hd_sen_l = _hd_sen("ES", _hd_pu)
    _hd_jove_f = _hd_jove("ES", _hd_pf)
    _hd_jove_l = _hd_jove("ES", _hd_pu)
    _hd_dones_l = _hd_dones("ES", _hd_pu)
    _hd_perf_ok = _hd_sen_l is not None

# ─── HEADER ──────────────────────────────────────────────────
if _ca:
    if _hd_ok:
        action_title(
            f"El comerç afegeix hores ({fpct(_hd_var_h, 0)}), no ocupació "
            f"({fpct(_hd_var_oc, 0)}), des del {_hd_fy}"
        )
    else:
        action_title("Ocupació del comerç al detall")
    deck(
        "El sector intensifica la jornada de la plantilla existent més que no contracta, "
        "paga per sota de la mitjana i envelleix de pressa."
    )
else:
    if _hd_ok:
        action_title(
            f"El comercio añade horas ({fpct(_hd_var_h, 0)}), no empleo "
            f"({fpct(_hd_var_oc, 0)}), desde {_hd_fy}"
        )
    else:
        action_title("Empleo del comercio minorista")
    deck(
        "El sector intensifica la jornada de la plantilla existente más que contrata, "
        "paga por debajo de la media y envejece rápido."
    )

if _ca:
    _takeaways = []
    if _hd_ok:
        _takeaways.append(
            f"Entre {_hd_fy} i {_hd_ly}, les hores treballades creixen un "
            f"<b>{fpct(_hd_var_h, 1)}</b> i el personal ocupat només un "
            f"<b>{fpct(_hd_var_oc, 1)}</b>: la jornada per treballador puja de "
            f"<b>{fnum(_hd_hpt_f)}</b> a <b>{fnum(_hd_hpt_l)}</b> h/any."
        )
    if _hd_sal_ok:
        _takeaways.append(
            f"El sector comerç paga un <b>{fpct(abs(_hd_sal_pct), 1, sign=False)} menys</b> "
            f"que la mitjana de l'economia espanyola "
            f"(<b>{fnum(_hd_vc)}</b> vs {fnum(_hd_vt)} EUR, EAES {_hd_yr})."
        )
    if _hd_perf_ok:
        _takeaways.append(
            f"La plantilla envelleix: els 50 anys o més passen del "
            f"<b>{fpct(_hd_sen_f, 1, sign=False)}</b> ({_hd_pf}) al "
            f"<b>{fpct(_hd_sen_l, 1, sign=False)}</b> ({_hd_pu}), i els joves 15-24 cauen del "
            f"<b>{fpct(_hd_jove_f, 1, sign=False)}</b> al <b>{fpct(_hd_jove_l, 1, sign=False)}</b>."
        )
    _tk_label = "Conclusions clau"
else:
    _takeaways = []
    if _hd_ok:
        _takeaways.append(
            f"Entre {_hd_fy} y {_hd_ly}, las horas trabajadas crecen un "
            f"<b>{fpct(_hd_var_h, 1)}</b> y el personal ocupado solo un "
            f"<b>{fpct(_hd_var_oc, 1)}</b>: la jornada por trabajador sube de "
            f"<b>{fnum(_hd_hpt_f)}</b> a <b>{fnum(_hd_hpt_l)}</b> h/año."
        )
    if _hd_sal_ok:
        _takeaways.append(
            f"El sector comercio paga un <b>{fpct(abs(_hd_sal_pct), 1, sign=False)} menos</b> "
            f"que la media de la economía española "
            f"(<b>{fnum(_hd_vc)}</b> vs {fnum(_hd_vt)} EUR, EAES {_hd_yr})."
        )
    if _hd_perf_ok:
        _takeaways.append(
            f"La plantilla envejece: los 50 años o más pasan del "
            f"<b>{fpct(_hd_sen_f, 1, sign=False)}</b> ({_hd_pf}) al "
            f"<b>{fpct(_hd_sen_l, 1, sign=False)}</b> ({_hd_pu}), y los jóvenes 15-24 caen del "
            f"<b>{fpct(_hd_jove_f, 1, sign=False)}</b> al <b>{fpct(_hd_jove_l, 1, sign=False)}</b>."
        )
    _tk_label = "Conclusiones clave"

if _takeaways:
    key_takeaways(_takeaways, label=_tk_label)
freshness_badge(["ocupacio_comerc", "eaes"], st.session_state.lang)

_tabs_lbl = [
    ("Volum i intensitat" if _ca else "Volumen e intensidad"),
    ("Salaris" if _ca else "Salarios"),
    ("Perfil: sexe i edat" if _ca else "Perfil: sexo y edad"),
    ("Conjuntura trimestral (EPA)" if _ca else "Coyuntura trimestral (EPA)"),
]
tab_vol, tab_sal, tab_perfil, tab_epa = st.tabs(_tabs_lbl, default=tab_destinacio("pages/3_Ocupació.py", _tabs_lbl))

# ════════════════════════════════════════════════════════════
# TAB 1: VOLUM I INTENSITAT (personal ocupat, hores, treb/empresa)
# ════════════════════════════════════════════════════════════
with tab_vol:
    if _ca:
        intro(
            "El <strong>personal ocupat</strong> (persones que treballen al sector) i les "
            "<strong>hores treballades</strong> (volum total de treball efectiu) revelen la "
            "<strong>intensitat laboral</strong>: si l'ocupació creix més que les hores, augmenta "
            "la parcialitat; si les hores creixen més, s'intensifiquen les jornades. La ràtio de "
            "<strong>treballadors per empresa</strong> connecta l'ocupació amb l'estructura empresarial."
        )
    else:
        intro(
            "El <strong>personal ocupado</strong> (personas que trabajan en el sector) y las "
            "<strong>horas trabajadas</strong> (volumen total de trabajo efectivo) revelan la "
            "<strong>intensidad laboral</strong>: si el empleo crece más que las horas, aumenta "
            "la parcialidad; si las horas crecen más, se intensifican las jornadas. La ratio de "
            "<strong>trabajadores por empresa</strong> conecta el empleo con la estructura empresarial."
        )

    # ─── Ocupats i hores treballades ───
    if not df_prod.empty and "personal_ocupat" in df_prod.columns:
        df = df_prod.sort_values("any")

        first = df.dropna(subset=["personal_ocupat"]).iloc[0]
        last = df.dropna(subset=["personal_ocupat"]).iloc[-1]
        var_ocu = ((last["personal_ocupat"] / first["personal_ocupat"]) - 1) * 100

        if _ca:
            exhibit_header(
                1, f"El personal ocupat varia un {fpct(var_ocu, 1)} entre "
                   f"{int(first['any'])} i {int(last['any'])}",
                note="El nombre de persones al sector es manté gairebé pla; el moviment "
                     "rellevant és a les hores, no als caps.",
            )
        else:
            exhibit_header(
                1, f"El personal ocupado varía un {fpct(var_ocu, 1)} entre "
                   f"{int(first['any'])} y {int(last['any'])}",
                note="El número de personas en el sector se mantiene casi plano; el movimiento "
                     "relevante está en las horas, no en las cabezas.",
            )
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["any"], y=df["personal_ocupat"],
            mode="lines", name=t("kpi_ocupacio"),
            line=dict(color=NAVY, shape="spline", smoothing=0.5, width=3),
            fill="tozeroy", fillcolor="rgba(11,58,102,0.06)",
            hovertemplate="<b>%{y:,.0f}</b><extra></extra>"))
        _x_oc = int(df.dropna(subset=["personal_ocupat"])["any"].iloc[-1])
        _y_oc = float(df.dropna(subset=["personal_ocupat"])["personal_ocupat"].iloc[-1])
        fig.add_trace(go.Scatter(
            x=[_x_oc], y=[_y_oc], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(color=NAVY, size=10, line=dict(color="white", width=2))))
        _l1 = premium_plotly_layout(height=400, margin_right=120,
                                    ytitle=("Persones" if _ca else "Personas"))
        _l1["yaxis"]["rangemode"] = "normal"
        _l1["yaxis"]["range"] = [
            float(df["personal_ocupat"].min()) * 0.96,
            float(df["personal_ocupat"].max()) * 1.03,
        ]
        _l1["annotations"] = [dict(
            x=_x_oc, y=_y_oc, xanchor="left", xshift=14, showarrow=False, align="left",
            text=f"<b>{fnum(_y_oc)}</b><br><span style='color:{G1_P}'>{_x_oc}</span>",
            font=dict(color=NAVY, size=13))]
        fig.update_layout(**_l1)
        st.plotly_chart(fig, use_container_width=True)
        source("INE, Estadística Estructural d'Empreses (EEE)" if _ca
               else "INE, Estadística Estructural de Empresas (EEE)")

        if "hores_treballades" in df.columns:
            df_h2 = df.dropna(subset=["hores_treballades"])
            _vh = (df_h2.iloc[-1]["hores_treballades"] / df_h2.iloc[0]["hores_treballades"] - 1) * 100
            if _ca:
                exhibit_header(
                    2, f"Les hores treballades creixen un {fpct(_vh, 1)}: quatre vegades "
                       f"més que els caps",
                    note="El volum total de treball efectiu puja molt per sobre del nombre "
                         "de persones: el sector estira la jornada.",
                )
            else:
                exhibit_header(
                    2, f"Las horas trabajadas crecen un {fpct(_vh, 1)}: cuatro veces "
                       f"más que las cabezas",
                    note="El volumen total de trabajo efectivo sube muy por encima del número "
                         "de personas: el sector estira la jornada.",
                )
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df["any"], y=df["hores_treballades"] / 1e6,
                marker_color=NAVY,
                text=[f"{fnum(v / 1e6)}M" for v in df["hores_treballades"]],
                textposition="outside",
                textfont=dict(size=10, color=G1_P, family="Manrope, system-ui, sans-serif")))
            _l2 = premium_plotly_layout(
                height=400, margin_right=30,
                ytitle=("Milions d'hores" if _ca else "Millones de horas"))
            _l2["yaxis"]["rangemode"] = "normal"
            _l2["yaxis"]["range"] = [0, float(df["hores_treballades"].max() / 1e6) * 1.12]
            fig2.update_layout(**_l2)
            st.plotly_chart(fig2, use_container_width=True)
            source("INE, EEE")

            # Shock stat: intensificació de jornada
            if _hd_ok and _ca:
                shock_stat(
                    fpct(_hd_gap, 1), " pp",
                    f"de diferència entre el creixement de les hores ({fpct(_hd_var_h, 1)}) i el "
                    f"de l'ocupació ({fpct(_hd_var_oc, 1)}) entre {_hd_fy} i {_hd_ly}. "
                    f"El sector treballa més estirant la plantilla, no ampliant-la.",
                    sub="Intensificació de la jornada",
                )
            elif _hd_ok:
                shock_stat(
                    fpct(_hd_gap, 1), " pp",
                    f"de diferencia entre el crecimiento de las horas ({fpct(_hd_var_h, 1)}) y el "
                    f"del empleo ({fpct(_hd_var_oc, 1)}) entre {_hd_fy} y {_hd_ly}. "
                    f"El sector trabaja más estirando la plantilla, no ampliándola.",
                    sub="Intensificación de la jornada",
                )

        if "hores_treballades" in df.columns and "personal_ocupat" in df.columns:
            df["hores_per_treballador"] = df["hores_treballades"] / df["personal_ocupat"]
            _lbl_hpt_exp = ("Veure hores anuals per treballador" if _ca
                            else "Ver horas anuales por trabajador")
            with highlight_expander(_lbl_hpt_exp, expanded=False):
                _dfk = df.dropna(subset=["hores_per_treballador"])
                fig_hpt = go.Figure()
                fig_hpt.add_trace(go.Scatter(
                    x=_dfk["any"], y=_dfk["hores_per_treballador"],
                    mode="lines",
                    line=dict(color=OCRE, shape="spline", smoothing=0.5, width=3),
                    fill="tozeroy", fillcolor="rgba(176,125,43,0.07)",
                    hovertemplate="%{x}: <b>%{y:,.0f}</b> h<extra></extra>"))
                _lk = premium_plotly_layout(
                    height=380, margin_right=30,
                    ytitle=("Hores/any per treballador" if _ca else "Horas/año por trabajador"))
                _lk["yaxis"]["rangemode"] = "normal"
                _lk["yaxis"]["range"] = [
                    float(_dfk["hores_per_treballador"].min()) * 0.96,
                    float(_dfk["hores_per_treballador"].max()) * 1.04,
                ]
                fig_hpt.update_layout(**_lk)
                st.plotly_chart(fig_hpt, use_container_width=True)
                source("INE, EEE. Càlcul propi" if _ca else "INE, EEE. Cálculo propio")

        if "hores_treballades" in df.columns and "valor_afegit_constants" in df.columns and "xifra_negoci_constants" in df.columns:
            first_h = df.dropna(subset=["hores_treballades"]).iloc[0]
            last_h = df.dropna(subset=["hores_treballades"]).iloc[-1]
            var_h = ((last_h["hores_treballades"] / first_h["hores_treballades"]) - 1) * 100
            hpt_first = df.dropna(subset=["hores_per_treballador"]).iloc[0]["hores_per_treballador"]
            hpt_last = df.dropna(subset=["hores_per_treballador"]).iloc[-1]["hores_per_treballador"]
            any_f = int(first["any"])
            any_l = int(last["any"])
            _intensifica = var_h > var_ocu
            _hpt_creix = hpt_last > hpt_first
            if _ca:
                if _intensifica:
                    titol_bloc = "<strong>Més hores, no més contractació.</strong>"
                    lectura = (
                        "El sector ha optat per <strong>intensificar la jornada</strong> de la plantilla "
                        "existent abans que crear nous llocs de treball. La reforma laboral de 2022 — que va "
                        "limitar la temporalitat i va impulsar la conversió a contractes indefinits — ha "
                        "contribuït a aquest patró: menys rotació i més hores per treballador."
                    )
                else:
                    titol_bloc = "<strong>Més contractació, menys intensitat.</strong>"
                    lectura = (
                        "El sector ha optat per <strong>ampliar la plantilla</strong> més que intensificar "
                        "la jornada existent: la creació de nous llocs de treball ha anat per davant de "
                        "l'augment d'hores per treballador."
                    )
                verb_hpt = "ha passat" if _hpt_creix else "ha passat (a la baixa)"
                txt = (
                    f"{titol_bloc} "
                    f"Entre {any_f} i {any_l}, el personal ocupat ha variat un {fpct(var_ocu)}, "
                    f"mentre que les hores treballades han variat un {fpct(var_h)}. "
                    f"{lectura} "
                    f"La ràtio d'hores per treballador {verb_hpt} de {fnum(hpt_first)} a {fnum(hpt_last)} h/any."
                    f"<br><br>"
                    f"<strong>La contractació segueix el valor afegit, no la facturació.</strong> "
                    f"El valor afegit i el personal ocupat mostren trajectòries paral·leles, "
                    f"mentre que la xifra de negoci creix a un ritme diferent. "
                    f"Això suggereix que les decisions de contractació responen al <strong>valor net generat</strong> "
                    f"(descomptant costos intermedis), no al volum de vendes brut."
                )
            else:
                if _intensifica:
                    titol_bloc = "<strong>Más horas, no más contratación.</strong>"
                    lectura = (
                        "El sector ha optado por <strong>intensificar la jornada</strong> de la plantilla "
                        "existente antes que crear nuevos puestos de trabajo. La reforma laboral de 2022 — "
                        "que limitó la temporalidad e impulsó la conversión a contratos indefinidos — ha "
                        "contribuido a este patrón: menos rotación y más horas por trabajador."
                    )
                else:
                    titol_bloc = "<strong>Más contratación, menos intensidad.</strong>"
                    lectura = (
                        "El sector ha optado por <strong>ampliar la plantilla</strong> más que intensificar "
                        "la jornada existente: la creación de nuevos puestos ha ido por delante del "
                        "aumento de horas por trabajador."
                    )
                verb_hpt = "ha pasado" if _hpt_creix else "ha pasado (a la baja)"
                txt = (
                    f"{titol_bloc} "
                    f"Entre {any_f} y {any_l}, el personal ocupado ha variado un {fpct(var_ocu)}, "
                    f"mientras que las horas trabajadas han variado un {fpct(var_h)}. "
                    f"{lectura} "
                    f"La ratio de horas por trabajador {verb_hpt} de {fnum(hpt_first)} a {fnum(hpt_last)} h/año."
                    f"<br><br>"
                    f"<strong>La contratación sigue al valor añadido, no a la facturación.</strong> "
                    f"El valor añadido y el personal ocupado muestran trayectorias paralelas, "
                    f"mientras que la cifra de negocio crece a un ritmo diferente. "
                    f"Esto sugiere que las decisiones de contratación responden al <strong>valor neto generado</strong> "
                    f"(descontando costes intermedios), no al volumen de ventas bruto."
                )
            insight(txt)

    # ─── Treballadors per empresa ───
    df_esp = df_emp[df_emp["territori"] == "espanya"].sort_values("any") if not df_emp.empty else pd.DataFrame()

    if not df_prod.empty and not df_esp.empty and "personal_ocupat" in df_prod.columns:
        merged = df_prod[["any", "personal_ocupat"]].merge(df_esp[["any", "empreses"]], on="any")
        merged["treb_per_empresa"] = merged["personal_ocupat"] / merged["empreses"]

        _te_f0 = merged.iloc[0]["treb_per_empresa"] if len(merged) else None
        _te_l0 = merged.iloc[-1]["treb_per_empresa"] if len(merged) else None
        if _te_f0 is not None and _te_l0 is not None:
            _te_pj = _te_l0 > _te_f0
            if _ca:
                exhibit_header(
                    3, f"La dimensió mitjana {'puja' if _te_pj else 'baixa'} a "
                       f"{fnum(_te_l0, 1)} treballadors per empresa",
                    note="La ràtio connecta l'ocupació amb el cens d'empreses; reflecteix "
                         "el canvi d'escala del teixit comercial.",
                )
            else:
                exhibit_header(
                    3, f"La dimensión media {'sube' if _te_pj else 'baja'} a "
                       f"{fnum(_te_l0, 1)} trabajadores por empresa",
                    note="La ratio conecta el empleo con el censo de empresas; refleja "
                         "el cambio de escala del tejido comercial.",
                )
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=merged["any"], y=merged["treb_per_empresa"],
            mode="lines",
            line=dict(color=OCRE, shape="spline", smoothing=0.5, width=3),
            fill="tozeroy", fillcolor="rgba(176,125,43,0.07)",
            hovertemplate="%{x}: <b>%{y:.1f}</b><extra></extra>"))
        _l3 = premium_plotly_layout(
            height=400, margin_right=30,
            ytitle=("Treballadors / empresa" if _ca else "Trabajadores / empresa"))
        _l3["yaxis"]["rangemode"] = "normal"
        _l3["yaxis"]["range"] = [
            float(merged["treb_per_empresa"].min()) * 0.92,
            float(merged["treb_per_empresa"].max()) * 1.06,
        ]
        _l3["yaxis"]["tickformat"] = ".1f"
        fig3.update_layout(**_l3)
        st.plotly_chart(fig3, use_container_width=True)
        source("INE, EEE i DIRCE. Càlcul propi" if _ca else "INE, EEE y DIRCE. Cálculo propio")

        if len(merged) > 1:
            te_first = merged.iloc[0]["treb_per_empresa"]
            te_last = merged.iloc[-1]["treb_per_empresa"]
            _te_puja = te_last > te_first
            if _ca:
                if _te_puja:
                    lectura_te = (
                        "<strong>Que pugi indica que les empreses supervivents són més grans</strong>: "
                        "la concentració empresarial elimina petits comerços i deixa al sector "
                        "empreses amb plantilles més àmplies. Això té implicacions per a la "
                        "<strong>qualitat de l'ocupació</strong>: les empreses més grans solen "
                        "oferir millors condicions laborals, convenis col·lectius més favorables "
                        "i més oportunitats de promoció interna."
                    )
                else:
                    lectura_te = (
                        "<strong>Que baixi indica una atomització creixent</strong>: el sector guanya "
                        "empreses més que treballadors, reflectint l'entrada de microempreses, autònoms "
                        "i nous formats sense plantilla. Aquesta dinàmica pot indicar dinamisme "
                        "emprenedor però redueix l'escala mitjana i el poder negociador."
                    )
                insight(
                    f"La ràtio de treballadors per empresa ha passat de <strong>{fnum(te_first, 1)}</strong> "
                    f"({int(merged.iloc[0]['any'])}) a <strong>{fnum(te_last, 1)}</strong> "
                    f"({int(merged.iloc[-1]['any'])}). {lectura_te}"
                )
            else:
                if _te_puja:
                    lectura_te = (
                        "<strong>Que suba indica que las empresas supervivientes son más grandes</strong>: "
                        "la concentración empresarial elimina pequeños comercios y deja al sector "
                        "empresas con plantillas más amplias. Esto tiene implicaciones para la "
                        "<strong>calidad del empleo</strong>: las empresas más grandes suelen ofrecer "
                        "mejores condiciones laborales, convenios colectivos más favorables y más "
                        "oportunidades de promoción interna."
                    )
                else:
                    lectura_te = (
                        "<strong>Que baje indica una atomización creciente</strong>: el sector gana "
                        "empresas más que trabajadores, reflejando la entrada de microempresas, "
                        "autónomos y nuevos formatos sin plantilla. Esta dinámica puede indicar "
                        "dinamismo emprendedor, pero reduce la escala media y el poder negociador."
                    )
                insight(
                    f"La ratio de trabajadores por empresa ha pasado de <strong>{fnum(te_first, 1)}</strong> "
                    f"({int(merged.iloc[0]['any'])}) a <strong>{fnum(te_last, 1)}</strong> "
                    f"({int(merged.iloc[-1]['any'])}). {lectura_te}"
                )
    else:
        st.info("Dades insuficients per calcular treballadors per empresa." if _ca
                else "Datos insuficientes para calcular trabajadores por empresa.")

    # ─── Banda de mètriques (resum volum i intensitat) ───
    if _hd_ok:
        _mb_voc = ("+" if _hd_var_oc >= 0 else "") + fnum(_hd_var_oc, 1)
        _mb_vh = ("+" if _hd_var_h >= 0 else "") + fnum(_hd_var_h, 1)
        if _ca:
            metrics_band([
                (fnum(_hd_oc.iloc[-1]["personal_ocupat"]), "", f"Personal ocupat ({_hd_ly})"),
                (_mb_voc, "%", f"Variació ocupació {_hd_fy}–{_hd_ly}"),
                (_mb_vh, "%", f"Variació hores {_hd_fy}–{_hd_ly}"),
                (fnum(_hd_hpt_l), "h", f"Jornada anual · {fnum(_hd_hpt_f)} h el {_hd_fy}"),
            ])
        else:
            metrics_band([
                (fnum(_hd_oc.iloc[-1]["personal_ocupat"]), "", f"Personal ocupado ({_hd_ly})"),
                (_mb_voc, "%", f"Variación empleo {_hd_fy}–{_hd_ly}"),
                (_mb_vh, "%", f"Variación horas {_hd_fy}–{_hd_ly}"),
                (fnum(_hd_hpt_l), "h", f"Jornada anual · {fnum(_hd_hpt_f)} h en {_hd_fy}"),
            ])

# ════════════════════════════════════════════════════════════
# TAB 2: SALARIS (EAES, comerç vs total economia)
# ════════════════════════════════════════════════════════════
with tab_sal:
    if df_eaes.empty:
        st.info("Sense dades salarials disponibles." if _ca
                else "Sin datos salariales disponibles.")
    else:
        if _ca:
            st.markdown(
                "Per situar el sector en el conjunt de l'economia, fem servir l'**Enquesta Anual "
                "d'Estructura Salarial (EAES, taula INE 28185)**, que mesura el salari brut anual "
                "per treballador a jornada equivalent i és **consistent entre sectors**. "
                "Permet comparar el comerç amb la mitjana de l'economia espanyola."
            )
        else:
            st.markdown(
                "Para situar el sector en el conjunto de la economía, usamos la **Encuesta Anual "
                "de Estructura Salarial (EAES, tabla INE 28185)**, que mide el salario bruto anual "
                "por trabajador a jornada equivalente y es **consistente entre sectores**. "
                "Permite comparar el comercio con la media de la economía española."
            )

        _yr_eaes = int(df_eaes["any"].max())
        _eaes_last = df_eaes[df_eaes["any"] == _yr_eaes]
        SECTOR_TOTAL = "Industria, construcción y servicios (excepto actividades de los hogares como empleadores y de organizaciones y organismos extraterritoriales)"
        SECTOR_COMERCIO = "Comercio al por mayor y al por menor; reparación de vehículos de motor y motocicletas"

        _total = _eaes_last[_eaes_last["sector"] == SECTOR_TOTAL]
        _comer = _eaes_last[_eaes_last["sector"] == SECTOR_COMERCIO]

        if not _total.empty and not _comer.empty:
            _v_total = float(_total["valor"].iloc[0])
            _v_comer = float(_comer["valor"].iloc[0])
            _diff = _v_comer - _v_total
            _diff_pct = (_diff / _v_total) * 100

            if _ca:
                exhibit_header(
                    1, f"El sector comerç paga un {fpct(abs(_diff_pct), 1, sign=False)} menys "
                       f"que la mitjana de l'economia ({_yr_eaes})",
                    note="Salari brut anual per treballador a jornada equivalent; la xifra del "
                         "sector G inclou majorista i tendeix a sobreestimar el retail pur.",
                )
            else:
                exhibit_header(
                    1, f"El sector comercio paga un {fpct(abs(_diff_pct), 1, sign=False)} menos "
                       f"que la media de la economía ({_yr_eaes})",
                    note="Salario bruto anual por trabajador a jornada equivalente; la cifra del "
                         "sector G incluye mayorista y tiende a sobreestimar el retail puro.",
                )

            _lbl_total = "Total economia espanyola" if _ca else "Total economía española"
            _lbl_comer = "Sector comerç (G)" if _ca else "Sector comercio (G)"
            _comp = pd.DataFrame({
                "Categoria": [_lbl_total, _lbl_comer],
                "Valor": [_v_total, _v_comer],
                "Color": [G2_P, NAVY],
            })

            fig_c = go.Figure()
            fig_c.add_trace(go.Bar(
                y=_comp["Categoria"], x=_comp["Valor"], orientation="h",
                marker=dict(color=_comp["Color"]),
                text=[f"{fnum(v)} EUR" for v in _comp["Valor"]],
                textposition="outside", textfont=dict(size=13, color=G1_P),
                hovertemplate="<b>%{y}</b>: %{x:,.0f} EUR<extra></extra>", width=0.5))
            apply_layout(fig_c,
                xaxis_title="EUR / treballador / any" if _ca else "EUR / trabajador / año",
                height=240, margin=dict(l=220, r=120, t=20, b=50))
            st.plotly_chart(fig_c, use_container_width=True)
            source(f"INE, Encuesta Anual de Estructura Salarial (EAES), taula 28185 · {_yr_eaes}")

            _serie_total = df_eaes[df_eaes["sector"] == SECTOR_TOTAL].sort_values("any")
            _serie_comer = df_eaes[df_eaes["sector"] == SECTOR_COMERCIO].sort_values("any")

            if len(_serie_total) >= 3 and len(_serie_comer) >= 3:
                _lbl_evo = ("Veure evolució 2014-{:d}".format(_yr_eaes) if _ca
                            else "Ver evolución 2014-{:d}".format(_yr_eaes))
                with highlight_expander(_lbl_evo, expanded=False):
                    fig_evo = go.Figure()
                    fig_evo.add_trace(go.Scatter(
                        x=_serie_total["any"], y=_serie_total["valor"],
                        mode="lines+markers", name=_lbl_total,
                        line=dict(color=NAVY, width=2.8), marker=dict(size=7),
                        hovertemplate="<b>%{x}</b>: %{y:,.0f} EUR<extra></extra>"))
                    fig_evo.add_trace(go.Scatter(
                        x=_serie_comer["any"], y=_serie_comer["valor"],
                        mode="lines+markers", name=_lbl_comer,
                        line=dict(color=OCRE, width=2.8),
                        marker=dict(size=7, line=dict(color=OCRE_DEEP, width=1)),
                        hovertemplate="<b>%{x}</b>: %{y:,.0f} EUR<extra></extra>"))
                    apply_layout(fig_evo,
                        yaxis_title="EUR / treballador / any" if _ca else "EUR / trabajador / año",
                        height=380, margin=dict(l=70, r=20, t=40, b=50))
                    st.plotly_chart(fig_evo, use_container_width=True)
                    source(f"INE, EAES (taula 28185) · sèrie 2014-{_yr_eaes}")

            if _ca:
                insight(
                    f"Segons l'EAES de l'any {_yr_eaes}, el sector comerç (G45+G46+G47) paga "
                    f"un <strong>{fpct(abs(_diff_pct), 1, sign=False)} menys</strong> que la "
                    f"mitjana de l'economia espanyola: <strong>{fnum(_v_comer)} EUR vs "
                    f"{fnum(_v_total)} EUR</strong>. Aquesta diferència reflecteix el pes elevat "
                    f"d'ocupacions de menor qualificació i la presència de jornades parcials, "
                    f"especialment al comerç al detall G47. "
                    f"<br><br><em>Nota: l'EAES només publica el sector G complet (que inclou "
                    f"comerç majorista G45+G46 i venda i reparació de vehicles G45), no "
                    f"el CNAE 47 aïllat. La xifra del sector comerç de l'EAES tendeix a "
                    f"sobreestimar lleugerament el salari del retail estrictament G47 "
                    f"perquè el majorista paga més de mitjana.</em>"
                )
            else:
                insight(
                    f"Según la EAES del año {_yr_eaes}, el sector comercio (G45+G46+G47) paga "
                    f"un <strong>{fpct(abs(_diff_pct), 1, sign=False)} menos</strong> que la "
                    f"media de la economía española: <strong>{fnum(_v_comer)} EUR vs "
                    f"{fnum(_v_total)} EUR</strong>. Esta diferencia refleja el peso elevado "
                    f"de ocupaciones de menor cualificación y la presencia de jornadas parciales, "
                    f"especialmente en el comercio minorista G47. "
                    f"<br><br><em>Nota: la EAES solo publica el sector G completo (que incluye "
                    f"comercio mayorista G45+G46 y venta y reparación de vehículos G45), no "
                    f"el CNAE 47 aislado. La cifra del sector comercio de la EAES tiende a "
                    f"sobreestimar ligeramente el salario del retail estrictamente G47 "
                    f"porque el mayorista paga más de media.</em>"
                )

            # ─── Banda de mètriques (resum salaris) ───
            if _ca:
                metrics_band([
                    (fnum(_v_comer), "EUR", f"Salari sector comerç ({_yr_eaes})"),
                    (fnum(_v_total), "EUR", "Mitjana economia espanyola"),
                    (fnum(_diff_pct, 1), "%", "Diferència sobre la mitjana"),
                    (fnum(_diff), "EUR", "Bretxa anual per treballador"),
                ])
            else:
                metrics_band([
                    (fnum(_v_comer), "EUR", f"Salario sector comercio ({_yr_eaes})"),
                    (fnum(_v_total), "EUR", "Media economía española"),
                    (fnum(_diff_pct, 1), "%", "Diferencia sobre la media"),
                    (fnum(_diff), "EUR", "Brecha anual por trabajador"),
                ])

# ════════════════════════════════════════════════════════════
# TAB 3: PERFIL — sexe i edat (Eurostat EU-LFS)
# ════════════════════════════════════════════════════════════
with tab_perfil:
    if df_ocu.empty:
        st.info("Sense dades de perfil disponibles." if _ca
                else "Sin datos de perfil disponibles.")
    else:
        intro(
            ("Més enllà de quantes persones treballen al comerç, importa <strong>qui</strong> ho fa. "
             "Amb l'Enquesta de Població Activa europea (Eurostat, CNAE 47) radiografiem el sector per "
             "<strong>sexe</strong> i <strong>edat</strong>, i el comparem amb la UE-27. Dues preguntes: "
             "és un sector feminitzat? I es renova generacionalment o envelleix?"
             if _ca else
             "Más allá de cuántas personas trabajan en el comercio, importa <strong>quién</strong> lo hace. "
             "Con la Encuesta de Población Activa europea (Eurostat, CNAE 47) radiografiamos el sector por "
             "<strong>sexo</strong> y <strong>edad</strong>, y lo comparamos con la UE-27. Dos preguntas: "
             "¿es un sector feminizado? ¿Y se renueva generacionalmente o envejece?")
        )

        _ages = ["15-24", "25-39", "40-49", "50-59", "60-64", "65+"]
        # Rampa seqüencial jove (clar) -> gran (fosc), família navy de marca
        _RAMP = ["#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"]
        _ult = int(df_ocu["any"].max())
        _first = int(df_ocu["any"].min())

        def _wshare(p, y):
            b = df_ocu[(df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
            tot = b[b["sexe"] == "Total"]["ocupats_milers"].sum()
            don = b[b["sexe"] == "Dones"]["ocupats_milers"].sum()
            return (don / tot * 100) if tot else None

        def _ageshare(p, y, band):
            a = df_ocu[(df_ocu["sexe"] == "Total") & (df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
            s = a.groupby("edat")["ocupats_milers"].sum()
            return (s.get(band, 0) / s.sum() * 100) if s.sum() else None

        def _senshare(p, y):  # 50 anys o més
            a = df_ocu[(df_ocu["sexe"] == "Total") & (df_ocu["pais_codi"] == p) & (df_ocu["any"] == y)]
            s = a.groupby("edat")["ocupats_milers"].sum()
            if not s.sum():
                return None
            return (s.get("50-59", 0) + s.get("60-64", 0) + s.get("65+", 0)) / s.sum() * 100

        w_es, w_ue = _wshare("ES", _ult), _wshare("EU27_2020", _ult)
        jove_es, jove_ue = _ageshare("ES", _ult, "15-24"), _ageshare("EU27_2020", _ult, "15-24")
        sen_es, sen_first = _senshare("ES", _ult), _senshare("ES", _first)

        jove_first = _ageshare("ES", _first, "15-24")
        if _ca:
            metrics_band([
                (fpct(w_es, 1, sign=False), "", f"Dones al comerç · UE-27 {fpct(w_ue, 1, sign=False)}"),
                (fpct(jove_es, 1, sign=False), "", f"Joves 15-24 · {fpct(jove_first, 1, sign=False)} el {_first}"),
                (fpct(sen_es, 1, sign=False), "", f"50 anys o més · {fpct(sen_first, 1, sign=False)} el {_first}"),
            ])
        else:
            metrics_band([
                (fpct(w_es, 1, sign=False), "", f"Mujeres en el comercio · UE-27 {fpct(w_ue, 1, sign=False)}"),
                (fpct(jove_es, 1, sign=False), "", f"Jóvenes 15-24 · {fpct(jove_first, 1, sign=False)} en {_first}"),
                (fpct(sen_es, 1, sign=False), "", f"50 años o más · {fpct(sen_first, 1, sign=False)} en {_first}"),
            ])

        _sub_sexe, _sub_edat = st.tabs([
            ("Sexe" if _ca else "Sexo"),
            ("Edat: relleu generacional" if _ca else "Edad: relevo generacional"),
        ])

        with _sub_sexe:
            if _ca:
                exhibit_header(
                    1, f"Les dones són el {fpct(w_es, 1, sign=False)} dels ocupats al comerç, "
                       f"per sota de la UE-27 ({fpct(w_ue, 1, sign=False)})")
            else:
                exhibit_header(
                    1, f"Las mujeres son el {fpct(w_es, 1, sign=False)} de los ocupados del comercio, "
                       f"por debajo de la UE-27 ({fpct(w_ue, 1, sign=False)})")
            _piv = df_ocu.pivot_table(index=["pais_codi", "any"], columns="sexe",
                                      values="ocupats_milers", aggfunc="sum").reset_index()
            _piv["quota_dones"] = _piv["Dones"] / _piv["Total"] * 100
            figg = go.Figure()
            for _p, _col, _nm in [("ES", NAVY, ("Espanya" if _ca else "España")),
                                  ("EU27_2020", OCRE, "UE-27")]:
                _d = _piv[_piv["pais_codi"] == _p].sort_values("any")
                figg.add_trace(go.Scatter(
                    x=_d["any"], y=_d["quota_dones"], mode="lines+markers", name=_nm,
                    line=dict(color=_col, width=2.5), marker=dict(size=5)))
            apply_layout(figg, yaxis_title="% dones" if _ca else "% mujeres", height=380)
            st.plotly_chart(figg, use_container_width=True)
            source("Eurostat lfsa_egan22d (EU-LFS), CNAE G47")

        with _sub_edat:
            # (a) Evolució longitudinal de l'estructura d'edat a Espanya (àrea apilada 100%)
            if _ca:
                exhibit_header(
                    1, f"El pes dels 50 anys o més passa del {fpct(sen_first, 1, sign=False)} "
                       f"al {fpct(sen_es, 1, sign=False)} entre {_first} i {_ult}",
                    note="Estructura d'edat dels ocupats a Espanya en percentatge del total, "
                         "any rere any. Les franges fosques són les edats altes.",
                )
            else:
                exhibit_header(
                    1, f"El peso de los 50 años o más pasa del {fpct(sen_first, 1, sign=False)} "
                       f"al {fpct(sen_es, 1, sign=False)} entre {_first} y {_ult}",
                    note="Estructura de edad de los ocupados en España en porcentaje del total, "
                         "año tras año. Las franjas oscuras son las edades altas.",
                )
            _es = df_ocu[(df_ocu["sexe"] == "Total") & (df_ocu["pais_codi"] == "ES")]
            _pv = _es.pivot_table(index="any", columns="edat",
                                  values="ocupats_milers", aggfunc="sum")
            _pv = _pv.reindex(columns=_ages)
            _pvs = _pv.div(_pv.sum(axis=1), axis=0) * 100
            figL = go.Figure()
            for _b, _colr in zip(_ages, _RAMP):
                figL.add_trace(go.Scatter(
                    x=_pvs.index, y=_pvs[_b], mode="lines", name=_b,
                    stackgroup="one", line=dict(width=0.5, color=_colr), fillcolor=_colr))
            apply_layout(figL, yaxis_title="% dels ocupats" if _ca else "% de los ocupados",
                         height=400, yaxis_range=[0, 100])
            st.plotly_chart(figL, use_container_width=True)
            source("Eurostat lfsa_egan22d (EU-LFS), CNAE G47")

            # (b) Foto actual: Espanya vs UE-27 per franja
            if _ca:
                exhibit_header(
                    2, f"El comerç espanyol té menys joves 15-24 que la UE-27 "
                       f"({fpct(jove_es, 1, sign=False)} vs {fpct(jove_ue, 1, sign=False)}) el {_ult}")
            else:
                exhibit_header(
                    2, f"El comercio español tiene menos jóvenes 15-24 que la UE-27 "
                       f"({fpct(jove_es, 1, sign=False)} vs {fpct(jove_ue, 1, sign=False)}) en {_ult}")
            figa = go.Figure()
            for _p, _col, _nm in [("ES", NAVY, ("Espanya" if _ca else "España")),
                                  ("EU27_2020", OCRE, "UE-27")]:
                _ys = [_ageshare(_p, _ult, b) for b in _ages]
                figa.add_trace(go.Bar(x=_ages, y=_ys, name=_nm, marker_color=_col))
            apply_layout(figa, yaxis_title="% dels ocupats" if _ca else "% de los ocupados",
                         height=360, barmode="group")
            st.plotly_chart(figa, use_container_width=True)
            source("Eurostat lfsa_egan22d (EU-LFS), CNAE G47")

        insight(
            (f"El comerç és un <strong>sector feminitzat</strong> ({fpct(w_es, 1, sign=False)} de dones a Espanya, "
             f"lleugerament per sota de la UE-27, {fpct(w_ue, 1, sign=False)}), però <strong>envelleix de pressa</strong>. "
             f"El pes dels joves 15-24 ha caigut del {fpct(_ageshare('ES', _first, '15-24'), 1, sign=False)} ({_first}) "
             f"al {fpct(jove_es, 1, sign=False)} ({_ult}) —ara per sota de la UE-27 ({fpct(jove_ue, 1, sign=False)})—, "
             f"mentre el pes dels 50 anys o més ha pujat del {fpct(sen_first, 1, sign=False)} al {fpct(sen_es, 1, sign=False)}. "
             f"El <strong>relleu generacional és feble</strong>: cada cop entren menys joves i la plantilla es fa gran."
             if _ca else
             f"El comercio es un <strong>sector feminizado</strong> ({fpct(w_es, 1, sign=False)} de mujeres en España, "
             f"ligeramente por debajo de la UE-27, {fpct(w_ue, 1, sign=False)}), pero <strong>envejece rápido</strong>. "
             f"El peso de los jóvenes 15-24 ha caído del {fpct(_ageshare('ES', _first, '15-24'), 1, sign=False)} ({_first}) "
             f"al {fpct(jove_es, 1, sign=False)} ({_ult}) —ahora por debajo de la UE-27 ({fpct(jove_ue, 1, sign=False)})—, "
             f"mientras el peso de los 50 años o más ha subido del {fpct(sen_first, 1, sign=False)} al {fpct(sen_es, 1, sign=False)}. "
             f"El <strong>relevo generacional es débil</strong>: entran cada vez menos jóvenes y la plantilla envejece.")
        )

# ════════════════════════════════════════════════════════════
# TAB 4: CONJUNTURA TRIMESTRAL (EPA, INE)
# ════════════════════════════════════════════════════════════
with tab_epa:
    if df_epa.empty:
        st.info("Sense dades de l'EPA disponibles." if _ca
                else "Sin datos de la EPA disponibles.")
    else:
        if _ca:
            intro(
                "L'<strong>Enquesta de Població Activa</strong> (INE) dona el pols trimestral "
                "de l'ocupació, mentre que les altres pestanyes treballen amb dades anuals. "
                "La sèrie no està desestacionalitzada, i per això cada trimestre es compara "
                "amb el mateix trimestre de l'any anterior. Els <strong>ocupats</strong> són "
                "del comerç al detall (CNAE 47). Els <strong>aturats</strong> i les "
                "<strong>hores</strong> només es publiquen per a tot el sector comerç "
                "(secció G), que inclou també l'engròs i els vehicles."
            )
        else:
            intro(
                "La <strong>Encuesta de Población Activa</strong> (INE) da el pulso trimestral "
                "del empleo, mientras que las otras pestañas trabajan con datos anuales. "
                "La serie no está desestacionalizada, por eso cada trimestre se compara "
                "con el mismo trimestre del año anterior. Los <strong>ocupados</strong> son "
                "del comercio minorista (CNAE 47). Los <strong>parados</strong> y las "
                "<strong>horas</strong> solo se publican para todo el sector comercio "
                "(sección G), que incluye también el mayorista y los vehículos."
            )

        _ep = df_epa[df_epa["sexe"] == "total"].set_index("data").sort_index()
        _ep_dt = _ep.index.max()
        _ep_prev_dt = _ep_dt - pd.DateOffset(years=1)
        _ep_l = _ep.loc[_ep_dt]
        _ep_p = _ep.loc[_ep_prev_dt] if _ep_prev_dt in _ep.index else None
        _ep_lbl = f"T{int(_ep_l['trimestre'])} {int(_ep_l['any'])}"

        def _yoy(col):
            if _ep_p is None or pd.isna(_ep_p[col]) or not _ep_p[col]:
                return None
            return (float(_ep_l[col]) / float(_ep_p[col]) - 1) * 100

        _v_ocu = _yoy("ocupats_cnae47_milers")
        _v_atu = _yoy("aturats_seccio_g_milers")
        _d_hor = (float(_ep_l["hores_setmana_seccio_g"]) - float(_ep_p["hores_setmana_seccio_g"])
                  if _ep_p is not None else None)

        st.caption(("Darrera dada disponible: " if _ca else "Último dato disponible: ")
                   + _ep_lbl)
        _e1, _e2, _e3, _e4 = st.columns(4)
        with _e1:
            st.metric(("Ocupats comerç al detall (milers)" if _ca
                       else "Ocupados comercio minorista (miles)"),
                      fnum(float(_ep_l["ocupats_cnae47_milers"]), 1))
        with _e2:
            st.metric(("Variació anual ocupats" if _ca else "Variación anual ocupados"),
                      fpct(_v_ocu, 1) if _v_ocu is not None else "—")
        with _e3:
            st.metric(("Aturats sector comerç (milers)" if _ca
                       else "Parados sector comercio (miles)"),
                      fnum(float(_ep_l["aturats_seccio_g_milers"]), 1))
        with _e4:
            st.metric(("Hores setmanals per ocupat" if _ca
                       else "Horas semanales por ocupado"),
                      fnum(float(_ep_l["hores_setmana_seccio_g"]), 1))

        def _q_lbls(idx):
            return [f"T{(d.month - 1) // 3 + 1} {d.year}" for d in idx]

        # ─── Ex. 1: ocupats CNAE 47 per sexe ───
        if _v_ocu is not None:
            if _ca:
                _verb = "creix" if _v_ocu > 0 else ("cau" if _v_ocu < 0 else "no varia")
                exhibit_header(
                    1, f"L'ocupació del comerç al detall {_verb} un "
                       f"{fpct(abs(_v_ocu), 1, sign=False)} interanual el {_ep_lbl}",
                    note="Ocupats del comerç al detall (CNAE 47), en milers, per sexe.")
            else:
                _verb = "crece" if _v_ocu > 0 else ("cae" if _v_ocu < 0 else "no varía")
                exhibit_header(
                    1, f"El empleo del comercio minorista {_verb} un "
                       f"{fpct(abs(_v_ocu), 1, sign=False)} interanual en el {_ep_lbl}",
                    note="Ocupados del comercio minorista (CNAE 47), en miles, por sexo.")

        _sx_lbl = {
            "total": "Total",
            "dones": ("Dones" if _ca else "Mujeres"),
            "homes": ("Homes" if _ca else "Hombres"),
        }
        _sx_style = {
            "total": dict(color=NAVY, width=2.8),
            "dones": dict(color=OCRE_DEEP, width=2),
            "homes": dict(color=G2_P, width=2),
        }
        fig_epa = go.Figure()
        for _sx in ["total", "dones", "homes"]:
            _s = df_epa[df_epa["sexe"] == _sx].set_index("data").sort_index()
            fig_epa.add_trace(go.Scatter(
                x=_s.index, y=_s["ocupats_cnae47_milers"], mode="lines",
                name=_sx_lbl[_sx], line=_sx_style[_sx],
                customdata=_q_lbls(_s.index),
                hovertemplate=f"<b>{_sx_lbl[_sx]}</b><br>%{{customdata}}: %{{y:,.1f}}<extra></extra>"))
        apply_layout(fig_epa, yaxis_title=("Milers d'ocupats" if _ca else "Miles de ocupados"),
                     height=420, separators=",.")
        st.plotly_chart(fig_epa, use_container_width=True)
        source("INE, Encuesta de Población Activa (taula 65123), CNAE 47" if _ca
               else "INE, Encuesta de Población Activa (tabla 65123), CNAE 47")

        # ─── Ex. 2: aturats i hores, secció G ───
        if _v_atu is not None:
            if _ca:
                _verb_a = "baixa" if _v_atu < 0 else ("puja" if _v_atu > 0 else "no varia")
                exhibit_header(
                    2, f"L'atur del sector comerç {_verb_a} un "
                       f"{fpct(abs(_v_atu), 1, sign=False)} interanual el {_ep_lbl}",
                    note="Aturats segons el sector de la seva darrera feina (secció G: "
                         "detall, engròs i vehicles), en milers.")
            else:
                _verb_a = "baja" if _v_atu < 0 else ("sube" if _v_atu > 0 else "no varía")
                exhibit_header(
                    2, f"El paro del sector comercio {_verb_a} un "
                       f"{fpct(abs(_v_atu), 1, sign=False)} interanual en el {_ep_lbl}",
                    note="Parados según el sector de su último empleo (sección G: "
                         "minorista, mayorista y vehículos), en miles.")
        _lbl_ep = _q_lbls(_ep.index)
        fig_atu = go.Figure()
        fig_atu.add_trace(go.Scatter(
            x=_ep.index, y=_ep["aturats_seccio_g_milers"], mode="lines",
            name=("Aturats" if _ca else "Parados"),
            line=dict(color=NAVY, width=2.6),
            fill="tozeroy", fillcolor="rgba(11,58,102,0.06)",
            customdata=_lbl_ep,
            hovertemplate="%{customdata}: <b>%{y:,.1f}</b><extra></extra>"))
        apply_layout(fig_atu, yaxis_title=("Milers d'aturats" if _ca else "Miles de parados"),
                     height=380, showlegend=False, separators=",.")
        st.plotly_chart(fig_atu, use_container_width=True)
        source("INE, Encuesta de Población Activa (taula 65249), secció G" if _ca
               else "INE, Encuesta de Población Activa (tabla 65249), sección G")

        if _ca:
            exhibit_header(
                3, "Hores efectives setmanals per ocupat al sector comerç",
                note="Mitjana d'hores treballades de veritat la setmana de referència "
                     "(secció G). El tercer trimestre baixa cada any per les vacances.")
        else:
            exhibit_header(
                3, "Horas efectivas semanales por ocupado en el sector comercio",
                note="Media de horas realmente trabajadas en la semana de referencia "
                     "(sección G). El tercer trimestre baja cada año por las vacaciones.")
        fig_hor = go.Figure()
        fig_hor.add_trace(go.Scatter(
            x=_ep.index, y=_ep["hores_setmana_seccio_g"], mode="lines+markers",
            line=dict(color=OCRE_DEEP, width=2.2), marker=dict(size=4),
            customdata=_lbl_ep,
            hovertemplate="%{customdata}: <b>%{y:,.1f} h</b><extra></extra>"))
        apply_layout(fig_hor, yaxis_title=("Hores per setmana" if _ca else "Horas por semana"),
                     height=340, showlegend=False, separators=",.")
        st.plotly_chart(fig_hor, use_container_width=True)
        source("INE, Encuesta de Población Activa (taula 65159), secció G" if _ca
               else "INE, Encuesta de Población Activa (tabla 65159), sección G")

        if _v_ocu is not None and _v_atu is not None and _d_hor is not None:
            _ep_prev_lbl = f"T{int(_ep_l['trimestre'])} {int(_ep_l['any']) - 1}"
            if _ca:
                insight(
                    f"El <strong>{_ep_lbl}</strong>, el comerç al detall ocupa "
                    f"<strong>{fnum(float(_ep_l['ocupats_cnae47_milers']) / 1000, 2)} milions</strong> de "
                    f"persones, un <strong>{fpct(_v_ocu, 1)}</strong> respecte al {_ep_prev_lbl}. "
                    f"Al conjunt del sector comerç, els aturats varien un "
                    f"<strong>{fpct(_v_atu, 1)}</strong> i la jornada efectiva passa de "
                    f"{fnum(float(_ep_p['hores_setmana_seccio_g']), 1)} a "
                    f"{fnum(float(_ep_l['hores_setmana_seccio_g']), 1)} hores setmanals."
                )
            else:
                insight(
                    f"En el <strong>{_ep_lbl}</strong>, el comercio minorista ocupa a "
                    f"<strong>{fnum(float(_ep_l['ocupats_cnae47_milers']) / 1000, 2)} millones</strong> de "
                    f"personas, un <strong>{fpct(_v_ocu, 1)}</strong> respecto al {_ep_prev_lbl}. "
                    f"En el conjunto del sector comercio, los parados varían un "
                    f"<strong>{fpct(_v_atu, 1)}</strong> y la jornada efectiva pasa de "
                    f"{fnum(float(_ep_p['hores_setmana_seccio_g']), 1)} a "
                    f"{fnum(float(_ep_l['hores_setmana_seccio_g']), 1)} horas semanales."
                )

# ─── Descàrrega de dades ─────────────────────────────────────
with st.expander(t("download_data")):
    if not df_prod.empty:
        st.dataframe(df_prod, use_container_width=True)
        st.download_button("CSV", df_prod.to_csv(index=False).encode("utf-8"),
                           "ocupacio_cnae47.csv", "text/csv")

page_meta("INE (EEE, EAES) + Eurostat (EU-LFS)" if _ca
          else "INE (EEE, EAES) + Eurostat (EU-LFS)", st.session_state.lang)
