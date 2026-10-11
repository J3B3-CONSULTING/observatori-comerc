"""
Migració completa del pipeline CSV -> DuckDB pel chatbot de retail.
Esquema (format llarg/tidy) definit a schema.sql: observations + series_metadata.

Convenció (confirmada 2026-08-03 després del pilot amb icm/epa_retail/ipc_coicop):
  - Magnituds/unitats diferents (encara que vinguin en un mateix CSV, ample o
    llarg) -> serie_id propi.
  - Categories DINS la mateixa magnitud (territori, sexe, branca CNAE, grup
    ECOICOP, tecnologia...) -> dimensió (dim_1/dim_2/dim_3), no serie propi.

30 caches -> 3 exclusions:
  - municipal: exclòs del chatbot públic (decisió explícita).
  - lideres_empreses, prediccions_estructura: NO són series temporals
    (entitat-atribut / registre d'esdeveniments amb múltiples dates per fila)
    — no encaixen amb l'esquema observations. Vegeu SKIPPED avall.

Execució: python3 data/sql/migrate.py
"""
import os
import sys
import duckdb
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.config import TRENCAMENTS_DIRCE, nota_trencament_dirce  # noqa: E402
from data.sql.derivats import DERIVATS  # noqa: E402
from data.sql.fets import construeix as construeix_fets  # noqa: E402
from data.sql.dimensions import (  # noqa: E402
    ALIES_BRANCA, ALIES_CCAA_INE, ALIES_PROV_INE, ALIES_TERRITORI,
    DIM_AVIS, DIM_BRANCA, DIM_TERRITORI, resol,
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "observatori.duckdb")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def _load(name):
    # Els codis de territori ("08", "00") han de quedar com a text.
    return pd.read_csv(os.path.join(CACHE_DIR, f"{name}.csv"),
                       dtype={"codi_geo": str, "codi_prov": str, "codi_ccaa": str,
                              "cnae": str})


# ─── Helpers genèrics de data ────────────────────────────────────────────────

def _annual_date(df):
    return pd.to_datetime(dict(year=df["any"], month=1, day=1)).dt.date


def _monthly_date(df, any_col="any", mes_col="mes"):
    return pd.to_datetime(dict(year=df[any_col], month=df[mes_col], day=1)).dt.date


def _periode_monthly_date(df, col="periode"):
    return pd.to_datetime(df[col] + "-01").dt.date


def _asis_date(df, col="data"):
    return pd.to_datetime(df[col]).dt.date


# ─── Helper genèric: cache CSV (ample o llarg) -> tidy (date,value,dim_1..3) ─
# Cobreix TOTS els casos: extreure una columna d'un CSV ample (split per
# mètrica) i extreure la columna "valor" d'un CSV ja llarg (nomes cal
# renombrar dims) són la mateixa operació.

def _series_builder(cache_name, metric_col, date_fn, dim_cols=(), row_filter=None):
    def _build():
        df = _load(cache_name).copy()
        if row_filter is not None:
            df = df[row_filter(df)].copy()
        out = pd.DataFrame({"date": date_fn(df), "value": df[metric_col].values})
        for i, dc in enumerate(dim_cols, start=1):
            out[f"dim_{i}"] = df[dc].values
        return out
    return _build


# ─── Transformacions: CSV cache (ample o llarg) -> tidy (date,value,dim_1,dim_2,dim_3) ───

def _build_icm(tipus):
    df = _load("icm")
    df = df[df["tipus"] == tipus].copy()
    df["date"] = pd.to_datetime(df["data"]).dt.date
    return df.rename(columns={"valor": "value", "branca": "dim_1", "ambit": "dim_2",
                               "indicador": "dim_3"})[["date", "value", "dim_1", "dim_2", "dim_3"]]


def _build_epa_retail(metric_col):
    df = _load("epa_retail").copy()
    mes_inici = (df["trimestre"] - 1) * 3 + 1
    df["date"] = pd.to_datetime(dict(year=df["any"], month=mes_inici, day=1)).dt.date
    df["value"] = df[metric_col]
    df["dim_1"] = df["sexe"]
    return df[["date", "value", "dim_1"]]


def _build_ipc_coicop():
    df = _load("ipc_coicop").copy()
    df["date"] = pd.to_datetime(dict(year=df["any"], month=df["mes"], day=1)).dt.date
    df["value"] = df["ipc"]
    df["dim_1"] = df["grup"]
    return df[["date", "value", "dim_1"]]


# ─── Registre de sèries pilot ────────────────────────────────────────────────
# "tipus" de l'ICM (nominal/real/ocupació) esdevé serie_id perquè són magnituds
# i unitats diferents (€ corrents / € constants / persones), no una dimensió
# dins la mateixa magnitud — a diferència de "branca" o "grup", que sí ho són.

