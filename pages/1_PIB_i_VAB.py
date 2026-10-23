"""Pàgina 1: PIB i Valor Afegit Brut (CNAE 47) — disseny premium consultora"""
import streamlit as st
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, cagr, highlight_expander, PALETTE,
    kicker, action_title, deck, key_takeaways, shock_stat, exhibit_header,
    metrics_band, premium_plotly_layout, freshness_badge,
    NAVY, OCRE, OCRE_DEEP, G1_P, G2_P,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()
_ca = st.session_state.lang == "ca"

_CHART_CONFIG = {"displayModeBar": False, "responsive": True}


df = load_dataset("pib_vab")

# ─── HEADER ──────────────────────────────────────────────────

kicker("Anàlisi estructural · PIB i VAB" if _ca else "Análisis estructural · PIB y VAB")

if df.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

df = df.sort_values("any")

# ─── Càlculs per a takeaways i shock stat ────────────────────

_df_nom = df.dropna(subset=["vab_cnae47_corrents"])
_df_both = df.dropna(subset=["vab_cnae47_corrents", "vab_cnae47_constants"])

_last_nom = _df_nom.iloc[-1]
_first_nom = _df_nom.iloc[0]
_last_both = _df_both.iloc[-1]
_first_both = _df_both.iloc[0]

_any_last = int(_last_nom["any"])
_any_first_nom = int(_first_nom["any"])
_any_first_real = int(_first_both["any"])

_n_nom = _any_last - _any_first_nom
_n_real = _any_last - _any_first_real

_var_nom = (_last_both["vab_cnae47_corrents"] / _first_both["vab_cnae47_corrents"] - 1) * 100
_var_real = (_last_both["vab_cnae47_constants"] / _first_both["vab_cnae47_constants"] - 1) * 100
_gap_pp = _var_nom - _var_real
_cagr_nom = cagr(_first_both["vab_cnae47_corrents"], _last_both["vab_cnae47_corrents"], _n_real)
_cagr_real = cagr(_first_both["vab_cnae47_constants"], _last_both["vab_cnae47_constants"], _n_real)

_df_pes = df.dropna(subset=["pes_cnae47"])
_pes_first = _df_pes.iloc[0]
_pes_last = _df_pes.iloc[-1]
_pes_any_first = int(_pes_first["any"])
_pes_any_last = int(_pes_last["any"])
_pes_drop_pp = (_pes_first["pes_cnae47"] - _pes_last["pes_cnae47"]) * 100

# Pitjor any de variació real (per a la nota de l'Exhibit 3)
_worst_year = _worst_drop = None
if "var_vab_cnae47_constants" in df.columns:
    _df_wr = df.dropna(subset=["var_vab_cnae47_constants"])
    if not _df_wr.empty:
        _wr = _df_wr.loc[_df_wr["var_vab_cnae47_constants"].idxmin()]
        _worst_year = int(_wr["any"])
        _worst_drop = _wr["var_vab_cnae47_constants"] * 100

if _ca:
    _takeaways = [
        f"Entre {_any_first_real} i {_any_last}, el VAB nominal ha crescut un "
        f"<b>{fpct(_var_nom, 1, sign=False)}</b> (CAGR {fpct(_cagr_nom, 1)}); "
        f"el real un <b>{fpct(_var_real, 1, sign=False)}</b> (CAGR {fpct(_cagr_real, 1)}).",
        f"La diferència de <b>{fnum(_gap_pp, 1)} punts percentuals</b> entre nominal i real "
        f"és l'efecte acumulat de la inflació: el sector creix en facturació però quasi no en riquesa real.",
        f"El pes de CNAE 47 sobre el PIB ha baixat del "
        f"<b>{fpct(_pes_first['pes_cnae47'] * 100, 1, sign=False)}</b> ({_pes_any_first}) "
        f"al <b>{fpct(_pes_last['pes_cnae47'] * 100, 1, sign=False)}</b> ({_pes_any_last}): "
        f"pèrdua estructural de pes en l'economia.",
    ]
    _tk_label = "Conclusions clau"
