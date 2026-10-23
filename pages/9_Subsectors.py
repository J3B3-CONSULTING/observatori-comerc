"""Pagina 9: Subsectors del comerc al detall (CNAE 47 a 3 digits + despesa familiar)"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.loader import read_dataset
from navegacio import tab_destinacio
from style import (
    inject_css, inject_premium_page_css, setup_lang, page_header,
    insight, source, page_meta,
    fnum, fpct, apply_layout, highlight_expander,
    kicker, action_title, deck, key_takeaways, exhibit_header,
    freshness_badge,
    NAVY, OCRE, OCRE_DEEP, RED, G1_P, PALETTE,
)

inject_css()
inject_premium_page_css()
t = setup_lang(show_selector=False)
page_header()

_ca = st.session_state.lang == "ca"

# ─── Càrrega de dades ────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_csv(name, code_col=None, code_pad=0):
    """Llegeix CSV i converteix la columna de codi a string (amb zfill opcional per COICOP)."""
    df = read_dataset(name)
    if df.empty:
        return df
    if code_col and code_col in df.columns:
        df[code_col] = df[code_col].astype(str).str.zfill(code_pad) if code_pad else df[code_col].astype(str)
    return df


df_dirce = load_csv("subsectors_dirce", code_col="codi")
df_eas = load_csv("subsectors_eas", code_col="codi")
df_472 = load_csv("subsectors_472", code_col="codi")  # 4 dígits del grup d'alimentació
df_epf = load_csv("subsectors_epf", code_col="codi_coicop", code_pad=2)

# ─── Etiquetes (bilingue) ───────────────────────────────────

SUBSECTOR_LABELS = {
    "ca": {
        "47":  "CNAE 47 (total)",
        "471": "Establiments no especialitzats",
        "472": "Alimentació, begudes i tabac",
        "474": "Equips TIC",
        "475": "Articles d'ús domèstic",
        "476": "Cultura i recreatius",
        "477": "Vestit i altres",
        "478": "Mercadillos",
        "479": "E-commerce i venda directa",
    },
    "es": {
        "47":  "CNAE 47 (total)",
        "471": "Estab. no especializados",
        "472": "Alimentación, bebidas y tabaco",
        "474": "Equipos TIC",
        "475": "Artículos de uso doméstico",
        "476": "Cultura y recreativos",
        "477": "Vestido y otros",
        "478": "Mercadillos",
        "479": "E-commerce y venta directa",
    },
}

# Codi CNAE a excloure de la pagina (sense interes per a una analisi de retail)
EXCLUDE_CODES = ["473"]

# Exemples concrets per a cada subsector (mostrats al hover de cada barra)
SUBSECTOR_EXAMPLES = {
    "ca": {
        "471": "Supermercats (Mercadona, Caprabo, Consum, Bonpreu), hipermercats (Carrefour, Alcampo, Eroski Center, Hipercor), descompte (Lidl, Aldi, Dia), grans magatzems (El Corte Inglés), tot a 1€ (Action, Tedi, Primaprix), botigues de barri i 24h",
        "472": "Forns i pastisseries, carnisseries, peixateries, fruiteries, queviures, estancs, herbolaris, vinateries i cellers especialitzats",
        "474": "Botigues d'electrònica (MediaMarkt, FNAC), informàtica (PcComponentes botiga física), telefonia (Phone House), botigues d'operadors (Movistar, Vodafone, Orange)",
        "475": "Mobles i decoració (Ikea, Conforama, Maisons du Monde), il·luminació, parament de la llar, electrodomèstics blancs, ferreteries i bricolatge (Leroy Merlin, Bauhaus)",
        "476": "Llibreries (Casa del Libro, FNAC llibres), jugueteries (Imaginarium, ToysRUs, Drim), música, esports (Intersport, Forum Sport, Sprinter), papereries i material d'oficina",
        "477": "Roba i moda (Inditex, Mango, H&M, Primark), calçat (Camper, Kalenji), farmàcies, joieria i rellotgeria, cosmètica i perfumeria (Sephora, Druni), òptiques, regals, articles per a animals",
        "478": "Mercats setmanals i mercadillos a la via pública: alimentació, roba, antiguitats, encants",
        "479": "Comerç electrònic pure-play (PcComponentes, Privalia, Hawkers, Tradeinn), venda per correspondència, vending (màquines expenedores), venda a domicili (porta a porta, telefònica), subhastes presencials",
    },
    "es": {
        "471": "Supermercados (Mercadona, Caprabo, Consum, Bonpreu), hipermercados (Carrefour, Alcampo, Eroski Center, Hipercor), descuento (Lidl, Aldi, Dia), grandes almacenes (El Corte Inglés), todo a 1€ (Action, Tedi, Primaprix), tiendas de barrio y 24h",
        "472": "Panaderías y pastelerías, carnicerías, pescaderías, fruterías, ultramarinos, estancos, herbolarios, vinaterías y bodegas especializadas",
        "474": "Tiendas de electrónica (MediaMarkt, FNAC), informática (PcComponentes tienda física), telefonía (Phone House), tiendas de operadores (Movistar, Vodafone, Orange)",
        "475": "Muebles y decoración (Ikea, Conforama, Maisons du Monde), iluminación, menaje del hogar, electrodomésticos, ferreterías y bricolaje (Leroy Merlin, Bauhaus)",
        "476": "Librerías (Casa del Libro, FNAC libros), jugueterías (Imaginarium, ToysRUs, Drim), música, deportes (Intersport, Forum Sport, Sprinter), papelerías y material de oficina",
        "477": "Ropa y moda (Inditex, Mango, H&M, Primark), calzado (Camper, Kalenji), farmacias, joyería y relojería, cosmética y perfumería (Sephora, Druni), ópticas, regalos, artículos para animales",
        "478": "Mercados semanales y mercadillos en la vía pública: alimentación, ropa, antigüedades, rastros",
        "479": "E-commerce pure-play (PcComponentes, Privalia, Hawkers, Tradeinn), venta por correspondencia, vending (máquinas expendedoras), venta a domicilio (puerta a puerta, telefónica), subastas presenciales",
    },
}


def wrap_text(text, width=70):
    """Trenca un text en linies de longitud maxima per a hover de Plotly."""
    import textwrap
    return "<br>".join(textwrap.wrap(text, width=width))

COICOP_LABELS = {
    "ca": {
        "00": "Total despesa",
        "01": "Aliments i begudes no alc.",
        "02": "Begudes alc., tabac",
        "03": "Vestit i calçat",
        "04": "Habitatge i energia",
        "05": "Mobles i articles llar",
        "06": "Sanitat",
        "07": "Transport",
        "08": "Informació i comunicacions",
        "09": "Oci, cultura i esport",
        "10": "Educació",
        "11": "Restauració i allotjament",
        "12": "Cura personal i altres",
    },
    "es": {
        "00": "Total gasto",
        "01": "Alim. y bebidas no alc.",
        "02": "Bebidas alc., tabaco",
        "03": "Vestido y calzado",
        "04": "Vivienda y energía",
        "05": "Muebles y hogar",
        "06": "Sanidad",
        "07": "Transporte",
        "08": "Información y com.",
        "09": "Ocio, cultura y deporte",
        "10": "Educación",
        "11": "Rest. y alojamiento",
        "12": "Cuidado personal y otros",
    },
}

# Etiqueta de subsector CNAE corresponent a cada categoria de despesa familiar
# (per homogeneitzar amb les pestanyes Estructura i Activitat)
DEMAND_CNAE_LABELS = {
    "ca": {
        "01": "Alimentació (especialitzada + no especialitzada)",
        "02": "Alimentació, begudes i tabac",
        "03": "Vestit i calçat",
        "05": "Articles d'ús domèstic",
        "06": "Farmàcies i productes sanitaris",
        "08": "Equips TIC",
        "09": "Cultura i recreatius",
        "12": "Cosmètics i cura personal",
    },
    "es": {
        "01": "Alimentación (especializada + no especializada)",
        "02": "Alimentación, bebidas y tabaco",
        "03": "Vestido y calzado",
        "05": "Artículos de uso doméstico",
        "06": "Farmacias y productos sanitarios",
        "08": "Equipos TIC",
        "09": "Cultura y recreativos",
        "12": "Cosméticos y cuidado personal",
    },
}

# Exemples breus per categoria de despesa (hover compacte, no tapa les barres).
DEMAND_EXAMPLES = {
    "ca": {
        "01": "Supermercats, hipermercats, alimentació especialitzada",
        "02": "Vinateries, cellers, estancs",
        "03": "Inditex, Mango, H&M, Primark, Camper, Decimas",
        "05": "Ikea, Conforama, Leroy Merlin, parament de la llar",
        "06": "Farmàcies, parafarmàcies, ortopèdies",
        "08": "MediaMarkt, FNAC, Phone House, operadors telefònics",
        "09": "Llibreries, jugueteries, Intersport, Forum Sport, Sprinter",
        "12": "Sephora, Druni, Primor, Bodybell, drogueries",
    },
    "es": {
        "01": "Supermercados, hipermercados, alimentación especializada",
        "02": "Vinaterías, bodegas, estancos",
        "03": "Inditex, Mango, H&M, Primark, Camper, Decimas",
        "05": "Ikea, Conforama, Leroy Merlin, menaje del hogar",
        "06": "Farmacias, parafarmacias, ortopedias",
        "08": "MediaMarkt, FNAC, Phone House, operadores telefónicos",
        "09": "Librerías, jugueterías, Intersport, Forum Sport, Sprinter",
        "12": "Sephora, Druni, Primor, Bodybell, droguerías",
    },
}

# Mapeig COICOP -> CNAE 47 (categories de despesa familiar que es compren al comerc al detall)
COICOP_TO_CNAE = {
    "01": ["471", "472"],  # Aliments → no especialitzats + alimentacio especialitzada
    "02": ["472"],         # Begudes alc., tabac → estanc + begudes
    "03": ["477"],         # Vestit i calcat → 4771, 4772 (dins 477)
    "05": ["475"],         # Mobles i articles llar
    "06": ["477"],         # Sanitat → farmacia 4773 (dins 477)
    "08": ["474"],         # Info/comunicacions → equips TIC
    "09": ["476"],         # Oci, cultura → llibreries, jugueteries, esports
    "12": ["477"],         # Cura personal → cosmetics 4775 (dins 477)
}

LANG = "ca" if _ca else "es"
SLABEL = SUBSECTOR_LABELS[LANG]
SEXAMPLES = {k: wrap_text(v) for k, v in SUBSECTOR_EXAMPLES[LANG].items()}
CLABEL = COICOP_LABELS[LANG]
DLABEL = DEMAND_CNAE_LABELS[LANG]  # subsector CNAE per a la pestanya Demanda
HOVER_LBL_EX = "Exemples" if _ca else "Ejemplos"

# ─── Capçalera ──────────────────────────────────────────────

kicker("Anàlisi sectorial · Subsectors CNAE 47" if _ca
       else "Análisis sectorial · Subsectores CNAE 47")

if df_dirce.empty and df_eas.empty and df_epf.empty:
    st.warning("No hi ha dades disponibles." if _ca else "No hay datos disponibles.")
    st.stop()

# ─── Càlculs per a header i takeaways ─────────────────────────
_hdr = {}
if not df_dirce.empty:
    _hd_ly = int(df_dirce["any"].max())
    _hd_fy = int(df_dirce["any"].min())
    _hd_subs = df_dirce[
        (df_dirce["codi"] != "47") & (~df_dirce["codi"].isin(EXCLUDE_CODES))
    ].copy()
    _hd_f = _hd_subs[_hd_subs["any"] == _hd_fy][["codi", "empreses"]].rename(columns={"empreses": "f"})
    _hd_l = _hd_subs[_hd_subs["any"] == _hd_ly][["codi", "empreses"]].rename(columns={"empreses": "l"})
    _hd_m = _hd_f.merge(_hd_l, on="codi")
    _hd_m["var"] = (_hd_m["l"] / _hd_m["f"] - 1) * 100
    _hd_win = _hd_m.sort_values("var").iloc[-1]
    _hd_los = _hd_m.sort_values("var").iloc[0]
    _hd_n_grow = int((_hd_m["var"] >= 0).sum())
    _hd_n_lose = int((_hd_m["var"] < 0).sum())
    _hd_n_tot = len(_hd_m)
    _hdr.update(fy=_hd_fy, ly=_hd_ly, win=_hd_win, los=_hd_los,
                n_grow=_hd_n_grow, n_lose=_hd_n_lose, n_tot=_hd_n_tot)

# Líder en facturació (EAS), per al deck
if not df_eas.empty:
    _he_ly = int(df_eas["any"].max())
    _he = df_eas[(df_eas["codi"] != "47") & (~df_eas["codi"].isin(EXCLUDE_CODES))
                 & (df_eas["any"] == _he_ly)].copy()
    if not _he.empty:
        _he_tot = _he["xifra_negoci"].sum()
        _he_top = _he.sort_values("xifra_negoci", ascending=False).iloc[0]
        _hdr["xn_top_code"] = _he_top["codi"]
        _hdr["xn_top_share"] = _he_top["xifra_negoci"] / _he_tot * 100 if _he_tot else 0
        _he["productiv"] = _he["valor_afegit"] / _he["personal_ocupat"]
        _he_s = _he.sort_values("productiv")
        _hdr["prod_ratio"] = _he_s.iloc[-1]["productiv"] / _he_s.iloc[0]["productiv"] if _he_s.iloc[0]["productiv"] else 0

# ─── HEADER ──────────────────────────────────────────────────
if "win" in _hdr:
    _win_lbl = SUBSECTOR_LABELS[LANG].get(_hdr["win"]["codi"], _hdr["win"]["codi"])
    _los_lbl = SUBSECTOR_LABELS[LANG].get(_hdr["los"]["codi"], _hdr["los"]["codi"])
    if _ca:
        action_title(
            f"{_hdr['n_lose']} de {_hdr['n_tot']} subsectors del comerç al detall "
            f"perden empreses entre {_hdr['fy']} i {_hdr['ly']}")
        deck(
            f"L'únic subsector en expansió és {_win_lbl} ({fpct(_hdr['win']['var'])}); "
            f"el comerç físic especialitzat es contrau, encapçalat per {_los_lbl} "
            f"({fpct(_hdr['los']['var'])}).")
    else:
        action_title(
            f"{_hdr['n_lose']} de {_hdr['n_tot']} subsectores del comercio minorista "
            f"pierden empresas entre {_hdr['fy']} y {_hdr['ly']}")
        deck(
            f"El único subsector en expansión es {_win_lbl} ({fpct(_hdr['win']['var'])}); "
            f"el comercio físico especializado se contrae, encabezado por {_los_lbl} "
            f"({fpct(_hdr['los']['var'])}).")

    if _ca:
        _takeaways = [
            f"Entre {_hdr['fy']} i {_hdr['ly']}, <b>{_hdr['n_lose']} dels "
            f"{_hdr['n_tot']} subsectors</b> a tres dígits redueixen el nombre d'empreses; "
            f"només <b>{_win_lbl.lower()}</b> creix (<b>{fpct(_hdr['win']['var'])}</b>).",
            f"<b>{_los_lbl}</b> és el subsector que més es contrau "
            f"(<b>{fpct(_hdr['los']['var'])}</b>), pressionat per la digitalització i el gran format.",
        ]
        if "xn_top_share" in _hdr:
            _xn_lbl = SUBSECTOR_LABELS[LANG].get(_hdr["xn_top_code"], _hdr["xn_top_code"])
            _takeaways.append(
                f"El rànquing per empreses no és el de facturació: "
                f"<b>{_xn_lbl.lower()}</b> mou el <b>{fpct(_hdr['xn_top_share'], 1, sign=False)}</b> "
                f"de la xifra de negoci amb pocs operadors grans.")
        _tk_label = "Conclusions clau"
    else:
        _takeaways = [
            f"Entre {_hdr['fy']} y {_hdr['ly']}, <b>{_hdr['n_lose']} de los "
            f"{_hdr['n_tot']} subsectores</b> a tres dígitos reducen el número de empresas; "
            f"solo <b>{_win_lbl.lower()}</b> crece (<b>{fpct(_hdr['win']['var'])}</b>).",
            f"<b>{_los_lbl}</b> es el subsector que más se contrae "
            f"(<b>{fpct(_hdr['los']['var'])}</b>), presionado por la digitalización y el gran formato.",
        ]
        if "xn_top_share" in _hdr:
            _xn_lbl = SUBSECTOR_LABELS[LANG].get(_hdr["xn_top_code"], _hdr["xn_top_code"])
            _takeaways.append(
                f"El ranking por empresas no coincide con el de facturación: "
                f"<b>{_xn_lbl.lower()}</b> mueve el <b>{fpct(_hdr['xn_top_share'], 1, sign=False)}</b> "
                f"de la cifra de negocios con pocos operadores grandes.")
        _tk_label = "Conclusiones clave"
    key_takeaways(_takeaways, label=_tk_label)

freshness_badge(["subsectors_dirce", "subsectors_eas", "subsectors_epf"], st.session_state.lang)

# ─── TABS ────────────────────────────────────────────────────

_tabs_lbl = [
    ("Estructura empresarial" if _ca else "Estructura empresarial"),
    ("Activitat i productivitat" if _ca else "Actividad y productividad"),
    ("Demanda (despesa famílies)" if _ca else "Demanda (gasto familias)"),
    ("Detall alimentació" if _ca else "Detalle alimentación"),
]
tab1, tab2, tab3, tab4 = st.tabs(_tabs_lbl, default=tab_destinacio("pages/9_Subsectors.py", _tabs_lbl))

# ============================================================
# TAB 1: ESTRUCTURA - DIRCE
# ============================================================
with tab1:
    if df_dirce.empty:
        st.info("Sense dades DIRCE." if _ca else "Sin datos DIRCE.")
    else:
        last_year = int(df_dirce["any"].max())
        df_subs = df_dirce[
            (df_dirce["codi"] != "47") & (df_dirce["any"] == last_year)
            & (~df_dirce["codi"].isin(EXCLUDE_CODES))
        ].copy()
        df_subs["label"] = df_subs["codi"].map(SLABEL)
        df_subs["examples"] = df_subs["codi"].map(SEXAMPLES).fillna("")
        df_subs = df_subs.sort_values("empreses", ascending=True)

        _t1_lead = df_subs.iloc[-1]
        _t1_total = df_subs["empreses"].sum()
        _t1_share = _t1_lead["empreses"] / _t1_total * 100 if _t1_total else 0
        if _ca:
            exhibit_header(
                1, f"{_t1_lead['label']} concentra {fpct(_t1_share, 1, sign=False)} "
                   f"de les empreses del comerç al detall ({last_year})",
                note="El rànquing per nombre d'empreses no és el de facturació: el lideratge "
                     "en establiments i el lideratge en volum recauen en subsectors diferents.")
        else:
            exhibit_header(
                1, f"{_t1_lead['label']} concentra {fpct(_t1_share, 1, sign=False)} "
                   f"de las empresas del comercio minorista ({last_year})",
                note="El ranking por número de empresas no coincide con el de facturación: "
                     "el liderazgo en establecimientos y en volumen recaen en subsectores distintos.")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_subs["label"], x=df_subs["empreses"],
            orientation="h",
            marker_color=NAVY,
            text=[fnum(v) for v in df_subs["empreses"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_subs[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"<i>{HOVER_LBL_EX}:</i> "
                "%{customdata[0]}<br>"
                + ("<b>Empreses</b>: " if _ca else "<b>Empresas</b>: ")
                + "%{x:,.0f}<extra></extra>"
            ).replace(",", "."),
        ))
        apply_layout(fig_bar,
            title=f"{'Empreses per subsector' if _ca else 'Empresas por subsector'} ({last_year})",
            xaxis_title=("Empreses" if _ca else "Empresas"),
            height=max(420, len(df_subs) * 38 + 100),
            margin=dict(l=240, r=100, t=50, b=50),
            hovermode="closest",
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        source("INE, Directori Central d'Empreses (DIRCE), taula 73019" if _ca
               else "INE, Directorio Central de Empresas (DIRCE), tabla 73019")

        if _ca:
            st.caption(
                "**CNAE 471 — Establiments no especialitzats:** botigues que venen una varietat "
                "àmplia de productes sota un mateix sostre, sense estar especialitzades en una "
                "sola categoria. Inclou **supermercats** (Mercadona, Caprabo, Consum, Bonpreu), "
                "**hipermercats** (Carrefour, Alcampo, Eroski Center, Hipercor), **botigues de "
                "descompte** (Lidl, Aldi, Dia), **botigues de barri/24h**, **grans magatzems** "
                "(El Corte Inglés) i **botigues de tot a 1€** (Action, Tedi, Primaprix). "
                "És el subsector amb més facturació del comerç al detall espanyol per concentrar "
                "la cistella alimentària quotidiana.\n\n"
                "**CNAE 479 — E-commerce i venda directa:** comerç al detall per internet o "
                "correspondència, vending, venda a domicili (porta a porta), subhastes presencials "
                "i venda telefònica. **No inclou** el comerç online d'empreses tradicionals amb "
                "botiga física: aquestes vendes online es comptabilitzen al subsector principal "
                "de l'empresa (ex: Carrefour online → 471, Decathlon online → 4764 dins 476). "
                "**Per això CNAE 479 NO coincideix amb el volum d'e-commerce de la pàgina "
                "E-commerce** (font CNMC): el 2024 el CNAE 479 (17.181 M€) representa només un "
                "67% del volum CNMC (25.739 M€). Veure detall a la pàgina Metodologia."
            )
        else:
            st.caption(
                "**CNAE 471 — Establecimientos no especializados:** tiendas que venden una "
                "variedad amplia de productos bajo un mismo techo, sin estar especializadas en "
                "una sola categoría. Incluye **supermercados** (Mercadona, Caprabo, Consum, "
                "Bonpreu), **hipermercados** (Carrefour, Alcampo, Eroski Center, Hipercor), "
                "**tiendas de descuento** (Lidl, Aldi, Dia), **tiendas de barrio/24h**, **grandes "
                "almacenes** (El Corte Inglés) y **tiendas de todo a 1€** (Action, Tedi, "
                "Primaprix). Es el subsector con mayor facturación del comercio al detalle "
                "español por concentrar la cesta alimentaria cotidiana.\n\n"
                "**CNAE 479 — E-commerce y venta directa:** comercio minorista por internet o "
                "correspondencia, vending, venta a domicilio (puerta a puerta), subastas "
                "presenciales y venta telefónica. **No incluye** el comercio online de empresas "
                "tradicionales con tienda física: esas ventas online se contabilizan en el "
                "subsector principal de la empresa (ej: Carrefour online → 471, Decathlon online "
                "→ 4764 dentro de 476). **Por eso CNAE 479 NO coincide con el volumen de "
                "e-commerce de la página E-commerce** (fuente CNMC): en 2024 el CNAE 479 "
                "(17.181 M€) representa solo un 67% del volumen CNMC (25.739 M€). Ver detalle "
                "en la página Metodología."
            )

        # Evolució per subsector
        first_year = int(df_dirce["any"].min())
        df_first = df_dirce[
            (df_dirce["codi"] != "47") & (df_dirce["any"] == first_year)
            & (~df_dirce["codi"].isin(EXCLUDE_CODES))
        ][["codi", "empreses"]].rename(columns={"empreses": "emp_first"})
        df_last = df_dirce[
            (df_dirce["codi"] != "47") & (df_dirce["any"] == last_year)
            & (~df_dirce["codi"].isin(EXCLUDE_CODES))
        ][["codi", "empreses"]].rename(columns={"empreses": "emp_last"})
        df_var = df_first.merge(df_last, on="codi")
        df_var["var_pct"] = ((df_var["emp_last"] / df_var["emp_first"]) - 1) * 100
        df_var["label"] = df_var["codi"].map(SLABEL)
        df_var["examples"] = df_var["codi"].map(SEXAMPLES).fillna("")
        df_var = df_var.sort_values("var_pct", ascending=True)

        _n_grow_t1 = int((df_var["var_pct"] >= 0).sum())
        _n_lose_t1 = int((df_var["var_pct"] < 0).sum())
        if _ca:
            exhibit_header(
                2, f"{_n_lose_t1} dels {len(df_var)} subsectors perden empreses "
                   f"entre {first_year} i {last_year}",
                note="Les barres blaves marquen subsectors que guanyen teixit empresarial; "
                     "les vermelles, els que en perden.")
        else:
            exhibit_header(
                2, f"{_n_lose_t1} de los {len(df_var)} subsectores pierden empresas "
                   f"entre {first_year} y {last_year}",
                note="Las barras azules marcan subsectores que ganan tejido empresarial; "
                     "las rojas, los que lo pierden.")

        fig_var = go.Figure()
        colors = [NAVY if v >= 0 else RED for v in df_var["var_pct"]]
        fig_var.add_trace(go.Bar(
            y=df_var["label"], x=df_var["var_pct"],
            orientation="h",
            marker_color=colors,
            text=[fpct(v) for v in df_var["var_pct"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_var[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"<i>{HOVER_LBL_EX}:</i> "
                "%{customdata[0]}<br>"
                + ("<b>Variació</b>: " if _ca else "<b>Variación</b>: ")
                + "%{x:.1f}%<extra></extra>"
            ),
        ))
        apply_layout(fig_var,
            title=f"{'Variació' if _ca else 'Variación'} {first_year}-{last_year} (%)",
            xaxis_title="%",
            height=max(420, len(df_var) * 38 + 100),
            margin=dict(l=240, r=80, t=50, b=50),
            hovermode="closest",
        )
        fig_var.add_vline(x=0, line_dash="dash", line_color="rgba(0,0,0,0.2)")
        st.plotly_chart(fig_var, use_container_width=True)
        source("INE, DIRCE. Càlcul propi" if _ca else "INE, DIRCE. Cálculo propio")

        # ── Insight estructural (analisi profunda) ─────────────
        leader = df_subs.iloc[-1]
        runner = df_subs.iloc[-2] if len(df_subs) >= 2 else None
        loser = df_var.iloc[0]
        winner = df_var.iloc[-1]

        # Concentracio top-3 vs base llarga
        df_subs_desc = df_subs.sort_values("empreses", ascending=False).reset_index(drop=True)
        total_subs = df_subs_desc["empreses"].sum()
        top3_share = df_subs_desc.head(3)["empreses"].sum() / total_subs * 100 if total_subs else 0

        # Subsectors que creixen vs perden
        n_grow = int((df_var["var_pct"] >= 0).sum())
        n_lose = int((df_var["var_pct"] < 0).sum())

        # Variacio mitjana ponderada
        emp_first_total = df_var["emp_first"].sum()
        emp_last_total = df_var["emp_last"].sum()
        var_total = (emp_last_total / emp_first_total - 1) * 100 if emp_first_total else 0

        if _ca:
            txt = (
                f"El comerç al detall espanyol agrupa <strong>{fnum(total_subs)} empreses</strong> en "
                f"<strong>{len(df_subs)} subsectors</strong>. <strong>{leader['label']}</strong> "
                f"és el que té més empreses ({fnum(leader['empreses'])}), seguit de "
                f"<strong>{runner['label'] if runner is not None else '—'}</strong>"
                + (f" ({fnum(runner['empreses'])})" if runner is not None else "")
                + f". Els tres subsectors amb més empreses concentren un "
                f"<strong>{fpct(top3_share, 1, sign=False)}</strong> del total — un nivell de "
                f"concentració moderat per la naturalesa fragmentada del comerç de proximitat. "
                f"<br><br>"
            )
            # Verb dinàmic segons signe agregat
            verb_agregat = "ha perdut" if var_total < 0 else "ha guanyat"
            # Validar que el winner realment creix (var_pct > 0); altrament reformular
            _winner_positiu = float(winner["var_pct"]) > 0
            _loser_negatiu = float(loser["var_pct"]) < 0
            lider_frase = (
                f"<strong>{winner['label']}</strong> lidera el creixement "
                f"({fpct(winner['var_pct'])}), una xifra coherent amb el desplaçament del consum "
                f"cap a canals digitals i nous formats de proximitat. "
                if _winner_positiu else
                f"Cap subsector no creix de manera neta; <strong>{winner['label']}</strong> "
                f"({fpct(winner['var_pct'])}) és el que cau menys, mentre que "
            )
            pateix_frase = (
                f"<strong>{loser['label']}</strong> és el que més pateix ({fpct(loser['var_pct'])}), "
                f"un patró típic dels subsectors amb més pressió de la digitalització i del comerç de gran format. "
                if _loser_negatiu else
                f"<strong>{loser['label']}</strong> ({fpct(loser['var_pct'])}) tanca el rànquing, "
                f"encara que també en territori positiu. "
            )
            txt += (
                f"Entre {first_year} i {last_year}, el sector <strong>{verb_agregat}</strong> un "
                f"<strong>{fpct(abs(var_total), 1, sign=False)}</strong> d'empreses en agregat. La dinàmica és "
                f"asimètrica: <strong>{n_grow} subsector{'s' if n_grow != 1 else ''} creixen</strong> i "
                f"<strong>{n_lose} subsector{'s' if n_lose != 1 else ''} perden</strong> teixit "
                f"empresarial. {lider_frase}{pateix_frase}"
                f"<br><br>"
                f"<em>Lectura amb les altres pestanyes:</em> el rànquing per <strong>nombre d'empreses</strong> "
                f"no és el mateix que el rànquing per <strong>facturació</strong> o per "
                f"<strong>ocupació</strong>. Els subsectors amb molts establiments petits (vestit, "
                f"alimentació especialitzada) tenen molt més pes en empreses que en xifra de negoci. "
                f"Els no especialitzats, al revés, dominen en facturació amb un nombre relativament reduït "
                f"d'empreses (consolidació en grans operadors). Veure pestanya Activitat per a la "
                f"comparativa."
            )
            insight(txt)
        else:
            txt_es = (
                f"El comercio al detalle español agrupa <strong>{fnum(total_subs)} empresas</strong> en "
                f"<strong>{len(df_subs)} subsectores</strong>. <strong>{leader['label']}</strong> "
                f"es el que tiene más empresas ({fnum(leader['empreses'])}), seguido de "
                f"<strong>{runner['label'] if runner is not None else '—'}</strong>"
                + (f" ({fnum(runner['empreses'])})" if runner is not None else "")
                + f". Los tres subsectores con más empresas concentran un "
                f"<strong>{fpct(top3_share, 1, sign=False)}</strong> del total — un nivel de "
                f"concentración moderado por la naturaleza fragmentada del comercio de proximidad. "
                f"<br><br>"
            )
            verb_agregat_es = "ha perdido" if var_total < 0 else "ha ganado"
            _winner_positiu = float(winner["var_pct"]) > 0
            _loser_negatiu = float(loser["var_pct"]) < 0
            lider_frase_es = (
                f"<strong>{winner['label']}</strong> lidera el crecimiento "
                f"({fpct(winner['var_pct'])}), una cifra coherente con el desplazamiento del consumo "
                f"hacia canales digitales y nuevos formatos de proximidad. "
                if _winner_positiu else
                f"Ningún subsector crece de forma neta; <strong>{winner['label']}</strong> "
                f"({fpct(winner['var_pct'])}) es el que menos cae, mientras que "
            )
            pateix_frase_es = (
                f"<strong>{loser['label']}</strong> es el que más sufre ({fpct(loser['var_pct'])}), "
                f"un patrón típico de los subsectores con más presión de la digitalización y del comercio de gran formato. "
                if _loser_negatiu else
                f"<strong>{loser['label']}</strong> ({fpct(loser['var_pct'])}) cierra el ranking, "
                f"aunque también en territorio positivo. "
            )
            txt_es += (
                f"Entre {first_year} y {last_year}, el sector <strong>{verb_agregat_es}</strong> un "
                f"<strong>{fpct(abs(var_total), 1, sign=False)}</strong> de empresas en agregado. La dinámica es "
                f"asimétrica: <strong>{n_grow} subsector{'es' if n_grow != 1 else ''} crecen</strong> y "
                f"<strong>{n_lose} subsector{'es' if n_lose != 1 else ''} pierden</strong> tejido "
                f"empresarial. {lider_frase_es}{pateix_frase_es}"
                f"<br><br>"
                f"<em>Lectura con las otras pestañas:</em> el ranking por <strong>número de empresas</strong> "
                f"no coincide con el ranking por <strong>facturación</strong> o por "
                f"<strong>empleo</strong>. Los subsectores con muchos establecimientos pequeños (vestido, "
                f"alimentación especializada) pesan mucho más en empresas que en cifra de negocios. "
                f"Los no especializados, al revés, dominan en facturación con un número relativamente "
                f"reducido de empresas (consolidación en grandes operadores). Ver pestaña Actividad para "
                f"la comparativa."
            )
            insight(txt_es)

# ============================================================
# TAB 2: ACTIVITAT I PRODUCTIVITAT - EAS
# ============================================================
with tab2:
    if df_eas.empty:
        st.info("Sense dades disponibles." if _ca else "Sin datos disponibles.")
    else:
        last_year = int(df_eas["any"].max())
        df_last = df_eas[df_eas["any"] == last_year].copy()
        df_subs = df_last[
            (df_last["codi"] != "47") & (~df_last["codi"].isin(EXCLUDE_CODES))
        ].copy()
        df_subs["label"] = df_subs["codi"].map(SLABEL)
        df_subs["examples"] = df_subs["codi"].map(SEXAMPLES).fillna("")

        if _ca:
            st.caption(
                "**Notes metodològiques.** *Inclou comerç electrònic*: l'Enquesta Estructural d'Empreses "
                "recull totes les empreses CNAE 47, incloent el comerç electrònic pur (CNAE 479) i les "
                "vendes online d'establiments tradicionals (que es comptabilitzen al seu subsector "
                "principal). *Preus corrents*: les magnituds es mostren a preus de cada any (no "
                "deflactades). Per a una comparació real amb la pàgina Productivitat, cal aplicar el "
                "deflactor IPC. *Coincidència amb altres apartats*: el Personal coincideix amb la pàgina "
                "Productivitat; la suma dels subsectors té un gap del 0,5–1% respecte al total CNAE 47 "
                "per arrodoniments estadístics de la mateixa enquesta."
            )
        else:
            st.caption(
                "**Notas metodológicas.** *Incluye comercio electrónico*: la Encuesta Estructural de "
                "Empresas recoge todas las empresas CNAE 47, incluyendo el comercio electrónico puro "
                "(CNAE 479) y las ventas online de establecimientos tradicionales (contabilizadas en su "
                "subsector principal). *Precios corrientes*: las magnitudes se muestran a precios de "
                "cada año (sin deflactar). Para una comparación real con la página Productividad, "
                "aplicar el deflactor IPC. *Coincidencia con otros apartados*: el Personal coincide con "
                "la página Productividad; la suma de subsectores tiene un gap del 0,5–1% respecto al "
                "total CNAE 47 por redondeos estadísticos de la misma encuesta."
            )

        df_xn = df_subs.sort_values("xifra_negoci", ascending=True)
        _xn_lead = df_xn.iloc[-1]
        _xn_tot = df_subs["xifra_negoci"].sum()
        _xn_share = _xn_lead["xifra_negoci"] / _xn_tot * 100 if _xn_tot else 0
        if _ca:
            exhibit_header(
                1, f"{_xn_lead['label']} factura {fpct(_xn_share, 1, sign=False)} "
                   f"del comerç al detall ({last_year})",
                note="Pocs operadors grans (Mercadona, Carrefour, Lidl, El Corte Inglés) "
                     "expliquen el gruix del volum dels establiments no especialitzats.")
        else:
            exhibit_header(
                1, f"{_xn_lead['label']} factura {fpct(_xn_share, 1, sign=False)} "
                   f"del comercio minorista ({last_year})",
                note="Pocos operadores grandes (Mercadona, Carrefour, Lidl, El Corte Inglés) "
                     "explican el grueso del volumen de los establecimientos no especializados.")

        fig_xn = go.Figure()
        fig_xn.add_trace(go.Bar(
            y=df_xn["label"], x=df_xn["xifra_negoci"] / 1e9,
            orientation="h",
            marker_color=NAVY,
            text=[f"{v/1e9:.1f}".replace(".", ",") + " M€" for v in df_xn["xifra_negoci"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_xn[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"<i>{HOVER_LBL_EX}:</i> "
                "%{customdata[0]}<br>"
                + ("<b>Xifra de negoci</b>: " if _ca else "<b>Cifra de negocios</b>: ")
                + "%{x:.1f} k milions €<extra></extra>"
            ),
        ))
        apply_layout(fig_xn,
            xaxis_title=("Xifra de negoci (k milions €)" if _ca else "Cifra de negocios (mil millones €)"),
            height=max(420, len(df_xn) * 38 + 100),
            margin=dict(l=240, r=120, t=40, b=50),
            hovermode="closest",
        )
        st.plotly_chart(fig_xn, use_container_width=True)
        source("INE, Enquesta Estructural d'Empreses Sector Comerç, taula 76818" if _ca
               else "INE, Encuesta Estructural de Empresas Sector Comercio, tabla 76818")

        # Productivitat: VA per persona ocupada
        df_pr = df_subs.copy()
        df_pr["productivitat"] = df_pr["valor_afegit"] / df_pr["personal_ocupat"]
        df_pr = df_pr.sort_values("productivitat", ascending=True)

        # Mitjana ponderada dels subsectors mostrats (exclou 473)
        va_sum = df_subs["valor_afegit"].sum()
        per_sum = df_subs["personal_ocupat"].sum()
        avg_prod = va_sum / per_sum if per_sum else None

        _pr_top = df_pr.iloc[-1]
        _pr_bot = df_pr.iloc[0]
        _pr_ratio = _pr_top["productivitat"] / _pr_bot["productivitat"] if _pr_bot["productivitat"] else 0
        if _ca:
            exhibit_header(
                2, f"{_pr_top['label']} genera {fnum(_pr_ratio, 1)} vegades més valor "
                   f"per ocupat que {_pr_bot['label']} ({last_year})",
                note="La bretxa de productivitat reflecteix intensitat de capital, tícket mitjà "
                     "i escala empresarial molt diferents entre subsectors.")
        else:
            exhibit_header(
                2, f"{_pr_top['label']} genera {fnum(_pr_ratio, 1)} veces más valor "
                   f"por ocupado que {_pr_bot['label']} ({last_year})",
                note="La brecha de productividad refleja intensidad de capital, ticket medio "
                     "y escala empresarial muy distintos entre subsectores.")

        fig_pr = go.Figure()
        fig_pr.add_trace(go.Bar(
            y=df_pr["label"], x=df_pr["productivitat"],
            orientation="h",
            marker_color=OCRE,
            text=[f"{v/1000:.1f}".replace(".", ",") + "k€" for v in df_pr["productivitat"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_pr[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"<i>{HOVER_LBL_EX}:</i> "
                "%{customdata[0]}<br>"
                + ("<b>Productivitat</b>: " if _ca else "<b>Productividad</b>: ")
                + "%{x:,.0f} €/ocupat<extra></extra>"
            ).replace(",", "."),
        ))
        if avg_prod:
            fig_pr.add_vline(
                x=avg_prod, line_dash="dash", line_color=NAVY, line_width=2,
                annotation_text=f"{'Mitjana subsectors' if _ca else 'Media subsectores'}: {avg_prod/1000:.1f}k€".replace(".", ","),
                annotation_position="top right",
            )
        apply_layout(fig_pr,
            xaxis_title=("VA / persona ocupada (€)" if _ca else "VA / persona ocupada (€)"),
            height=max(420, len(df_pr) * 38 + 100),
            margin=dict(l=240, r=180, t=40, b=50),
            hovermode="closest",
        )
        st.plotly_chart(fig_pr, use_container_width=True)
        source("INE, Enquesta Estructural d'Empreses Sector Comerç. Càlcul propi" if _ca
               else "INE, Encuesta Estructural de Empresas Sector Comercio. Cálculo propio")

        # Personal ocupat
        df_per = df_subs.sort_values("personal_ocupat", ascending=True)
        _per_lead = df_per.iloc[-1]
        _per_tot = df_subs["personal_ocupat"].sum()
        _per_share = _per_lead["personal_ocupat"] / _per_tot * 100 if _per_tot else 0
        if _ca:
            exhibit_header(
                3, f"{_per_lead['label']} ocupa {fpct(_per_share, 1, sign=False)} "
                   f"de les persones del comerç al detall ({last_year})")
        else:
            exhibit_header(
                3, f"{_per_lead['label']} ocupa {fpct(_per_share, 1, sign=False)} "
                   f"de las personas del comercio minorista ({last_year})")

        df_per = df_subs.sort_values("personal_ocupat", ascending=True)
        fig_per = go.Figure()
        fig_per.add_trace(go.Bar(
            y=df_per["label"], x=df_per["personal_ocupat"],
            orientation="h",
            marker_color=OCRE_DEEP,
            text=[fnum(v) for v in df_per["personal_ocupat"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_per[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"<i>{HOVER_LBL_EX}:</i> "
                "%{customdata[0]}<br>"
                + ("<b>Persones ocupades</b>: " if _ca else "<b>Personas ocupadas</b>: ")
                + "%{x:,.0f}<extra></extra>"
            ).replace(",", "."),
        ))
        apply_layout(fig_per,
            xaxis_title=("Persones ocupades" if _ca else "Personas ocupadas"),
            height=max(420, len(df_per) * 38 + 100),
            margin=dict(l=240, r=120, t=40, b=50),
            hovermode="closest",
        )
        st.plotly_chart(fig_per, use_container_width=True)
        source("INE, Enquesta Estructural d'Empreses Sector Comerç" if _ca
               else "INE, Encuesta Estructural de Empresas Sector Comercio")

        # ── Insight productivitat (analisi profunda) ──────────
        top_pr = df_pr.iloc[-1]
        bot_pr = df_pr.iloc[0]
        ratio_pr = top_pr["productivitat"] / bot_pr["productivitat"] if bot_pr["productivitat"] else 0

        # Concentracio: subsector amb mes xifra negoci i quina quota representa
        df_xn_desc = df_subs.sort_values("xifra_negoci", ascending=False).reset_index(drop=True)
        top_xn = df_xn_desc.iloc[0]
        total_xn = df_subs["xifra_negoci"].sum()
        share_top_xn = top_xn["xifra_negoci"] / total_xn * 100 if total_xn else 0

        # Subsector mes intensiu en ma d'obra (mes ocupats per cada milio de XN)
        df_subs_ratio = df_subs.copy()
        df_subs_ratio["intensitat_laboral"] = df_subs_ratio["personal_ocupat"] / (df_subs_ratio["xifra_negoci"] / 1e6)
        most_labor = df_subs_ratio.sort_values("intensitat_laboral", ascending=False).iloc[0]
        least_labor = df_subs_ratio.sort_values("intensitat_laboral", ascending=True).iloc[0]

        # Empreses mitjanes (xifra negoci / nombre empreses)
        df_subs_size = df_subs.copy()
        if "n_empreses_eas" in df_subs_size.columns:
            df_subs_size["xn_per_empresa"] = df_subs_size["xifra_negoci"] / df_subs_size["n_empreses_eas"]
            biggest = df_subs_size.sort_values("xn_per_empresa", ascending=False).iloc[0]
            smallest = df_subs_size.sort_values("xn_per_empresa", ascending=True).iloc[0]
        else:
            biggest = smallest = None

        if _ca:
            txt = (
                f"<strong>{top_xn['label']}</strong> domina la facturació del comerç al detall espanyol "
                f"amb <strong>{top_xn['xifra_negoci']/1e9:.1f} k milions €</strong>".replace(".", ",")
                + f" — un <strong>{fpct(share_top_xn, 1, sign=False)}</strong> del total. "
                f"Aquesta concentració contrasta amb el rànquing per nombre d'empreses (vegeu pestanya "
                f"Estructura empresarial): hi ha pocs operadors molt grans (Mercadona, Carrefour, El "
                f"Corte Inglés, Lidl) que mouen el gruix del volum. "
                f"<br><br>"
                f"<strong>Dispersió de la productivitat:</strong> "
                f"<strong>{top_pr['label']}</strong> ({top_pr['productivitat']/1000:.1f}k€".replace(".", ",")
                + f" de VA per ocupat) genera "
                f"<strong>{ratio_pr:.1f}".replace(".", ",")
                + f" vegades més valor</strong> per persona que <strong>{bot_pr['label']}</strong> "
                f"({bot_pr['productivitat']/1000:.1f}k€)".replace(".", ",") + ". "
                f"Aquesta bretxa s'explica per tres factors: "
                f"<strong>(i) intensitat de capital</strong> "
                f"(equips TIC i articles d'us domestic operen amb molts metres quadrats de magatzem "
                f"automatitzat per ocupat); "
                f"<strong>(ii) tícket mitjà</strong> "
                f"(un sofà o una rentadora tenen marges absoluts molt superiors a una camisa); "
                f"<strong>(iii) escala empresarial</strong> "
                f"(els subsectors amb operadors grans negocien amb proveïdors i optimitzen costos). "
                f"<br><br>"
                f"<strong>Intensitat laboral:</strong> <strong>{most_labor['label']}</strong> és el "
                f"subsector amb més persones ocupades per milió de € facturats "
                f"({most_labor['intensitat_laboral']:.1f}".replace(".", ",")
                + f" ocupats/M€), reflectint la importància de l'atenció al client en aquest segment. "
                f"<strong>{least_labor['label']}</strong> és el menys intensiu "
                f"({least_labor['intensitat_laboral']:.1f}".replace(".", ",")
                + f" ocupats/M€). "
                + (f"<br><br><strong>Dimensió empresarial mitjana:</strong> les empreses de "
                   f"<strong>{biggest['label']}</strong> facturen "
                   f"<strong>{biggest['xn_per_empresa']/1e6:.1f} M€</strong>".replace(".", ",")
                   + f" de mitjana cada una, mentre que les de <strong>{smallest['label']}</strong> "
                   f"només facturen {smallest['xn_per_empresa']/1e6:.1f} M€".replace(".", ",")
                   + ". Aquesta diferència de més de "
                   f"<strong>{biggest['xn_per_empresa']/smallest['xn_per_empresa']:.0f}× </strong>"
                   f"il·lustra la dualitat estructural del sector: pocs operadors grans en alguns "
                   f"subsectors versus xarxes molt fragmentades de petits comerços en altres."
                   if biggest is not None else "")
            )
            insight(txt)
        else:
            txt = (
                f"<strong>{top_xn['label']}</strong> domina la facturación del comercio al detalle "
                f"español con <strong>{top_xn['xifra_negoci']/1e9:.1f} k millones €</strong>".replace(".", ",")
                + f" — un <strong>{fpct(share_top_xn, 1, sign=False)}</strong> del total. "
                f"Esta concentración contrasta con el ranking por número de empresas (ver pestaña "
                f"Estructura empresarial): hay pocos operadores muy grandes (Mercadona, Carrefour, "
                f"El Corte Inglés, Lidl) que mueven el grueso del volumen. "
                f"<br><br>"
                f"<strong>Dispersión de la productividad:</strong> "
                f"<strong>{top_pr['label']}</strong> ({top_pr['productivitat']/1000:.1f}k€".replace(".", ",")
                + f" de VA por ocupado) genera "
                f"<strong>{ratio_pr:.1f}".replace(".", ",")
                + f" veces más valor</strong> por persona que <strong>{bot_pr['label']}</strong> "
                f"({bot_pr['productivitat']/1000:.1f}k€)".replace(".", ",") + ". "
                f"Esta brecha se explica por tres factores: "
                f"<strong>(i) intensidad de capital</strong> "
                f"(equipos TIC y artículos de uso doméstico operan con muchos metros cuadrados de "
                f"almacén automatizado por ocupado); "
                f"<strong>(ii) ticket medio</strong> "
                f"(un sofá o una lavadora tienen márgenes absolutos muy superiores a una camisa); "
                f"<strong>(iii) escala empresarial</strong> "
                f"(los subsectores con operadores grandes negocian con proveedores y optimizan costes). "
                f"<br><br>"
                f"<strong>Intensidad laboral:</strong> <strong>{most_labor['label']}</strong> es el "
                f"subsector con más personas ocupadas por millón de € facturados "
                f"({most_labor['intensitat_laboral']:.1f}".replace(".", ",")
                + f" ocupados/M€), reflejando la importancia de la atención al cliente en este segmento. "
                f"<strong>{least_labor['label']}</strong> es el menos intensivo "
                f"({least_labor['intensitat_laboral']:.1f}".replace(".", ",")
                + f" ocupados/M€). "
                + (f"<br><br><strong>Dimensión empresarial media:</strong> las empresas de "
                   f"<strong>{biggest['label']}</strong> facturan "
                   f"<strong>{biggest['xn_per_empresa']/1e6:.1f} M€</strong>".replace(".", ",")
                   + f" de media cada una, mientras que las de <strong>{smallest['label']}</strong> "
                   f"solo facturan {smallest['xn_per_empresa']/1e6:.1f} M€".replace(".", ",")
                   + ". Esta diferencia de más de "
                   f"<strong>{biggest['xn_per_empresa']/smallest['xn_per_empresa']:.0f}× </strong>"
                   f"ilustra la dualidad estructural del sector: pocos operadores grandes en algunos "
                   f"subsectores versus redes muy fragmentadas de pequeños comercios en otros."
                   if biggest is not None else "")
            )
            insight(txt)

# ============================================================
# TAB 3: DEMANDA - EPF
# ============================================================
with tab3:
    if df_epf.empty:
        st.info("Sense dades disponibles." if _ca else "Sin datos disponibles.")
    else:
        last_year = int(df_epf["any"].max())
        first_year = int(df_epf["any"].min())
        retail_codis = list(COICOP_TO_CNAE.keys())

        # Filtrar nomes categories de despesa que es compren al CNAE 47
        df_last = df_epf[df_epf["any"] == last_year].copy()
        df_groups = df_last[df_last["codi_coicop"].isin(retail_codis)].copy()
        # Etiquetes alineades amb els subsectors CNAE de les altres pestanyes
        df_groups["label"] = df_groups["codi_coicop"].map(DLABEL)
        df_groups["label_demanda"] = df_groups["codi_coicop"].map(CLABEL)
        df_groups["cnae_codis"] = df_groups["codi_coicop"].map(
            lambda c: ", ".join(COICOP_TO_CNAE.get(c, []))
        )
        def _demand_examples(c):
            override = DEMAND_EXAMPLES[LANG].get(c)
            if override:
                return wrap_text(override)
            return wrap_text(", ".join(
                SUBSECTOR_EXAMPLES[LANG].get(cnae, "") for cnae in COICOP_TO_CNAE.get(c, [])
            ).strip(", "))
        df_groups["examples"] = df_groups["codi_coicop"].map(_demand_examples)

        if _ca:
            st.caption(
                "Es mostren només les categories de despesa de les llars que es compren al "
                "**comerç al detall (CNAE 47)**. Es deixen fora les categories que no es compren "
                "al comerç minorista (habitatge, transport, restauració, educació). Vestit, "
                "farmàcies i cosmètics formen part del mateix subsector CNAE 477 però es "
                "mostren separats perquè la despesa familiar els recull en categories diferents. "
                "Veure el mapeig detallat a la pàgina Metodologia."
            )
        else:
            st.caption(
                "Se muestran solo las categorías de gasto de los hogares que se compran en el "
                "**comercio al detalle (CNAE 47)**. Se dejan fuera las categorías que no se compran "
                "en el comercio minorista (vivienda, transporte, restauración, educación). Vestido, "
                "farmacias y cosméticos forman parte del mismo subsector CNAE 477 pero se muestran "
                "separados porque el gasto familiar los recoge en categorías diferentes. "
                "Ver el mapeo detallado en la página Metodología."
            )

        df_groups = df_groups.sort_values("despesa_per_llar", ascending=True)

        _ep_lead = df_groups.iloc[-1]
        if _ca:
            exhibit_header(
                1, f"{_ep_lead['label']} encapçala la despesa de la llar al comerç al "
                   f"detall: {fnum(_ep_lead['despesa_per_llar'])} €/any ({last_year})",
                note="Es mostren només les categories de despesa que es compren al comerç "
                     "minorista; queden fora habitatge, transport, restauració i educació.")
        else:
            exhibit_header(
                1, f"{_ep_lead['label']} encabeza el gasto del hogar en el comercio "
                   f"minorista: {fnum(_ep_lead['despesa_per_llar'])} €/año ({last_year})",
                note="Se muestran solo las categorías de gasto que se compran en el comercio "
                     "minorista; quedan fuera vivienda, transporte, restauración y educación.")

        fig_epf = go.Figure()
        fig_epf.add_trace(go.Bar(
            y=df_groups["label"], x=df_groups["despesa_per_llar"],
            orientation="h",
            marker_color=NAVY,
            text=[fnum(v) + " €" for v in df_groups["despesa_per_llar"]],
            textposition="outside",
            textfont=dict(size=11),
            customdata=df_groups[["examples"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                + f"<i>{HOVER_LBL_EX}:</i> "
                + "%{customdata[0]}<br>"
                + ("<b>Despesa anual</b>: " if _ca else "<b>Gasto anual</b>: ")
                + "%{x:,.0f} €<extra></extra>"
            ).replace(",", "."),
        ))
        apply_layout(fig_epf,
            xaxis_title=("Despesa mitjana anual per llar (€)" if _ca else "Gasto medio anual por hogar (€)"),
            height=max(420, len(df_groups) * 38 + 100),
            margin=dict(l=320, r=120, t=40, b=50),
            hovermode="closest",
        )
        st.plotly_chart(fig_epf, use_container_width=True)
        source("INE, Enquesta de Pressupostos Familiars, taula 75003. Càlcul propi" if _ca
               else "INE, Encuesta de Presupuestos Familiares, tabla 75003. Cálculo propio")

        # KPIs: despesa al comerc al detall vs total llar, evolucio
        df_total = df_last[df_last["codi_coicop"] == "00"]
        despesa_retail = df_groups["despesa_per_llar"].sum()
        despesa_total = df_total.iloc[0]["despesa_per_llar"] if not df_total.empty else None
        quota_retail = (despesa_retail / despesa_total * 100) if despesa_total else 0

        # Evolucio quota: comparar amb primer any disponible
        df_first_yr = df_epf[df_epf["any"] == first_year]
        d_retail_first = df_first_yr[df_first_yr["codi_coicop"].isin(retail_codis)]["despesa_per_llar"].sum()
        d_total_first = df_first_yr[df_first_yr["codi_coicop"] == "00"]["despesa_per_llar"].sum()
        quota_first = (d_retail_first / d_total_first * 100) if d_total_first else 0
        delta_quota = quota_retail - quota_first

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            f"{'Despesa al comerç al detall' if _ca else 'Gasto en el comercio al detalle'} ({last_year})",
            fnum(despesa_retail) + " €",
        )
        col2.metric(
            f"{'Despesa total / llar' if _ca else 'Gasto total / hogar'} ({last_year})",
            (fnum(despesa_total) + " €") if despesa_total else "—",
        )
        col3.metric(
            f"{'% al comerç al detall' if _ca else '% en el comercio al detalle'}",
            fpct(quota_retail, 1, sign=False),
            delta=fpct(delta_quota, 1) + (f" vs {first_year}"),
            delta_color="normal",
        )
        col4.metric(
            f"{'Categoria principal' if _ca else 'Categoría principal'}",
            df_groups.iloc[-1]["label"],
            delta=fnum(df_groups.iloc[-1]["despesa_per_llar"]) + " €/any",
            delta_color="off",
        )

        _lbl_evo_exp = ("Veure evolució temporal de la despesa per categoria"
                       if _ca else
                       "Ver evolución temporal del gasto por categoría")
        with highlight_expander(_lbl_evo_exp, expanded=False):
            # Evolucio temporal (line chart simple amb pivot table)
            sel_default = ["01", "03", "05", "09"]
            sel_codis = st.multiselect(
                ("Selecciona categories" if _ca else "Selecciona categorías"),
                options=retail_codis,
                default=sel_default,
                format_func=lambda c: DLABEL.get(c, c),
                key="evo_subsectors",
            )

            if sel_codis:
                df_evo = df_epf[df_epf["codi_coicop"].isin(sel_codis)].copy()
                df_evo["categoria"] = df_evo["codi_coicop"].map(DLABEL)
                df_evo = df_evo.sort_values(["codi_coicop", "any"])

                fig_evo = go.Figure()
                for i, codi in enumerate(sel_codis):
                    d = df_evo[df_evo["codi_coicop"] == codi]
                    if d.empty:
                        continue
                    fig_evo.add_trace(go.Scatter(
                        x=d["any"].tolist(),
                        y=d["despesa_per_llar"].tolist(),
                        mode="lines+markers",
                        name=DLABEL.get(codi, codi),
                        line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
                        marker=dict(size=6),
                        hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:,.0f} €<extra></extra>",
                    ))
                fig_evo.update_layout(
                    yaxis_title=("Despesa mitjana anual per llar (€)" if _ca else "Gasto medio anual por hogar (€)"),
                    height=460,
                    font=dict(family="Inter, sans-serif", size=13),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=60, r=260, t=40, b=50),
                    xaxis=dict(gridcolor="rgba(0,0,0,0.06)", zeroline=False),
                    yaxis=dict(gridcolor="rgba(0,0,0,0.06)", zeroline=False),
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1.0,
                        xanchor="left",
                        x=1.02,
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="rgba(0,0,0,0.1)",
                        borderwidth=1,
                    ),
                    hovermode="x unified",
                )
                st.plotly_chart(fig_evo, use_container_width=True)
                source("INE, Enquesta de Pressupostos Familiars (preus constants)" if _ca
                       else "INE, Encuesta de Presupuestos Familiares (precios constantes)")

        # ── Insight Demanda (analisi profunda) ─────────────────
        df_groups_sorted = df_groups.sort_values("despesa_per_llar", ascending=False)
        cat_top = df_groups_sorted.iloc[0]
        cat_bot = df_groups_sorted.iloc[-1]

        # Categoria amb major creixement i caiguda entre first_year i last_year
        df_first_lookup = df_epf[df_epf["any"] == first_year].set_index("codi_coicop")["despesa_per_llar"]
        df_last_lookup = df_epf[df_epf["any"] == last_year].set_index("codi_coicop")["despesa_per_llar"]
        var_per_cat = []
        for c in retail_codis:
            if c in df_first_lookup.index and c in df_last_lookup.index:
                v0 = df_first_lookup[c]
                v1 = df_last_lookup[c]
                if v0 > 0:
                    var_per_cat.append({
                        "codi": c,
                        "label": DLABEL.get(c, c),
                        "var_pct": (v1 / v0 - 1) * 100,
                        "abs_diff": v1 - v0,
                    })
        df_dyn = pd.DataFrame(var_per_cat)
        cat_winner = df_dyn.sort_values("var_pct", ascending=False).iloc[0] if not df_dyn.empty else None
        cat_loser = df_dyn.sort_values("var_pct", ascending=True).iloc[0] if not df_dyn.empty else None

        if _ca:
            insight(
                f"Les llars espanyoles dediquen <strong>{fnum(despesa_retail)} €/any</strong> a categories "
                f"que es compren al comerç al detall, un <strong>{fpct(quota_retail, 1, sign=False)}</strong> "
                f"de la seva despesa total ({fnum(despesa_total) if despesa_total else '—'} €). "
                f"Aquest pes ha {('augmentat' if delta_quota >= 0 else 'disminuït')} "
                f"<strong>{fpct(abs(delta_quota), 1, sign=False)}</strong> respecte al {first_year}, "
                f"cosa que reflecteix com el comerç de proximitat compita cada cop més contra "
                f"despeses no comercialitzables (lloguer, energia, oci fora de la llar). "
                f"<br><br>"
                f"<strong>{cat_top['label']}</strong> ({fnum(cat_top['despesa_per_llar'])} €/any) "
                f"concentra el gruix de la despesa al comerç al detall per llar. "
                f"La categoria amb més dinamisme és <strong>{cat_winner['label']}</strong> "
                f"({fpct(cat_winner['var_pct'])} entre {first_year} i {last_year}), reflectint canvis "
                f"de patrons de consum. <strong>{cat_loser['label']}</strong> mostra la pitjor evolució "
                f"({fpct(cat_loser['var_pct'])}), un senyal de pressió sobre el comerç tradicional al "
                f"qual va lligada aquesta categoria. "
                f"<br><br>"
                f"<em>Despesa de les llars vs facturació de les empreses:</em> les dades d'aquesta "
                f"pestanya recullen <strong>què compren les llars espanyoles</strong>, sigui on sigui "
                f"que ho comprin (botiga del barri, web espanyola o web estrangera). En canvi, la "
                f"pestanya Activitat recull <strong>què venen les empreses fiscalment establertes "
                f"a Espanya</strong>. La diferència entre tots dos imports és informativa: "
                f"<br><br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;• Si en una categoria <strong>la despesa de les llars creix "
                f"més ràpid que la facturació del subsector espanyol</strong> corresponent, és senyal "
                f"que part del consum se'n va a canals fora del comerç al detall espanyol: marketplaces "
                f"estrangers (Amazon, AliExpress, Temu, Shein), importacions directes, o operadors "
                f"d'altres CNAE (per exemple, telefonia es paga a operadores classificats fora del CNAE 47).<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;• Si la facturació espanyola creix més ràpid que la despesa "
                f"de les llars, és senyal de captura de quota: el comerç espanyol està venent més a "
                f"empreses, turistes o exportant.<br>"
                f"<br>"
                f"<em>La comparació no és literal</em> (cal multiplicar la despesa per llar pel nombre "
                f"de llars i el mapeig categories↔subsectors és aproximat), però la <strong>tendència "
                f"relativa</strong> sí que és reveladora i explica part de la pèrdua de teixit "
                f"empresarial en categories molt exposades als marketplaces internacionals (moda, "
                f"electrònica, articles de la llar)."
            )
        else:
            insight(
                f"Los hogares españoles dedican <strong>{fnum(despesa_retail)} €/año</strong> a categorías "
                f"que se compran en el comercio al detalle, un <strong>{fpct(quota_retail, 1, sign=False)}</strong> "
                f"de su gasto total ({fnum(despesa_total) if despesa_total else '—'} €). "
                f"Este peso ha {('aumentado' if delta_quota >= 0 else 'disminuido')} "
                f"<strong>{fpct(abs(delta_quota), 1, sign=False)}</strong> respecto a {first_year}, "
                f"reflejando cómo el comercio de proximidad compite cada vez más contra "
                f"gastos no comercializables (alquiler, energía, ocio fuera del hogar). "
                f"<br><br>"
                f"<strong>{cat_top['label']}</strong> ({fnum(cat_top['despesa_per_llar'])} €/año) "
                f"concentra el grueso del gasto minorista por hogar. "
                f"La categoría más dinámica es <strong>{cat_winner['label']}</strong> "
                f"({fpct(cat_winner['var_pct'])} entre {first_year} y {last_year}), reflejando cambios "
                f"en patrones de consumo. <strong>{cat_loser['label']}</strong> muestra la peor evolución "
                f"({fpct(cat_loser['var_pct'])}), señal de presión sobre el comercio tradicional ligado "
                f"a esta categoría. "
                f"<br><br>"
                f"<em>Gasto de los hogares vs facturación de las empresas:</em> los datos de esta "
                f"pestaña recogen <strong>qué compran los hogares españoles</strong>, sea donde sea "
                f"que lo compren (tienda del barrio, web española o web extranjera). En cambio, la "
                f"pestaña Actividad recoge <strong>qué venden las empresas fiscalmente establecidas "
                f"en España</strong>. La diferencia entre ambos importes es informativa: "
                f"<br><br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;• Si en una categoría <strong>el gasto de los hogares crece "
                f"más rápido que la facturación del subsector español</strong> correspondiente, es "
                f"señal de que parte del consumo se va a canales fuera del comercio al detalle español: "
                f"marketplaces extranjeros (Amazon, AliExpress, Temu, Shein), importaciones directas, "
                f"u operadores de otros CNAE (por ejemplo, telefonía se paga a operadoras clasificadas "
                f"fuera del CNAE 47).<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;• Si la facturación española crece más rápido que el gasto "
                f"de los hogares, es señal de captura de cuota: el comercio español está vendiendo "
                f"más a empresas, turistas o exportando.<br>"
                f"<br>"
                f"<em>La comparación no es literal</em> (hay que multiplicar el gasto por hogar por "
                f"el número de hogares y el mapeo categorías↔subsectores es aproximado), pero la "
                f"<strong>tendencia relativa</strong> sí es reveladora y explica parte de la pérdida "
                f"de tejido empresarial en categorías muy expuestas a los marketplaces internacionales "
                f"(moda, electrónica, artículos del hogar)."
            )

# ─── Descàrrega ──────────────────────────────────────────────

with st.expander("Descàrrega de dades" if _ca else "Descarga de datos"):
    if not df_dirce.empty:
        st.markdown(
            "**Estructura empresarial** (empreses per subsector — Directori Central d'Empreses)"
            if _ca else
            "**Estructura empresarial** (empresas por subsector — Directorio Central de Empresas)"
        )
        st.dataframe(df_dirce, use_container_width=True, hide_index=True)
        st.download_button(
            ("Descarregar CSV (estructura)" if _ca else "Descargar CSV (estructura)"),
            df_dirce.to_csv(index=False).encode("utf-8"),
            "subsectors_estructura.csv", "text/csv",
        )
    if not df_eas.empty:
        st.markdown(
            "**Activitat empresarial** (xifra de negoci, valor afegit, personal — Enquesta Estructural d'Empreses)"
            if _ca else
            "**Actividad empresarial** (cifra de negocios, valor añadido, personal — Encuesta Estructural de Empresas)"
        )
        st.dataframe(df_eas, use_container_width=True, hide_index=True)
        st.download_button(
            ("Descarregar CSV (activitat)" if _ca else "Descargar CSV (actividad)"),
            df_eas.to_csv(index=False).encode("utf-8"),
            "subsectors_activitat.csv", "text/csv",
        )
    if not df_epf.empty:
        st.markdown(
            "**Despesa familiar** (despesa per categoria — Enquesta de Pressupostos Familiars)"
            if _ca else
            "**Gasto familiar** (gasto por categoría — Encuesta de Presupuestos Familiares)"
        )
        st.dataframe(df_epf, use_container_width=True, hide_index=True)
        st.download_button(
            ("Descarregar CSV (despesa)" if _ca else "Descargar CSV (gasto)"),
            df_epf.to_csv(index=False).encode("utf-8"),
            "subsectors_despesa.csv", "text/csv",
        )

page_meta(
    "INE: Directori Central d'Empreses (T=73019), Enquesta Estructural d'Empreses Sector Comerç (T=76818), Enquesta de Pressupostos Familiars (T=75003)"
    if _ca else
    "INE: Directorio Central de Empresas (T=73019), Encuesta Estructural de Empresas Sector Comercio (T=76818), Encuesta de Presupuestos Familiares (T=75003)",
    st.session_state.lang,
)

# ============================================================
# TAB 4: DETALL ALIMENTACIÓ (472) - EAS 4 dígits
# ============================================================
with tab4:
    if df_472.empty:
        st.info("Sense dades disponibles." if _ca else "Sin datos disponibles.")
    else:
        if _ca:
            exhibit_header(
                1, "Dins l'alimentació especialitzada, cada especialitat segueix la seva pròpia corba",
                note="Tria una especialitat per separar el creixement nominal de l'efecte preus.")
        else:
            exhibit_header(
                1, "Dentro de la alimentación especializada, cada especialidad sigue su propia curva",
                note="Elige una especialidad para separar el crecimiento nominal del efecto precios.")
        st.caption(
            "Tria una especialitat per veure'n l'evolució 2018-2024. El gràfic s'indexa a l'any "
            "inicial (=100) i mostra la facturació a preus corrents (nominal) i constants (deflactada "
            "per IPC general): el solc entre totes dues és l'efecte de la inflació. "
            "Font: INE, Enquesta Estructural d'Empreses (taula 76818) + IPC (taula 50902)." if _ca
            else "Elige una especialidad para ver su evolución 2018-2024. El gráfico se indexa al año "
                 "inicial (=100) y muestra la facturación a precios corrientes (nominal) y constantes "
                 "(deflactada con IPC general): la brecha entre ambas es el efecto de la inflación. "
                 "Fuente: INE, Encuesta Estructural de Empresas (tabla 76818) + IPC (tabla 50902)."
        )

        LABELS_472 = {
            "4721": ("Fruiteries", "Fruterías"),
            "4722": ("Carnisseries", "Carnicerías"),
            "4723": ("Peixateries", "Pescaderías"),
            "4724": ("Forns i pastisseries", "Panaderías y pastelerías"),
            "4725": ("Begudes", "Bebidas"),
            "4726": ("Estancs (tabac)", "Estancos (tabaco)"),
            "4729": ("Altres aliments", "Otros alimentos"),
        }
        lbl472 = lambda c: LABELS_472.get(c, (c, c))[0 if _ca else 1]

        # Selector d'especialitat (ordre: peix, carn, fruita, forn, begudes, tabac, altres)
        ordre = ["4723", "4722", "4721", "4724", "4725", "4726", "4729"]
        codis = [c for c in ordre if c in df_472["codi"].unique()]
        sel = st.selectbox(
            "Especialitat" if _ca else "Especialidad",
            options=codis, format_func=lbl472, key="sec_472",
        )

        d = df_472[df_472["codi"] == sel].sort_values("any")
        yr0, yr1 = int(d["any"].min()), int(d["any"].max())
        r0, r1 = d[d["any"] == yr0].iloc[0], d[d["any"] == yr1].iloc[0]
        sec = lbl472(sel)

        def _delta(a, b):
            return (b / a - 1) * 100 if a else float("nan")

        f0, f1 = r0["xifra_negoci"], r1["xifra_negoci"]
        e0, e1 = r0["n_empreses_eas"], r1["n_empreses_eas"]
        o0, o1 = r0["personal_ocupat"], r1["personal_ocupat"]
        df_pct, de_pct, do_pct = _delta(f0, f1), _delta(e0, e1), _delta(o0, o1)
        has_real = ("xifra_negoci_constants" in d.columns
                    and pd.notna(r0.get("xifra_negoci_constants"))
                    and pd.notna(r1.get("xifra_negoci_constants")))
        if has_real:
            fc0, fc1 = r0["xifra_negoci_constants"], r1["xifra_negoci_constants"]
            dfr_pct = _delta(fc0, fc1)

        # KPIs (últim any + variació respecte de l'any inicial)
        if has_real:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(("Facturació nominal" if _ca else "Facturación nominal") + f" {yr1}",
                      f"{fnum(f1 / 1e6)} M€", fpct(df_pct, 1))
            k2.metric(("Facturació real" if _ca else "Facturación real") + f" {yr0}-{yr1}",
                      fpct(dfr_pct, 1))
            k3.metric(("Establiments" if _ca else "Establecimientos") + f" {yr1}",
                      fnum(e1), fpct(de_pct, 1))
            k4.metric(("Ocupació" if _ca else "Ocupación") + f" {yr1}",
                      fnum(o1), fpct(do_pct, 1))
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric(("Facturació" if _ca else "Facturación") + f" {yr1}",
                      f"{fnum(f1 / 1e6)} M€", fpct(df_pct, 1))
            k2.metric(("Establiments" if _ca else "Establecimientos") + f" {yr1}",
                      fnum(e1), fpct(de_pct, 1))
            k3.metric(("Ocupació" if _ca else "Ocupación") + f" {yr1}",
                      fnum(o1), fpct(do_pct, 1))

        # Gràfic indexat (base any inicial = 100): fa visible la divergència
        fig = go.Figure()
        for col, name, color in (
            ("xifra_negoci", "Facturació (nominal)" if _ca else "Facturación (nominal)", NAVY),
            ("n_empreses_eas", "Establiments" if _ca else "Establecimientos", OCRE),
            ("personal_ocupat", "Ocupació" if _ca else "Ocupación", G1_P),
        ):
            base = d[d["any"] == yr0][col].iloc[0]
            if base:
                fig.add_trace(go.Scatter(
                    x=d["any"], y=d[col] / base * 100, mode="lines+markers",
                    name=name, line=dict(color=color, width=2.8),
                ))
        # Facturació a preus constants (puntejada): el solc respecte de la nominal és la inflació.
        if has_real:
            base_c = d[d["any"] == yr0]["xifra_negoci_constants"].iloc[0]
            if base_c:
                fig.add_trace(go.Scatter(
                    x=d["any"], y=d["xifra_negoci_constants"] / base_c * 100,
                    mode="lines+markers",
                    name=("Facturació (constant)" if _ca else "Facturación (constante)"),
                    line=dict(color=OCRE_DEEP, width=2.2, dash="dash"),
                ))
        fig.add_hline(y=100, line=dict(color="#bbb", width=1, dash="dot"))
        apply_layout(fig, yaxis_title=f"Índex ({yr0}=100)", height=420)
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)
        source(
            "INE, Enquesta Estructural d'Empreses Sector Comerç, taula 76818 (CNAE 4 dígits)" if _ca
            else "INE, Encuesta Estructural de Empresas Sector Comercio, tabla 76818 (CNAE 4 dígitos)"
        )

        # ── Anàlisi desenvolupada per especialitat ──
        size0, size1 = (f0 / e0 if e0 else 0), (f1 / e1 if e1 else 0)
        ds_pct = _delta(size0, size1)
        emp0, emp1 = (o0 / e0 if e0 else 0), (o1 / e1 if e1 else 0)
        emp0_s, emp1_s = f"{emp0:.1f}".replace(".", ","), f"{emp1:.1f}".replace(".", ",")
        fo0, fo1 = (f0 / o0 if o0 else 0), (f1 / o1 if o1 else 0)
        dfo_pct = _delta(fo0, fo1)
        tot_f1 = df_472[df_472["any"] == yr1]["xifra_negoci"].sum()
        share = f1 / tot_f1 * 100 if tot_f1 else 0

        if de_pct < -1 and df_pct > 1:
            patro = ("una dinàmica de <strong>consolidació</strong>: la facturació creix mentre el "
                     "nombre d'establiments es redueix") if _ca else (
                     "una dinámica de <strong>consolidación</strong>: la facturación crece mientras "
                     "el número de establecimientos se reduce")
        elif de_pct > 1 and df_pct > 1:
            patro = ("una fase d'<strong>expansió</strong>: creixen alhora la facturació i el nombre "
                     "d'establiments") if _ca else (
                     "una fase de <strong>expansión</strong>: crecen a la vez la facturación y el "
                     "número de establecimientos")
        elif df_pct < -1 and de_pct < -1:
            patro = ("un <strong>retrocés</strong>: cauen tant la facturació com el nombre "
                     "d'establiments") if _ca else (
                     "un <strong>retroceso</strong>: caen tanto la facturación como el número de "
                     "establecimientos")
        else:
            patro = ("una evolució <strong>mixta</strong>") if _ca else (
                     "una evolución <strong>mixta</strong>")

        puja = lambda x, ca: (("puja" if x >= 0 else "cau") if ca else ("sube" if x >= 0 else "cae"))
        if has_real:
            inf_dif = df_pct - dfr_pct  # punts de diferència nominal − real (efecte preus)
            tot_infl_ca = "tot el creixement nominal és inflació" if (df_pct > 0 and dfr_pct <= 0) else "la inflació n'explica bona part"
            tot_infl_es = "todo el crecimiento nominal es inflación" if (df_pct > 0 and dfr_pct <= 0) else "la inflación explica buena parte"
            real_ca = (f" En termes <strong>reals</strong> (deflactat per IPC, base {yr0}), però, la facturació "
                       f"{puja(dfr_pct, 1)} un <strong>{fpct(abs(dfr_pct), 1, sign=False)}</strong>: "
                       f"{tot_infl_ca} ({fpct(abs(inf_dif), 1, sign=False)} de diferència).")
            real_es = (f" En términos <strong>reales</strong> (deflactado con IPC, base {yr0}), en cambio, la facturación "
                       f"{puja(dfr_pct, 0)} un <strong>{fpct(abs(dfr_pct), 1, sign=False)}</strong>: "
                       f"{tot_infl_es} ({fpct(abs(inf_dif), 1, sign=False)} de diferencia).")
        else:
            real_ca = real_es = ""
        if _ca:
            analisi = (
                f"Entre {yr0} i {yr1}, les <strong>{sec.lower()}</strong> mostren {patro}. "
                f"La facturació nominal {puja(df_pct, 1)} un <strong>{fpct(abs(df_pct), 1, sign=False)}</strong> "
                f"(fins a {fnum(f1 / 1e6)} M€).{real_ca} "
                f"Els establiments {puja(de_pct, 1)} un "
                f"<strong>{fpct(abs(de_pct), 1, sign=False)}</strong> i l'ocupació {puja(do_pct, 1)} un "
                f"<strong>{fpct(abs(do_pct), 1, sign=False)}</strong>."
                "<br><br>"
                f"<strong>Lectura estructural.</strong> La facturació mitjana per establiment ha passat de "
                f"{fnum(size0 / 1e3)} a {fnum(size1 / 1e3)} milers d'euros ({fpct(ds_pct, 1)}); cada "
                f"establiment ocupa ara {emp1_s} persones de mitjana (era {emp0_s} el {yr0}). "
                f"La facturació per persona ocupada {puja(dfo_pct, 1)} un "
                f"{fpct(abs(dfo_pct), 1, sign=False)}, senyal de "
                f"{'guany' if dfo_pct >= 0 else 'pèrdua'} de productivitat aparent. "
                f"L'especialitat concentra el <strong>{fpct(share, 1, sign=False)}</strong> de la "
                f"facturació del comerç d'alimentació especialitzat (grup 472)."
            )
        else:
            analisi = (
                f"Entre {yr0} y {yr1}, las <strong>{sec.lower()}</strong> muestran {patro}. "
                f"La facturación nominal {puja(df_pct, 0)} un <strong>{fpct(abs(df_pct), 1, sign=False)}</strong> "
                f"(hasta {fnum(f1 / 1e6)} M€).{real_es} "
                f"Los establecimientos {puja(de_pct, 0)} un "
                f"<strong>{fpct(abs(de_pct), 1, sign=False)}</strong> y la ocupación {puja(do_pct, 0)} un "
                f"<strong>{fpct(abs(do_pct), 1, sign=False)}</strong>."
                "<br><br>"
                f"<strong>Lectura estructural.</strong> La facturación media por establecimiento ha pasado de "
                f"{fnum(size0 / 1e3)} a {fnum(size1 / 1e3)} miles de euros ({fpct(ds_pct, 1)}); cada "
                f"establecimiento ocupa ahora {emp1_s} personas de media (era {emp0_s} en {yr0}). "
                f"La facturación por persona ocupada {puja(dfo_pct, 0)} un "
                f"{fpct(abs(dfo_pct), 1, sign=False)}, señal de "
                f"{'ganancia' if dfo_pct >= 0 else 'pérdida'} de productividad aparente. "
                f"La especialidad concentra el <strong>{fpct(share, 1, sign=False)}</strong> de la "
                f"facturación del comercio de alimentación especializado (grupo 472)."
            )
        insight(analisi)