SERIES = [
    dict(serie_id="icm_nominal", name="ICM — cifra de negoci nominal",
         description="Índex de comerç al detall (cifra de negoci a preus corrents), "
                      "per branca CNAE 47 i CCAA. Base 2021=100.",
         source="INE", source_table="T=59787+60110",
         frequency="monthly", unit="índex / % variació",
         is_critical=True, is_derived=False, is_public=True,
         build=lambda: _build_icm("nominal")),
    dict(serie_id="icm_real", name="ICM — cifra de negoci real",
         description="Índex de comerç al detall (cifra de negoci a preus constants, "
                      "deflactat), per branca CNAE 47 i CCAA. Base 2021=100.",
         source="INE", source_table="T=60096+60111",
         frequency="monthly", unit="índex / % variació",
         is_critical=True, is_derived=False, is_public=True,
         build=lambda: _build_icm("real")),
    dict(serie_id="icm_ocupacio", name="ICM — ocupació",
         description="Índex d'ocupació mensual del comerç al detall, per branca "
                      "CNAE 47. Base 2021=100.",
         source="INE", source_table="T=60114+60115",
         frequency="monthly", unit="índex / % variació",
         is_critical=True, is_derived=False, is_public=True,
         build=lambda: _build_icm("ocupacio")),
    dict(serie_id="epa_retail_ocupats", name="EPA — ocupats al comerç al detall",
         description="Ocupats CNAE 47 net (comerç al detall, excepte vehicles de "
                      "motor i motocicletes), per sexe. Font: Encuesta de Población "
                      "Activa (EPA).",
         source="INE", source_table="T=65123",
         frequency="quarterly", unit="milers de persones",
         is_critical=False, is_derived=False, is_public=True,
         build=lambda: _build_epa_retail("ocupats_cnae47_milers")),
    dict(serie_id="epa_retail_aturats", name="EPA — aturats (secció G)",
         description="Aturats de la secció G (comerç a l'engròs + al detall + "
                      "reparació de vehicles), per sexe. L'INE NO desglossa els "
                      "aturats a nivell CNAE 47 — aquesta xifra inclou també "
                      "l'engròs i la reparació de vehicles, no només comerç al "
                      "detall.",
         source="INE", source_table="T=65249",
         frequency="quarterly", unit="milers de persones",
         is_critical=False, is_derived=False, is_public=True,
         build=lambda: _build_epa_retail("aturats_seccio_g_milers")),
    dict(serie_id="epa_retail_hores", name="EPA — hores setmanals (secció G)",
         description="Mitjana d'hores efectives setmanals treballades a la "
                      "secció G (comerç a l'engròs + al detall + reparació de "
                      "vehicles), per sexe. L'INE NO desglossa aquesta magnitud "
                      "a nivell CNAE 47.",
         source="INE", source_table="T=65159",
         frequency="quarterly", unit="hores/setmana (mitjana)",
         is_critical=False, is_derived=False, is_public=True,
         build=lambda: _build_epa_retail("hores_setmana_seccio_g")),
    dict(serie_id="ipc_coicop", name="IPC per grups (alimentació, vestit, llar)",
         description="Índex de Preus de Consum mensual per grups ECOICOP "
                      "rellevants pel comerç al detall (alimentació, vestit i "
                      "calçat, parament de la llar) + índex general de referència. "
                      "Base 2021=100.",
         source="INE", source_table="T=76125",
         frequency="monthly", unit="índex (base 2021=100)",
         is_critical=False, is_derived=False, is_public=True,
         build=_build_ipc_coicop),
]


# ─── Sèries restants (26 caches -> ~90 sèries) ───────────────────────────────
# is_critical s'hereta de CRITICAL_SOURCES a processor.py: totes les sub-series
# d'un cache crític (pib_vab, empreses, productivitat, europa_vab,
# europa_retail_mensual) hereten is_critical=True; la resta, False.
# is_derived=True nomes per estructura_comerc (model propi J3B3).

def _icm_distribucio_build(tipus):
    return _series_builder(
        "icm_distribucion", "valor",
        lambda df: _asis_date(df),
        dim_cols=["modo", "indicador"],
        row_filter=lambda df, t=tipus: df["tipus"] == t,
    )()


SERIES_EXTRA = []


def _add(serie_id, name, description, source, source_table, frequency, unit,
         is_critical, is_derived, cache_name, metric_col, date_fn, dim_cols=(),
         row_filter=None, nota_trencament=None):
    SERIES_EXTRA.append(dict(
        serie_id=serie_id, name=name, description=description, source=source,
        source_table=source_table, frequency=frequency, unit=unit,
        is_critical=is_critical, is_derived=is_derived, is_public=True,
        nota_trencament=nota_trencament,
        build=_series_builder(cache_name, metric_col, date_fn, dim_cols, row_filter),
    ))


# Sèries del DIRCE: la nota surt de TRENCAMENTS_DIRCE (data/config.py).
_NOTA_DIRCE = nota_trencament_dirce()


# --- pib_vab (INE T=69070) — CRITICAL — sense dimensió (agregat nacional) ---
for col, unit, desc in [
    ("vab_total_corrents", "M EUR (preus corrents)", "VAB total de l'economia espanyola, preus corrents."),
    ("vab_cnae47_corrents", "M EUR (preus corrents)", "VAB del comerç al detall (CNAE 47), preus corrents."),
    ("vab_cnae47_constants", "M EUR (preus constants)", "VAB del comerç al detall (CNAE 47), preus constants (volum encadenat)."),
    ("vab_total_constants", "M EUR (preus constants)", "VAB total de l'economia espanyola, preus constants."),
    ("pes_cnae47", "ràtio (0-1)", "Pes del VAB del comerç al detall sobre el VAB total (preus corrents)."),
    ("var_vab_cnae47_corrents", "% variació anual", "Variació interanual del VAB CNAE 47 a preus corrents."),
    ("var_vab_cnae47_constants", "% variació anual", "Variació interanual del VAB CNAE 47 a preus constants."),
]:
    _add(f"pib_vab_{col}", f"PIB/VAB — {col}", desc, "INE", "T=69070",
         "annual", unit, True, False, "pib_vab", col, _annual_date)

# --- empreses (INE T=39372+3954+298 DIRCE + T=2915+56934 Padró) — CRITICAL ---
_add("empreses_count", "Empreses actives CNAE 47", "Nombre d'empreses actives del comerç al detall (CNAE 47), per territori.",
     "INE", "T=39372+3954+298", "annual", "nombre d'empreses", True, False,
     "empreses", "empreses", _annual_date, dim_cols=["territori"],
     nota_trencament=_NOTA_DIRCE)
_add("empreses_poblacio", "Població (per territori)", "Població per territori, usada com a denominador de densitat comercial.",
     "INE", "T=2915+56934", "annual", "persones", True, False,
     "empreses", "poblacio", _annual_date, dim_cols=["territori"])
_add("empreses_per_1000hab", "Densitat comercial", "Empreses actives CNAE 47 per cada 1.000 habitants, per territori.",
     "INE", "T=39372+3954+298 / T=2915+56934 (ràtio derivada)", "annual", "empreses / 1.000 hab.", True, False,
     "empreses", "empreses_per_1000hab", _annual_date, dim_cols=["territori"],
     nota_trencament=_NOTA_DIRCE)

