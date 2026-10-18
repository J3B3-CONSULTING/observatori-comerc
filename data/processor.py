"""
Processador de dades: obte dades via API, processa i desa a cache/.
Jerarquia de fonts:
  1. API (INE, Eurostat, CNMC) — font primaria per actualitzacions automatiques
  2. CSV cache existent — fallback si l'API falla (mante dades anteriors)
  3. Excel local — nomes per a la carrega inicial (els Excel no es pugen a GitHub)
"""
import os
import json
import pandas as pd
from data.fetchers import ine, eurostat, cnmc, bde
from data.config import trencaments_travessats

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


# ─── Sistema de detecció automàtica de fallades (Nivell 1) ─────────────────
#
# Cada process_* funcio crítica anota la font d'on ha obtingut les dades al
# diccionari global _FETCH_STATUS. Al final de process_all() es valida que
# totes les fonts crítiques tinguin estat 'ok' (= dades obtingudes des de
# l'API primària, no des de cache de seguretat). Si alguna ha caigut a
# 'fallback' o 'error', el processador surt amb codi 1 → el workflow de
# GitHub Actions falla → GitHub envia notificació per email a l'autor del
# commit. Així ens assabentem AUTOMÀTICAMENT quan una API canvia.

_FETCH_STATUS = {}
_VALIDATION_WARNINGS = []

# Fonts que han d'actualitzar-se obligatoriament des de l'API primaria cada dia.
# Si alguna cau a cache de seguretat, el workflow ha de fer fail per avisar.
# Resta de fonts: la cache servirà mentre es resolen.
#
# NOTA: "ecommerce" (CNMC) està exclòs intencionadament. La CNMC publica dades
# amb freqüència trimestral; la cache és el fallback esperat la majoria de dies.
# Un fallback de la CNMC no implica cap problema d'actualització.
CRITICAL_SOURCES = {
    "pib_vab",                  # INE — pes G47 al PIB
    "empreses",                 # INE — DIRCE
    "productivitat",            # INE — EEE Comercio
    "europa_vab",               # Eurostat — pes G47 UE
    "europa_retail_mensual",    # Eurostat — sts_trtu_m
    "icm",                      # INE — Índices de Comercio al por Menor
    "icm_distribucion",         # INE — ICM per modo de distribució
    "cdmge",                    # INE — comerç diari grans empreses
}


def _record_status(name, estat, font="api", missatge=""):
    """Registra l'estat d'una font de dades.

    estat: 'ok' (dades fresques des de l'API), 'fallback' (cache o Excel),
           'error' (cap font ha funcionat).
    """
    _FETCH_STATUS[name] = {"estat": estat, "font": font, "missatge": str(missatge)[:200]}