else:
    _takeaways = [
        f"Entre {_any_first_real} y {_any_last}, el VAB nominal ha crecido un "
        f"<b>{fpct(_var_nom, 1, sign=False)}</b> (CAGR {fpct(_cagr_nom, 1)}); "
        f"el real un <b>{fpct(_var_real, 1, sign=False)}</b> (CAGR {fpct(_cagr_real, 1)}).",
        f"La diferencia de <b>{fnum(_gap_pp, 1)} puntos porcentuales</b> entre nominal y real "
        f"es el efecto acumulado de la inflación: el sector crece en facturación pero casi nada en riqueza real.",
        f"El peso de CNAE 47 sobre el PIB ha bajado del "
        f"<b>{fpct(_pes_first['pes_cnae47'] * 100, 1, sign=False)}</b> ({_pes_any_first}) "
        f"al <b>{fpct(_pes_last['pes_cnae47'] * 100, 1, sign=False)}</b> ({_pes_any_last}): "
        f"pérdida estructural de peso en la economía.",
    ]
    _tk_label = "Conclusiones clave"

if _ca:
    action_title(f"El comerç ven com mai, però val menys que el {_any_first_nom}")
    deck(
        "La facturació del comerç al detall s'ha doblat en tres dècades. "
        "El valor real que crea, un cop descomptada la inflació, amb prou feines s'ha mogut."
    )
else:
    action_title(f"El comercio vende como nunca, pero vale menos que en {_any_first_nom}")
    deck(
        "La facturación del comercio minorista se ha duplicado en tres décadas. "
        "El valor real que crea, una vez descontada la inflación, apenas se ha movido."
    )

key_takeaways(_takeaways, label=_tk_label)
freshness_badge("pib_vab", st.session_state.lang)

# ─── TABS ────────────────────────────────────────────────────

_tabs_lbl = [
    "Espanya" if _ca else "España",
    "Comunitats autònomes" if _ca else "Comunidades autónomas",
]
tab1, tab2 = st.tabs(_tabs_lbl, default=tab_destinacio("pages/1_PIB_i_VAB.py", _tabs_lbl))