# --- locals_provincia (INE T=301 DIRCE locals + T=29005 Padró sumat) — no crítica ---
# LOCALS, no empreses: sèries independents de empreses_*, no comparables.
# dim_1 = codi INE de província ('00' = Espanya), dim_2 = nom.
_LOCALS_AVIS = (" Mesura LOCALS (unitats locals: una empresa amb tres botigues compta "
                "tres), no empreses: no es pot comparar amb empreses_count.")
for sid, col, unit, tbl, desc in [
    ("locals_prov_count", "locals_cnae47", "nombre de locals", "T=301",
     "Locals actius del comerç al detall (CNAE 47) per província."),
    ("locals_prov_per_1000hab", "locals_per_1000hab", "locals / 1.000 hab.",
     "T=301 / T=29005 (ràtio derivada)",
     "Densitat comercial: locals CNAE 47 per cada 1.000 habitants, per província."),
]:
    _add(sid, f"Locals per província — {col}", desc + _LOCALS_AVIS, "INE", tbl,
         "annual", unit, False, False, "locals_provincia", col, _annual_date,
         dim_cols=["codi_geo", "provincia"], nota_trencament=_NOTA_DIRCE)
_add("poblacio_prov", "Població per província (padró)",
     "Població oficial del padró a 1 de gener per província (suma dels municipis), "
     "denominador de la densitat de locals.",
     "INE", "T=29005 (sumada per província)", "annual", "persones", False, False,
     "locals_provincia", "poblacio", _annual_date, dim_cols=["codi_geo", "provincia"])

# --- locals_ccaa_grups (INE T=294 DIRCE locals per grups) — no crítica ---
# dim_1 = codi INE de CCAA ('00' = Espanya), dim_2 = grup CNAE (47, 471..479), dim_3 = nom CCAA.
_add("locals_ccaa_grup", "Locals per CCAA i grup CNAE 47",
     "Locals actius del comerç al detall per CCAA i grup CNAE (471-479, més el total 47)."
     + _LOCALS_AVIS,
     "INE", "T=294", "annual", "nombre de locals", False, False,
     "locals_ccaa_grups", "locals", _annual_date, dim_cols=["codi_geo", "cnae", "ccaa"],
     nota_trencament=_NOTA_DIRCE)

# --- productivitat (INE T=36194 EEE Comercio + T=36199 P&L + T=50902 IPC) — CRITICAL ---
_PROD = [
    ("xifra_negoci_constants", "EUR (preus constants)", "T=36194 (deflactat amb T=50902)", "Xifra de negoci del comerç al detall, preus constants."),
    ("valor_afegit_constants", "EUR (preus constants)", "T=36194 (deflactat amb T=50902)", "Valor afegit del comerç al detall, preus constants."),
    ("personal_ocupat", "persones", "T=36194", "Personal ocupat al comerç al detall."),
    ("hores_treballades", "milers d'hores", "T=36194", "Hores treballades pel personal remunerat, comerç al detall."),
    ("productivitat_va_hora", "EUR/hora", "T=36194 (ràtio derivada)", "Productivitat: valor afegit constant per hora treballada."),
    ("productivitat_xn_hora", "EUR/hora", "T=36194 (ràtio derivada)", "Productivitat: xifra de negoci constant per hora treballada."),
    ("gastos_personal", "EUR (preus corrents)", "T=36194", "Despeses de personal, comerç al detall."),
    ("gastos_personal_constants", "EUR (preus constants)", "T=36194 (deflactat amb T=50902)", "Despeses de personal, preus constants."),
    ("quota_salarial", "ràtio (0-1)", "T=36194 (ràtio derivada)", "Despeses de personal sobre valor afegit."),
    ("excedent_brut", "EUR (preus corrents)", "T=36194 (ràtio derivada)", "Excedent brut d'explotació (valor afegit - despeses de personal)."),
    ("cost_laboral_per_ocupat", "EUR/persona", "T=36194 (ràtio derivada)", "Cost laboral mitjà per ocupat."),
    ("cost_laboral_hora", "EUR/hora", "T=36194+50902 (ràtio derivada)", "Cost laboral per hora treballada, preus constants."),
    ("cogs", "EUR (preus corrents)", "T=36199", "Consum de béns i serveis per a revenda (cost de mercaderia venuda)."),
    ("cogs_constants", "EUR (preus constants)", "T=36199 (deflactat amb T=50902)", "COGS, preus constants."),
    ("serveis_exteriors", "EUR (preus corrents)", "T=36199", "Despeses en serveis exteriors (lloguers, energia, serveis externs)."),
    ("serveis_exteriors_constants", "EUR (preus constants)", "T=36199 (deflactat amb T=50902)", "Serveis exteriors, preus constants."),
    ("marge_brut", "ràtio (0-1)", "T=36194+36199 (ràtio derivada)", "Marge brut comptable: (vendes - COGS) / vendes."),
]
for col, unit, tbl, desc in _PROD:
    _add(f"productivitat_{col}", f"Productivitat — {col}", desc, "INE", tbl,
         "annual", unit, True, False, "productivitat", col, _annual_date)

# --- europa_vab (Eurostat nama_10_a64) — CRITICAL — dim: pais ---
for col, unit, desc in [
    ("vab_meur", "M EUR", "VAB del comerç al detall (G47), per país."),
    ("vab_total_meur", "M EUR", "VAB total de l'economia, per país."),
    ("pes_cnae47", "ràtio (0-1)", "Pes del G47 sobre el VAB total, per país."),
]:
    _add(f"europa_vab_{col}", f"Europa VAB — {col}", desc, "Eurostat", "nama_10_a64",
         "annual", unit, True, False, "europa_vab", col, _annual_date, dim_cols=["pais"])

