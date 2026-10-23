"""Pàgina: Líders del comerç (CNAE 47) — anatomia de la concentració.
Mostra de grans empreses (comptes del Registre Mercantil) + dinàmica de formats (ICM).
Es publiquen xifres absolutes i quotes: són fets públics del Registre Mercantil.
L'export verbatim del proveïdor de dades NO es redistribueix (queda al raw, gitignored)."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import load_dataset, read_dataset
from style import (inject_css, inject_premium_page_css, setup_lang, page_header,
                   insight, source, page_meta, fnum, fpct, apply_layout,
                   kicker, action_title, deck, key_takeaways, exhibit_header,
                   freshness_badge,
                   PALETTE, BRAND, RED, GRAY, GRAY_DARK,
                   NAVY, G2_P)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"
_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


@st.cache_data(ttl=3600)
def _sector_total():
    """Xifra de negoci total del sector CNAE 47 (EAS), últim any. Retorna (any, M€)."""
    e = read_dataset("subsectors_eas")
    if e.empty:
        return None, None
    e = e[e["codi"] == 47].sort_values("any")
    if e.empty:
        return None, None
    r = e.iloc[-1]
    return int(r["any"]), r["xifra_negoci"] / 1e6  # € -> M€


@st.cache_data(ttl=3600)
def _icm_modos():
    """Sèrie de l'índex de xifra de negoci per modo de distribució (ICM, nominal)."""
    d = read_dataset("icm_distribucion")
    if d.empty:
        return None
    ix = d[(d["indicador"] == "index") & (d["tipus"] == "nominal")].copy()
    ix["data"] = pd.to_datetime(ix["data"])
    base = ix[ix["any"] == 2016].groupby("modo")["valor"].mean()
    last = ix.sort_values("data").groupby("modo").tail(1).set_index("modo")
    va = d[(d["indicador"] == "var_anual") & (d["tipus"] == "nominal")].copy()
    va["data"] = pd.to_datetime(va["data"])
    rec = va[va["data"] >= va["data"].max() - pd.Timedelta(days=365)]
    var12 = rec.groupby("modo")["valor"].mean()
    return {"serie": ix, "base": base, "last": last, "var12": var12,
            "last_date": ix["data"].max()}


d = load_dataset("lideres_empreses")

kicker("Anatomia de la concentració · Líders del comerç" if _ca
       else "Anatomía de la concentración · Líderes del comercio")

if d.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

# ── Mètriques de concentració ──
d = d.sort_values("ing_2024", ascending=False).reset_index(drop=True)
ing = d["ing_2024"].dropna().values            # milers d'€
q = d["quota_2024"].dropna().values            # % sobre la mostra
cr1, cr4, cr10 = q[:1].sum(), q[:4].sum(), q[:10].sum()
hhi = (q ** 2).sum()
mostra_meur = ing.sum() / 1000                 # M€
lider_meur = ing[0] / 1000                     # M€
eas_any, sector_meur = _sector_total()
quota_lider_sector = (lider_meur / sector_meur * 100) if sector_meur else None
quota_mostra_sector = (mostra_meur / sector_meur * 100) if sector_meur else None

# quants competidors immediats supera el líder sumats
_lead = ing[0]; _cum = 0.0; _nbeat = 0
for v in ing[1:]:
    if _cum + v <= _lead:
        _cum += v; _nbeat += 1
    else:
        break
_ratio2 = f"{ing[0]/ing[1]:.1f}".replace(".", ",")  # vegades sobre el nº 2

_lider_nom = d["nombre"].iloc[0]
_n_grans = d["nombre"].nunique()
_un_de_cada = round(100 / quota_lider_sector) if quota_lider_sector else None

if _ca:
    action_title(
        f"Un sol operador concentra el {fpct(quota_lider_sector, 1, sign=False)} de tot el comerç al detall"
        if quota_lider_sector else
        f"El comerç al detall té un cap molt concentrat i una base molt fragmentada")
    deck("Els comptes del Registre Mercantil identifiquen els grans; el denominador EAS els situa "
         "sobre el sector. La bretxa real és entre el bloc dels grans i el petit comerç.")
    _takeaways = [
        f"<strong>{_lider_nom}</strong> representa el <b>{fpct(quota_lider_sector, 1, sign=False)}</b> "
        f"de tot el comerç minorista espanyol (EAS {eas_any}): aproximadament "
        f"<b>1 de cada {_un_de_cada} euros</b>."
        if quota_lider_sector else
        f"<strong>{_lider_nom}</strong> és el primer operador de la mostra de grans.",
        f"Els quatre majors (CR4) sumen el <b>{fpct(cr4, 1, sign=False)}</b> de la mostra i l'HHI és de "
        f"<b>{fnum(hhi)}</b>: una estructura concentrada al capdamunt.",
        f"Però els <b>{_n_grans} grans</b> són només el <b>{fpct(quota_mostra_sector, 1, sign=False)}</b> "
        f"del sector; la resta es reparteix entre desenes de milers d'empreses. La bretxa que importa "
        f"és grans vs petit comerç, no entre grans.",
    ]
    _tk_label = "Conclusions clau"