def _assert_critical_ok():
    """Comprova que totes les fonts critiques s'hagin actualitzat des de l'API.

    Persisteix l'estat a fetch_status.json i, si alguna critica ha caigut
    a fallback o error, surt amb codi 1 per fer fallar el workflow.
    """
    ensure_cache_dir()
    status_path = os.path.join(CACHE_DIR, "fetch_status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(_FETCH_STATUS, f, indent=2, ensure_ascii=False, sort_keys=True)

    problemes = []
    for name in sorted(CRITICAL_SOURCES):
        s = _FETCH_STATUS.get(name)
        if s is None:
            problemes.append(f"{name}: NO EXECUTAT")
        elif s["estat"] != "ok":
            msg = s.get("missatge", "")[:80]
            problemes.append(f"{name}: {s['estat'].upper()} via {s.get('font','?')} ({msg})")

    # ── GitHub Step Summary (visible a Actions UI sense haver de buscar logs) ──
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## Estat de les fonts de dades\n\n")
            f.write("| Font | Estat | Via | Missatge |\n")
            f.write("|------|-------|-----|----------|\n")
            for sname, s in sorted(_FETCH_STATUS.items()):
                icon = "✅" if s["estat"] == "ok" else ("⚠️" if s["estat"] == "fallback" else "❌")
                f.write(f"| `{sname}` | {icon} {s['estat']} | {s.get('font','?')} "
                        f"| {s.get('missatge','')[:80]} |\n")
            if _VALIDATION_WARNINGS:
                f.write("\n## Avisos de validació de contingut\n\n")
                for w in _VALIDATION_WARNINGS:
                    f.write(f"- ⚠️ {w}\n")
            else:
                f.write("\n*Sense avisos de validació de contingut.*\n")

    if problemes:
        print()
        print("=" * 68)
        print("  ALERTA: FONTS CRITIQUES NO ACTUALITZADES DES DE L'API PRIMARIA")
        print("=" * 68)
        for p in problemes:
            print(f"  - {p}")
        print("=" * 68)
        print("  El workflow es fa fallar perque les dades servides poden estar")
        print("  obsoletes. Reviseu el fetcher corresponent (canvi d'API, endpoint")
        print("  retirat, credencials caducades, etc).")
        print("=" * 68)
        raise SystemExit(1)

    print()
    print(f"  [OK] {len(CRITICAL_SOURCES)} fonts critiques actualitzades des de l'API.")
    if _VALIDATION_WARNINGS:
        print(f"  [AVIS] {len(_VALIDATION_WARNINGS)} avisos de validació de contingut:")
        for w in _VALIDATION_WARNINGS:
            print(f"    - {w}")


def _is_valid_series(df, col, name, min_rows=5, max_nan_pct=0.5, max_jump=10.0,
                     group_by=None):
    """Valida que una sèrie tingui prou dades i cap valor absurd.

    Registra avisos a _VALIDATION_WARNINGS (no fa fallar el workflow,
    però apareixen al Step Summary i als logs per a revisió manual).

    Args:
        df:          DataFrame a validar.
        col:         Columna numèrica a inspeccionar.
        name:        Nom de la font (per al log).
        min_rows:    Mínim de files amb valor no-NaN exigit.
        max_nan_pct: Fracció màxima de NaN tolerada (0–1).
        max_jump:    Ratio màxim acceptable entre valors consecutius dins
                     una mateixa sèrie. Un salt de 10× o més és probable
                     error de dades.
        group_by:    Columna (o llista de columnes) que identifica cada
                     sèrie independent dins el DataFrame. Quan s'indica,
                     els ratios es calculen dins cada grup per evitar
                     falsos positius als límits entre sèries concatenades
                     (ex: icm té ~300 sèries amb escales dispars).
    Returns:
        True si la sèrie sembla vàlida; False si hi ha un problema seriós.
    """
    if df is None or df.empty:
        _VALIDATION_WARNINGS.append(f"{name}/{col}: DataFrame buit")
        return False
    if col not in df.columns:
        _VALIDATION_WARNINGS.append(f"{name}/{col}: columna absent al CSV")
        return False

    series = df[col]
    n_total = len(series)
    n_valid = int(series.notna().sum())

    if n_valid < min_rows:
        _VALIDATION_WARNINGS.append(
            f"{name}/{col}: massa poques files ({n_valid} no-NaN de {n_total}; mínim {min_rows})"
        )
        return False

    nan_pct = 1.0 - n_valid / n_total if n_total > 0 else 1.0
    if nan_pct > max_nan_pct:
        _VALIDATION_WARNINGS.append(
            f"{name}/{col}: {nan_pct:.0%} NaN ({n_total - n_valid}/{n_total} files)"
        )
        return False

    # Detecció de salts bruscos (possible canvi de taula o error d'escala).
    # Si group_by indica la columna de sèrie, el ratio es calcula dins cada
    # grup per no creuar límits entre sèries d'escales diferents.
    def _max_ratio_in(values):
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        if len(numeric) < 2:
            return 0.0
        nonzero = numeric[numeric != 0]
        if len(nonzero) < 2:
            return 0.0
        return float((nonzero / nonzero.shift(1)).abs().dropna().max())

    group_cols = [group_by] if isinstance(group_by, str) else list(group_by or [])
    if group_cols and all(c in df.columns for c in group_cols):
        max_ratio = float(df.groupby(group_by, sort=False)[col]
                          .apply(_max_ratio_in).max())
    else:
        max_ratio = _max_ratio_in(series)

    if max_ratio > max_jump:
        _VALIDATION_WARNINGS.append(
            f"{name}/{col}: salt inesperat de {max_ratio:.1f}× entre "
            f"valors consecutius (possible canvi d'escala o metodologia)"
        )
        # Avís, no error: pot ser un canvi metodològic legítim.

    return True


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def save_cache(df, name):
    ensure_cache_dir()
    pq = os.path.join(CACHE_DIR, f"{name}.parquet")
    csv = os.path.join(CACHE_DIR, f"{name}.csv")
    df.to_parquet(pq, index=False)
    df.to_csv(csv, index=False)
    print(f"  Desat: {name}.parquet + {name}.csv ({len(df)} files)")


def load_cache(name):
    pq = os.path.join(CACHE_DIR, f"{name}.parquet")
    if os.path.exists(pq):
        return pd.read_parquet(pq)
    csv = os.path.join(CACHE_DIR, f"{name}.csv")
    if os.path.exists(csv):
        return pd.read_csv(csv)
    return pd.DataFrame()


# ─── FONTS EXCEL (CARREGA INICIAL LOCAL) ─────────────────────

def load_excel_pib():
    """Carrega dades del PIB CNAE 47 des de l'Excel existent com a base."""
    try:
        import openpyxl
    except ImportError:
        return pd.DataFrame()

    path = os.path.join(os.path.dirname(__file__), "..", "..", "PIB CNAE 47.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["PIB "]

    records = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if row[0] is None:
            continue
        try:
            any_ = int(str(row[0]).strip())
        except (ValueError, TypeError):
            continue

        rec = {"any": any_}
        if row[1] is not None:
            rec["vab_total_corrents"] = float(row[1])
        if row[3] is not None:
            rec["vab_cnae47_corrents"] = float(row[3])
        if len(row) > 9 and row[9] is not None:
            rec["vab_total_constants"] = float(row[9])
        if len(row) > 11 and row[11] is not None:
            rec["vab_cnae47_constants"] = float(row[11])
        if len(row) > 24 and row[24] is not None:
            rec["empreses"] = float(row[24])
        if len(row) > 25 and row[25] is not None:
            rec["pib_per_empresa"] = float(row[25])

        records.append(rec)

    return pd.DataFrame(records)


def load_excel_productivitat():
    """Carrega dades de productivitat des de l'Excel existent."""
    try:
        import openpyxl
    except ImportError:
        return pd.DataFrame()

    path = os.path.join(os.path.dirname(__file__), "..", "..", "PRODUCTIVITAT.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Hoja1"]

    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
    if len(rows) < 5:
        return pd.DataFrame()

    anys = [int(v) for v in rows[0][1:] if isinstance(v, (int, float))]
    data = {}
    labels = [
        "xifra_negoci_constants", "valor_afegit_constants",
        "personal_ocupat", "hores_treballades"
    ]

    for i, label in enumerate(labels):
        if i + 1 < len(rows):
            vals = [v for v in rows[i + 1][1:] if isinstance(v, (int, float))]
            data[label] = vals[:len(anys)]

    records = []
    for j, any_ in enumerate(anys):
        rec = {"any": any_}
        for label in labels:
            if label in data and j < len(data[label]):
                rec[label] = data[label][j]
        records.append(rec)

    df = pd.DataFrame(records)

    if "valor_afegit_constants" in df.columns and "hores_treballades" in df.columns:
        df["productivitat_va_hora"] = df["valor_afegit_constants"] / df["hores_treballades"]
    if "xifra_negoci_constants" in df.columns and "hores_treballades" in df.columns:
        df["productivitat_xn_hora"] = df["xifra_negoci_constants"] / df["hores_treballades"]

    return df


def load_excel_empreses_cat():
    """Carrega dades d'empreses de Catalunya."""
    try:
        import openpyxl
    except ImportError:
        return pd.DataFrame()

    path = os.path.join(os.path.dirname(__file__), "..", "..", "empreses cnae47 Catalunya.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["tabla-298"]

    records = []
    for row in ws.iter_rows(min_row=9, max_row=ws.max_row, values_only=True):
        if row[0] and "Cataluny" in str(row[0]):
            for i, val in enumerate(row[1:], start=0):
                if isinstance(val, (int, float)):
                    any_ = 2020 - i
                    records.append({"territori": "catalunya", "any": any_, "empreses": int(val)})
        elif row[0] and "Espany" in str(row[0]):
            for i, val in enumerate(row[1:], start=0):
                if isinstance(val, (int, float)):
                    any_ = 2020 - i
                    records.append({"territori": "espanya", "any": any_, "empreses": int(val)})

    return pd.DataFrame(records)


# ─── FONTS API ────────────────────────────────────────────────

def fetch_ipc_annual():
    """Obte IPC mitjana anual (base 2021=100) des de l'API INE."""
    print("  Obtenint IPC (taula 50902)...")
    try:
        df_ipc = ine.fetch_ipc()
        if df_ipc.empty:
            print("  IPC: sense dades")
            return pd.DataFrame()

        df_ipc["ipc"] = pd.to_numeric(df_ipc["ipc"], errors="coerce")
        df_ipc["any"] = pd.to_numeric(df_ipc["any"], errors="coerce")
        ipc_anual = df_ipc.groupby("any")["ipc"].mean().reset_index()
        ipc_anual.columns = ["any", "ipc_mitjana"]
        print(f"  IPC: {len(ipc_anual)} anys (base 2021=100)")
        return ipc_anual

    except Exception as e:
        print(f"  Error IPC: {e}")
        return pd.DataFrame()


def fetch_pib_vab_from_api():
    """
    Obte PIB/VAB CNAE 47 des de l'API INE (taula 69070).
    Deflacta amb IPC general reancorat al primer any de la serie:
      VAB_constants = VAB_corrents / (IPC_any / IPC_primer_any)
    Així el valor real del primer any = nominal, i després real <= nominal sempre.
    """
    print("  Intentant API INE (taula 69070)...")
    try:
        df_api = ine.fetch_vab_ramas()
        if df_api.empty:
            print("  API INE: sense dades")
            return pd.DataFrame()

        # Pivotar: una fila per any amb columnes per indicador
        pivots = {}
        for ind in df_api["indicador"].unique():
            df_ind = df_api[df_api["indicador"] == ind][["any", "valor"]].copy()
            df_ind = df_ind.rename(columns={"valor": ind})
            pivots[ind] = df_ind

        if "vab_total_corrents" not in pivots or "vab_cnae47_corrents" not in pivots:
            print("  API INE: no s'han trobat series corrents")
            return pd.DataFrame()

        # Merge series corrents
        df = pivots["vab_total_corrents"]
        if "vab_cnae47_corrents" in pivots:
            df = df.merge(pivots["vab_cnae47_corrents"], on="any", how="outer")

        df = df.sort_values("any").reset_index(drop=True)

        # Obtenir IPC per deflactar
        ipc = fetch_ipc_annual()
        if not ipc.empty:
            df = df.merge(ipc, on="any", how="left")

            # Deflactar: reancorar IPC al primer any amb dades
            if "ipc_mitjana" in df.columns:
                ipc_base = df["ipc_mitjana"].dropna().iloc[0]
                df["vab_cnae47_constants"] = df["vab_cnae47_corrents"] / (df["ipc_mitjana"] / ipc_base)
                df["vab_total_constants"] = df["vab_total_corrents"] / (df["ipc_mitjana"] / ipc_base)
                any_base = int(df.loc[df["ipc_mitjana"].first_valid_index(), "any"])
                print(f"  Deflactat amb IPC reancorat a {any_base} (IPC base={ipc_base:.2f})")

            # Netejar columna auxiliar
            df = df.drop(columns=["ipc_mitjana"], errors="ignore")

        print(f"  API INE: {len(df)} anys obtinguts")
        return df

    except Exception as e:
        print(f"  Error API INE: {e}")
        return pd.DataFrame()


def fetch_empreses_from_api():
    """Obte empreses CNAE 47 des de l'API INE (taula 298)."""
    print("  Intentant API INE (taula 298)...")
    try:
        # Espanya + Catalunya
        df_api = ine.fetch_empreses()
        if df_api.empty:
            print("  API INE empreses: sense dades")
            return pd.DataFrame()

        # Agregar per any anual (l'API pot tornar dades amb periode)
        df_api["any"] = pd.to_numeric(df_api["any"], errors="coerce")
        df_api["empreses"] = pd.to_numeric(df_api["empreses"], errors="coerce")
        df = df_api.dropna(subset=["any", "empreses"]).copy()
        df["any"] = df["any"].astype(int)
        df["empreses"] = df["empreses"].astype(int)

        print(f"  API INE empreses: {len(df)} registres")
        return df[["territori", "any", "empreses"]]

    except Exception as e:
        print(f"  Error API INE empreses: {e}")
        return pd.DataFrame()


def fetch_europa_from_api():
    """Obte dades europees des de l'API Eurostat."""
    print("  Intentant API Eurostat...")
    try:
        df_vab47 = eurostat.fetch_vab_cnae47()
        df_vab_total = eurostat.fetch_vab_total()

        if df_vab47.empty or df_vab_total.empty:
            print("  Eurostat: sense dades")
            return pd.DataFrame()

        df = df_vab47.merge(df_vab_total, on=["pais", "pais_codi", "any"], how="inner")
        df["pes_cnae47"] = df["vab_meur"] / df["vab_total_meur"]

        print(f"  Eurostat: {len(df)} registres de {df['pais_codi'].nunique()} paisos")
        return df

    except Exception as e:
        print(f"  Error Eurostat: {e}")
        return pd.DataFrame()


def fetch_ecommerce_from_api():
    """Obte dades d'e-commerce des de l'API CNMC."""
    print("  Intentant API CNMC...")
    try:
        df_api = cnmc.fetch_ecommerce()
        if df_api.empty:
            print("  CNMC: sense dades")
            return pd.DataFrame()
        print(f"  CNMC: {len(df_api)} registres")
        return df_api
    except Exception as e:
        print(f"  Error CNMC: {e}")
        return pd.DataFrame()


def fetch_productivitat_from_api():
    """
    Obte dades de productivitat des de l'API INE.
    Font: Taula 36194 (EEE Sector Comercio) — CNAE 47.
    Metodologia:
      1. Obtenir magnituds a preus corrents (xifra negoci, VA, personal, hores)
      2. Deflactar amb IPC reancorat al primer any: valor_constants = valor_corrents / (IPC/IPC_base)
      3. Calcular productivitat: VA/hora, XN/hora
    """
    print("  Intentant API INE (taula 36194 - EEE Comercio)...")
    try:
        df = ine.fetch_eee_comercio()
        if df.empty:
            print("  API INE EEE: sense dades")
            return pd.DataFrame()

        print(f"  EEE Comercio: {len(df)} anys, magnituds: {list(df.columns)}")

        # Obtenir IPC per deflactar
        ipc = fetch_ipc_annual()
        if ipc.empty:
            print("  No es pot deflactar sense IPC")
            return pd.DataFrame()

        df = df.merge(ipc, on="any", how="left")

        # Deflactar xifra negoci i valor afegit amb IPC reancorat al primer any
        if "ipc_mitjana" in df.columns:
            ipc_base = df["ipc_mitjana"].dropna().iloc[0]
            deflactor = df["ipc_mitjana"] / ipc_base
            if "xifra_negoci" in df.columns:
                df["xifra_negoci_constants"] = df["xifra_negoci"] / deflactor
            if "valor_afegit" in df.columns:
                df["valor_afegit_constants"] = df["valor_afegit"] / deflactor
            any_base = int(df.loc[df["ipc_mitjana"].first_valid_index(), "any"])
            print(f"  Deflactat amb IPC reancorat a {any_base}")

        # Calcular productivitat
        if "valor_afegit_constants" in df.columns and "hores_treballades" in df.columns:
            df["productivitat_va_hora"] = df["valor_afegit_constants"] / df["hores_treballades"]
        if "xifra_negoci_constants" in df.columns and "hores_treballades" in df.columns:
            df["productivitat_xn_hora"] = df["xifra_negoci_constants"] / df["hores_treballades"]

        # ── Afegir dades de Resultats d'explotacio (T=36199) ──
        try:
            df_pyl = ine.fetch_eee_pyl()
            if not df_pyl.empty:
                # Merge per any (mantenim columnes existents si hi ha conflicte)
                cols_pyl = [c for c in ["cogs", "serveis_exteriors", "sueldos_salaris"]
                            if c in df_pyl.columns]
                df = df.merge(df_pyl[["any"] + cols_pyl], on="any", how="left")
                print(f"  Resultats d'explotacio (T=36199): {len(df_pyl)} anys integrats")
        except Exception as e:
            print(f"  Error obtenint T=36199: {e}")

        # Deflactar gastos de personal
        if "gastos_personal" in df.columns and "ipc_mitjana" in df.columns:
            df["gastos_personal_constants"] = df["gastos_personal"] / deflactor

        # Deflactar COGS i serveis exteriors per fer ratios consistents en preus constants
        if "cogs" in df.columns and "ipc_mitjana" in df.columns:
            df["cogs_constants"] = df["cogs"] / deflactor
        if "serveis_exteriors" in df.columns and "ipc_mitjana" in df.columns:
            df["serveis_exteriors_constants"] = df["serveis_exteriors"] / deflactor

        # Marge brut comptable: (Vendes - COGS) / Vendes (a preus corrents = ratio invariant)
        if "cogs" in df.columns and "xifra_negoci" in df.columns:
            df["marge_brut"] = (df["xifra_negoci"] - df["cogs"]) / df["xifra_negoci"]

        # Distribucio del VAB: quota salarial i excedent brut
        if "gastos_personal" in df.columns and "valor_afegit" in df.columns:
            df["quota_salarial"] = df["gastos_personal"] / df["valor_afegit"]
            df["excedent_brut"] = df["valor_afegit"] - df["gastos_personal"]
        if "gastos_personal" in df.columns and "personal_ocupat" in df.columns:
            df["cost_laboral_per_ocupat"] = df["gastos_personal"] / df["personal_ocupat"]
        if "gastos_personal_constants" in df.columns and "hores_treballades" in df.columns:
            df["cost_laboral_hora"] = df["gastos_personal_constants"] / df["hores_treballades"]

        # Seleccionar columnes finals
        cols_finals = ["any", "xifra_negoci_constants", "valor_afegit_constants",
                       "personal_ocupat", "hores_treballades",
                       "productivitat_va_hora", "productivitat_xn_hora",
                       "gastos_personal", "gastos_personal_constants",
                       "quota_salarial", "excedent_brut",
                       "cost_laboral_per_ocupat", "cost_laboral_hora",
                       "cogs", "cogs_constants", "serveis_exteriors",
                       "serveis_exteriors_constants", "marge_brut"]
        cols_disponibles = [c for c in cols_finals if c in df.columns]
        df = df[cols_disponibles]

        print(f"  Productivitat calculada: {len(df)} anys")
        return df

    except Exception as e:
        print(f"  Error API INE productivitat: {e}")
        return pd.DataFrame()


# ─── PROCESSAMENT (API → CACHE → EXCEL) ──────────────────────

def process_pib_vab():
    """
    Processa PIB/VAB.
    1. Intenta API INE
    2. Fallback: cache existent
    3. Fallback: Excel local
    """
    print("  Font 1: API INE")
    df = fetch_pib_vab_from_api()
    if not df.empty:
        _record_status("pib_vab", "ok", "api_ine", f"{len(df)} files")
    else:
        print("  Font 2: Cache existent")
        df = load_cache("pib_vab")
        if not df.empty:
            _record_status("pib_vab", "fallback", "cache", "API INE buida")
        else:
            print("  Font 3: Excel local")
            df = load_excel_pib()
            if not df.empty:
                _record_status("pib_vab", "fallback", "excel", "API i cache buides")
            else:
                _record_status("pib_vab", "error", "cap", "Cap font ha funcionat")
                print("  Cap font disponible per PIB/VAB")
                return pd.DataFrame()

    # Calcular metriques derivades
    if "vab_cnae47_corrents" in df.columns and "vab_total_corrents" in df.columns:
        df["pes_cnae47"] = df["vab_cnae47_corrents"] / df["vab_total_corrents"]

    for col in ["vab_cnae47_corrents", "vab_cnae47_constants"]:
        if col in df.columns:
            df[f"var_{col}"] = df[col].pct_change()

    _is_valid_series(df, "vab_cnae47_corrents", "pib_vab")
    save_cache(df, "pib_vab")
    return df


def process_empreses():
    """
    Processa empreses.
    1. Intenta API INE (Espanya + Catalunya)
    2. Fallback: cache existent
    3. Fallback: Excel local
    """
    print("  Font 1: API INE")
    df = fetch_empreses_from_api()
    if not df.empty:
        _record_status("empreses", "ok", "api_ine", f"{len(df)} files")
    else:
        print("  Font 2: Cache existent")
        df = load_cache("empreses")
        if not df.empty:
            _record_status("empreses", "fallback", "cache", "API INE buida")
        else:
            print("  Font 3: Excel local")
            df_pib = load_excel_pib()
            df_cat = load_excel_empreses_cat()

            records = []
            if not df_pib.empty and "empreses" in df_pib.columns:
                for _, row in df_pib.iterrows():
                    if pd.notna(row.get("empreses")):
                        records.append({
                            "territori": "espanya",
                            "any": int(row["any"]),
                            "empreses": int(row["empreses"]),
                        })

            if not df_cat.empty:
                for _, row in df_cat.iterrows():
                    records.append({
                        "territori": row["territori"],
                        "any": int(row["any"]),
                        "empreses": int(row["empreses"]),
                    })

            df = pd.DataFrame(records)
            if not df.empty:
                _record_status("empreses", "fallback", "excel", "API i cache buides")
            else:
                _record_status("empreses", "error", "cap", "Cap font ha funcionat")
                print("  Cap font disponible per empreses")
                return pd.DataFrame()

    # ── Afegir població i densitat comercial ──
    print("  Obtenint dades de població...")
    try:
        df_pob = ine.fetch_poblacio()
        if not df_pob.empty:
            # Homogeneitzar noms de territori (Padrón vs DIRCE)
            NORM = {
                "Asturias, Principado de": "Asturias (Principado de)",
                "Balears, Illes": "Balears (Illes)",
                "Madrid, Comunidad de": "Madrid (Comunidad de)",
                "Murcia, Región de": "Murcia (Región de)",
                "Navarra, Comunidad Foral de": "Navarra (Comunidad Foral de)",
                "Rioja, La": "Rioja (La)",
            }
            df_pob["territori"] = df_pob["territori"].replace(NORM)
            df_pob["any"] = pd.to_numeric(df_pob["any"], errors="coerce")
            df_pob["poblacio"] = pd.to_numeric(df_pob["poblacio"], errors="coerce")

            df["any"] = pd.to_numeric(df["any"], errors="coerce")
            df = df.merge(df_pob[["territori", "any", "poblacio"]], on=["territori", "any"], how="left")

            # Empreses per 1.000 habitants
            mask = df["poblacio"].notna() & (df["poblacio"] > 0)
            df.loc[mask, "empreses_per_1000hab"] = (df.loc[mask, "empreses"] / df.loc[mask, "poblacio"]) * 1000

            n_with = df["empreses_per_1000hab"].notna().sum()
            print(f"  Densitat comercial calculada: {n_with} registres")
    except Exception as e:
        print(f"  Error obtenint població: {e}")

    save_cache(df, "empreses")
    return df


# ─── Territori: locals DIRCE per província i per CCAA × grup ──────────────
#
# Sèries de LOCALS (unitats locals), independents de empreses.csv: no el
# substitueixen ni s'hi poden comparar. Anuals (foto a 1 de gener, publicació
# al desembre): fora de CRITICAL_SOURCES, com l'e-commerce.

GEO_DIR = os.path.join(os.path.dirname(__file__), "geo")


def _load_provincies():
    return pd.read_csv(os.path.join(GEO_DIR, "provincies.csv"), dtype=str)


def _marca_trencaments(df, valor_col, group_cols):
    """Afegeix var_interanual_pct, travessa_trencament i nota_trencament.

    La variació es calcula contra l'any anterior disponible dins cada sèrie.
    travessa_trencament marca les variacions que creuen un any de
    TRENCAMENTS_DIRCE (data/config.py); la nota diu quin.
    """
    df = df.sort_values(group_cols + ["any"]).reset_index(drop=True)
    prev_val = df.groupby(group_cols)[valor_col].shift(1)
    prev_any = df.groupby(group_cols)["any"].shift(1)
    df["var_interanual_pct"] = ((df[valor_col] / prev_val - 1) * 100).round(2)

    travessa, nota = [], []
    for a, pa in zip(df["any"], prev_any):
        t = trencaments_travessats(pa, a) if pd.notna(pa) else []
        travessa.append(bool(t))
        nota.append(
            f"La variació {int(pa)}→{int(a)} travessa el trencament de sèrie "
            f"DIRCE de {', '.join(map(str, t))}: no comparable." if t else "")
    df["travessa_trencament"] = travessa
    df["nota_trencament"] = nota
    return df


def _poblacio_provincia(cache_name):
    """Padró per província (T=29005 sumada). Si l'API falla, reaprofita la
    columna poblacio del cache existent en lloc d'estimar-la."""
    pob = ine.fetch_poblacio_provincia()
    if not pob.empty:
        return pob[["codi_prov", "any", "poblacio"]], "api"
    prev = load_cache(cache_name)
    if not prev.empty and "poblacio" in prev.columns:
        pob = (prev[prev["nivell_geo"] == "provincia"]
               .rename(columns={"codi_geo": "codi_prov"})[["codi_prov", "any", "poblacio"]])
        pob["codi_prov"] = pob["codi_prov"].astype(str).str.zfill(2)
        return pob.dropna().drop_duplicates(), "cache"
    return pd.DataFrame(columns=["codi_prov", "any", "poblacio"]), "cap"


def process_locals_provincia():
    """
    Locals CNAE 47 per província (T=301) + padró provincial (T=29005 sumada).
    1. API INE  2. Cache existent
    Sortida: locals_provincia.csv (52 províncies + fila espanya).
    """
    name = "locals_provincia"
    print("  Font 1: API INE (T=301 locals + T=29005 padró)")
    loc = ine.fetch_locals_provincia()
    if loc.empty:
        print("  Font 2: Cache existent")
        df = load_cache(name)
        if df.empty:
            _record_status(name, "error", "cap", "API INE buida i sense cache")
            return pd.DataFrame()
        _record_status(name, "fallback", "cache", "API INE T=301 buida")
        return df

    geo = _load_provincies()
    pob, via_pob = _poblacio_provincia(name)
    pob = pob.copy()
    pob["any"] = pob["any"].astype(int)
    pob["poblacio"] = pd.to_numeric(pob["poblacio"], errors="coerce").astype(float)
    loc["any"] = loc["any"].astype(int)

    prov = loc[loc["codi_geo"] != "00"].merge(geo, left_on="codi_geo",
                                               right_on="codi_prov", how="left")
    prov["nivell_geo"] = "provincia"
    prov = prov.merge(pob, on=["codi_prov", "any"], how="left")

    esp = loc[loc["codi_geo"] == "00"].copy()
    esp["nivell_geo"] = "espanya"
    esp["codi_prov"] = "00"
    esp["provincia"] = "Espanya"
    esp["codi_ccaa"] = "00"
    esp["ccaa"] = "espanya"
    # Espanya = suma de les 52 províncies; només anys amb totes presents.
    pob_esp = pob.groupby("any").agg(poblacio=("poblacio", "sum"),
                                      n=("codi_prov", "nunique")).reset_index()
    pob_esp = pob_esp[pob_esp["n"] == len(geo)][["any", "poblacio"]]
    esp = esp.merge(pob_esp, on="any", how="left")

    df = pd.concat([esp, prov], ignore_index=True)
    mask = df["poblacio"].notna() & (df["poblacio"] > 0)
    df.loc[mask, "locals_per_1000hab"] = (
        df.loc[mask, "locals_cnae47"] / df.loc[mask, "poblacio"] * 1000).round(3)
    df = _marca_trencaments(df, "locals_cnae47", ["codi_geo"])
    df["font"] = "INE DIRCE T=301 (locals); INE Padró T=29005 sumat per província"

    cols = ["nivell_geo", "codi_geo", "provincia", "codi_ccaa", "ccaa", "any",
            "locals_cnae47", "poblacio", "locals_per_1000hab", "var_interanual_pct",
            "travessa_trencament", "nota_trencament", "font"]
    df = df[cols].astype({"locals_cnae47": "Int64", "poblacio": "Int64"})

    sense_nom = df[df["provincia"].isna()]["codi_geo"].unique()
    if len(sense_nom):
        _VALIDATION_WARNINGS.append(f"{name}: codis sense província a geo/provincies.csv: {list(sense_nom)}")
    _is_valid_series(df, "locals_cnae47", name, group_by="codi_geo")
    _is_valid_series(df, "poblacio", name, group_by="codi_geo")

    missatge = f"{len(df)} files" + ("" if via_pob == "api" else f" (padró via {via_pob})")
    _record_status(name, "ok" if via_pob == "api" else "fallback", "api_ine", missatge)
    save_cache(df, name)
    return df


def process_locals_ccaa_grups():
    """
    Locals per CCAA × grup CNAE 471-479 + divisió 47 (T=294), amb padró per
    CCAA (T=29005 sumada via geo/provincies.csv).
    1. API INE  2. Cache existent
    Sortida: locals_ccaa_grups.csv.
    """
    name = "locals_ccaa_grups"
    print("  Font 1: API INE (T=294 locals per grups)")
    loc = ine.fetch_locals_ccaa_grups()
    if loc.empty:
        print("  Font 2: Cache existent")
        df = load_cache(name)
        if df.empty:
            _record_status(name, "error", "cap", "API INE buida i sense cache")
            return pd.DataFrame()
        _record_status(name, "fallback", "cache", "API INE T=294 buida")
        return df

    geo = _load_provincies()
    noms_ccaa = dict(zip(geo["codi_ccaa"], geo["ccaa"]))
    noms_ccaa["00"] = "espanya"

    # Padró per CCAA: reaprofita el de locals_provincia (mateixa font, ja
    # descarregat en aquest run) per no tornar a baixar la T=29005.
    lp = load_cache("locals_provincia")
    pob = pd.DataFrame(columns=["codi_geo", "any", "poblacio"])
    if not lp.empty:
        lp = lp.astype({"codi_geo": str, "codi_ccaa": str})
        pp = lp[lp["nivell_geo"] == "provincia"]
        pob_ccaa = (pp.groupby(["codi_ccaa", "any"])
                      .agg(poblacio=("poblacio", "sum"), n=("poblacio", "count"))
                      .reset_index())
        # Només anys amb totes les províncies de la CCAA amb padró.
        n_prov = geo.groupby("codi_ccaa").size()
        pob_ccaa = pob_ccaa[pob_ccaa["n"] == pob_ccaa["codi_ccaa"].map(n_prov)]
        pob_ccaa = pob_ccaa.rename(columns={"codi_ccaa": "codi_geo"})[["codi_geo", "any", "poblacio"]]
        pob_esp = lp[lp["nivell_geo"] == "espanya"][["codi_geo", "any", "poblacio"]]
        pob = pd.concat([pob_ccaa, pob_esp], ignore_index=True).dropna()

    loc["any"] = loc["any"].astype(int)
    pob["any"] = pob["any"].astype(int)
    pob["poblacio"] = pd.to_numeric(pob["poblacio"], errors="coerce").astype(float)
    df = loc.merge(pob, on=["codi_geo", "any"], how="left")
    df["nivell_geo"] = df["codi_geo"].map(lambda c: "espanya" if c == "00" else "ccaa")
    df["ccaa"] = df["codi_geo"].map(noms_ccaa)
    df["cnae_nom"] = df["cnae"].map(ine.CNAE_47_MARGES_LABELS)
    mask = df["poblacio"].notna() & (df["poblacio"] > 0)
    df.loc[mask, "locals_per_1000hab"] = (
        df.loc[mask, "locals"] / df.loc[mask, "poblacio"] * 1000).round(3)
    df = _marca_trencaments(df, "locals", ["codi_geo", "cnae"])
    df["font"] = "INE DIRCE T=294 (locals); INE Padró T=29005 sumat per CCAA"

    cols = ["nivell_geo", "codi_geo", "ccaa", "any", "cnae", "cnae_nom", "locals",
            "poblacio", "locals_per_1000hab", "var_interanual_pct",
            "travessa_trencament", "nota_trencament", "font"]
    df = df[cols].astype({"locals": "Int64", "poblacio": "Int64"})

    _is_valid_series(df, "locals", name, group_by=["codi_geo", "cnae"])
    _record_status(name, "ok", "api_ine", f"{len(df)} files")
    save_cache(df, name)
    return df


def process_productivitat():
    """
    Processa productivitat.
    Nota: les dades de productivitat de l'INE requereixen transformacio
    complexa. Prioritzem cache > Excel > API.
    """
    print("  Font 1: API INE")
    df = fetch_productivitat_from_api()
    if not df.empty:
        _record_status("productivitat", "ok", "api_ine", f"{len(df)} files")
    else:
        print("  Font 2: Cache existent")
        df = load_cache("productivitat")
        if not df.empty:
            _record_status("productivitat", "fallback", "cache", "API INE buida")
        else:
            print("  Font 3: Excel local")
            df = load_excel_productivitat()
            if not df.empty:
                _record_status("productivitat", "fallback", "excel", "API i cache buides")
            else:
                _record_status("productivitat", "error", "cap", "Cap font ha funcionat")
                print("  Cap font disponible per productivitat")
                return pd.DataFrame()

    save_cache(df, "productivitat")
    return df


def process_ecommerce():
    """
    Processa e-commerce.
    1. Intenta API CNMC
    2. Fallback: cache existent
    3. Fallback: Excel local
    """
    print("  Font 1: API CNMC")
    df = fetch_ecommerce_from_api()
    if not df.empty:
        _record_status("ecommerce", "ok", "api_cnmc", f"{len(df)} files")
    else:
        print("  Font 2: Cache existent")
        df = load_cache("ecommerce")
        if not df.empty:
            _record_status("ecommerce", "fallback", "cache", "API CNMC buida")
        else:
            print("  Font 3: Excel local")
            df = cnmc.fetch_ecommerce_from_excel()
            if not df.empty:
                _record_status("ecommerce", "fallback", "excel", "API i cache buides")
            else:
                _record_status("ecommerce", "error", "cap", "Cap font ha funcionat")
                print("  Cap font disponible per e-commerce")
                return pd.DataFrame()

    if "ecommerce_total_eur" in df.columns and "ecommerce_cnae47_eur" in df.columns:
        df["pes_cnae47_ecommerce"] = df["ecommerce_cnae47_eur"] / df["ecommerce_total_eur"]

    save_cache(df, "ecommerce")
    return df


def process_europa():
    """
    Processa comparativa europea.
    1. Intenta API Eurostat
    2. Fallback: cache existent
    3. Fallback: Excel local
    """
    COUNTRY_NAMES_CA = {
        "EU27_2020": "UE-27", "EA20": "Eurozona",
        "BE": "Belgica", "BG": "Bulgaria", "CZ": "Txequia",
        "DK": "Dinamarca", "DE": "Alemanya", "EE": "Estonia", "IE": "Irlanda",
        "EL": "Grecia", "ES": "Espanya", "FR": "Franca", "HR": "Croacia",
        "IT": "Italia", "CY": "Xipre", "LV": "Letonia", "LT": "Lituania",
        "LU": "Luxemburg", "HU": "Hongria", "MT": "Malta", "NL": "Paisos Baixos",
        "AT": "Austria", "PL": "Polonia", "PT": "Portugal", "RO": "Romania",
        "SI": "Eslovenia", "SK": "Eslovaquia", "FI": "Finlandia", "SE": "Suecia",
        "IS": "Islandia", "NO": "Noruega", "CH": "Suissa", "RS": "Serbia",
        "BA": "Bosnia",
    }

    print("  Font 1: API Eurostat")
    df = fetch_europa_from_api()
    if not df.empty:
        # Assegurar noms en catala
        df["pais"] = df["pais_codi"].map(COUNTRY_NAMES_CA).fillna(df["pais"])
        _record_status("europa_vab", "ok", "api_eurostat", f"{len(df)} files")
    else:
        print("  Font 2: Cache existent")
        df = load_cache("europa_vab")
        if not df.empty:
            _record_status("europa_vab", "fallback", "cache", "API Eurostat buida")
        else:
            print("  Font 3: Excel local")
            df = _load_europa_from_excel(COUNTRY_NAMES_CA)
            if not df.empty:
                _record_status("europa_vab", "fallback", "excel", "API i cache buides")
            else:
                _record_status("europa_vab", "error", "cap", "Cap font ha funcionat")
                print("  Cap font disponible per Europa")
                return pd.DataFrame()

    save_cache(df, "europa_vab")
    return df


def _load_europa_from_excel(country_names_ca):
    """Llegeix dades europees de l'Excel local (nomes primera carrega)."""
    try:
        import openpyxl
    except ImportError:
        return pd.DataFrame()

    path = os.path.join(os.path.dirname(__file__), "..", "..", "nama_10_a64__custom_16418785_spreadsheet.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    wb = openpyxl.load_workbook(path, data_only=True)
    if "PIB UE CNAE47" not in wb.sheetnames:
        return pd.DataFrame()

    ws = wb["PIB UE CNAE47"]
    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))

    if not rows:
        return pd.DataFrame()

    header = rows[0]
    anys = []
    for v in header[1:]:
        if v is None:
            continue
        try:
            if isinstance(v, str) and "Variaci" in v:
                break
            anys.append(int(v))
        except (ValueError, TypeError):
            continue

    COUNTRY_CODES = {
        "European Union - 27 countries (from 2020)": "EU27_2020",
        "EU - 27 countries": "EU27_2020",
        "Belgium": "BE", "Bulgaria": "BG", "Czechia": "CZ", "Denmark": "DK",
        "Germany": "DE", "Estonia": "EE", "Ireland": "IE", "Greece": "EL",
        "Spain": "ES", "France": "FR", "Croatia": "HR", "Italy": "IT",
        "Cyprus": "CY", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU",
        "Hungary": "HU", "Malta": "MT", "Netherlands": "NL", "Austria": "AT",
        "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Slovenia": "SI",
        "Slovakia": "SK", "Finland": "FI", "Sweden": "SE",
        "Iceland": "IS", "Norway": "NO", "Switzerland": "CH",
        "Serbia": "RS", "Bosnia and Herzegovina": "BA",
    }

    records = []
    seen_countries = set()
    for row in rows[1:]:
        pais_name = row[0]
        if pais_name is None:
            continue
        pais_name = str(pais_name).strip()
        pais_codi = COUNTRY_CODES.get(pais_name)
        if not pais_codi:
            continue

        if pais_codi in seen_countries:
            continue
        seen_countries.add(pais_codi)

        for i, any_ in enumerate(anys):
            idx = i + 1
            if idx < len(row) and row[idx] is not None:
                try:
                    pes = float(row[idx])
                    if pes > 1:
                        continue
                    records.append({
                        "pais": country_names_ca.get(pais_codi, pais_name),
                        "pais_codi": pais_codi,
                        "any": any_,
                        "pes_cnae47": pes,
                    })
                except (ValueError, TypeError):
                    continue

    return pd.DataFrame(records)


def _estimate_vab_eurostat(df):
    """
    Estimació híbrida del VAB CNAE 47 per CCAA combinant:
    - Eurostat nama_10r_3gva: VAB secció G-I per CCAA (comptabilitat regional real)
    - Eurostat nama_10_a64: VAB G47 nacional (per calcular ratio G47/GI)
    - INE EEE taula 76817: xifra de negoci per CCAA (per ponderar)

    Metode:
    1. ratio_g47_gi = VAB_G47_ES / VAB_GI_ES (pes del detall dins G-I a nivell nacional)
    2. Base: VAB_G47_ccaa = VAB_GI_ccaa * ratio_g47_gi
    3. Ajust proporcional amb quotes de xifra de negoci per reflectir que
       el pes del retail dins G-I varia per CCAA (ex: turisme a Balears pesa més en G-I)
    4. Restriccio: la suma de VAB estimat per CCAA = VAB G47 nacional d'Eurostat
    """
    print("  Estimant VAB via Eurostat (metode hibrid)...")
    try:
        df_gi = eurostat.fetch_vab_regional_gi()
        df_g47 = eurostat.fetch_vab_nacional_g47()
        df_total = eurostat.fetch_vab_regional_total()
    except Exception as e:
        print(f"  Error Eurostat regional: {e}")
        return df

    if df_gi.empty or df_g47.empty:
        print("  Eurostat regional: sense dades suficients")
        return df

    gi_es = df_gi[df_gi["territori"] == "espanya"][["any", "vab_gi_meur"]].rename(
        columns={"vab_gi_meur": "vab_gi_es"})
    gi_ccaa = df_gi[df_gi["territori"] != "espanya"][["territori", "any", "vab_gi_meur"]]

    ratio = gi_es.merge(df_g47, on="any", how="inner")
    ratio["r_g47_gi"] = ratio["vab_g47_meur"] / ratio["vab_gi_es"]
    print(f"  Ratio G47/GI nacional: {dict(zip(ratio['any'].astype(int), ratio['r_g47_gi'].round(4)))}")

    df = df.merge(gi_ccaa, on=["territori", "any"], how="left")
    df = df.merge(ratio[["any", "r_g47_gi", "vab_g47_meur"]], on="any", how="left")

    # Base estimate: proportional to G-I
    df["_vab_base"] = df["vab_gi_meur"] * df["r_g47_gi"]

    # XN-weighted adjustment: redistribute so CCAA with higher retail XN share
    # get proportionally more. This corrects for tourism-heavy CCAA where G-I
    # is dominated by hospitality rather than retail.
    df_nac = df[df["territori"] == "espanya"]
    xn_nac_by_year = df_nac[["any", "xifra_negoci"]].rename(
        columns={"xifra_negoci": "xn_nac"}).dropna()

    df = df.merge(xn_nac_by_year, on="any", how="left")

    mask_calc = (
        df["territori"] != "espanya") & (
        df["vab_gi_meur"].notna()) & (
        df["r_g47_gi"].notna()) & (
        df["xifra_negoci"].notna()) & (
        df["xn_nac"].notna()
    )

    for year in df.loc[mask_calc, "any"].unique():
        ym = mask_calc & (df["any"] == year)
        if ym.sum() == 0:
            continue

        # G-I shares and XN shares per CCAA
        gi_total = df.loc[ym, "vab_gi_meur"].sum()
        gi_shares = df.loc[ym, "vab_gi_meur"] / gi_total
        xn_total = df.loc[ym, "xifra_negoci"].sum()
        xn_shares = df.loc[ym, "xifra_negoci"] / xn_total

        # Hybrid share: average of G-I share (top-down) and XN share (bottom-up)
        hybrid_shares = (gi_shares + xn_shares) / 2
        hybrid_shares = hybrid_shares / hybrid_shares.sum()

        # Distribute the national G47 total using hybrid shares
        vab_g47_es = df.loc[ym, "vab_g47_meur"].iloc[0]
        df.loc[ym, "vab_eurostat_meur"] = hybrid_shares * vab_g47_es

    # Also set national total
    mask_es = (df["territori"] == "espanya") & df["vab_g47_meur"].notna()
    df.loc[mask_es, "vab_eurostat_meur"] = df.loc[mask_es, "vab_g47_meur"]

    # Convert M EUR to EUR for consistency with other columns
    if "vab_eurostat_meur" in df.columns:
        df["vab_eurostat"] = df["vab_eurostat_meur"] * 1e6
        n = df["vab_eurostat"].notna().sum()
        print(f"  VAB Eurostat estimat per {n} registres")

    # Pes del CNAE 47 sobre el PIB de cada CCAA
    if not df_total.empty:
        df = df.merge(
            df_total[["territori", "any", "vab_total_meur"]],
            on=["territori", "any"], how="left")
        mask_pes = df["vab_eurostat_meur"].notna() & df["vab_total_meur"].notna() & (df["vab_total_meur"] > 0)
        df.loc[mask_pes, "pes_cnae47_pib"] = df.loc[mask_pes, "vab_eurostat_meur"] / df.loc[mask_pes, "vab_total_meur"]
        n_pes = df["pes_cnae47_pib"].notna().sum()
        print(f"  Pes CNAE 47 / PIB calculat per {n_pes} registres")
    else:
        print("  VAB total regional no disponible, pes no calculat")

    df = df.drop(columns=["vab_gi_meur", "r_g47_gi", "vab_g47_meur", "_vab_base",
                           "xn_nac", "vab_eurostat_meur", "vab_total_meur"], errors="ignore")

    return df


def process_eee_ccaa():
    """
    Processa dades EEE Comercio per CCAA (taula 76817).
    Tres estimacions de VAB CNAE 47 per CCAA:
    - vab_estimat: via ratio nacional VA/XN (EEE, preus constants)
    - vab_estimat_nominal: via ratio nacional VAB_corrents/XN (INE CNA + EEE)
    - vab_eurostat: metode hibrid Eurostat (comptabilitat regional G-I + EEE XN)
    """
    print("  Font 1: API INE (taula 76817)")
    try:
        df = ine.fetch_eee_comercio_ccaa()
        if df.empty:
            print("  API INE EEE CCAA: sense dades")
            df = load_cache("eee_ccaa")
    except Exception as e:
        print(f"  Error API INE EEE CCAA: {e}")
        df = load_cache("eee_ccaa")

    if df.empty:
        print("  Cap font disponible per EEE CCAA")
        return pd.DataFrame()

    print(f"  EEE CCAA: {len(df)} registres, {df['territori'].nunique()} territoris")

    df_nac = df[df["territori"] == "espanya"].copy()
    df_prod = load_cache("productivitat")
    df_pib = load_cache("pib_vab")

    if not df_nac.empty and "xifra_negoci" in df_nac.columns:
        xn_nac = df_nac[["any", "xifra_negoci"]].rename(columns={"xifra_negoci": "xn_nac"})

        # VAB real (preus constants) via productivitat
        if not df_prod.empty and "valor_afegit_constants" in df_prod.columns:
            ratio_real = df_prod[["any"]].copy()
            ratio_real = ratio_real.merge(xn_nac, on="any", how="inner")
            ratio_real["va_real"] = df_prod.set_index("any").loc[ratio_real["any"].values, "valor_afegit_constants"].values
            ratio_real["ratio"] = ratio_real["va_real"] / ratio_real["xn_nac"]

            df = df.merge(ratio_real[["any", "ratio"]].rename(columns={"ratio": "_r_real"}), on="any", how="left")
            mask = df["_r_real"].notna() & df["xifra_negoci"].notna()
            df.loc[mask, "vab_estimat"] = df.loc[mask, "xifra_negoci"] * df.loc[mask, "_r_real"]
            df = df.drop(columns=["_r_real"])
            print(f"  VAB real estimat per {df['vab_estimat'].notna().sum()} registres")

        # VAB nominal (preus corrents) via pib_vab
        if not df_pib.empty and "vab_cnae47_corrents" in df_pib.columns:
            ratio_nom = df_pib[["any", "vab_cnae47_corrents"]].copy()
            ratio_nom = ratio_nom.merge(xn_nac, on="any", how="inner")
            ratio_nom["ratio"] = ratio_nom["vab_cnae47_corrents"] * 1e6 / ratio_nom["xn_nac"]

            df = df.merge(ratio_nom[["any", "ratio"]].rename(columns={"ratio": "_r_nom"}), on="any", how="left")
            mask = df["_r_nom"].notna() & df["xifra_negoci"].notna()
            df.loc[mask, "vab_estimat_nominal"] = df.loc[mask, "xifra_negoci"] * df.loc[mask, "_r_nom"]
            df = df.drop(columns=["_r_nom"])
            print(f"  VAB nominal estimat per {df['vab_estimat_nominal'].notna().sum()} registres")

    # Estimació híbrida Eurostat (comptabilitat regional + EEE)
    df = _estimate_vab_eurostat(df)

    save_cache(df, "eee_ccaa")
    return df


def process_municipal():
    """
    Combina dades municipals de 3 fonts INE per construir un index relatiu de
    capacitat comercial municipal:
      - DIRCE municipal T=4721 (empreses Total + sector G-I)
      - Atlas Renda T=30896 (renda neta mitjana per llar)
      - Padron T=33167 (poblacio per municipi)

    AVIS: l'index NO es VAB CNAE 47 estricte (impossible amb dades publiques).
    Es una proxy d'activitat comercial+associada per municipi (G-I inclou
    transport i hostaleria).

    Genera CSV: municipal.csv amb columnes:
      municipi, any_dirce, total_empreses, empreses_g_i, any_renda,
      renda_llar, any_pob, poblacio, gi_per_1000hab, despesa_potencial,
      index_capacitat (0-100, normalitzat)
    """
    print("  Font 1: DIRCE municipal (T=4721)")
    try:
        df_emp = ine.fetch_empreses_municipal()
        df_emp = df_emp.rename(columns={"any": "any_dirce"})
        print(f"  Empreses: {len(df_emp)} municipis")
    except Exception as e:
        print(f"  Error: {e}")
        df_emp = pd.DataFrame()

    # NOTA: Atlas Renda esta fragmentat en ~52 taules INE (1 per provincia).
    # Saltat al MVP per evitar fer 52 crides API. Pendent per a futura iteracio.
    df_renda = pd.DataFrame()

    print("  Font 2: Padron (T=33167)")
    try:
        df_pob = ine.fetch_poblacio_municipal()
        print(f"  Poblacio: {len(df_pob)} municipis")
    except Exception as e:
        print(f"  Error: {e}")
        df_pob = pd.DataFrame()

    if df_emp.empty:
        print("  Sense dades d'empreses, abortant")
        return pd.DataFrame()

    # Merge per nom de municipi (basic match - alguns no coincidiran per accents/format)
    df = df_emp.copy()
    if not df_renda.empty:
        df = df.merge(df_renda, on="municipi", how="left")
    if not df_pob.empty:
        df = df.merge(df_pob, on="municipi", how="left")

    # Indicadors derivats
    if "empreses_g_i" in df.columns and "poblacio" in df.columns:
        mask = df["poblacio"].notna() & (df["poblacio"] > 0)
        df.loc[mask, "gi_per_1000hab"] = df.loc[mask, "empreses_g_i"] / df.loc[mask, "poblacio"] * 1000

    # Index de capacitat comercial: combinacio normalitzada de:
    #   - empreses G-I absolutes (escala) — log scale
    #   - densitat (qualitat per habitant) — escala lineal
    # Pesos: 50% escala + 50% densitat
    # Filtre: nomes municipis amb poblacio >= 5.000 hab. (eviten falsos positius
    # per duplicats de noms com "Sada", "Mieres", "Cieza", etc.)
    if "empreses_g_i" in df.columns and "gi_per_1000hab" in df.columns:
        mask = (df["empreses_g_i"].notna() & df["gi_per_1000hab"].notna()
                & (df["empreses_g_i"] > 0) & (df["poblacio"] >= 5000))
        sub = df.loc[mask].copy()
        if not sub.empty:
            import numpy as np
            log_emp = np.log10(sub["empreses_g_i"])
            dens = sub["gi_per_1000hab"]
            # Normalitzar 0-100
            def norm(x):
                rng = x.max() - x.min()
                return (x - x.min()) / rng * 100 if rng > 0 else x * 0
            score = (norm(log_emp) + norm(dens)) / 2
            df.loc[mask, "index_capacitat"] = score.values

    save_cache(df, "municipal")
    print(f"  Municipal: {len(df)} files, {df['index_capacitat'].notna().sum() if 'index_capacitat' in df.columns else 0} amb index complet")
    return df


def process_subsectors():
    """
    Processa subsectors CNAE 47:
      - DIRCE (T=73019): empreses per subsector 471-479
      - EAS (T=76818): xifra negoci, VA, personal, inversio per subsector
      - EPF (T=75003): despesa familiar per categoria COICOP

    Genera tres CSVs separats al cache (subsectors_dirce, subsectors_eas, subsectors_epf).
    Cada font te schemas diferents - es deixa la combinacio a la pagina de visualitzacio.
    """
    # ── DIRCE ──
    print("  Font 1: DIRCE (T=73019)")
    try:
        df_dirce = ine.fetch_dirce_subsectors()
        if not df_dirce.empty:
            df_dirce["nom"] = df_dirce["codi"].map(ine.CNAE_47_SUBSECTORS).fillna("CNAE 47 total")
            save_cache(df_dirce, "subsectors_dirce")
            print(f"  DIRCE: {len(df_dirce)} files, anys {df_dirce['any'].min()}-{df_dirce['any'].max()}")
        else:
            print("  DIRCE: sense dades, mantenint cache")
    except Exception as e:
        print(f"  Error DIRCE: {e}")

    # ── EAS ──
    print("  Font 2: EAS / EEE Comercio (T=76818)")
    try:
        df_eas = ine.fetch_eas_subsectors()
        if not df_eas.empty:
            df_eas["codi"] = df_eas["codi"].astype(str)
            # 3 dígits (i total 47): cache principal, consumidors existents sense canvis.
            df_eas3 = df_eas[df_eas["codi"].str.len() <= 3].copy()
            df_eas3["nom"] = df_eas3["codi"].map(ine.CNAE_47_SUBSECTORS).fillna("CNAE 47 total")
            save_cache(df_eas3, "subsectors_eas")
            print(f"  EAS: {len(df_eas3)} files, anys {df_eas3['any'].min()}-{df_eas3['any'].max()}")
            # 4 dígits del grup d'alimentació (472): cache separada per al desglossament.
            df_472 = df_eas[df_eas["codi"].str.len() == 4].copy()
            if not df_472.empty:
                df_472["nom"] = df_472["codi"].map(ine.CNAE_472_SUBSECTORS).fillna(df_472["codi"])
                # Facturació a preus constants (IPC general, base = primer any de la sèrie),
                # mateix criteri que PIB/VAB i Productivitat: real[base] = nominal, real <= nominal després.
                ipc = fetch_ipc_annual()
                if not ipc.empty:
                    ipc_map = dict(zip(ipc["any"].astype(int), ipc["ipc_mitjana"]))
                    base_any = int(df_472["any"].min())
                    ipc_base = ipc_map.get(base_any)
                    if ipc_base:
                        df_472["xifra_negoci_constants"] = df_472.apply(
                            lambda r: r["xifra_negoci"] * ipc_base / ipc_map[int(r["any"])]
                            if ipc_map.get(int(r["any"])) and pd.notna(r["xifra_negoci"]) else None,
                            axis=1,
                        )
                save_cache(df_472, "subsectors_472")
                print(f"  EAS 472 (4 dígits): {len(df_472)} files, {df_472['codi'].nunique()} classes, "
                      f"anys {df_472['any'].min()}-{df_472['any'].max()}")
        else:
            print("  EAS: sense dades, mantenint cache")
    except Exception as e:
        print(f"  Error EAS: {e}")

    # ── EPF ──
    print("  Font 3: EPF (T=75003)")
    try:
        df_epf = ine.fetch_epf_coicop()
        if not df_epf.empty:
            df_epf["nom"] = df_epf["codi_coicop"].map(ine.COICOP_GROUPS).fillna("Total despesa")
            save_cache(df_epf, "subsectors_epf")
            print(f"  EPF: {len(df_epf)} files, anys {df_epf['any'].min()}-{df_epf['any'].max()}")
        else:
            print("  EPF: sense dades, mantenint cache")
    except Exception as e:
        print(f"  Error EPF: {e}")


MARGES_FONT = ("INE, EEE Comercio (Encuesta Anual de Comercio), taula 76818 · "
               "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/76818")


def process_marges_branca():
    """
    Marges per branca del comerç minorista (INE, EEE Comercio / Encuesta Anual
    de Comercio, T=76818). marge = EBE / xifra de negoci × 100 per branca CNAE 47
    a 3 dígits (471-479, excepte 478 que l'INE no publica), sèrie anual des de 2018.

    Font oficial anual; substitueix l'estimació PATECO. La consumeix el pipeline
    de la newsletter (bloc 3 'marges_branca'). Mateix patró que EAS: si l'API
    torna dades es reescriu la cache; si torna buit, es manté la cache anterior.
    """
    try:
        df = ine.fetch_marges_branca()
        if not df.empty:
            df["font"] = MARGES_FONT
            df["verificat"] = True
            df = df[["any", "cnae", "branca", "marge_vendes_pct", "font", "verificat"]]
            save_cache(df, "marges_branca_ine")
            print(f"  Marges branca: {len(df)} files, {df['cnae'].nunique()} branques, "
                  f"anys {df['any'].min()}-{df['any'].max()}")
        else:
            print("  Marges branca: sense dades, mantenint cache")
    except Exception as e:
        print(f"  Error marges branca: {e}")


def process_ipc():
    """
    IPC general nacional, sèrie mensual base 2021=100 (T=50902).
    Desa data/cache/ipc.csv amb columnes (any, mes, ipc).
    Necessari per deflactar series d'alta frequencia (com CDMGE).
    """
    print("  Carregant IPC mensual (taula 50902)...")
    try:
        df = ine.fetch_ipc()
    except Exception as e:
        print(f"  AVIS: error IPC API ({e}); mantenint cache existent")
        return load_cache("ipc")

    if df.empty:
        print("  AVIS: cap dada IPC; mantenint cache existent")
        return load_cache("ipc")
    df = df.dropna(subset=["any", "mes", "ipc"])
    df["any"] = df["any"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df = df.sort_values(["any", "mes"]).reset_index(drop=True)
    save_cache(df, "ipc")
    return df


def process_ipc_coicop():
    """
    IPC per grups ECOICOP rellevants pel comerç (INE T=76125): alimentació,
    vestit i calçat, parament de la llar + índex general de referència.
    Mensual, base 2021=100, sèrie des de 2002. No crítica: si l'API falla,
    es manté la cache existent en silenci.
    """
    print("  Carregant IPC per grups ECOICOP (taula 76125)...")
    try:
        df = ine.fetch_ipc_coicop()
    except Exception as e:
        print(f"  Error API IPC COICOP: {e}")
        df_cache = load_cache("ipc_coicop")
        _record_status("ipc_coicop", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades IPC COICOP; mantenint cache existent")
        df_cache = load_cache("ipc_coicop")
        _record_status("ipc_coicop", "fallback" if not df_cache.empty else "error",
                       "cache", "API INE IPC COICOP buida")
        return df_cache

    _is_valid_series(df, "ipc", "ipc_coicop", group_by="grup_codi")
    save_cache(df, "ipc_coicop")
    _record_status("ipc_coicop", "ok", "api_ine", f"{len(df)} files")
    print(f"  IPC COICOP: {len(df)} files, {df['grup_codi'].nunique()} grups, "
          f"{df['any'].min()}-{df['any'].max()}")
    return df


def process_epa_retail():
    """
    EPA — ocupats, aturats i hores treballades al comerç, per sexe (INE
    T=65123+65249+65159). Només ocupats_cnae47_milers és CNAE 47 net; aturats
    i hores només arriben a secció G (comerç a l'engròs + al detall +
    reparació de vehicles) — l'INE no publica cap desglossament EPA a nivell
    CNAE 47 per aquestes dues magnituds (vegeu docstring de
    ine.fetch_epa_retail()). No crítica: fallback silenciós a cache.
    """
    print("  Carregant EPA retail (taules 65123+65249+65159)...")
    try:
        df = ine.fetch_epa_retail()
    except Exception as e:
        print(f"  Error API EPA: {e}")
        df_cache = load_cache("epa_retail")
        _record_status("epa_retail", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades EPA; mantenint cache existent")
        df_cache = load_cache("epa_retail")
        _record_status("epa_retail", "fallback" if not df_cache.empty else "error",
                       "cache", "API INE EPA buida")
        return df_cache

    _is_valid_series(df, "ocupats_cnae47_milers", "epa_retail", group_by="sexe")
    _is_valid_series(df, "aturats_seccio_g_milers", "epa_retail", group_by="sexe")
    save_cache(df, "epa_retail")
    _record_status("epa_retail", "ok", "api_ine", f"{len(df)} files")
    print(f"  EPA retail: {len(df)} files, {df['periode'].min()}-{df['periode'].max()}")
    return df


def process_confianza_consumidor():
    """
    Índex de confiança del consumidor (Eurostat ei_bsco_m, ES). No hi ha
    taula pròpia de l'INE per aquest indicador — la sèrie harmonitzada UE es
    publica a Eurostat (vegeu docstring de eurostat.fetch_confianza_consumidor()).
    Inclou l'indicador compost i el desglossament situació actual /
    expectatives. No crítica: fallback silenciós a cache.
    """
    print("  Carregant confiança del consumidor (Eurostat ei_bsco_m)...")
    try:
        df = eurostat.fetch_confianza_consumidor()
    except Exception as e:
        print(f"  Error API Eurostat confiança: {e}")
        df_cache = load_cache("confianza_consumidor")
        _record_status("confianza_consumidor", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades confiança; mantenint cache existent")
        df_cache = load_cache("confianza_consumidor")
        _record_status("confianza_consumidor", "fallback" if not df_cache.empty else "error",
                       "cache", "API Eurostat ei_bsco_m buida")
        return df_cache

    _is_valid_series(df, "index_confianca", "confianza_consumidor")
    save_cache(df, "confianza_consumidor")
    _record_status("confianza_consumidor", "ok", "api_eurostat", f"{len(df)} files")
    print(f"  Confiança consumidor: {len(df)} files, {df['periode'].min()}-{df['periode'].max()}")
    return df


def process_targetes_tpv():
    """
    Compres amb targeta en terminals de punt de venda (Banco de España, STMP).
    Trimestral des de 2005: operacions, import i tiquet mitjà. Totes les
    activitats (no només CNAE 47): context del consum pagat amb targeta.
    No crítica: fallback silenciós a cache.
    """
    print("  Carregant compres amb targeta en TPV (Banco de España)...")
    try:
        df = bde.fetch_targetes_tpv()
    except Exception as e:
        print(f"  Error BdE targetes: {e}")
        df_cache = load_cache("targetes_tpv")
        _record_status("targetes_tpv", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio BdE: {e}")
        return df_cache

    _is_valid_series(df, "import_milions", "targetes_tpv")
    save_cache(df, "targetes_tpv")
    _record_status("targetes_tpv", "ok", "xlsx_bde", f"{len(df)} files")
    print(f"  Targetes TPV: {len(df)} files, {df['periode'].min()}-{df['periode'].max()}")
    return df


def process_europa_retail_mensual():
    """
    Volum de vendes mensual del comerç minorista G47 per país (Eurostat sts_trtu_m).
    Base 2021=100, ajustat estacional. Es calcula la variacio interanual (YoY).
    Cau silenciosament al cache existent si l'API falla.
    """
    print("  Carregant retail mensual Eurostat (sts_trtu_m)...")
    try:
        df = eurostat.fetch_retail_volume_monthly()
    except Exception as e:
        print(f"  Error API Eurostat retail mensual: {e}")
        df_cache = load_cache("europa_retail_mensual")
        _record_status("europa_retail_mensual", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades; mantenint cache existent")
        df_cache = load_cache("europa_retail_mensual")
        _record_status("europa_retail_mensual", "fallback" if not df_cache.empty else "error",
                       "cache", "API Eurostat sts_trtu_m buida")
        return df_cache

    df = df.sort_values(["pais_codi", "periode"]).reset_index(drop=True)
    # Variacio interanual: index_volum vs el mateix mes de l'any anterior (12 mesos enrere)
    df["yoy"] = df.groupby("pais_codi")["index_volum"].pct_change(periods=12) * 100
    save_cache(df, "europa_retail_mensual")
    _record_status("europa_retail_mensual", "ok", "api_eurostat", f"{len(df)} files")
    return df


def process_europa_retail_branques():
    """
    Volum de vendes mensual del comerç al detall per branca (Eurostat sts_trtu_m):
    alimentació, no alimentari, farmàcia, internet... per a Espanya, UE-27,
    Eurozona i quatre països veïns. Base 2021=100, ajustat estacional.
    Cau silenciosament al cache existent si l'API falla.
    """
    print("  Carregant retail mensual per branca Eurostat (sts_trtu_m)...")
    try:
        df = eurostat.fetch_retail_volume_branques()
    except Exception as e:
        print(f"  Error API Eurostat retail per branca: {e}")
        df_cache = load_cache("europa_retail_branques")
        _record_status("europa_retail_branques", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades; mantenint cache existent")
        df_cache = load_cache("europa_retail_branques")
        _record_status("europa_retail_branques", "fallback" if not df_cache.empty else "error",
                       "cache", "API Eurostat sts_trtu_m (branques) buida")
        return df_cache

    df = df.sort_values(["pais_codi", "nace_codi", "periode"]).reset_index(drop=True)
    df["yoy"] = df.groupby(["pais_codi", "nace_codi"])["index_volum"].pct_change(periods=12) * 100
    save_cache(df, "europa_retail_branques")
    _record_status("europa_retail_branques", "ok", "api_eurostat", f"{len(df)} files")
    return df


def process_digitalitzacio_comerc():
    """
    Radiografia de digitalització del comerç (NACE G47): % d'empreses que
    adopten venda electrònica, IA i núvol (Eurostat, enquesta TIC). ES vs
    UE-27, anual. Cau silenciosament al cache existent si l'API falla.
    """
    print("  Carregant digitalització del comerç (Eurostat TIC: e-commerce/IA/núvol)...")
    try:
        df = eurostat.fetch_digitalitzacio_comerc()
    except Exception as e:
        print(f"  Error API Eurostat digitalització: {e}")
        df_cache = load_cache("digitalitzacio_comerc")
        _record_status("digitalitzacio_comerc", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades digitalització; mantenint cache existent")
        df_cache = load_cache("digitalitzacio_comerc")
        _record_status("digitalitzacio_comerc", "fallback" if not df_cache.empty else "error",
                       "cache", "API Eurostat TIC buida")
        return df_cache

    save_cache(df, "digitalitzacio_comerc")
    _record_status("digitalitzacio_comerc", "ok", "api_eurostat", f"{len(df)} registres")
    print(f"  Digitalització comerç: {len(df)} registres")
    return df


def process_ocupacio_comerc():
    """
    Ocupació al comerç (NACE G47) per sexe i edat (Eurostat lfsa_egan22d, EU-LFS).
    Radiografia de qui treballa al sector: pes femení i relleu generacional.
    ES vs UE-27, anual. Cau silenciosament al cache existent si l'API falla.
    """
    print("  Carregant ocupació comerç per sexe/edat (Eurostat lfsa_egan22d)...")
    try:
        df = eurostat.fetch_ocupacio_comerc()
    except Exception as e:
        print(f"  Error API Eurostat ocupació: {e}")
        df_cache = load_cache("ocupacio_comerc")
        _record_status("ocupacio_comerc", "fallback" if not df_cache.empty else "error",
                       "cache", f"Excepcio API: {e}")
        return df_cache

    if df.empty:
        print("  AVIS: sense dades ocupació LFS; mantenint cache existent")
        df_cache = load_cache("ocupacio_comerc")
        _record_status("ocupacio_comerc", "fallback" if not df_cache.empty else "error",
                       "cache", "API Eurostat lfsa_egan22d buida")
        return df_cache

    save_cache(df, "ocupacio_comerc")
    _record_status("ocupacio_comerc", "ok", "api_eurostat", f"{len(df)} registres")
    print(f"  Ocupació comerç (sexe/edat): {len(df)} registres")
    return df


# Noms comercials curats per a la pàgina de Líders (la raó social verbatim del
# SABI queda lletja amb .title()). Clau = Nombre original del raw (majúscules).
# Editable: si un nom comercial no és correcte, ajusta'l aquí.
_LIDERES_BRAND = {
    "MERCADONA SA": "Mercadona",
    "CENTROS COMERCIALES CARREFOUR SA": "Carrefour",
    "LIDL SUPERMERCADOS SAU": "Lidl",
    "ALCAMPO SA": "Alcampo",
    "DIA RETAIL ESPAÑA SA": "Dia",
    "CONSUM S COOP V": "Consum",
    "LEROY MERLIN ESPAÑA SL": "Leroy Merlin",
    "MANGO MNG S.A.": "Mango",
    "BON PREU SAU": "Bon Preu",
    "MEDIA MARKT SATURN SAU": "MediaMarkt",
    "AHORRAMAS, SA": "Ahorramás",
    "EROSKI, S.COOP.": "Eroski",
    "IKEA IBERICA SAU": "Ikea",
    "BRICOLAJE BRICOMAN SLU": "Bricoman",
    "DECATHLON ESPAÑA SAU": "Decathlon",
    "PRIMARK TIENDAS SLU": "Primark",
    "BERSHKA BSK ESPAÑA SA": "Bershka",
    "STRADIVARIUS ESPAÑA SA": "Stradivarius",
    "TENDAM RETAIL SA.": "Tendam",
    "ALIMERKA S.A.": "Alimerka",
    "CAPRABO SA": "Caprabo",
    "SPRINTER MEGACENTROS DEL DEPORTE SL": "Sprinter",
    "CASA AMETLLER SL": "Casa Ametller",
    "APPLE RETAIL SPAIN SL": "Apple Store",
    "PC COMPONENTES Y MULTIMEDIA SLU": "PcComponentes",
    "FAMILYCASH SL": "Family Cash",
    "HENNES AND MAURITZ SLU": "H&M",
    "JD SPAIN SPORTS FASHION 2010 SL.": "JD Sports",
    "JOYERIA TOUS SA": "Tous",
    "FRAGADIS SL": "Fragadis",
    "FRANCHISING CALZEDONIA ESPAÑA SA": "Calzedonia",
    "SEPHORA COSMETICOS ESPAÑA SL": "Sephora",
    "GRANDES ALMACENES FNAC ESPAÑA SA": "Fnac",
    "GAME STORES IBERIA SL": "GAME",
    "CONFORAMA ESPAÑA SA": "Conforama",
    "ARENAL PERFUMERIAS SL": "Arenal Perfumerías",
    "GENERAL OPTICA SA": "General Óptica",
    "TIENDANIMAL COMERCIO ELECTRONICO DE ARTICULOS PARA MASCOTAS SL": "Tiendanimal",
    "KIABI ESPAÑA KSCE SA": "Kiabi",
    "KAVE HOME SL": "Kave Home",
    "LA SIRENA ALIMENTACION CONGELADA SAU": "La Sirena",
    "ACTION RETAIL SPAIN SL.": "Action",
    "BIMBA Y LOLA SOCIEDAD LIMITADA.": "Bimba y Lola",
    "CHRISTIAN DIOR ESPAÑOLA SLU": "Christian Dior",
    "FOOT LOCKER SPAIN SL": "Foot Locker",
    "FORUM SPORT SOCIEDAD ANONIMA": "Forum Sport",
    "MERKAL CALZADOS SL": "Merkal",
    "ADOLFO DOMINGUEZ SA": "Adolfo Domínguez",
    "MAISONS DU MONDE ESPAÑA SL.": "Maisons du Monde",
    "KIKO RETAIL ESPAÑA SL": "Kiko Milano",
    "ALDI MASQUEFA SUPERMERCADOS SL": "Aldi",
}

_LIDERES_LEGAL = {"SA", "SL", "SAU", "SLU", "SLP", "SLNE", "SCCL", "SCP", "SC",
                  "SCV", "SAL", "SCA", "SE", "SLL", "SAS", "SCOOP", "COOP"}


_LIDERES_MINUS = {"Y", "I", "DE", "DEL", "LA", "EL", "AND", "DE'"}


def _pretty_name(raw):
    """Nom comercial net: mapa curat si hi és, si no neteja genèrica (col·lapsa
    formes jurídiques —deletrejades o amb punts— a sigla, capitalitza la resta)."""
    import re
    raw = (raw or "").strip()
    if raw in _LIDERES_BRAND:
        return _LIDERES_BRAND[raw]
    txt = raw
    # formes jurídiques deletrejades -> sigla
    txt = re.sub(r"\bSOCIEDAD\s+ANONIMA(\s+UNIPERSONAL)?\.?", "SA", txt, flags=re.I)
    txt = re.sub(r"\bSOCIEDAD\s+LIMITADA(\s+UNIPERSONAL)?\.?", "SL", txt, flags=re.I)
    txt = re.sub(r"\bSOCIEDAD\s+COOPERATIVA\b", "SCOOP", txt, flags=re.I)
    # formes jurídiques amb punts (S.A.U. -> SAU, S.L. -> SL)
    txt = re.sub(r"\bS(\.[A-Za-z])+\.?", lambda m: m.group(0).replace(".", "").upper(), txt)
    txt = re.sub(r"[.,]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    out = []
    for tk in txt.split(" "):
        tk = tk.strip("-")
        if not tk:
            continue
        u = tk.upper()
        if u in _LIDERES_LEGAL:
            out.append(u)
        elif u in _LIDERES_MINUS:
            out.append(tk.lower())
        else:
            out.append("-".join(p.capitalize() for p in tk.split("-")))
    return " ".join(out)


def process_lideres():
    """
    Líders del comerç (CNAE 47): comptes anuals dipositats al Registre Mercantil,
    top empreses 2020-2024 (font: extracció manual SABI, sense API). Llegeix el
    fitxer cru data/raw/lideres_comerc_sabi.csv, el neteja (format espanyol,
    n.d.->buit, descarta TotalPasivoCP duplicat) i el desa en format llarg
    (empresa × any) amb derivats (marges, ràtio personal, productivitat).
    Actualització: reemplaçar el raw i tornar a executar.
    """
    import numpy as np
    raw_path = os.path.join(CACHE_DIR, "..", "raw", "lideres_comerc_sabi.csv")
    if not os.path.exists(raw_path):
        print("  AVIS: sense raw de líders; mantenint cache existent")
        return load_cache("lideres_comerc")
    print("  Processant líders del comerç (Registre Mercantil, raw manual)...")
    raw = pd.read_csv(raw_path, sep=";", quotechar='"', dtype=str, keep_default_na=False)

    def _num(x):
        x = (x or "").strip()
        if x in ("", "n.d.", "n.d", "nd"):
            return np.nan
        neg = x.startswith("-")
        x = x.lstrip("-").replace(".", "").replace(",", ".")
        try:
            v = float(x)
            return -v if neg else v
        except ValueError:
            return np.nan

    years = [2024, 2023, 2022, 2021, 2020]
    metrics = ["Ingresos", "EBITDA", "EBIT", "Resultado", "TotalActivo",
               "DeudasFin", "Empleados", "GastosPersonal"]  # TotalPasivoCP descartat (duplicat d'Activo)
    sub = {"4711": "Alimentació", "4719": "No especialitzat", "4729": "Alim. especialitzada",
           "4730": "Combustible", "4741": "Informàtica/electrònica", "4752": "Bricolatge i ferreteria",
           "4754": "Electrodomèstics", "4759": "Mobles i llar", "4761": "Llibres i cultura",
           "4764": "Esports", "4771": "Moda i tèxtil", "4772": "Calçat", "4774": "Òptica",
           "4775": "Cosmètica i perfumeria", "4776": "Mascotes", "4777": "Joieria",
           "4778": "Òptica"}
    rows = []
    for _, c in raw.iterrows():
        cn = str(c["CNAE_primario"]).strip()
        for y in years:
            rec = {"num": int(c["Num"]), "nombre": c["Nombre"], "nif": c["Codigo_NIF"],
                   "localitat": c["Localidad"], "forma": c["Forma_juridica"], "cnae": cn,
                   "subsector": sub.get(cn, "Altres"), "any": y}
            for m in metrics:
                rec[m.lower()] = _num(c.get(f"{m}_{y}", ""))
            rows.append(rec)
    d = pd.DataFrame(rows)
    # CACHE PÚBLICA = mètriques per empresa (snapshot 2024) + creixement orgànic.
    # Ràtios derivats + facturació + plantilla; el detall financer absolut de 5
    # anys (l'export verbatim) NO es publica (queda al raw, gitignored).
    piv = d.pivot_table(index="nombre", columns="any", values="ingresos")

    def _break(nom):
        s = piv.loc[nom].dropna().sort_index()
        if len(s) < 2:
            return False
        if s.min() / s.max() < 0.10:
            return True
        yoy = (s / s.shift(1)).dropna()
        return bool((yoy > 4.5).any() or (yoy < 0.22).any())

    # Per empresa, prenem la fila de l'any més recent disponible amb facturació.
    # Algunes filials grans (Lidl, Eroski) tanquen exercici després que les altres
    # i el 2024 encara no està dipositat; sense aquest fallback queden fora de la
    # foto i el missatge de la pàgina perd dues peces clau de l'argumentari.
    ANYS_PREF = [2024, 2023, 2022, 2021, 2020]
    base = d[d["any"] == 2020].set_index("nombre")["ingresos"]
    recs = []
    for nom, grp in d.groupby("nombre"):
        c = None
        snapshot_any = None
        for y in ANYS_PREF:
            sub = grp[grp["any"] == y]
            if not sub.empty and pd.notna(sub.iloc[0]["ingresos"]):
                c = sub.iloc[0]
                snapshot_any = y
                break
        if c is None:
            continue
        I = c["ingresos"]
        ta = c["totalactivo"]
        brk = _break(nom)
        ing20 = base.get(nom, float("nan"))
        cagr = (((I / ing20) ** 0.25 - 1) * 100
                if (pd.notna(I) and pd.notna(ing20) and ing20 > 0 and not brk
                    and snapshot_any == 2024) else float("nan"))
        recs.append({
            "nombre": _pretty_name(nom), "subsector": c["subsector"], "cnae": c["cnae"],
            "snapshot_any": snapshot_any,
            "ing_2024": I, "ing_2020": ing20, "empleados": c["empleados"],
            "marge_ebitda": c["ebitda"] / I * 100 if I else float("nan"),
            "marge_ebit": c["ebit"] / I * 100 if I else float("nan"),
            "marge_net": c["resultado"] / I * 100 if I else float("nan"),
            "roa": c["resultado"] / ta * 100 if ta else float("nan"),
            "ratio_personal": c["gastospersonal"] / I * 100 if I else float("nan"),
            "productivitat": I * 1000 / c["empleados"] if c["empleados"] else float("nan"),
            "cost_empleat": c["gastospersonal"] * 1000 / c["empleados"] if c["empleados"] else float("nan"),
            "cagr": cagr, "break_flag": brk,
        })
    emp = pd.DataFrame(recs)
    # CACHE PÚBLICA = ràtios + xifres absolutes (facturació, plantilla, quota).
    # La facturació i la plantilla són fets PÚBLICS del Registre Mercantil; el que
    # NO es redistribueix és l'export SABI verbatim (llicència), que queda al raw
    # gitignored. Afegim quota dins la mostra i rang per facturació 2024.
    tot24 = emp["ing_2024"].sum(skipna=True)
    emp["quota_2024"] = (emp["ing_2024"] / tot24 * 100) if tot24 else float("nan")
    emp = emp.sort_values("ing_2024", ascending=False, na_position="last").reset_index(drop=True)
    emp["rank_2024"] = emp["ing_2024"].rank(ascending=False, method="min").astype("Int64")
    emp_pub = emp
    save_cache(emp_pub, "lideres_empreses")
    print(f"  Líders del comerç: {len(emp_pub)} empreses (absoluts+ràtios) · "
          f"top1 quota {emp['quota_2024'].max():.1f}% · {int(emp['break_flag'].sum())} ruptures")
    return emp_pub


def process_cdmge():
    """
    CDMGE — comerç diari grans empreses (T=37808, INE experimental).
    Sèrie diària 2019-actualitat. 5 indicadors. Cobreix CNAE 47 grans empreses.
    """
    print("  Carregant CDMGE (taula 37808)...")
    df = ine.fetch_cdmge()
    if df.empty:
        print("  AVIS: cap dada CDMGE; mantenint cache existent")
        df_cache = load_cache("cdmge")
        _record_status("cdmge", "fallback" if not df_cache.empty else "error",
                       "cache", "API INE CDMGE buida")
        return df_cache
    _is_valid_series(df, "valor", "cdmge", group_by="indicador")
    save_cache(df, "cdmge")
    _record_status("cdmge", "ok", "api_ine", f"{len(df)} files")
    return df


def process_icm():
    """
    ICM — Índices de Comercio al por Menor (INE, base 2021=100).
    Sèrie mensual oficial del comerç al detall espanyol.

    7 taules INE combinades:
      - 60096 (cifra real Nacional × branca)
      - 59787 (cifra nominal Nacional × especials agregats)
      - 60103 (cifra real Nacional × especials agregats)
      - 60110 (cifra nominal per CCAA)
      - 60111 (cifra real per CCAA)
      - 60114 (ocupació Nacional)
      - 60115 (ocupació Nacional; els modes de distribució es descarten)

    Genera data/cache/icm.csv (~48k files típicament).
    """
    print("  Carregant ICM (taules 60096+59787+60103+60110+60111+60114+60115)...")
    df = ine.fetch_icm()
    if df.empty:
        print("  AVIS: cap dada ICM; mantenint cache existent")
        df_cache = load_cache("icm")
        _record_status("icm", "fallback" if not df_cache.empty else "error",
                       "cache", "API INE ICM buida")
        return df_cache
    # Validem només les sèries d'índex (base 2021=100). Les derivades
    # (var_mensual, var_anual, var_mitjana_acum) poden tenir valors prop de zero
    # seguits de pics estacionals grans (ex: 0.1% nov → 24.2% des), cosa que
    # dispara falsos positius per ràtio sense indicar cap canvi d'escala real.
    df_idx = df[df["indicador"] == "index"] if "indicador" in df.columns else df
    _is_valid_series(df_idx, "valor", "icm", group_by="serie_id")
    save_cache(df, "icm")
    _record_status("icm", "ok", "api_ine", f"{len(df)} files")
    return df


def process_eaes():
    """
    EAES — Encuesta Anual de Estructura Salarial (INE T=28185).
    Salari brut anual mitjà total nacional per sector. Per comparar el
    sector G (comerç) amb la mitjana de la economia espanyola.
    """
    print("  Carregant EAES (taula 28185, salari brut anual per sector)...")
    df = ine.fetch_eaes()
    if df.empty:
        print("  AVIS: cap dada EAES; mantenint cache existent")
        return load_cache("eaes")
    save_cache(df, "eaes")
    return df


def process_icm_distribucion():
    """
    ICM per modo de distribución comercial (INE).
    Substitueix la taula 25982 descatalogada el 2023 (Antiguos índices de
    grandes superficies) amb el desglossament actual integrat a l'ICM base
    2021=100. Modos: Empresas unilocalizadas, Pequeñas cadenas, Grandes
    cadenas, Grandes Superficies.

    Taules INE: 60105 (nominal) + 75809 (real) + 60115 (ocupació).
    Genera icm_distribucion.csv.
    """
    print("  Carregant ICM per modo de distribució (60105+75809+60115)...")
    df = ine.fetch_icm_distribucion()
    if df.empty:
        print("  AVIS: cap dada ICM distribució; mantenint cache existent")
        df_cache = load_cache("icm_distribucion")
        _record_status("icm_distribucion", "fallback" if not df_cache.empty else "error",
                       "cache", "API INE ICM distribució buida")
        return df_cache
    save_cache(df, "icm_distribucion")
    _record_status("icm_distribucion", "ok", "api_ine", f"{len(df)} files")
    return df


def process_estructura_retail():
    """
    Estructura empresarial CNAE 47 — Eurostat Business Demography (bd_size).
    Genera 3 caches:
      - estructura_retail.csv: indicadors totals (ES + UE27 + top economies, 2009-2023)
      - estructura_retail_mida.csv: distribució per mida d'empresa (ES + UE27)
      - estructura_retail_supervivencia.csv: % supervivència Y1-Y2 (ES + UE27)
    Tot CNAE G47 estricte.
    """
    print("  Carregant Business Demography G47 (bd_size totals)...")
    try:
        df_total = eurostat.fetch_bsd_total()
    except Exception as e:
        print(f"  Error fetch_bsd_total: {e}")
        df_total = load_cache("estructura_retail")

    if df_total.empty:
        print("  AVIS: cap dada bd_size totals; mantenint cache existent")
    else:
        df_total = df_total.sort_values(["pais_codi", "any", "indic_sbs"]).reset_index(drop=True)
        save_cache(df_total, "estructura_retail")

    print("  Carregant Business Demography G47 (bd_size per mida)...")
    try:
        df_size = eurostat.fetch_bsd_sizeclas()
    except Exception as e:
        print(f"  Error fetch_bsd_sizeclas: {e}")
        df_size = load_cache("estructura_retail_mida")

    if df_size.empty:
        print("  AVIS: cap dada bd_size mida; mantenint cache existent")
    else:
        df_size = df_size.sort_values(["pais_codi", "any", "indic_sbs", "sizeclas"]).reset_index(drop=True)
        save_cache(df_size, "estructura_retail_mida")

    print("  Carregant Business Demography G47 (bd_size supervivència)...")
    try:
        df_surv = eurostat.fetch_bsd_survival()
    except Exception as e:
        print(f"  Error fetch_bsd_survival: {e}")
        df_surv = load_cache("estructura_retail_supervivencia")

    if df_surv.empty:
        print("  AVIS: cap dada bd_size supervivència; mantenint cache existent")
    else:
        df_surv = df_surv.sort_values(["pais_codi", "any", "age"]).reset_index(drop=True)
        save_cache(df_surv, "estructura_retail_supervivencia")

    return df_total


def save_last_update():
    """Desa la data i hora de l'última actualització."""
    from datetime import datetime
    ensure_cache_dir()
    path = os.path.join(CACHE_DIR, "last_update.txt")
    with open(path, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(f"  Data actualització: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# Datasets vigilats pel sistema d'alertes de la home. Per cada un, la
# columna que marca la "última dada de la sèrie" i l'etiqueta editorial.
DATASETS_VIGILATS = {
    # "valor": columna que ha de tenir dada perquè el període compti. Cal quan la
    # font publica abans el total que el desglossament: el 30/09/2026 l'INE va
    # donar el VAB total de 2025 sense el del CNAE 47, i la novetat deia 2025.
    "pib_vab":               {"col": "any",     "ca": "PIB i VAB",                  "es": "PIB y VAB",
                              "valor": "vab_cnae47_corrents"},
    "empreses":              {"col": "any",     "ca": "Empreses",                   "es": "Empresas"},
    "productivitat":         {"col": "any",     "ca": "Productivitat",              "es": "Productividad"},
    "ecommerce":             {"col": "any",     "ca": "E-commerce",                 "es": "E-commerce"},
    "eee_ccaa":              {"col": "any",     "ca": "Territori",                  "es": "Territorio"},
    "europa_vab":            {"col": "any",     "ca": "Europa (VAB)",               "es": "Europa (VAB)"},
    "icm":                   {"col": "data",    "ca": "Pols mensual (ICM)",         "es": "Pulso mensual (ICM)"},
    "icm_distribucion":      {"col": "data",    "ca": "ICM per format de venda",    "es": "ICM por formato de venta"},
    "eaes":                  {"col": "any",     "ca": "Salaris (EAES)",             "es": "Salarios (EAES)"},
    "europa_retail_mensual": {"col": "periode", "ca": "Comerç a Europa (mensual)",  "es": "Comercio en Europa (mensual)"},
    "europa_retail_branques": {"col": "periode", "ca": "Comerç a Europa per branca (mensual)", "es": "Comercio en Europa por rama (mensual)"},
    "digitalitzacio_comerc": {"col": "any", "ca": "Digitalització del comerç", "es": "Digitalización del comercio"},
    "ocupacio_comerc": {"col": "any", "ca": "Ocupació per sexe i edat", "es": "Ocupación por sexo y edad"},
    "cdmge":                 {"col": "data",    "ca": "Pols diari",                 "es": "Pulso diario"},
    "ipc":                   {"col": "any",     "ca": "IPC",                        "es": "IPC"},
    "subsectors_dirce":      {"col": "any",     "ca": "Subsectors (oferta, DIRCE)",  "es": "Subsectores (oferta, DIRCE)"},
    "subsectors_eas":        {"col": "any",     "ca": "Subsectors (oferta, EAS)",    "es": "Subsectores (oferta, EAS)"},
    "subsectors_epf":        {"col": "any",     "ca": "Pressupostos familiars (EPF)", "es": "Presupuestos Familiares (EPF)"},
    "subsectors_472":        {"col": "any",     "ca": "Subsectors d'alimentació (472)", "es": "Subsectores de alimentación (472)"},
    "marges_branca_ine":     {"col": "any",     "ca": "Marges per branca",           "es": "Márgenes por rama"},
    "estructura_consum":     {"col": "any",     "ca": "Consum: béns i serveis (Eurostat)", "es": "Consumo: bienes y servicios (Eurostat)"},
    "ipc_coicop":            {"col": "periode", "ca": "IPC per grups (alimentació, vestit, llar)", "es": "IPC por grupos (alimentación, vestido, hogar)"},
    "epa_retail":            {"col": "periode", "ca": "EPA — ocupats, aturats i hores",  "es": "EPA — ocupados, parados y horas"},
    "confianza_consumidor":  {"col": "periode", "ca": "Confiança del consumidor",     "es": "Confianza del consumidor"},
    "targetes_tpv":          {"col": "data",    "ca": "Compres amb targeta (Banc d'Espanya)", "es": "Compras con tarjeta (Banco de España)"},
    "estructura_retail":     {"col": "any",     "ca": "Estructura del comerç a la UE (SBS)", "es": "Estructura del comercio en la UE (SBS)"},
    "estructura_retail_mida": {"col": "any",    "ca": "Comerç UE per mida d'empresa", "es": "Comercio UE por tamaño de empresa"},
    "estructura_retail_supervivencia": {"col": "any", "ca": "Supervivència d'empreses (UE)", "es": "Supervivencia de empresas (UE)"},
}

# Caches .csv que NO es vigilen a propòsit (amb el motiu). Serveix perquè
# check_unwatched_caches() no els marqui com a oblidats. Si afegeixes una font
# nova al pipeline, dona-la d'alta a DATASETS_VIGILATS o, si no toca vigilar-la,
# aquí amb el motiu.
CACHES_NO_VIGILATS = {
    "estructura_comerc",        # sèrie projectada fins al 2035: el marcador no és una dada real
    "prediccions_estructura",   # projeccions internes pròpies, no una font externa
    "lideres_empreses",         # export manual SABI, sense columna de data i ritme irregular
    "municipal",                # només local (OBSERVATORI_LOCAL=1), no es publica
    "fets",                     # lectures del motor de fets (data/sql/fets.py), no una font
}


def _dataset_last_marker(name, col, valor=None):
    """Retorna un string que identifica la última dada de la sèrie d'un
    dataset (any, periode YYYY-MM o data YYYY-MM-DD), o None si no es pot.
    Si es dona `valor`, només compten les files on aquesta columna té dada."""
    df = load_cache(name)
    if df.empty or col not in df.columns:
        return None
    if valor and valor in df.columns:
        df = df[df[valor].notna()]
    serie = df[col].dropna()
    if serie.empty:
        return None
    if col == "any":
        try:
            return str(int(serie.max()))
        except (ValueError, TypeError):
            return None
    if col == "periode":
        return str(serie.max())
    # col == "data"
    d = pd.to_datetime(serie, errors="coerce").max()
    return d.strftime("%Y-%m-%d") if pd.notna(d) else None


def record_dataset_updates():
    """Detecta quins datasets han avançat de data respecte l'última execució
    i registra els events a cache/updates_log.json. La home en mostra els
    recents al bloc 'Novetats'. La primera execució inicialitza en silenci
    (sense events) per no generar falses novetats."""
    import json
    from datetime import date
    ensure_cache_dir()
    path = os.path.join(CACHE_DIR, "updates_log.json")
    log = {"datasets": {}, "events": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, OSError):
            log = {"datasets": {}, "events": []}
    log.setdefault("datasets", {})
    log.setdefault("events", [])

    today = date.today().isoformat()
    nous = 0
    for name, cfg in DATASETS_VIGILATS.items():
        marker = _dataset_last_marker(name, cfg["col"], cfg.get("valor"))
        if marker is None:
            continue
        prev = log["datasets"].get(name, {}).get("last_data")
        if marker != prev:
            log["datasets"][name] = {"last_data": marker, "detected_at": today}
            # Només generem event si ja teníem un valor anterior (evita
            # 13 falses novetats el primer cop que s'inicialitza el log).
            if prev is not None:
                log["events"].insert(0, {
                    "dataset": name,
                    "label_ca": cfg["ca"],
                    "label_es": cfg["es"],
                    "last_data": marker,
                    "detected_at": today,
                })
                nous += 1
    # Conservem només els 60 events més recents
    log["events"] = log["events"][:60]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(f"  Registre d'actualitzacions: {nous} novetat(s) detectada(es)")
    check_unwatched_caches()


def check_unwatched_caches():
    """Avisa de caches .csv que no es vigilen ni són a la llista d'exclusions.
    Evita que una font nova del pipeline es quedi fora del bloc Novetats sense
    que ningú se n'adoni. Només avisa (no atura el pipeline)."""
    if not os.path.isdir(CACHE_DIR):
        return []
    presents = {f[:-4] for f in os.listdir(CACHE_DIR) if f.endswith(".csv")}
    oblidats = sorted(presents - set(DATASETS_VIGILATS) - CACHES_NO_VIGILATS)
    if oblidats:
        print("  AVÍS: caches sense vigilar (ni a CACHES_NO_VIGILATS). "
              "Dona'ls d'alta a DATASETS_VIGILATS o exclou-los amb el motiu:")
        for c in oblidats:
            print(f"    - {c}")
    return oblidats


def process_estructura_comerc():
    """Trajectòria estructural del comerç (ES): el DOBLE PINÇAMENT.

    Quota del comerç físic de béns sobre el consum de les llars =
        quota de béns (↓, els serveis guanyen) × (1 − penetració online ↑).
    Dues forces lentes i PROJECTABLES (a diferència del soroll mensual):
      - quota de béns: Eurostat nama_10_fcs (fetch_estructura_consum).
      - penetració online: e-commerce CNAE47 / consum de béns (cache ecommerce).
    El COVID 2020-2022 distorsiona (serveis suprimits → béns inflats) i s'exclou
    de l'ajust. Projecció lineal + log-odds (banda) fins 2035.
    Escriu estructura_comerc.csv + estructura_comerc_meta.json.
    """
    import numpy as np
    COVID = {2020, 2021, 2022}
    HORIZON = list(range(2026, 2036))

    print("  Font: Eurostat nama_10_fcs (consum de les llars per durabilitat)")
    try:
        est = eurostat.fetch_estructura_consum()
    except Exception as e:
        est = pd.DataFrame()
        print(f"  Error Eurostat nama_10_fcs: {e}")
    if est.empty:
        est = load_cache("estructura_consum")
        if not est.empty:
            _record_status("estructura_comerc", "fallback", "cache", "Eurostat buit")
        else:
            _record_status("estructura_comerc", "error", "cap", "Eurostat nama_10_fcs buit")
            return pd.DataFrame()
    else:
        save_cache(est, "estructura_consum")
        _record_status("estructura_comerc", "ok", "api_eurostat", f"{len(est)} files")

    es = est[est["pais_codi"] == "ES"][["any", "bens_meur", "bens_share"]].copy()
    ec = load_cache("ecommerce")
    ec = ec[ec["any"] < 2025][["any", "ecommerce_cnae47_eur"]]  # 2025 incomplet
    m = es.merge(ec, on="any")
    m["online_pen"] = m["ecommerce_cnae47_eur"] / 1e6 / m["bens_meur"] * 100

    def fit(years, vals):
        A = np.column_stack([np.ones(len(years)), years])
        bl, *_ = np.linalg.lstsq(A, vals, rcond=None)
        p = np.clip(vals / 100, 1e-4, 1 - 1e-4)
        bz, *_ = np.linalg.lstsq(A, np.log(p / (1 - p)), rcond=None)
        lin = lambda y: float(bl[0] + bl[1] * y)
        logit = lambda y: float(100 / (1 + np.exp(-(bz[0] + bz[1] * y))))
        r2 = 1 - ((vals - A @ bl) ** 2).sum() / ((vals - vals.mean()) ** 2).sum()
        return lin, logit, float(bl[1]), float(r2)

    g_tr = es[~es["any"].isin(COVID)]
    o_tr = m[~m["any"].isin(COVID)]
    g_lin, g_log, g_sl, g_r2 = fit(g_tr["any"].values.astype(float),
                                   g_tr["bens_share"].values.astype(float))
    o_lin, o_log, o_sl, o_r2 = fit(o_tr["any"].values.astype(float),
                                   o_tr["online_pen"].values.astype(float))

    def fisic(y, mode):
        g = (g_lin if mode == "lin" else g_log)(y)
        o = (o_lin if mode == "lin" else o_log)(y)
        return g * (1 - o / 100)

    rows = []
    for _, r in m.iterrows():
        rows.append({"any": int(r["any"]), "tipus": "historic",
                     "bens_share": round(float(r["bens_share"]), 2),
                     "serveis_share": round(100 - float(r["bens_share"]), 2),
                     "online_pen": round(float(r["online_pen"]), 2),
                     "comerc_fisic_share": round(float(r["bens_share"]) * (1 - float(r["online_pen"]) / 100), 2),
                     "comerc_fisic_logodds": np.nan})
    for y in HORIZON:
        rows.append({"any": y, "tipus": "projeccio",
                     "bens_share": round(g_lin(y), 2),
                     "serveis_share": round(100 - g_lin(y), 2),
                     "online_pen": round(o_lin(y), 2),
                     "comerc_fisic_share": round(fisic(y, "lin"), 2),
                     "comerc_fisic_logodds": round(fisic(y, "log"), 2)})
    df = pd.DataFrame(rows)
    save_cache(df, "estructura_comerc")

    meta = {
        "bens_slope_pp_any": round(g_sl, 3), "bens_r2": round(g_r2, 3),
        "online_slope_pp_any": round(o_sl, 3), "online_r2": round(o_r2, 3),
        "ultim_any_real": int(m["any"].max()),
        "covid_exclos": sorted(COVID),
    }
    with open(os.path.join(CACHE_DIR, "estructura_comerc_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"  béns {g_sl:+.2f}pp/any (R²{g_r2:.2f}) · online {o_sl:+.2f}pp/any (R²{o_r2:.2f})")
    return df


def process_all():
    """Executa tot el processament."""
    print("Processant dades...")
    print("Jerarquia: API -> Cache CSV -> Excel local\n")

    print("1. PIB i VAB:")
    process_pib_vab()

    print("\n2. Empreses:")
    process_empreses()

    print("\n2b. Locals CNAE 47 per província (DIRCE T=301 + padró T=29005):")
    process_locals_provincia()

    print("\n2c. Locals per CCAA × grup 471-479 (DIRCE T=294):")
    process_locals_ccaa_grups()

    print("\n3. Productivitat:")
    process_productivitat()

    print("\n4. E-commerce:")
    process_ecommerce()

    print("\n5. Europa:")
    process_europa()

    print("\n5b. Europa retail mensual (Eurostat sts_trtu_m):")
    process_europa_retail_mensual()

    print("\n5b2. Europa retail mensual per branca (Eurostat sts_trtu_m):")
    process_europa_retail_branques()

    print("\n5c. Digitalització del comerç (Eurostat TIC: e-commerce/IA/núvol):")
    process_digitalitzacio_comerc()

    print("\n5d. Ocupació comerç per sexe/edat (Eurostat lfsa_egan22d):")
    process_ocupacio_comerc()

    print("\n5e. Líders del comerç (Registre Mercantil, raw manual):")
    process_lideres()

    print("\n6. EEE Comercio per CCAA:")
    process_eee_ccaa()

    print("\n7. Subsectors CNAE 47 (DIRCE + EAS + EPF):")
    process_subsectors()

    print("\n7b. Marges per branca (INE EEE Comercio, T=76818):")
    process_marges_branca()

    print("\n8. IPC mensual (per deflactor):")
    process_ipc()

    print("\n8b. IPC per grups ECOICOP (alimentació, vestit, llar):")
    process_ipc_coicop()

    print("\n8c. EPA retail — ocupats, aturats i hores:")
    process_epa_retail()

    print("\n8d. Confiança del consumidor (Eurostat ei_bsco_m):")
    process_confianza_consumidor()

    print("\n8e. Compres amb targeta en TPV (Banco de España):")
    process_targetes_tpv()

    print("\n9. CDMGE — comerc diari grans empreses:")
    process_cdmge()

    print("\n9b. ICM — Índices de Comercio al por Menor (INE):")
    process_icm()

    print("\n9c. ICM per modo de distribució (Grandes superficies, etc):")
    process_icm_distribucion()

    print("\n9d. EAES — Encuesta Anual de Estructura Salarial:")
    process_eaes()

    print("\n10. Estructura empresarial G47 (Eurostat bd_size):")
    process_estructura_retail()

    print("\n10b. Trajectòria estructural del comerç (béns→serveis × online):")
    process_estructura_comerc()

    print("\n11. Registrant data actualitzacio:")
    save_last_update()

    print("\n12. Detectant novetats per al bloc d'alertes de la home:")
    record_dataset_updates()

    print("\n13. Validant que les fonts critiques s'hagin actualitzat des de l'API:")
    _assert_critical_ok()

    print("\nProcessament complet!")


if __name__ == "__main__":
    process_all()