# --- europa_retail_mensual (Eurostat sts_trtu_m) — CRITICAL — dim: pais ---
_add("europa_retail_mensual_index", "Europa — volum de vendes retail (índex)",
     "Índex de volum de vendes del comerç al detall (G47), ajustat estacional, base 2021=100, per país.",
     "Eurostat", "sts_trtu_m", "monthly", "índex (base 2021=100)", True, False,
     "europa_retail_mensual", "index_volum", _periode_monthly_date, dim_cols=["pais"])
_add("europa_retail_mensual_yoy", "Europa — volum de vendes retail (variació interanual)",
     "Variació interanual de l'índex de volum de vendes retail, per país.",
     "Eurostat", "sts_trtu_m", "monthly", "% variació anual", True, False,
     "europa_retail_mensual", "yoy", _periode_monthly_date, dim_cols=["pais"])

# --- icm_distribucion (INE T=60105 nominal / T=75809 real / T=60115 ocupació) — CRITICAL ---
for tipus, tid, label in [
    ("nominal", "T=60105", "cifra de negoci nominal"),
    ("real", "T=75809", "cifra de negoci real"),
    ("ocupacio", "T=60115", "ocupació"),
]:
    SERIES_EXTRA.append(dict(
        serie_id=f"icm_distribucio_{tipus}", name=f"ICM per modo distribució — {label}",
        description=f"Índex de {label} del comerç al detall per modo de distribució "
                     "(Empresas unilocalizadas / Pequeñas cadenas / Grandes cadenas / "
                     "Grandes Superficies). Base 2021=100.",
        source="INE", source_table=tid, frequency="monthly", unit="índex / % variació",
        is_critical=True, is_derived=False, is_public=True,
        build=(lambda t=tipus: _icm_distribucio_build(t)),
    ))

# --- ipc (INE T=50902) — no crítica — sense dimensió ---
_add("ipc", "IPC general", "Índex de Preus de Consum general nacional, base 2021=100.",
     "INE", "T=50902", "monthly", "índex (base 2021=100)", False, False,
     "ipc", "ipc", _monthly_date)

# --- confianza_consumidor (Eurostat ei_bsco_m) — no crítica — sense dimensió ---
for col, label, desc in [
    ("index_confianca", "índex compost", "Indicador compost de confiança del consumidor (mitjana de 4 components a 12 mesos vista)."),
    ("situacio_actual_financera", "situació actual — financera", "Balanç d'opinió sobre la situació financera de la llar, últims 12 mesos."),
    ("situacio_actual_economica", "situació actual — econòmica", "Balanç d'opinió sobre la situació econòmica general, últims 12 mesos."),
    ("expectatives_financera", "expectatives — financera", "Balanç d'opinió sobre la situació financera de la llar, propers 12 mesos."),
    ("expectatives_economica", "expectatives — econòmica", "Balanç d'opinió sobre la situació econòmica general, propers 12 mesos."),
]:
    _add(f"confianza_consumidor_{col}", f"Confiança consumidor — {label}", desc,
         "Eurostat", "ei_bsco_m", "monthly", "balanç de respostes (-100..100)", False, False,
         "confianza_consumidor", col, _monthly_date)

# --- targetes_tpv (Banco de España, STMP) — no crítica — sense dimensió ---
for col, unit, desc in [
    ("import_milions", "M EUR", "Import de les compres amb targeta en terminals de punt de venda a Espanya (totes les activitats, no només comerç)."),
    ("operacions_milers", "milers d'operacions", "Nombre de compres amb targeta en terminals de punt de venda a Espanya."),
    ("tiquet_mitja_eur", "EUR per operació", "Import mitjà per compra amb targeta (import / operacions)."),
    ("var_import", "% variació interanual", "Variació interanual de l'import de les compres amb targeta en TPV."),
    ("var_operacions", "% variació interanual", "Variació interanual del nombre de compres amb targeta en TPV."),
]:
    _add(f"targetes_tpv_{col}", f"Compres amb targeta en TPV — {col}", desc,
         "Banco de España", "tarjetas1.xlsx (STMP)", "quarterly", unit, False,
         col == "tiquet_mitja_eur", "targetes_tpv", col, _asis_date)

# --- digitalitzacio_comerc (Eurostat isoc_*) — no crítica — dims: tech, pais ---
_add("digitalitzacio_comerc", "Digitalització del comerç (TIC)",
     "Percentatge d'empreses del comerç (G47) que adopten venda electrònica, IA o núvol.",
     "Eurostat", "isoc_* (múltiples datasets TIC)", "annual", "% empreses", False, False,
     "digitalitzacio_comerc", "pct", _annual_date, dim_cols=["tech", "pais"])

# --- ocupacio_comerc (Eurostat lfsa_egan22d) — no crítica — dims: pais, sexe, edat ---
_add("ocupacio_comerc", "Ocupació al comerç per sexe i edat",
     "Persones ocupades al comerç al detall (G47), per país, sexe i franja d'edat.",
     "Eurostat", "lfsa_egan22d", "annual", "milers de persones", False, False,
     "ocupacio_comerc", "ocupats_milers", _annual_date, dim_cols=["pais", "sexe", "edat"])

# --- eaes (INE T=28185) — no crítica — dim: sector ---
_add("eaes", "Salari brut anual per sector", "Salari brut anual mitjà, per sector d'activitat (comparativa amb el comerç).",
     "INE", "T=28185", "annual", "EUR/any", False, False,
     "eaes", "valor", _annual_date, dim_cols=["sector"])

# --- ecommerce (CNMC) — no crítica (exclosa expressament) — sense dimensió ---
for sid, col, unit, desc in [
    ("ecommerce_total", "ecommerce_total_eur", "EUR", "Facturació total del comerç electrònic a Espanya (tots els sectors)."),
    ("ecommerce_cnae47", "ecommerce_cnae47_eur", "EUR", "Facturació del comerç electrònic del CNAE 47 (comerç al detall)."),
    ("ecommerce_pes_cnae47", "pes_cnae47_ecommerce", "ràtio (0-1)", "Pes del CNAE 47 sobre el total de comerç electrònic."),
]:
    _add(sid, f"E-commerce — {col}", desc, "CNMC", "Panel CNMC comercio electrónico",
         "annual", unit, False, False, "ecommerce", col, _annual_date)