else:
    action_title(
        f"Un solo operador concentra el {fpct(quota_lider_sector, 1, sign=False)} de todo el comercio minorista"
        if quota_lider_sector else
        f"El comercio minorista tiene una cúspide muy concentrada y una base muy fragmentada")
    deck("Las cuentas del Registro Mercantil identifican a los grandes; el denominador EAS los sitúa "
         "sobre el sector. La brecha real es entre el bloque de los grandes y el pequeño comercio.")
    _takeaways = [
        f"<strong>{_lider_nom}</strong> representa el <b>{fpct(quota_lider_sector, 1, sign=False)}</b> "
        f"de todo el comercio minorista español (EAS {eas_any}): aproximadamente "
        f"<b>1 de cada {_un_de_cada} euros</b>."
        if quota_lider_sector else
        f"<strong>{_lider_nom}</strong> es el primer operador de la muestra de grandes.",
        f"Los cuatro mayores (CR4) suman el <b>{fpct(cr4, 1, sign=False)}</b> de la muestra y el HHI es de "
        f"<b>{fnum(hhi)}</b>: una estructura concentrada en la cúspide.",
        f"Pero los <b>{_n_grans} grandes</b> son solo el <b>{fpct(quota_mostra_sector, 1, sign=False)}</b> "
        f"del sector; el resto se reparte entre decenas de miles de empresas. La brecha que importa "
        f"es grandes vs pequeño comercio, no entre grandes.",
    ]
    _tk_label = "Conclusiones clave"

key_takeaways(_takeaways, label=_tk_label)
freshness_badge(["subsectors_eas", "icm_distribucion"], st.session_state.lang)

k1, k2, k3, k4 = st.columns(4)
k1.metric(("El líder, sobre el sector" if _ca else "El líder, sobre el sector"),
          fpct(quota_lider_sector, 1, sign=False) if quota_lider_sector else "—",
          help=(f"{d['nombre'].iloc[0]}: 1 de cada {round(100/quota_lider_sector)} € del comerç minorista espanyol (EAS {eas_any})"
                if _ca else
                f"{d['nombre'].iloc[0]}: 1 de cada {round(100/quota_lider_sector)} € del comercio minorista español (EAS {eas_any})"))
k2.metric(("Top 4 (dins la mostra)" if _ca else "Top 4 (dentro de la muestra)"),
          fpct(cr4, 1, sign=False),
          help=("CR4: pes dels 4 majors sobre la mostra de grans" if _ca else "CR4: peso de los 4 mayores sobre la muestra de grandes"))
k3.metric("HHI", f"{fnum(hhi)}",
          help=("Índex Herfindahl-Hirschman dins la mostra; >1.500 = concentrat, >2.500 = molt concentrat"
                if _ca else "Índice Herfindahl-Hirschman dentro de la muestra; >1.500 = concentrado, >2.500 = muy concentrado"))
k4.metric(("La mostra, sobre el sector" if _ca else "La muestra, sobre el sector"),
          fpct(quota_mostra_sector, 1, sign=False) if quota_mostra_sector else "—",
          help=(f"Els {len(d)} grans = {fpct(quota_mostra_sector,1,sign=False)} del sector; la resta, desenes de milers d'empreses"
                if _ca else
                f"Los {len(d)} grandes = {fpct(quota_mostra_sector,1,sign=False)} del sector; el resto, decenas de miles de empresas"))

st.caption(
    ("**CR4** = suma de la quota dels 4 operadors més grans. "
     "**HHI** (Herfindahl-Hirschman) = suma dels quadrats de les quotes de tot el mercat; "
     "rangs antitrust de referència (DOJ-EUA i Comissió Europea): <1.500 poc concentrat, "
     "1.500–2.500 moderadament concentrat, >2.500 molt concentrat."
     if _ca else
     "**CR4** = suma de la cuota de los 4 operadores más grandes. "
     "**HHI** (Herfindahl-Hirschman) = suma de los cuadrados de las cuotas de todo el mercado; "
     "rangos antitrust de referencia (DOJ-EUA y Comisión Europea): <1.500 poco concentrado, "
     "1.500–2.500 moderadamente concentrado, >2.500 muy concentrado.")
)

tab_conc, tab_din, tab_efi, tab_mostra = st.tabs([
    ("Concentració" if _ca else "Concentración"),
    ("Dinàmica per formats" if _ca else "Dinámica por formatos"),
    ("Rendibilitat i creixement" if _ca else "Rentabilidad y crecimiento"),
    ("La mostra completa" if _ca else "La muestra completa"),
])