# ============================================================
# TAB 1: ESPANYA
# ============================================================
with tab1:

    # ─── Exhibit 1: VAB nominal vs real ──────────────────────
    if _ca:
        exhibit_header(
            1, "Dues trajectòries del VAB: nominal i real s'allunyen any rere any",
            note=(
                f"Les dues sèries arrenquen juntes cap al {_any_first_real} —l'any base "
                f"del deflactor— i s'allunyen any rere any. Tota la distància entre elles "
                f"és inflació acumulada sobre la xifra de negoci del sector."
            ),
        )
    else:
        exhibit_header(
            1, "Dos trayectorias del VAB: nominal y real se alejan año tras año",
            note=(
                f"Las dos series arrancan juntas hacia {_any_first_real} —el año base "
                f"del deflactor— y se alejan año tras año. Toda la distancia entre ellas "
                f"es inflación acumulada sobre la cifra de negocio del sector."
            ),
        )

    _nom_lbl = "Nominal"
    _real_lbl = "Real"

    df_nom = df.dropna(subset=["vab_cnae47_corrents"]).sort_values("any")
    df_real = df.dropna(subset=["vab_cnae47_constants"]).sort_values("any")

    fig1 = go.Figure()

    # 1. Real (ocre) — dibuixar primer per ancorar el fill
    if not df_real.empty:
        fig1.add_trace(go.Scatter(
            x=df_real["any"], y=df_real["vab_cnae47_constants"],
            mode="lines", name=_real_lbl,
            line=dict(color=OCRE, shape="spline", smoothing=0.5, width=3),
            hovertemplate=f"{_real_lbl}: <b>%{{y:,.0f}} M€</b><extra></extra>",
        ))

    # 2. Gap fill: nominal filtrat al rang del real, fill tonexty
    if not df_real.empty and not df_nom.empty:
        df_gap = df_nom[df_nom["any"].isin(df_real["any"])].copy()
        if not df_gap.empty:
            fig1.add_trace(go.Scatter(
                x=df_gap["any"], y=df_gap["vab_cnae47_corrents"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(176,125,43,0.10)",
                line=dict(color=NAVY, shape="spline", smoothing=0.5, width=0),
                showlegend=False,
                hoverinfo="skip",
            ))

    # 3. Nominal (navy) — sobre el fill
    if not df_nom.empty:
        fig1.add_trace(go.Scatter(
            x=df_nom["any"], y=df_nom["vab_cnae47_corrents"],
            mode="lines", name=_nom_lbl,
            line=dict(color=NAVY, shape="spline", smoothing=0.5, width=3),
            hovertemplate=f"{_nom_lbl}: <b>%{{y:,.0f}} M€</b><extra></extra>",
        ))

    # End markers
    _x_last = int(df_nom["any"].iloc[-1])
    _y_nom_last = float(df_nom["vab_cnae47_corrents"].iloc[-1])
    _x_real_last = int(df_real["any"].iloc[-1])
    _y_real_last = float(df_real["vab_cnae47_constants"].iloc[-1])

    fig1.add_trace(go.Scatter(
        x=[_x_last], y=[_y_nom_last],
        mode="markers", showlegend=False, hoverinfo="skip",
        marker=dict(color=NAVY, size=10, line=dict(color="white", width=2)),
    ))
    fig1.add_trace(go.Scatter(
        x=[_x_real_last], y=[_y_real_last],
        mode="markers", showlegend=False, hoverinfo="skip",
        marker=dict(color=OCRE, size=10, line=dict(color="white", width=2)),
    ))

    # End-label annotations
    _annots1 = [
        dict(
            x=_x_last, y=_y_nom_last, xanchor="left", xshift=14, yshift=8,
            showarrow=False, align="left",
            text=f"<b>{fnum(_y_nom_last)} M€</b><br>"
                 f"<span style='color:{G1_P}'>{_nom_lbl}</span>",
            font=dict(color=NAVY, size=13),
        ),
        dict(
            x=_x_real_last, y=_y_real_last, xanchor="left", xshift=14, yshift=-4,
            showarrow=False, align="left",
            text=f"<b>{fnum(_y_real_last)} M€</b><br>"
                 f"<span style='color:{G1_P}'>{_real_lbl}</span>",
            font=dict(color=OCRE_DEEP, size=13),
        ),
    ]

    _layout1 = premium_plotly_layout(height=480)
    _layout1["annotations"] = _annots1
    _layout1["yaxis"]["title"]["text"] = "M€"
    fig1.update_layout(**_layout1)

    st.plotly_chart(fig1, use_container_width=True, config=_CHART_CONFIG)
    source(
        "INE, Comptabilitat Nacional. Deflactor: IPC general, base 2002. Càlcul propi"
        if _ca else
        "INE, Contabilidad Nacional. Deflactor: IPC general, base 2002. Cálculo propio"
    )

    # ─── Shock stat ───────────────────────────────────────────
    if _ca:
        shock_stat(
            fnum(_gap_pp, 1), " pp",
            f"de diferència acumulada entre creixement nominal i real "
            f"({_any_first_real}–{_any_last}). "
            f"Tota aquella distància entre les dues línies és inflació "
            f"que va encarir el sector sense crear riquesa real.",
            sub="El titular nominal sobreestima el sector",
        )
    else:
        shock_stat(
            fnum(_gap_pp, 1), " pp",
            f"de diferencia acumulada entre crecimiento nominal y real "
            f"({_any_first_real}–{_any_last}). "
            f"Toda esa distancia entre las dos líneas es inflación "
            f"que encareció el sector sin crear riqueza real.",
            sub="El titular nominal sobreestima el sector",
        )

    # ─── Insight dinàmic ─────────────────────────────────────
    df_clean = df.dropna(subset=["vab_cnae47_corrents", "vab_cnae47_constants"])
    if len(df_clean) > 2:
        first_r = df_clean.iloc[0]
        last_r = df_clean.iloc[-1]
        n = int(last_r["any"]) - int(first_r["any"])

        var_nom_total = ((last_r["vab_cnae47_corrents"] / first_r["vab_cnae47_corrents"]) - 1) * 100
        var_real_total = ((last_r["vab_cnae47_constants"] / first_r["vab_cnae47_constants"]) - 1) * 100
        cagr_nom = cagr(first_r["vab_cnae47_corrents"], last_r["vab_cnae47_corrents"], n)
        cagr_real = cagr(first_r["vab_cnae47_constants"], last_r["vab_cnae47_constants"], n)
        gap = var_nom_total - var_real_total

        PIB_REF_REAL = 2.0
        if cagr_real > PIB_REF_REAL:
            _pos = "per damunt"
        elif cagr_real > 0:
            _pos = "per sota"
        else:
            _pos = "amb decreixement absolut respecte"

        if _ca:
            _verb_nom = "ha crescut" if var_nom_total > 0 else "s'ha contret"
            txt = (
                f"Entre {int(first_r['any'])} i {int(last_r['any'])}, el VAB nominal del comerç al detall "
                f"<strong>{_verb_nom}</strong> un "
                f"<strong>{fpct(var_nom_total, 1)}</strong> (CAGR {fpct(cagr_nom, 1)}), "
                f"i en termes reals la variació ha estat del <strong>{fpct(var_real_total, 1)}</strong> "
                f"(CAGR {fpct(cagr_real, 1)}). "
            )
            if gap > 10:
                txt += (
                    f"La diferència de <strong>{fpct(gap, 1, sign=False)}</strong> entre nominal i real "
                    f"és l'<strong>efecte acumulat de la inflació</strong>: una part del creixement aparent "
                    f"és simplement pujada de preus. "
                )
            _pos_map = {
                "per damunt": (
                    f"Amb un CAGR real del {fpct(cagr_real, 1)}, el sector creix <strong>per damunt</strong> "
                    f"del PIB general espanyol (~2% real), guanyant pes estructural."
                ),
                "per sota": (
                    f"Amb un CAGR real del {fpct(cagr_real, 1)}, el sector creix <strong>per sota</strong> "
                    f"del PIB general espanyol (~2% real), confirmant la <strong>pèrdua "
                    f"estructural de pes</strong> en l'economia. Factors explicatius: "
                    f"concentració empresarial, digitalització i canvi en patrons de consum."
                ),
                "amb decreixement absolut respecte": (
                    f"Amb un CAGR real negatiu del {fpct(cagr_real, 1)}, el sector es contreu en termes "
                    f"reals, amb pèrdua estructural de pes accelerada respecte al PIB general."
                ),
            }
            txt += _pos_map[_pos]
        else:
            _verb_nom = "ha crecido" if var_nom_total > 0 else "se ha contraído"
            txt = (
                f"Entre {int(first_r['any'])} y {int(last_r['any'])}, el VAB nominal del comercio minorista "
                f"<strong>{_verb_nom}</strong> un "
                f"<strong>{fpct(var_nom_total, 1)}</strong> (CAGR {fpct(cagr_nom, 1)}), "
                f"y en términos reales la variación ha sido del <strong>{fpct(var_real_total, 1)}</strong> "
                f"(CAGR {fpct(cagr_real, 1)}). "
            )
            if gap > 10:
                txt += (
                    f"La diferencia de <strong>{fpct(gap, 1, sign=False)}</strong> entre nominal y real "
                    f"es el <strong>efecto acumulado de la inflación</strong>: una parte del crecimiento "
                    f"aparente es simplemente subida de precios. "
                )
            _pos_map_es = {
                "per damunt": (
                    f"Con un CAGR real del {fpct(cagr_real, 1)}, el sector crece <strong>por encima</strong> "
                    f"del PIB general español (~2% real), ganando peso estructural."
                ),
                "per sota": (
                    f"Con un CAGR real del {fpct(cagr_real, 1)}, el sector crece <strong>por debajo</strong> "
                    f"del PIB general español (~2% real), confirmando la <strong>pérdida "
                    f"estructural de peso</strong> en la economía. Factores explicativos: "
                    f"concentración empresarial, digitalización y cambio en patrones de consumo."
                ),
                "amb decreixement absolut respecte": (
                    f"Con un CAGR real negativo del {fpct(cagr_real, 1)}, el sector se contrae en términos "
                    f"reales, con pérdida estructural de peso acelerada respecto al PIB general."
                ),
            }
            txt += _pos_map_es[_pos]
        insight(txt)

    # ─── Exhibit 2: Pes sobre PIB ─────────────────────────────
    if "pes_cnae47" in df.columns:
        if _ca:
            exhibit_header(
                2,
                f"El comerç al detall ha perdut {fnum(_pes_drop_pp, 1)} punts de pes "
                f"en el PIB des del {_pes_any_first}",
                note=(
                    "El sector creix, però més a poc a poc que la resta de l'economia. "
                    "Cada any que el PIB avança més de pressa, el comerç en perd pes relatiu."
                ),
            )
        else:
            exhibit_header(
                2,
                f"El comercio minorista ha perdido {fnum(_pes_drop_pp, 1)} puntos de peso "
                f"en el PIB desde {_pes_any_first}",
                note=(
                    "El sector crece, pero más despacio que el resto de la economía. "
                    "Cada año que el PIB avanza más rápido, el comercio pierde peso relativo."
                ),
            )

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=_df_pes["any"], y=_df_pes["pes_cnae47"] * 100,
            marker_color=NAVY,
            text=[fpct(v, 1, sign=False) for v in _df_pes["pes_cnae47"] * 100],
            textposition="outside",
            textfont=dict(size=10, color=G1_P, family="Manrope, system-ui, sans-serif"),
        ))
        _layout2 = premium_plotly_layout(height=380, margin_right=30, ytitle="%")
        _layout2["yaxis"]["rangemode"] = "normal"
        _layout2["yaxis"]["range"] = [0, float(_df_pes["pes_cnae47"].max() * 100) * 1.25]
        _layout2["yaxis"]["tickformat"] = ".1f"
        fig2.update_layout(**_layout2)
        st.plotly_chart(fig2, use_container_width=True, config=_CHART_CONFIG)
        source(
            "INE, Comptabilitat Nacional. Càlcul propi"
            if _ca else "INE, Contabilidad Nacional. Cálculo propio"
        )

    # ─── Variació anual (expander) ────────────────────────────
    _lbl_var_exp = ("Veure variació anual nominal i real"
                    if _ca else "Ver variación anual nominal y real")
    with highlight_expander(_lbl_var_exp, expanded=False):
        var_cols = [c for c in df.columns if c.startswith("var_")]
        if var_cols:
            if _worst_year is not None:
                _ex3_title_ca = f"La caiguda del {_worst_year} va ser la més forta de tota la sèrie"
                _ex3_title_es = f"La caída de {_worst_year} fue la más fuerte de toda la serie"
                _ex3_note_ca = (
                    f"La variació real anual mostra la fragilitat del sector: el {_worst_year} "
                    f"va restar un {fnum(abs(_worst_drop), 1)}% en un sol any, i el rebot "
                    f"posterior amb prou feines va recuperar el terreny perdut."
                )
                _ex3_note_es = (
                    f"La variación real anual muestra la fragilidad del sector: {_worst_year} "
                    f"restó un {fnum(abs(_worst_drop), 1)}% en un solo año, y el rebote "
                    f"posterior apenas recuperó el terreno perdido."
                )
            else:
                _ex3_title_ca = "Variació anual del VAB: nominal i real"
                _ex3_title_es = "Variación anual del VAB: nominal y real"
                _ex3_note_ca = _ex3_note_es = None
            if _ca:
                exhibit_header(3, _ex3_title_ca, note=_ex3_note_ca)
            else:
                exhibit_header(3, _ex3_title_es, note=_ex3_note_es)

            fig3 = go.Figure()
            _colors3 = {"var_vab_cnae47_corrents": NAVY, "var_vab_cnae47_constants": OCRE}
            for col in var_cols:
                df_var = df.dropna(subset=[col])
                _lbl3 = _nom_lbl if "corrents" in col else _real_lbl
                fig3.add_trace(go.Bar(
                    x=df_var["any"], y=df_var[col] * 100,
                    name=_lbl3,
                    marker_color=_colors3.get(col, G2_P),
                ))
            _layout3 = premium_plotly_layout(height=380, margin_right=30, ytitle="%")
            _layout3["showlegend"] = True
            _layout3["barmode"] = "group"
            _layout3["yaxis"]["rangemode"] = "normal"
            _layout3["yaxis"]["tickformat"] = ".1f"
            _layout3["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            fig3.update_layout(**_layout3)
            fig3.add_hline(y=0, line_dash="dash", line_color="rgba(0,0,0,0.15)")
            st.plotly_chart(fig3, use_container_width=True, config=_CHART_CONFIG)
            source(
                "INE, Comptabilitat Nacional. Càlcul propi"
                if _ca else "INE, Contabilidad Nacional. Cálculo propio"
            )

    # ─── Banda de mètriques (resum Espanya) ───────────────────
    _m_cagr_real = ("+" if _cagr_real >= 0 else "") + fnum(_cagr_real, 1)
    _m_cagr_nom = ("+" if _cagr_nom >= 0 else "") + fnum(_cagr_nom, 1)
    _m_nom = fnum(_last_nom["vab_cnae47_corrents"])
    _m_real = fnum(_last_both["vab_cnae47_constants"])
    _m_real_any = int(_last_both["any"])
    _m_pes = fnum(_pes_last["pes_cnae47"] * 100, 1)
    _m_pes_first = fnum(_pes_first["pes_cnae47"] * 100, 1)
    if _ca:
        metrics_band([
            (_m_nom, "M€", f"VAB nominal ({_any_last})"),
            (_m_real, "M€", f"VAB real ({_m_real_any})"),
            (_m_pes, "%", f"Pes sobre el PIB · {_m_pes_first}% el {_pes_any_first}"),
            (_m_cagr_real, "%", f"Creixement real anual · nominal {_m_cagr_nom}%"),
        ])
    else:
        metrics_band([
            (_m_nom, "M€", f"VAB nominal ({_any_last})"),
            (_m_real, "M€", f"VAB real ({_m_real_any})"),
            (_m_pes, "%", f"Peso sobre el PIB · {_m_pes_first}% en {_pes_any_first}"),
            (_m_cagr_real, "%", f"Crecimiento real anual · nominal {_m_cagr_nom}%"),
        ])

# ============================================================
# TAB 2: COMUNITATS AUTÒNOMES
# ============================================================
with tab2:
    if _ca:
        exhibit_header(1, "VAB nominal i real del comerç al detall per comunitat autònoma")
    else:
        exhibit_header(1, "VAB nominal y real del comercio minorista por comunidad autónoma")

    df_eee = load_dataset("eee_ccaa")

    _vab_nom_col = "vab_eurostat" if "vab_eurostat" in df_eee.columns else "vab_estimat_nominal"
    _vab_real_col = "vab_estimat"
    _has_vab = (
        not df_eee.empty
        and _vab_real_col in df_eee.columns
        and _vab_nom_col in df_eee.columns
    )

    if _has_vab:
        df_ccaa = df_eee[df_eee["territori"] != "espanya"].copy()
        ccaa_list = sorted(df_ccaa["territori"].unique())
        default_sel = [c for c in ["Cataluña", "Madrid (Comunidad de)", "Andalucía",
                                    "Comunitat Valenciana"] if c in ccaa_list]
        sel = st.multiselect(
            "Selecciona CCAA",
            ccaa_list, default=default_sel, key="vab_ccaa_sel",
        )
        if sel:
            fig_ccaa = go.Figure()
            for i, ccaa in enumerate(sel):
                dc = df_ccaa[df_ccaa["territori"] == ccaa].sort_values("any")
                color = PALETTE[i % len(PALETTE)]
                dc_nom = dc.dropna(subset=[_vab_nom_col])
                dc_real = dc.dropna(subset=[_vab_real_col])
                fig_ccaa.add_trace(go.Scatter(
                    x=dc_nom["any"], y=dc_nom[_vab_nom_col] / 1e6,
                    mode="lines+markers", name=f"{ccaa} (Nominal)",
                    line=dict(color=color, width=2),
                    marker=dict(size=5),
                    legendgroup=ccaa,
                ))
                fig_ccaa.add_trace(go.Scatter(
                    x=dc_real["any"], y=dc_real[_vab_real_col] / 1e6,
                    mode="lines+markers", name=f"{ccaa} (Real)",
                    line=dict(color=color, width=2, dash="dash"),
                    marker=dict(size=5, symbol="diamond"),
                    legendgroup=ccaa,
                ))
            _layout_ccaa = premium_plotly_layout(height=500, margin_right=30)
            _layout_ccaa["showlegend"] = True
            _layout_ccaa["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(family="Manrope, system-ui, sans-serif", size=12, color=G1_P),
                bgcolor="rgba(0,0,0,0)",
            )
            fig_ccaa.update_layout(**_layout_ccaa)
            st.plotly_chart(fig_ccaa, use_container_width=True, config=_CHART_CONFIG)
            source("INE + Eurostat. Estimació híbrida" if _ca
                   else "INE + Eurostat. Estimación híbrida")
    else:
        st.info("No hi ha dades regionals disponibles." if _ca
                else "No hay datos regionales disponibles.")

# ─── Descàrrega ───────────────────────────────────────────────

with st.expander(t("download_data")):
    st.dataframe(df, use_container_width=True)
    st.download_button("CSV", df.to_csv(index=False).encode("utf-8"),
                       "pib_vab_cnae47.csv", "text/csv")

page_meta(
    "INE, Comptabilitat Nacional d'Espanya" if _ca else "INE, Contabilidad Nacional de España",
    st.session_state.lang,
)