# --- eee_ccaa (INE T=76817 + Eurostat nama_10r_3gva/nama_10_a64 per vab_eurostat) — no crítica ---
_EEE_CCAA = [
    ("locals", "nombre de locals", "T=76817", "Nombre de locals del comerç al detall, per CCAA."),
    ("xifra_negoci", "EUR", "T=76817", "Xifra de negoci del comerç al detall, per CCAA."),
    ("sous_salaris", "EUR", "T=76817", "Sous i salaris del comerç al detall, per CCAA."),
    ("inversio", "EUR", "T=76817", "Inversió en actius materials, per CCAA."),
    ("personal_ocupat", "persones", "T=76817", "Personal ocupat del comerç al detall, per CCAA."),
    ("vab_estimat", "EUR", "T=76817 (estimació via ràtio VA/XN)", "VAB estimat per CCAA (mètode ràtio nacional, preus constants)."),
    ("vab_estimat_nominal", "EUR", "T=76817 (estimació via ràtio VAB corrents/XN)", "VAB estimat per CCAA (mètode ràtio nacional, preus corrents)."),
    ("vab_eurostat", "EUR", "Eurostat nama_10r_3gva+nama_10_a64 (mètode híbrid)", "VAB estimat per CCAA (mètode híbrid comptabilitat regional)."),
    ("pes_cnae47_pib", "ràtio (0-1)", "Eurostat nama_10r_3gva+nama_10_a64", "Pes del CNAE 47 sobre el PIB de cada CCAA."),
]
for col, unit, tbl, desc in _EEE_CCAA:
    _add(f"eee_ccaa_{col}", f"EEE CCAA — {col}", desc, "INE/Eurostat", tbl,
         "annual", unit, False, False, "eee_ccaa", col, _annual_date, dim_cols=["territori"])

# --- subsectors_dirce (INE T=73019) — no crítica — dim: nom (subsector) ---
_add("subsectors_dirce_empreses", "Subsectors CNAE 47 — empreses (DIRCE)",
     "Nombre d'empreses per subsector CNAE 47 (471-479).",
     "INE", "T=73019", "annual", "nombre d'empreses", False, False,
     "subsectors_dirce", "empreses", _annual_date, dim_cols=["nom"],
     nota_trencament=_NOTA_DIRCE)

# --- subsectors_eas (INE T=76818) — no crítica — dim: nom (subsector) ---
for col, unit, desc in [
    ("n_empreses_eas", "nombre d'empreses", "Empreses per subsector CNAE 47 (font EAS)."),
    ("xifra_negoci", "EUR", "Xifra de negoci per subsector CNAE 47."),
    ("valor_afegit", "EUR", "Valor afegit per subsector CNAE 47."),
    ("inversio", "EUR", "Inversió per subsector CNAE 47."),
    ("personal_ocupat", "persones", "Personal ocupat per subsector CNAE 47."),
]:
    _add(f"subsectors_eas_{col}", f"Subsectors EAS — {col}", desc, "INE", "T=76818",
         "annual", unit, False, False, "subsectors_eas", col, _annual_date, dim_cols=["nom"])

# --- subsectors_472 (INE T=76818, detall alimentació) — no crítica — dim: nom ---
for col, unit, desc in [
    ("n_empreses_eas", "nombre d'empreses", "Empreses per categoria d'alimentació (472)."),
    ("xifra_negoci", "EUR (preus corrents)", "Xifra de negoci per categoria d'alimentació."),
    ("xifra_negoci_constants", "EUR (preus constants)", "Xifra de negoci per categoria d'alimentació, preus constants."),
    ("valor_afegit", "EUR", "Valor afegit per categoria d'alimentació."),
    ("inversio", "EUR", "Inversió per categoria d'alimentació."),
    ("personal_ocupat", "persones", "Personal ocupat per categoria d'alimentació."),
]:
    _add(f"subsectors_472_{col}", f"Subsectors 472 — {col}", desc, "INE", "T=76818",
         "annual", unit, False, False, "subsectors_472", col, _annual_date, dim_cols=["nom"])

# --- subsectors_epf (INE T=75003) — no crítica — dim: nom (categoria COICOP) ---
_add("subsectors_epf_despesa", "Despesa per llar (EPF, COICOP)",
     "Despesa mitjana per llar, per categoria de consum COICOP.",
     "INE", "T=75003", "annual", "EUR/llar/any", False, False,
     "subsectors_epf", "despesa_per_llar", _annual_date, dim_cols=["nom"])

# --- marges_branca_ine (INE T=76818) — no crítica — dim: branca ---
_add("marges_branca_ine", "Marge sobre vendes per branca",
     "Marge (EBE / xifra de negoci) per branca CNAE 47 a 3 dígits.",
     "INE", "T=76818", "annual", "% sobre vendes", False, False,
     "marges_branca_ine", "marge_vendes_pct", _annual_date, dim_cols=["branca"])

# --- cdmge (INE T=37808) — CRITICAL — dim: indicador (totes les variacions %) ---
_add("cdmge", "Comerç diari grans empreses (CDMGE)",
     "Variacions de vendes diàries de grans empreses del comerç al detall "
     "(diverses finestres de comparació: mensual/anual, vs. mes/any anterior).",
     "INE", "T=37808", "daily", "% variació", True, False,
     "cdmge", "valor", _asis_date, dim_cols=["indicador"])