# ── TAB 1: CONCENTRACIÓ ──
with tab_conc:
    exhibit_header(
        1,
        ("Els grans operadors per facturació (2024, M€)" if _ca
         else "Los grandes operadores por facturación (2024, M€)"),
        note=("Un sol operador domina el conjunt de la mostra de grans." if _ca
              else "Un solo operador domina el conjunto de la muestra de grandes."))
    top = d.dropna(subset=["ing_2024"]).head(15).copy()
    top = top.sort_values("ing_2024")  # ascendent: el major queda a dalt
    top["meur"] = top["ing_2024"] / 1000
    colors = [NAVY if i == len(top) - 1 else "rgba(11,58,102,0.30)" for i in range(len(top))]
    figc = go.Figure(go.Bar(
        y=top["nombre"], x=top["meur"], orientation="h", marker_color=colors,
        text=[fnum(v) for v in top["meur"]], textposition="outside", textfont=dict(size=11),
        customdata=top["quota_2024"],
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} M€<br>%{customdata:.1f}% de la mostra<extra></extra>"))
    apply_layout(figc, xaxis_title="Facturació 2024 (M€)" if _ca else "Facturación 2024 (M€)",
                 height=560, margin=dict(l=160, r=80, t=20, b=40), showlegend=False)
    st.plotly_chart(figc, use_container_width=True)
    source("Comptes dipositats al Registre Mercantil . Càlcul propi" if _ca
           else "Cuentas depositadas en el Registro Mercantil . Cálculo propio")
    st.caption(("**Per què no hi surt Inditex?** El perímetre és el CNAE 47 (comerç al detall). Inditex SA és "
                "el grup tèxtil consolidat (fabricació + majorista), no una empresa de comerç al detall: incloure'l "
                "barrejaria verticals i duplicaria, perquè les seves cadenes de botigues a Espanya (Bershka, "
                "Stradivarius…) ja compten dins el sector i hi surten pel seu compte. Un rànquing que el posa al "
                "capdamunt no és comparable amb una mostra neta de CNAE 47."
                if _ca else
                "**¿Por qué no aparece Inditex?** El perímetro es el CNAE 47 (comercio minorista). Inditex SA es "
                "el grupo textil consolidado (fabricación + mayorista), no una empresa de comercio minorista: incluirlo "
                "mezclaría verticales y duplicaría, porque sus cadenas de tiendas en España (Bershka, Stradivarius…) "
                "ya cuentan dentro del sector y aparecen por su cuenta. Un ranking que lo sitúa en lo más alto no es "
                "comparable con una muestra limpia de CNAE 47."))

    c1, c2, c3 = st.columns(3)
    c1.metric(("Quota del líder (mostra)" if _ca else "Cuota del líder (muestra)"), fpct(cr1, 1, sign=False))
    c2.metric("CR10", fpct(cr10, 1, sign=False),
              help=("els 10 majors sobre la mostra" if _ca else "los 10 mayores sobre la muestra"))
    c3.metric(("Líder vs nº 2" if _ca else "Líder vs nº 2"), f"{ing[0]/ing[1]:.1f}×".replace(".", ","))
    insight(
        (f"<strong>{d['nombre'].iloc[0]}</strong> sol factura <strong>{fpct(cr1,1,sign=False)}</strong> de tota la mostra de "
         f"grans i representa el <strong>{fpct(quota_lider_sector,1,sign=False)} de tot el comerç minorista espanyol</strong> "
         f"(EAS {eas_any}): aproximadament <strong>1 de cada {round(100/quota_lider_sector)} euros</strong>. Factura més que "
         f"els <strong>{_nbeat} operadors següents plegats</strong> i {_ratio2}× el segon. "
         f"Els quatre primers (CR4) sumen el {fpct(cr4,1,sign=False)} i l'HHI és de {fnum(hhi)}: una "
         f"estructura concentrada al capdamunt, encara que la mostra només sigui el {fpct(quota_mostra_sector,1,sign=False)} del sector."
         if _ca else
         f"<strong>{d['nombre'].iloc[0]}</strong> factura por sí sola el <strong>{fpct(cr1,1,sign=False)}</strong> de toda la muestra de "
         f"grandes y representa el <strong>{fpct(quota_lider_sector,1,sign=False)} de todo el comercio minorista español</strong> "
         f"(EAS {eas_any}): aproximadamente <strong>1 de cada {round(100/quota_lider_sector)} euros</strong>. Factura más que "
         f"los <strong>{_nbeat} operadores siguientes juntos</strong> y {_ratio2}× el segundo. "
         f"Los cuatro primeros (CR4) suman el {fpct(cr4,1,sign=False)} y el HHI es de {fnum(hhi)}: una "
         f"estructura concentrada en la cúspide, aunque la muestra sea solo el {fpct(quota_mostra_sector,1,sign=False)} del sector.")
    )
    st.caption(("Quota dins la mostra = sobre els grans del gràfic. Quota sobre el sector = sobre la xifra de negoci "
                f"total del CNAE 47 (EAS {eas_any}). No són el mateix; les distingim sempre."
                if _ca else
                "Cuota dentro de la muestra = sobre los grandes del gráfico. Cuota sobre el sector = sobre la cifra de negocio "
                f"total del CNAE 47 (EAS {eas_any}). No son lo mismo; las distinguimos siempre."))

    # ── Dinàmica de la concentració 2020 → 2024 (mateix conjunt d'operadors) ──
    st.markdown("---")
    dyn = d.dropna(subset=["ing_2020", "ing_2024"]).copy()

    def _conc_shares(col):
        v = np.sort(dyn[col].values)[::-1]
        sh = v / v.sum() * 100
        return sh[0], sh[:4].sum(), sh[:10].sum(), (sh ** 2).sum()

    cr1_20, cr4_20, cr10_20, hhi_20 = _conc_shares("ing_2020")
    cr1_24c, cr4_24c, cr10_24c, hhi_24c = _conc_shares("ing_2024")

    exhibit_header(
        2,
        ("Evolució de la concentració, 2020–2024" if _ca
         else "Evolución de la concentración, 2020–2024"),
        note=(f"Comparem el mateix grup de {len(dyn)} grans operadors el 2020 i el 2024." if _ca
              else f"Comparamos el mismo grupo de {len(dyn)} grandes operadores en 2020 y 2024."))
    _lbl = ["Líder", "CR4", "CR10"]
    _y20 = [cr1_20, cr4_20, cr10_20]
    _y24 = [cr1_24c, cr4_24c, cr10_24c]
    figdin = go.Figure()
    figdin.add_trace(go.Bar(name="2020", x=_lbl, y=_y20, marker_color=G2_P,
                            text=[fpct(v, 1, sign=False) for v in _y20], textposition="outside", textfont=dict(size=11)))
    figdin.add_trace(go.Bar(name="2024", x=_lbl, y=_y24, marker_color=NAVY,
                            text=[fpct(v, 1, sign=False) for v in _y24], textposition="outside", textfont=dict(size=11)))
    apply_layout(figdin, yaxis_title="% sobre la mostra de grans" if _ca else "% sobre la muestra de grandes",
                 height=340, margin=dict(l=50, r=20, t=20, b=40))
    figdin.update_layout(barmode="group")
    figdin.update_yaxes(range=[0, 88])
    st.plotly_chart(figdin, use_container_width=True)
    insight(
        (f"Les tres mesures de concentració <strong>baixen lleugerament</strong> entre 2020 i 2024 "
         f"(l'HHI passa de {fnum(hhi_20)} a {fnum(hhi_24c)}): el grup de grans no s'està concentrant més. "
         "<strong>La separació principal no és entre grans, sinó entre el bloc dels grans i el petit comerç</strong> "
         "(vegeu «Dinàmica per formats»)."
         if _ca else
         f"Las tres medidas de concentración <strong>bajan ligeramente</strong> entre 2020 y 2024 "
         f"(el HHI pasa de {fnum(hhi_20)} a {fnum(hhi_24c)}): el grupo de grandes no se está concentrando más. "
         "<strong>La separación principal no es entre grandes, sino entre el bloque de los grandes y el pequeño comercio</strong> "
         "(véase «Dinámica por formatos»).")
    )
    st.caption((f"Panell constant de {len(dyn)} operadors amb comptes els dos anys; per això les xifres difereixen "
                "lleugerament de les de dalt, calculades sobre la mostra completa."
                if _ca else
                f"Panel constante de {len(dyn)} operadores con cuentas en ambos años; por eso las cifras difieren "
                "ligeramente de las de arriba, calculadas sobre la muestra completa."))

# ── TAB 2: DINÀMICA PER FORMATS (ICM) ──
with tab_din:
    icm = _icm_modos()
    if icm is None:
        st.info("Sèrie ICM no disponible." if _ca else "Serie ICM no disponible.")
    else:
        MODO_CA = {"Grandes cadenas": "Grans cadenes",
                   "Empresas unilocalizadas": "Botiga unilocalitzada (petit comerç)",
                   "Pequeñas cadenas": "Petites cadenes",
                   "Grandes Superficies": "Grans superfícies"}
        MODO_ES = {"Grandes cadenas": "Grandes cadenas",
                   "Empresas unilocalizadas": "Tienda unilocalizada (pequeño comercio)",
                   "Pequeñas cadenas": "Pequeñas cadenas",
                   "Grandes Superficies": "Grandes superficies"}
        STYLE = {"Grandes cadenas": (NAVY, 3.2), "Empresas unilocalizadas": (RED, 3.2),
                 "Pequeñas cadenas": (GRAY_DARK, 1.6), "Grandes Superficies": (GRAY, 1.6)}
        lbl = MODO_CA if _ca else MODO_ES
        exhibit_header(
            1,
            ("Les grans cadenes creixen molt per sobre del petit comerç" if _ca
             else "Las grandes cadenas crecen muy por encima del pequeño comercio"),
            note=("Índex de xifra de negoci del comerç per format de distribució (base 2016 = 100)." if _ca
                  else "Índice de cifra de negocio del comercio por formato de distribución (base 2016 = 100)."))
        figd = go.Figure()
        for modo in ["Grandes Superficies", "Pequeñas cadenas", "Empresas unilocalizadas", "Grandes cadenas"]:
            s = icm["serie"][icm["serie"]["modo"] == modo].sort_values("data")
            col, w = STYLE[modo]
            figd.add_trace(go.Scatter(
                x=s["data"], y=s["valor"], mode="lines", name=lbl[modo],
                line=dict(color=col, width=w),
                hovertemplate=f"<b>{lbl[modo]}</b><br>%{{x|%b %Y}}: %{{y:.1f}}<extra></extra>"))
        apply_layout(figd, yaxis_title="Índex (2016 = 100)" if _ca else "Índice (2016 = 100)",
                     height=440, hovermode="closest")
        st.plotly_chart(figd, use_container_width=True)
        source("INE, Índices de Comercio al por Menor (ICM) per modo de distribució" if _ca
               else "INE, Índices de Comercio al por Menor (ICM) por modo de distribución")

        def _acum(modo):
            return (icm["last"].loc[modo, "valor"] / icm["base"][modo] - 1) * 100
        gc, uni = _acum("Grandes cadenas"), _acum("Empresas unilocalizadas")
        m1, m2, m3 = st.columns(3)
        m1.metric(("Grans cadenes des de 2016" if _ca else "Grandes cadenas desde 2016"), fpct(gc, 0),
                  help=("creixement nominal acumulat de la xifra de negoci" if _ca else "crecimiento nominal acumulado de la cifra de negocio"))
        m2.metric(("Petit comerç des de 2016" if _ca else "Pequeño comercio desde 2016"), fpct(uni, 0))
        m3.metric(("Grans cadenes, últim any" if _ca else "Grandes cadenas, último año"),
                  fpct(icm["var12"]["Grandes cadenas"], 1),
                  help=("variació anual mitjana dels últims 12 mesos" if _ca else "variación anual media de los últimos 12 meses"))
        insight(
            (f"Des de 2016 les <strong>grans cadenes</strong> han fet créixer la facturació un "
             f"<strong>{fpct(gc,0)}</strong>, mentre que la <strong>botiga unilocalitzada</strong> —el petit comerç— s'ha quedat al "
             f"<strong>{fpct(uni,0)}</strong>. L'últim any la distància continua: grans cadenes "
             f"{fpct(icm['var12']['Grandes cadenas'],1)} vs petit comerç {fpct(icm['var12']['Empresas unilocalizadas'],1)}. "
             f"<strong>Els comptes del Registre Mercantil identifiquen qui són els grans (el nivell); l'ICM mostra que els formats s'estan separant (la dinàmica).</strong>"
             if _ca else
             f"Desde 2016 las <strong>grandes cadenas</strong> han hecho crecer la facturación un "
             f"<strong>{fpct(gc,0)}</strong>, mientras que la <strong>tienda unilocalizada</strong> —el pequeño comercio— se ha quedado en el "
             f"<strong>{fpct(uni,0)}</strong>. El último año la distancia continúa: grandes cadenas "
             f"{fpct(icm['var12']['Grandes cadenas'],1)} vs pequeño comercio {fpct(icm['var12']['Empresas unilocalizadas'],1)}. "
             f"<strong>Las cuentas del Registro Mercantil identifican quiénes son los grandes (el nivel); el ICM muestra que los formatos se están separando (la dinámica).</strong>")
        )
        st.page_link("pages/0b_ICM.py",
                     label=("Veure tota la sèrie ICM per modo de distribució →" if _ca
                            else "Ver toda la serie ICM por modo de distribución →"))

# ── TAB 3: RENDIBILITAT I CREIXEMENT (eficiència: com competeixen) ──
with tab_efi:
    cmap = {s: PALETTE[i % len(PALETTE)] for i, s in enumerate(sorted(d["subsector"].unique()))}
    sub = (d.groupby("subsector").agg(
        n=("nombre", "count"),
        marge_ebitda=("marge_ebitda", "median"), roa=("roa", "median"),
        productivitat=("productivitat", "median"), ratio_personal=("ratio_personal", "median")).reset_index())
    s3 = sub[sub["n"] >= 3].copy()

    # ── Mida ≠ rendibilitat (nivell empresa): el que el rànquing per facturació amaga ──
    ef = d.dropna(subset=["ing_2024", "marge_ebitda", "empleados"]).copy()
    ef["meur"] = ef["ing_2024"] / 1000
    med_marge = ef["marge_ebitda"].median()
    big4_med = ef.sort_values("ing_2024", ascending=False).head(4)["marge_ebitda"].median()
    top_marge_names = ", ".join(ef.sort_values("marge_ebitda", ascending=False).head(3)["nombre"])
    exhibit_header(
        1,
        ("Facturació i marge no van lligats, per empresa" if _ca
         else "Facturación y margen no van ligados, por empresa"),
        note=("Cada bombolla és una empresa: facturació (eix X, escala log) enfront del marge EBITDA; "
              "la mida és la plantilla." if _ca
              else "Cada burbuja es una empresa: facturación (eje X, escala log) frente al margen EBITDA; "
              "el tamaño es la plantilla."))
    figm = go.Figure()
    for s in sorted(ef["subsector"].unique()):
        g = ef[ef["subsector"] == s]
        emp_txt = g["empleados"].map(lambda v: f"{v:,.0f}".replace(",", "."))
        figm.add_trace(go.Scatter(
            x=g["meur"], y=g["marge_ebitda"], mode="markers", name=s,
            marker=dict(size=np.sqrt(g["empleados"].clip(lower=1)) / 8 + 6,
                        color=cmap.get(s, BRAND), line=dict(width=0.5, color="white"), opacity=0.82),
            customdata=np.stack([g["nombre"], emp_txt], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f} M€ · "
                          + ("marge EBITDA " if _ca else "margen EBITDA ")
                          + "%{y:.1f}%<br>%{customdata[1]} "
                          + ("empleats" if _ca else "empleados") + "<extra></extra>"))
    figm.add_hline(y=med_marge, line_dash="dot", line_color="rgba(0,0,0,0.35)",
                   annotation_text=f"mediana {fpct(med_marge,1,sign=False)}",
                   annotation_position="top left")
    apply_layout(figm, xaxis_title="Facturació 2024 (M€, escala log)" if _ca else "Facturación 2024 (M€, escala log)",
                 yaxis_title="Marge EBITDA (%)" if _ca else "Margen EBITDA (%)",
                 height=460, showlegend=True)
    figm.update_xaxes(type="log")
    st.plotly_chart(figm, use_container_width=True)
    source("Comptes dipositats al Registre Mercantil. Càlcul propi" if _ca else "Cuentas depositadas en el Registro Mercantil. Cálculo propio")
    insight(
        (f"Facturació i marge <strong>no van lligats</strong>: la correlació entre tots dos és pràcticament nul·la. "
         f"Els marges més gruixuts no són dels operadors de més volum, sinó "
         f"d'operadors mitjans de luxe, joieria, òptica i moda ({top_marge_names}). Els quatre majors per facturació "
         f"tenen un marge EBITDA medià del <strong>{fpct(big4_med,1,sign=False)}</strong>, per sota de la mediana de la "
         f"mostra ({fpct(med_marge,1,sign=False)}): <strong>el seu pes ve del volum i de la quota, no del marge "
         f"unitari</strong>. Un rànquing ordenat només per facturació no recull aquesta diferència."
         if _ca else
         f"Facturación y margen <strong>no van ligados</strong>: la correlación entre ambos es prácticamente nula. "
         f"Los márgenes más gruesos no son de los operadores de más volumen, sino "
         f"de operadores medianos de lujo, joyería, óptica y moda ({top_marge_names}). Los cuatro mayores por facturación "
         f"tienen un margen EBITDA mediano del <strong>{fpct(big4_med,1,sign=False)}</strong>, por debajo de la mediana de la "
         f"muestra ({fpct(med_marge,1,sign=False)}): <strong>su peso viene del volumen y de la cuota, no del margen "
         f"unitario</strong>. Un ranking ordenado solo por facturación no recoge esta diferencia.")
    )
    st.markdown("---")

    # ── Marges per model de negoci — focus alimentació ────────────────
    exhibit_header(
        2,
        ("Marges per model de negoci · alimentació" if _ca
         else "Márgenes por modelo de negocio · alimentación"),
        note=("La concentració per si sola no diu si el sector «esprem marges»: classifiquem els grans "
              "operadors d'alimentació per model i mostrem el marge EBITDA real." if _ca
              else "La concentración por sí sola no dice si el sector «exprime márgenes»: clasificamos a los "
              "grandes operadores de alimentación por modelo y mostramos el margen EBITDA real."))

    # Classificació editorial per model (manual; basat en estructura comercial i de format)
    MODEL_MAP = {
        "Mercadona":     "Premium-volum (marca pròpia + format compacte)",
        "Lidl":          "Discount madur (marca pròpia + central UE)",
        "Dia":           "Discount en recuperació",
        "Aldi":          "Discount en escalat",
        "Carrefour":     "Hipermercat tradicional",
        "Alcampo":       "Hipermercat tradicional",
        "Eroski":        "Cooperatiu",
        "Consum":        "Cooperatiu",
        "Bon Preu":      "Regional premium",
        "Ahorramás":     "Regional premium",
    }
    MODEL_MAP_ES = {
        "Mercadona":     "Premium-volumen (marca propia + formato compacto)",
        "Lidl":          "Discount maduro (marca propia + central UE)",
        "Dia":           "Discount en recuperación",
        "Aldi":          "Discount en escalado",
        "Carrefour":     "Hipermercado tradicional",
        "Alcampo":       "Hipermercado tradicional",
        "Eroski":        "Cooperativo",
        "Consum":        "Cooperativo",
        "Bon Preu":      "Regional premium",
        "Ahorramás":     "Regional premium",
    }
    MODEL_COLOR = {
        "Premium-volum (marca pròpia + format compacte)": "#0055A4",
        "Discount madur (marca pròpia + central UE)":     "#1ABC9C",
        "Discount en recuperació":                          "#16A085",
        "Discount en escalat":                              "#27AE60",
        "Hipermercat tradicional":                          "#E74C3C",
        "Cooperatiu":                                       "#9B59B6",
        "Regional premium":                                 "#F39C12",
        "Premium-volumen (marca propia + formato compacto)": "#0055A4",
        "Discount maduro (marca propia + central UE)":      "#1ABC9C",
        "Discount en recuperación":                          "#16A085",
        "Discount en escalado":                              "#27AE60",
        "Hipermercado tradicional":                          "#E74C3C",
        "Cooperativo":                                       "#9B59B6",
    }
    model_map = MODEL_MAP if _ca else MODEL_MAP_ES

    d_mod = d.dropna(subset=["ing_2024", "marge_ebitda"]).copy()
    d_mod = d_mod[d_mod["nombre"].isin(model_map.keys())].copy()
    d_mod["model"] = d_mod["nombre"].map(model_map)
    d_mod["meur"] = d_mod["ing_2024"] / 1000
    d_mod = d_mod.sort_values("marge_ebitda", ascending=True)

    # Etiquetes amb any de snapshot (Lidl/Eroski són 2023)
    def _lab(row):
        y = int(row["snapshot_any"]) if pd.notna(row.get("snapshot_any")) else None
        any_tag = f"  ({y})" if y and y != 2024 else ""
        return f"{row['nombre']}{any_tag}"

    d_mod["lab"] = d_mod.apply(_lab, axis=1)

    fig_mod = go.Figure(go.Bar(
        y=d_mod["lab"], x=d_mod["marge_ebitda"], orientation="h",
        marker_color=[MODEL_COLOR.get(m, "#999") for m in d_mod["model"]],
        text=[f"{v:.1f}%" for v in d_mod["marge_ebitda"]],
        textposition="outside", textfont=dict(size=11),
        customdata=np.stack([d_mod["meur"], d_mod["model"]], axis=-1),
        hovertemplate=("<b>%{y}</b><br>EBITDA %{x:.2f}%<br>"
                       "Facturació %{customdata[0]:,.0f} M€<br>Model: %{customdata[1]}<extra></extra>"
                       if _ca else
                       "<b>%{y}</b><br>EBITDA %{x:.2f}%<br>"
                       "Facturación %{customdata[0]:,.0f} M€<br>Modelo: %{customdata[1]}<extra></extra>"),
    ))
    apply_layout(fig_mod,
        xaxis_title=("Marge EBITDA (% sobre facturació, darrer any disponible)" if _ca
                     else "Margen EBITDA (% sobre facturación, último año disponible)"),
        height=520, margin=dict(l=200, r=70, t=20, b=40), showlegend=False)
    fig_mod.update_xaxes(range=[-2, 12])
    st.plotly_chart(fig_mod, use_container_width=True)

    # Llegenda manual amb la classificació
    models_present = sorted({m for m in d_mod["model"]}, key=lambda x: d_mod[d_mod["model"] == x]["marge_ebitda"].max(), reverse=True)
    leg_html = "<div style='font-size:12px; color:#555; margin-top:-8px;'>"
    for m in models_present:
        c = MODEL_COLOR.get(m, "#999")
        leg_html += f"<span style='display:inline-block; width:10px; height:10px; background:{c}; margin-right:5px; margin-left:18px;'></span>{m}"
    leg_html += "</div>"
    st.markdown(leg_html, unsafe_allow_html=True)

    source("Comptes dipositats al Registre Mercantil · Càlcul propi. Lidl i Eroski: dades 2023 (2024 encara no dipositat). "
           "Classificació per model: editorial J3B3."
           if _ca else
           "Cuentas depositadas en el Registro Mercantil · Cálculo propio. Lidl y Eroski: datos 2023 (2024 aún no depositado). "
           "Clasificación por modelo: editorial J3B3.")

    # Insight tied to Force 4 of the framework
    merc = d_mod[d_mod["nombre"] == "Mercadona"]["marge_ebitda"].iloc[0] if "Mercadona" in d_mod["nombre"].values else None
    lidl = d_mod[d_mod["nombre"] == "Lidl"]["marge_ebitda"].iloc[0] if "Lidl" in d_mod["nombre"].values else None
    carr = d_mod[d_mod["nombre"] == "Carrefour"]["marge_ebitda"].iloc[0] if "Carrefour" in d_mod["nombre"].values else None
    alcm = d_mod[d_mod["nombre"] == "Alcampo"]["marge_ebitda"].iloc[0] if "Alcampo" in d_mod["nombre"].values else None
    aldi = d_mod[d_mod["nombre"] == "Aldi"]["marge_ebitda"].iloc[0] if "Aldi" in d_mod["nombre"].values else None

    if _ca:
        insight_txt = (
            "Tres lectures contraintuïtives que el gràfic deixa fer. "
            f"<strong>(1)</strong> Mercadona ({merc:.1f}%) i Lidl ({lidl:.1f}%) tenen marges <strong>gairebé idèntics</strong>: el descompte madur "
            "amb marca pròpia i central de compres europea opera amb la mateixa rendibilitat que el premium-volum espanyol. "
            f"<strong>(2)</strong> Carrefour ({carr:.1f}%) i Alcampo ({alcm:.1f}%) — els hipermercats tradicionals — operen amb marges la meitat de prims, "
            "i Aldi en escalat encara és per sota. <strong>El cas espanyol no és \"descompte = marge prim\"</strong>: és "
            "<strong>hipermercat tradicional = marge prim</strong>. "
            f"<strong>(3)</strong> Conseqüència per al pes del comerç al PIB: la consolidació via supermercat compacte (Mercadona-Lidl model) "
            "manté el VAB retail per euro consumit; una consolidació via hipermercat tradicional el comprimiria. "
            "Espanya no ha seguit aquest segon camí — i això és part de per què el seu pes G47 no s'ha desplomat com l'alemany."
        )
    else:
        insight_txt = (
            "Tres lecturas contraintuitivas que el gráfico permite extraer. "
            f"<strong>(1)</strong> Mercadona ({merc:.1f}%) y Lidl ({lidl:.1f}%) tienen márgenes <strong>casi idénticos</strong>: el discount maduro "
            "con marca propia y central de compras europea opera con la misma rentabilidad que el premium-volumen español. "
            f"<strong>(2)</strong> Carrefour ({carr:.1f}%) y Alcampo ({alcm:.1f}%) — los hipermercados tradicionales — operan con márgenes la mitad de finos, "
            "y Aldi en escalado aún por debajo. <strong>El caso español no es \"discount = margen fino\"</strong>: es "
            "<strong>hipermercado tradicional = margen fino</strong>. "
            f"<strong>(3)</strong> Consecuencia para el peso del comercio en el PIB: la consolidación vía supermercado compacto (Mercadona-Lidl) "
            "mantiene el VAB retail por euro consumido; una consolidación vía hipermercado tradicional lo comprimiría. "
            "España no ha seguido ese segundo camino — y eso explica en parte por qué su peso G47 no se ha desplomado como el alemán."
        )
    insight(insight_txt)

    st.markdown("---")

    exhibit_header(
        3,
        ("Mapa de posicionament dels subsectors" if _ca
         else "Mapa de posicionamiento de los subsectores"),
        note=("Productivitat vs marge EBITDA (mediana, subsectors amb 3+ empreses)." if _ca
              else "Productividad vs margen EBITDA (mediana, subsectores con 3+ empresas)."))
    fig = go.Figure()
    for _, row in s3.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["productivitat"] / 1000], y=[row["marge_ebitda"]], mode="markers+text",
            text=[row["subsector"]], textposition="top center", textfont=dict(size=11),
            marker=dict(size=22, color=cmap.get(row["subsector"], BRAND), line=dict(width=1, color="white")),
            hovertemplate=f"<b>{row['subsector']}</b><br>%{{x:,.0f}} k€/empleat<br>marge EBITDA %{{y:.1f}}%<extra></extra>"))
    apply_layout(fig, xaxis_title="Facturació per empleat (k€)" if _ca else "Facturación por empleado (k€)",
                 yaxis_title="Marge EBITDA (mediana, %)" if _ca else "Margen EBITDA (mediana, %)",
                 height=440, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    source("Comptes dipositats al Registre Mercantil. Càlcul propi" if _ca else "Cuentas depositadas en el Registro Mercantil. Cálculo propio")
    insight(
        ("No hi ha un únic model dins la mostra. L'<strong>electrònica i informàtica</strong> tenen la productivitat "
         "més alta (ticket elevat, plantilla reduïda i pes de la venda online) però el <strong>marge EBITDA més prim</strong>, "
         "senyal d'una competència de preu intensa. La <strong>cosmètica</strong> i la <strong>moda</strong> registren els "
         "marges més alts. L'<strong>alimentació</strong> —on hi ha el líder— té marges continguts: el seu poder ve del "
         "<strong>volum</strong>, no del marge unitari."
         if _ca else
         "No hay un único modelo dentro de la muestra. La <strong>electrónica e informática</strong> tienen la productividad "
         "más alta (ticket elevado, plantilla reducida y peso de la venta online) pero el <strong>margen EBITDA más fino</strong>, "
         "señal de una competencia de precio intensa. La <strong>cosmética</strong> y la <strong>moda</strong> registran los "
         "márgenes más altos. La <strong>alimentación</strong> —donde está el líder— tiene márgenes contenidos: su poder viene del "
         "<strong>volumen</strong>, no del margen unitario.")
    )

    exhibit_header(
        4,
        ("Creixement orgànic 2020-2024 (CAGR)" if _ca
         else "Crecimiento orgánico 2020-2024 (CAGR)"),
        note=("N'excloem les empreses amb ruptura de sèrie (reorganitzacions societàries), "
              "el CAGR de les quals no seria comparable." if _ca
              else "Excluimos las empresas con ruptura de serie (reorganizaciones societarias), "
              "cuyo CAGR no sería comparable."))
    g = d.dropna(subset=["cagr"]).sort_values("cagr")
    sel = pd.concat([g.head(8), g.tail(8)]).drop_duplicates("nombre")
    figg = go.Figure(go.Bar(
        y=sel["nombre"], x=sel["cagr"], orientation="h",
        marker_color=[NAVY if v >= 0 else RED for v in sel["cagr"]],
        text=[fpct(v, 1) for v in sel["cagr"]], textposition="outside", textfont=dict(size=10)))
    figg.add_vline(x=0, line_color="rgba(0,0,0,0.3)")
    apply_layout(figg, xaxis_title="CAGR 2020-2024 (%)", height=520, margin=dict(l=170, r=70, t=20, b=40))
    st.plotly_chart(figg, use_container_width=True)
    source("Comptes dipositats al Registre Mercantil. Càlcul propi" if _ca else "Cuentas depositadas en el Registro Mercantil. Cálculo propio")
    _brk = d[d["break_flag"]]["nombre"].tolist()
    insight(
        ("Entre les empreses amb creixement orgànic comparable, els <strong>guanyadors</strong> són cadenes de moda, "
         "cosmètica i nous formats de descompte; els <strong>perdedors</strong>, formats sota pressió o en reestructuració. "
         f"<br><br><strong>Aclariment.</strong> Operadors com <strong>MediaMarkt</strong> mostren un salt comptable que "
         f"<strong>no és creixement real</strong>, sinó una reorganització societària; per això els excloem. Excloses per "
         f"ruptura: {', '.join(_brk) if _brk else '—'}."
         if _ca else
         "Entre las empresas con crecimiento orgánico comparable, los <strong>ganadores</strong> son cadenas de moda, "
         "cosmética y nuevos formatos de descuento; los <strong>perdedores</strong>, formatos bajo presión o en reestructuración. "
         f"<br><br><strong>Aclaración.</strong> Operadores como <strong>MediaMarkt</strong> muestran un salto contable que "
         f"<strong>no es crecimiento real</strong>, sino una reorganización societaria; por eso los excluimos. Excluidas por "
         f"ruptura: {', '.join(_brk) if _brk else '—'}.")
    )

# ── TAB 4: LA MOSTRA COMPLETA (taula ordenable amb absoluts + ràtios) ──
with tab_mostra:
    st.markdown(("Totes les empreses de la mostra (clica les capçaleres per ordenar). Facturació i quota dins la "
                 "mostra, més els ràtios d'eficiència."
                 if _ca else
                 "Todas las empresas de la muestra (clica las cabeceras para ordenar). Facturación y cuota dentro de la "
                 "muestra, más los ratios de eficiencia."))
    tbl = d.copy()
    tbl["fac_meur"] = tbl["ing_2024"] / 1000
    tbl["prod_keur"] = tbl["productivitat"] / 1000
    tbl = tbl[["rank_2024", "nombre", "subsector", "fac_meur", "quota_2024",
               "marge_ebitda", "roa", "prod_keur", "ratio_personal", "cagr"]]
    tbl = tbl.sort_values("fac_meur", ascending=False)
    tbl.columns = ["#", "Empresa", "Subsector",
                   "Facturació (M€)" if _ca else "Facturación (M€)",
                   "Quota mostra %" if _ca else "Cuota muestra %",
                   "Marge EBITDA %" if _ca else "Margen EBITDA %", "ROA %",
                   "Fact./empleat (k€)" if _ca else "Fact./empleado (k€)",
                   "Cost pers./vendes %" if _ca else "Coste pers./ventas %",
                   "CAGR 20-24 %"]
    st.dataframe(
        tbl, use_container_width=True, hide_index=True, height=560,
        column_config={
            "#": st.column_config.NumberColumn(format="%d", width="small"),
            ("Facturació (M€)" if _ca else "Facturación (M€)"): st.column_config.NumberColumn(format="%.0f"),
            ("Quota mostra %" if _ca else "Cuota muestra %"): st.column_config.NumberColumn(format="%.1f"),
            ("Marge EBITDA %" if _ca else "Margen EBITDA %"): st.column_config.NumberColumn(format="%.1f"),
            "ROA %": st.column_config.NumberColumn(format="%.1f"),
            ("Fact./empleat (k€)" if _ca else "Fact./empleado (k€)"): st.column_config.NumberColumn(format="%.0f"),
            ("Cost pers./vendes %" if _ca else "Coste pers./ventas %"): st.column_config.NumberColumn(format="%.1f"),
            "CAGR 20-24 %": st.column_config.NumberColumn(format="%.1f"),
        })
    source("Comptes anuals dipositats al Registre Mercantil . Càlcul propi" if _ca
           else "Cuentas anuales depositadas en el Registro Mercantil . Cálculo propio")
    st.caption(("Facturació i plantilla són dades públiques del Registre Mercantil. CAGR buit = empresa amb ruptura "
                "de sèrie (reorganització) o sense comptes per als dos anys."
                if _ca else
                "Facturación y plantilla son datos públicos del Registro Mercantil. CAGR vacío = empresa con ruptura "
                "de serie (reorganización) o sin cuentas para ambos años."))

page_meta("Comptes anuals dipositats al Registre Mercantil (2020-2024) · INE ICM per modo · EAS (denominador sectorial) · mostra de grans empreses CNAE 47" if _ca
          else "Cuentas anuales depositadas en el Registro Mercantil (2020-2024) · INE ICM por modo · EAS (denominador sectorial) · muestra de grandes empresas CNAE 47",
          st.session_state.lang)