# --- estructura_retail (Eurostat bd_size) — no crítica — dim: pais ---
_ER_INDIC = {
    "EMP_NR": ("estructura_retail_emp_nr", "persones", "Persones ocupades al comerç al detall (G47), per país."),
    "ENT_NR": ("estructura_retail_ent_nr", "nombre d'empreses", "Nombre d'empreses del comerç al detall (G47), per país."),
    "SAL_NR": ("estructura_retail_sal_nr", "persones", "Nombre d'assalariats al comerç al detall (G47), per país."),
    "ENT_BRTHR_PC": ("estructura_retail_ent_brthr_pc", "% anual", "Taxa de naixement d'empreses (G47), per país."),
    "ENT_DTHR_PC": ("estructura_retail_ent_dthr_pc", "% anual", "Taxa de mort d'empreses (G47), per país."),
    "ENT_BRTHR_DTHR_PC": ("estructura_retail_ent_brthr_dthr_pc", "% anual", "Taxa combinada naixement+mort d'empreses (G47), per país."),
    "GRW_ENT_PC": ("estructura_retail_grw_ent_pc", "% anual", "Taxa de creixement net d'empreses (G47), per país."),
}
for code, (sid, unit, desc) in _ER_INDIC.items():
    SERIES_EXTRA.append(dict(
        serie_id=sid, name=f"Estructura retail UE — {code}", description=desc,
        source="Eurostat", source_table="bd_size", frequency="annual", unit=unit,
        is_critical=False, is_derived=False, is_public=True,
        build=_series_builder("estructura_retail", "valor", _annual_date, dim_cols=["pais"],
                               row_filter=(lambda df, c=code: df["indic_sbs"] == c)),
    ))

# --- estructura_retail_mida (Eurostat bd_size, per mida d'empresa) — no crítica ---
_ERM_INDIC = {
    "EMP_NR": ("estructura_retail_mida_emp_nr", "persones", "Persones ocupades al comerç al detall (G47), per país i mida d'empresa."),
    "ENT_NR": ("estructura_retail_mida_ent_nr", "nombre d'empreses", "Nombre d'empreses del comerç al detall (G47), per país i mida d'empresa."),
}
for code, (sid, unit, desc) in _ERM_INDIC.items():
    SERIES_EXTRA.append(dict(
        serie_id=sid, name=f"Estructura retail UE per mida — {code}", description=desc,
        source="Eurostat", source_table="bd_size", frequency="annual", unit=unit,
        is_critical=False, is_derived=False, is_public=True,
        build=_series_builder("estructura_retail_mida", "valor", _annual_date,
                               dim_cols=["pais", "sizeclas"],
                               row_filter=(lambda df, c=code: df["indic_sbs"] == c)),
    ))

# --- estructura_retail_supervivencia (Eurostat bd_size) — no crítica — dims: pais, age ---
_add("estructura_retail_supervivencia", "Supervivència d'empreses (G47)",
     "Percentatge d'empreses del comerç al detall que sobreviuen N anys després de néixer.",
     "Eurostat", "bd_size", "annual", "% supervivència", False, False,
     "estructura_retail_supervivencia", "survival_pc", _annual_date, dim_cols=["pais", "age"])

# --- estructura_consum (Eurostat nama_10_fcs) — no crítica — dim: pais ---
for col, unit, desc in [
    ("bens_meur", "M EUR", "Consum de les llars en béns, per país."),
    ("serveis_meur", "M EUR", "Consum de les llars en serveis, per país."),
    ("bens_share", "%", "Quota de béns sobre el consum total de les llars, per país."),
    ("serveis_share", "%", "Quota de serveis sobre el consum total de les llars, per país."),
]:
    _add(f"estructura_consum_{col}", f"Estructura consum — {col}", desc, "Eurostat", "nama_10_fcs",
         "annual", unit, False, False, "estructura_consum", col, _annual_date, dim_cols=["pais"])

# --- estructura_comerc (DERIVAT: model propi J3B3) — is_derived=True — dim: tipus ---
for col, unit, desc in [
    ("bens_share", "%", "Quota de béns sobre el consum de les llars (històric + projecció lineal/logit)."),
    ("serveis_share", "%", "Quota de serveis sobre el consum de les llars (històric + projecció)."),
    ("online_pen", "%", "Penetració del canal online sobre el consum de béns (històric + projecció)."),
    ("comerc_fisic_share", "%", "Quota estimada del comerç físic (béns × (1 - penetració online))."),
    ("comerc_fisic_logodds", "%", "Quota estimada del comerç físic, variant log-odds (banda de projecció)."),
]:
    SERIES_EXTRA.append(dict(
        serie_id=f"estructura_comerc_{col}", name=f"Trajectòria estructural — {col}",
        description=f"{desc} MODEL PROPI DE J3B3 (no és font externa): combina Eurostat "
                     "nama_10_fcs (quota béns) i CNMC (penetració online), amb projecció "
                     "lineal + log-odds fins 2035. Citar sempre com a model propi, mai com "
                     "a dada oficial.",
        source="J3B3 (model propi)", source_table="derivat de Eurostat nama_10_fcs + CNMC",
        frequency="annual", unit=unit, is_critical=False, is_derived=True, is_public=True,
        build=_series_builder("estructura_comerc", col, _annual_date, dim_cols=["tipus"]),
    ))


# ─── Claus comunes: on és el territori i on és la branca de cada sèrie ──────
# Per prefix de serie_id, el primer que coincideix. Cada valor és:
#   - un codi fix ("pais:ES", "47") si tota la sèrie és d'un sol territori o branca;
#   - "dim_N" si la clau és en aquella dimensió (es tradueix amb els àlies generals);
#   - ("dim_N", alies) si cal un diccionari d'àlies propi (codis INE numèrics);
#   - None si no aplica (IPC, targetes: no són d'una branca CNAE).
# Una sèrie nova sense regla fa fallar la migració: cal decidir-ho, no endevinar-ho.
CLAUS = [
    ("icm_distribucio_", "pais:ES", "47"),
    ("icm_", "dim_2", "dim_1"),
    ("epa_retail_ocupats", "pais:ES", "47"),
    ("epa_retail_", "pais:ES", "G"),             # aturats i hores: només secció G
    ("ipc", "pais:ES", None),                    # ipc i ipc_coicop
    ("pib_vab_vab_total", "pais:ES", None),
    ("pib_vab_", "pais:ES", "47"),
    ("empreses_poblacio", "dim_1", None),
    ("empreses_", "dim_1", "47"),
    ("locals_prov_", ("dim_1", ALIES_PROV_INE), "47"),
    ("poblacio_prov", ("dim_1", ALIES_PROV_INE), None),
    ("locals_ccaa_grup", ("dim_1", ALIES_CCAA_INE), "dim_2"),
    ("productivitat_", "pais:ES", "47"),
    ("europa_vab_vab_total", "dim_1", None),
    ("europa_vab_", "dim_1", "47"),
    ("europa_retail_mensual_", "dim_1", "47"),
    ("confianza_consumidor_", "pais:ES", None),
    ("targetes_tpv_", "pais:ES", None),          # totes les activitats, no CNAE 47
    ("digitalitzacio_comerc", "dim_2", "47"),
    ("ocupacio_comerc", "dim_1", "47"),
    ("eaes", "pais:ES", None),                   # dim_1 = sector de tota l'economia
    ("ecommerce_total", "pais:ES", None),
    ("ecommerce_", "pais:ES", "47"),
    ("eee_ccaa_", "dim_1", "47"),
    ("subsectors_epf", "pais:ES", None),         # categories de consum, no CNAE
    ("subsectors_", "pais:ES", "dim_1"),
    ("marges_branca_ine", "pais:ES", "dim_1"),
    ("cdmge", "pais:ES", "47"),
    ("estructura_consum_", "dim_1", None),
    ("estructura_comerc_", "pais:ES", None),
    ("estructura_retail", "dim_1", "47"),
]


def _regla(serie_id):
    for prefix, geo, cnae in CLAUS:
        if serie_id.startswith(prefix):
            return geo, cnae
    raise KeyError(f"{serie_id}: sense regla a CLAUS (territori i branca). "
                   "Afegeix-la a data/sql/migrate.py.")


def _clau(tidy, spec, alies_defecte, que):
    if spec is None:
        return None
    if isinstance(spec, tuple):
        dim, alies = spec
    elif spec.startswith("dim_"):
        dim, alies = spec, alies_defecte
    else:
        return spec
    return resol(tidy[dim], alies, que=que).values


# ─── Avisos de qualitat per observació (codis a dimensions.DIM_AVIS) ─────────
AVIS = [
    ("icm_distribucio_", None),                  # aquesta sí que és CVEC
    ("icm_", "icm_brut"),
    ("eee_ccaa_vab_", "vab_ccaa_estimat"),
    ("eee_ccaa_pes_cnae47_pib", "vab_ccaa_estimat"),
    ("epa_retail_aturats", "seccio_g"),
    ("epa_retail_hores", "seccio_g"),
    ("targetes_tpv_", "tpv_totes_activitats"),
    ("productivitat_productivitat_", "deflactor_general"),
    ("productivitat_cost_laboral_hora", "deflactor_general"),
]


def _avis_base(s, tidy):
    codis = pd.Series([set() for _ in range(len(tidy))], index=tidy.index)
    for prefix, codi in AVIS:
        if s["serie_id"].startswith(prefix):
            if codi:
                codis.apply(lambda c, k=codi: c.add(k))
            break
    if "T=50902" in s["source_table"] and "constants" in s["serie_id"]:
        codis.apply(lambda c: c.add("deflactor_general"))
    if s.get("nota_trencament") == _NOTA_DIRCE and TRENCAMENTS_DIRCE:
        anys = pd.to_datetime(tidy["date"]).dt.year
        for t in sorted(TRENCAMENTS_DIRCE):
            for i in tidy.index[anys >= t]:
                codis[i].add(f"dirce_{t}")
    return codis.map(lambda c: ",".join(sorted(c)) or None)


_CODIS_AVIS = {a["avis_codi"] for a in DIM_AVIS}


def _comprova_avis(serie_id, avis):
    usats = {c for v in avis.dropna() for c in v.split(",")}
    falten = usats - _CODIS_AVIS
    if falten:
        raise KeyError(f"{serie_id}: avisos sense text a DIM_AVIS: {sorted(falten)}")


def _carrega_dimensions(con):
    con.execute("DELETE FROM dim_territori")
    con.execute("DELETE FROM dim_branca")
    con.execute("DELETE FROM dim_avis")
    con.register("da", pd.DataFrame(DIM_AVIS))
    con.execute("INSERT INTO dim_avis SELECT avis_codi, text FROM da")
    con.unregister("da")
    con.register("dt", pd.DataFrame(DIM_TERRITORI))
    con.execute("INSERT INTO dim_territori SELECT geo_codi, nivell, nom, geo_pare, "
                "codi_ine, codi_eurostat FROM dt")
    con.unregister("dt")
    con.register("db", pd.DataFrame(DIM_BRANCA))
    con.execute("INSERT INTO dim_branca SELECT cnae_codi, nivell, nom, cnae_pare FROM db")
    con.unregister("db")


# ─── Exclosos: no encaixen amb l'esquema observations (series temporals) ────
SKIPPED = [
    dict(cache="municipal", reason="Exclòs del chatbot públic (decisió explícita 2026-08-03). "
                                    "Segueix vivint al repo/CSV, no a l'esquema SQL."),
    dict(cache="lideres_empreses", reason="Taula entitat-atribut (63 empreses x mètriques "
                                           "financeres d'un any concret), no una sèrie temporal: "
                                           "no té columna de data per fila (nomes snapshot_any "
                                           "constant), i cada fila és una empresa, no una "
                                           "observació temporal. Necessitaria una taula pròpia "
                                           "(dimensió 'companies'), no observations."),
    dict(cache="prediccions_estructura", reason="Registre d'esdeveniments de predicció, no una "
                                                 "sèrie mesurada: cada fila té 3 dates diferents "
                                                 "(data_prediccio/horitzo/data_resolucio) i "
                                                 "4 valors relacionats (valor/banda/benchmark_flat/"
                                                 "valor_real) que pertanyen a UNA predicció, no a "
                                                 "una seqüència d'observacions. No encaixa amb "
                                                 "'una fila = una observació d'una mètrica'."),
]


_OBS_COLS = ["serie_id", "date", "frequency", "value", "unit", "dim_1", "dim_2",
             "dim_3", "source_table", "is_critical", "is_derived", "is_public",
             "geo_codi", "cnae_codi", "avis"]


def _desa(con, s, tidy):
    if tidy.empty:
        raise ValueError(f"{s['serie_id']}: cap observació (algun creuament no casa)")
    _comprova_avis(s["serie_id"], tidy["avis"])
    date_start, date_end = tidy["date"].min(), tidy["date"].max()

    # Ordre: esborrar filles (observations) abans que el pare (series_metadata);
    # inserir pare abans que filles (restriccio FOREIGN KEY).
    con.execute("DELETE FROM observations WHERE serie_id = ?", [s["serie_id"]])
    con.execute("DELETE FROM series_metadata WHERE serie_id = ?", [s["serie_id"]])
    con.execute("""
        INSERT INTO series_metadata
        (serie_id, name, description, source, frequency, date_start, date_end,
         is_critical, is_derived, is_public, nota_trencament, formula, fonts_origen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [s["serie_id"], s["name"], s["description"], s["source"], s["frequency"],
          date_start, date_end, s["is_critical"], s["is_derived"], s["is_public"],
          s.get("nota_trencament"), s.get("formula"), s.get("fonts_origen")])

    con.register("tidy_df", tidy[_OBS_COLS])
    con.execute(f"INSERT INTO observations ({', '.join(_OBS_COLS)}) "
                f"SELECT {', '.join(_OBS_COLS)} FROM tidy_df")
    con.unregister("tidy_df")

    print(f"    {len(tidy)} files, {date_start} .. {date_end}")


FETS_CSV = os.path.join(os.path.dirname(__file__), "..", "cache", "fets.csv")


def _exporta_fets(fets):
    """Còpia dels fets en CSV versionat, per als consumidors sense DuckDB (el
    snapshot del newsletter clona el repo i llegeix data/cache). Ordre i
    arrodoniment fixos: el diff entre dies només mostra fets que canvien."""
    textos = {a["avis_codi"]: a["text"] for a in DIM_AVIS}
    df = fets.copy()
    df["avisos_text"] = df["avis"].map(
        lambda v: " | ".join(textos[c] for c in v.split(",")) if v else None)
    for c in ("valor", "valor_referencia", "rellevancia"):
        df[c] = df[c].astype(float).round(4)
    df.sort_values("fet_id").to_csv(FETS_CSV, index=False)


def migrate(db_path=DB_PATH, series=None):
    if series is None:
        series = SERIES + SERIES_EXTRA

    con = duckdb.connect(db_path)
    with open(SCHEMA_PATH) as f:
        con.execute(f.read())
    _carrega_dimensions(con)

    for s in series:
        print(f"  Migrant {s['serie_id']}...")
        tidy = s["build"]()
        tidy = tidy.dropna(subset=["date", "value"]).copy()
        for col in ["dim_1", "dim_2", "dim_3"]:
            if col not in tidy.columns:
                tidy[col] = None
        tidy["serie_id"] = s["serie_id"]
        tidy["frequency"] = s["frequency"]
        tidy["unit"] = s["unit"]
        tidy["source_table"] = s["source_table"]
        tidy["is_critical"] = s["is_critical"]
        tidy["is_derived"] = s["is_derived"]
        tidy["is_public"] = s["is_public"]
        geo, cnae = _regla(s["serie_id"])
        tidy["geo_codi"] = _clau(tidy, geo, ALIES_TERRITORI, f"{s['serie_id']}: territori")
        tidy["cnae_codi"] = _clau(tidy, cnae, ALIES_BRANCA, f"{s['serie_id']}: branca")
        tidy["avis"] = _avis_base(s, tidy)
        _desa(con, s, tidy)

    # Derivats: després de les sèries de base, que llegeixen de la mateixa base.
    for d in DERIVATS:
        print(f"  Derivant {d['serie_id']}...")
        tidy = d["build"](con)
        tidy["date"] = pd.to_datetime(tidy["date"]).dt.date
        s = dict(d, source="J3B3 (derivat)", source_table=d["formula"],
                 is_critical=False, is_derived=True, is_public=True)
        for k, v in [("serie_id", d["serie_id"]), ("frequency", d["frequency"]),
                     ("unit", d["unit"]), ("source_table", d["formula"]),
                     ("is_critical", False), ("is_derived", True), ("is_public", True)]:
            tidy[k] = v
        _desa(con, s, tidy)

    # Fets: lectures sobre sèries i derivats ja desats.
    print("  Generant fets...")
    fets = construeix_fets(con)
    _comprova_avis("fets", fets["avis"])
    con.execute("DELETE FROM fets")
    con.register("fets_df", fets)
    con.execute("INSERT INTO fets SELECT * FROM fets_df")
    con.unregister("fets_df")
    _exporta_fets(fets)
    print(f"    {len(fets)} fets ({', '.join(f'{k}: {v}' for k, v in fets['regla'].value_counts().items())})")

    n_series = con.execute("SELECT count(*) FROM series_metadata").fetchone()[0]
    n_obs = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    n_critical = con.execute("SELECT count(*) FROM series_metadata WHERE is_critical").fetchone()[0]
    n_derived = con.execute("SELECT count(*) FROM series_metadata WHERE is_derived").fetchone()[0]
    con.close()

    print(f"\nMigracio completa: {db_path}")
    print(f"  series_metadata: {n_series} sèries ({n_critical} crítiques, {n_derived} derivades)")
    print(f"  observations:    {n_obs} files")
    if SKIPPED:
        print(f"\n  Exclosos ({len(SKIPPED)}):")
        for sk in SKIPPED:
            print(f"    - {sk['cache']}: {sk['reason']}")


if __name__ == "__main__":
    migrate()
