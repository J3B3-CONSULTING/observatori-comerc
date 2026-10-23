"""
Client API per l'Instituto Nacional de Estadística (INE).
Documentació: https://www.ine.es/dyngs/DAB/en/index.htm?cid=1102
"""
import requests
import pandas as pd
import time
import os

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _fetch_table(table_id, nult=None, retries=8, det=None, tip=None, tv=None):
    """Descarrega una taula de l'INE amb reintentos per peticions en cua.
    Les taules pesades (p.ex. series diaries com la 37808) s'encuen al servidor:
    l'INE respon HTTP 202 amb {"status": "Petición en proceso..."} —o bé 200 amb
    un cos d'estat «en proceso»— mentre materialitza la taula. En aquests casos
    esperem i reintentem fins que retorna les dades.
    det=2 retorna NombrePeriodo, Fecha i metadades de Periodo (necessari per series diaries).
    tip="AM" afegeix MetaData (codis de territori i d'activitat) a cada sèrie.
    tv=["idVariable:idValor", ...] filtra al servidor; diversos valors d'una
    mateixa variable es combinen com a O. Redueix les taules del DIRCE de
    ~100-190 MB a pocs centenars de KB."""
    url = f"{BASE_URL}/DATOS_TABLA/{table_id}"
    params = []
    if nult:
        params.append(("nult", nult))
    if det:
        params.append(("det", det))
    if tip:
        params.append(("tip", tip))
    for f in tv or []:
        params.append(("tv", f))

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=120)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            time.sleep(15)
            continue

        if resp.status_code == 200:
            data = resp.json()
            # Petició encara en cua retornada amb 200 i cos d'estat
            estat = ""
            if isinstance(data, dict):
                estat = str(data.get("Status") or data.get("status") or "")
            if "proceso" in estat.lower():
                time.sleep(15)
                continue
            return data
        elif resp.status_code == 202:
            # Petició acceptada però encara en proceso (taula pesada en cua)
            time.sleep(15)
        elif resp.status_code == 429:
            time.sleep(30)
        elif 500 <= resp.status_code < 600:
            # Error de servidor (502, 503, etc) — reintentar
            time.sleep(15)
        else:
            # Error de client (404, 400, etc) — fallar
            resp.raise_for_status()

    print(f"    Fallida INE T={table_id} (timeout o error de servidor). Retornant dades buides.")
    return []


def _parse_ine_series(data):
    """Converteix la resposta JSON de l'INE a un DataFrame."""
    rows = []
    if not isinstance(data, list):
        return pd.DataFrame()

    for serie in data:
        nombre = serie.get("Nombre", "")
        for obs in serie.get("Data", []):
            rows.append({
                "serie": nombre,
                "any": obs.get("Anyo"),
                "periode": obs.get("FK_Periodo"),
                "valor": obs.get("Valor"),
            })

    return pd.DataFrame(rows)


def fetch_vab_ramas():
    """
    Taula 69070: VAB per branques d'activitat.
    Retorna Total CNAE i CNAE 47 en:
      - Preus corrents (Dato base, M EUR)
      - Index volum encadenat (per calcular preus constants)
    IMPORTANT: cal nult=30 per obtenir la serie completa (1995-2023).
    """
    data = _fetch_table(69070, nult=30)
    if not isinstance(data, list):
        return pd.DataFrame()

    results = []
    for serie in data:
        nombre = serie.get("Nombre", "")

        # ── VAB Preus corrents (Dato base, M EUR) ──
        if "Dato base" in nombre and "Precios corrientes" in nombre:
            if nombre.startswith("Total Nacional. Valor añadido bruto. Total CNAE"):
                indicador = "vab_total_corrents"
            elif "Comercio al por menor, excepto" in nombre and nombre.startswith("Total Nacional"):
                indicador = "vab_cnae47_corrents"
            else:
                continue

        # ── Index volum encadenat (per preus constants) ──
        elif "volumen encadenados" in nombre and "Índice." in nombre:
            if "Total CNAE" in nombre:
                indicador = "idx_volum_total"
            elif "Comercio al por menor, excepto" in nombre:
                indicador = "idx_volum_cnae47"
            else:
                continue
        else:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            if val is not None:
                results.append({
                    "indicador": indicador,
                    "any": obs.get("Anyo"),
                    "valor": val,
                })

    return pd.DataFrame(results)


def fetch_empreses(ccaa=None):
    """
    Empreses actives CNAE 47 per territori.
    Combina dues fonts per obtenir la sèrie més completa (fins 2025):

    1. Taula 3954 (Nacional): "Total Nacional. Comercio al por menor...Todas las edades. Empresas."
       Dóna la sèrie nacional amb dades fins a l'any actual.

    2. Taula 39372 (CCAA + Nacional, 3 dígits CNAE): "{CCAA}. Total. 47 Comercio al por menor..."
       Dóna Nacional + totes les CCAA amb dades fins a l'any actual.

    Fallback: Taula 298 (històrica, fins ~2020).
    """
    results = []

    # ── Font principal: Taula 39372 (CCAA + Nacional fins 2025) ──
    print("    Intentant taula 39372 (CCAA + Nacional)...")
    try:
        data_ccaa = _fetch_table(39372, nult=20)
        if isinstance(data_ccaa, list):
            for serie in data_ccaa:
                nombre = serie.get("Nombre", "")
                # Nacional: "Nacional. Total. Total. 47 Comercio al por menor..."
                if "Nacional. Total. Total. 47 Comercio al por menor" in nombre:
                    for obs in serie.get("Data", []):
                        results.append({"territori": "espanya", "any": obs.get("Anyo"), "empreses": obs.get("Valor")})
                # CCAA: "{CCAA}. Total. 47 Comercio al por menor..." (sense "Total. Total.")
                elif ". Total. 47 Comercio al por menor" in nombre and ". Total. Total." not in nombre and "Nacional" not in nombre:
                    terr = nombre.split(".")[0].strip()
                    for obs in serie.get("Data", []):
                        results.append({"territori": terr, "any": obs.get("Anyo"), "empreses": obs.get("Valor")})
            print(f"    Taula 39372: {len(results)} registres")
    except Exception as e:
        print(f"    Error taula 39372: {e}")

    # ── Complementar Nacional amb Taula 3954 (sèrie més llarga) ──
    print("    Intentant taula 3954 (Nacional històric)...")
    try:
        data_nac = _fetch_table(3954, nult=30)
        if isinstance(data_nac, list):
            # Anys que ja tenim de la taula 39372 per evitar duplicats
            anys_existents = {r["any"] for r in results if r["territori"] == "espanya"}
            count_new = 0
            for serie in data_nac:
                nombre = serie.get("Nombre", "")
                if "Comercio al por menor" in nombre and "Todas las edades" in nombre:
                    for obs in serie.get("Data", []):
                        any_ = obs.get("Anyo")
                        if any_ not in anys_existents:
                            results.append({"territori": "espanya", "any": any_, "empreses": obs.get("Valor")})
                            count_new += 1
                    break
            print(f"    Taula 3954: {count_new} anys addicionals")
    except Exception as e:
        print(f"    Error taula 3954: {e}")

    # ── Complement: Taula 298 (històrica, CCAA fins ~2020) ──
    print("    Complementant amb taula 298 (CCAA històric)...")
    try:
        data_old = _fetch_table(298, nult=20)
        if isinstance(data_old, list):
            anys_existents_all = {(r["territori"], r["any"]) for r in results}
            count_298 = 0
            for serie in data_old:
                nombre = serie.get("Nombre", "")
                if ". Total. Total. 47 Comercio" in nombre and nombre.startswith("Nacional"):
                    terr = "espanya"
                elif ". Total. 47 Comercio" in nombre and ". Total. Total." not in nombre and not nombre.startswith("Nacional"):
                    terr = nombre.split(".")[0].strip()
                else:
                    continue
                for obs in serie.get("Data", []):
                    key = (terr, obs.get("Anyo"))
                    if key not in anys_existents_all:
                        results.append({"territori": terr, "any": obs.get("Anyo"), "empreses": obs.get("Valor")})
                        count_298 += 1
            print(f"    Taula 298: {count_298} registres addicionals")
    except Exception as e:
        print(f"    Error taula 298: {e}")

    return pd.DataFrame(results)


def fetch_epa_retail():
    """
    EPA (Encuesta de Población Activa): ocupats, aturats i hores treballades
    al comerç, per sexe i trimestre. Combina tres taules de granularitat
    DIFERENT — cal llegir-ho abans d'interpretar les columnes:

      - T=65123 "Ocupados por sexo y rama de actividad": arriba a CNAE 47
        net ("Comercio al por menor, excepto de vehículos de motor y
        motocicletas") -> columna ocupats_cnae47_milers.
      - T=65249 "Parados por sexo y rama de actividad": l'INE NOMÉS
        desglossa els aturats fins a la secció G ("Comercio al por mayor y
        al por menor; reparación de vehículos de motor y motocicletas"),
        que inclou també l'engròs i la reparació de vehicles, no només
        CNAE 47. No hi ha cap taula EPA amb aturats a 2 dígits (47) —
        verificat contra el llistat complet de taules de l'operació EPA.
        -> columna aturats_seccio_g_milers.
      - T=65159 "Número medio de horas efectivas semanales trabajadas...":
        pel mateix motiu de mostra, tampoc arriba a CNAE 47 net, només a
        secció G. -> columna hores_setmana_seccio_g.

    Per això només ocupats_cnae47_milers és CNAE 47 pur; les altres dues
    inclouen comerç a l'engròs i reparació de vehicles a més del detall.
    Sèrie disponible des de 2008 T1 (nult=80 per cobrir-la sencera).

    Retorna columnes: any, trimestre (1-4), periode (YYYY-TQ), sexe
    (total/homes/dones), ocupats_cnae47_milers, aturats_seccio_g_milers,
    hores_setmana_seccio_g.
    """
    SEXES = {"Ambos sexos": "total", "Hombres": "homes", "Mujeres": "dones"}
    CNAE47 = "Comercio al por menor, excepto de vehículos de motor y motocicletas"
    SECCIO_G = "Comercio al por mayor y al por menor; reparación de vehículos de motor y motocicletas"

    def _quarter(obs):
        per = obs.get("FK_Periodo")
        any_ = obs.get("Anyo")
        val = obs.get("Valor")
        if per is None or any_ is None or val is None:
            return None
        trimestre = int(per) - 18  # FK_Periodo 19-22 = T1-T4
        if trimestre < 1 or trimestre > 4:
            return None
        return int(any_), trimestre, float(val)

    results = {}

    def _merge(table_id, branch_text, col_name, extra_filter=None):
        data = _fetch_table(table_id, nult=80)
        if not isinstance(data, list):
            return
        for serie in data:
            nombre = serie.get("Nombre", "")
            if branch_text not in nombre:
                continue
            if "Valor absoluto" not in nombre and "Número medio" not in nombre:
                continue
            if extra_filter and not extra_filter(nombre):
                continue
            sexe = next((v for k, v in SEXES.items() if k in nombre), None)
            if sexe is None:
                continue
            for obs in serie.get("Data", []):
                parsed = _quarter(obs)
                if parsed is None:
                    continue
                any_, trimestre, val = parsed
                key = (any_, trimestre, sexe)
                if key not in results:
                    results[key] = {"any": any_, "trimestre": trimestre, "sexe": sexe}
                results[key][col_name] = val

    _merge(65123, CNAE47, "ocupats_cnae47_milers")
    _merge(65249, SECCIO_G, "aturats_seccio_g_milers")
    # 65159 inclou situació professional (Total/Trabajador por cuenta propia/...);
    # ". Total. " nomes apareix quan aquesta dimensio es "Total" (evita comptar
    # només assalariats o autonoms).
    _merge(65159, SECCIO_G, "hores_setmana_seccio_g", extra_filter=lambda n: ". Total. " in n)

    df = pd.DataFrame(list(results.values()))
    if df.empty:
        return df
    df["periode"] = df["any"].astype(str) + "-T" + df["trimestre"].astype(str)
    return df.sort_values(["any", "trimestre", "sexe"]).reset_index(drop=True)


def fetch_ipc_coicop():
    """
    Taula 76125: IPC nacional per grups ECOICOP ver.2, base 2021=100, mensual.
    Selecciona l'índex general (referència) + els 3 grups més rellevants pel
    comerç al detall: alimentació, vestit i calçat, parament de la llar.
    Sèrie disponible des de gener de 2002 (límit de la reconstrucció ver.2;
    nult=310 per cobrir-la sencera).

    Retorna columnes: any, mes, periode (YYYY-MM), grup_codi (00/01/03/05),
    grup, ipc.
    """
    GRUPS = {
        "Índice general": ("00", "Índex general"),
        "Alimentos y bebidas no alcohólicas": ("01", "Alimentació i begudes no alcohòliques"),
        "Vestido y calzado": ("03", "Vestit i calçat"),
        "Muebles, artículos del hogar y artículos para el mantenimiento corriente del hogar":
            ("05", "Parament de la llar"),
    }
    data = _fetch_table(76125, nult=310)
    if not isinstance(data, list):
        return pd.DataFrame()

    results = []
    for serie in data:
        nombre = serie.get("Nombre", "")
        parts = [p.strip() for p in nombre.rstrip(".").split(". ") if p.strip()]
        if len(parts) != 3 or parts[0] != "Nacional" or parts[2] != "Índice":
            continue
        grup_info = GRUPS.get(parts[1])
        if grup_info is None:
            continue
        codi, label = grup_info
        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            mes = obs.get("FK_Periodo")
            if val is None or any_ is None or mes is None:
                continue
            results.append({
                "any": int(any_), "mes": int(mes),
                "grup_codi": codi, "grup": label, "ipc": float(val),
            })

    df = pd.DataFrame(results)
    if not df.empty:
        df["periode"] = df["any"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
        df = df.sort_values(["grup_codi", "any", "mes"]).reset_index(drop=True)
    return df


def fetch_ipc():
    """
    Taula 50902: IPC general, mensual. Base 2021 = 100.
    Retorna index IPC mensual per calcular deflactor.
    IMPORTANT: nult=400 per obtenir serie completa (1995-2025, ~360 mesos).
    Filtra nomes la serie "Total Nacional. Indice general. Indice."
    """
    data = _fetch_table(50902, nult=400)

    results = []
    if not isinstance(data, list):
        return pd.DataFrame()

    for serie in data:
        nombre = serie.get("Nombre", "")
        if "ndice general" not in nombre or "ndice." not in nombre.split("general")[-1]:
            continue
        if "Variaci" in nombre:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            if val is not None:
                results.append({
                    "any": obs.get("Anyo"),
                    "mes": obs.get("FK_Periodo"),
                    "ipc": val,
                })
        break  # Nomes una serie

    return pd.DataFrame(results)


def fetch_eee_comercio():
    """
    Taula 36194: Estadistica Estructural d'Empreses - Sector Comercio.
    Principals magnituds CNAE 47 (Comercio al por menor).
    Retorna: xifra negoci, valor afegit, personal ocupat, hores treballades.
    Unitats: milers EUR (xifra/va), persones, milers hores.
    """
    data = _fetch_table(36194, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    # Mapeig de noms de serie a columnes
    MAGNITUDS = {
        "Cifra de negocios": "xifra_negoci",
        "Valor añadido a coste de los factores": "valor_afegit",
        "Personal ocupado": "personal_ocupat",
        "Horas trabajadas por el personal remunerado": "hores_treballades",
        "Gastos de personal": "gastos_personal",
    }

    results = {}
    for serie in data:
        nombre = serie.get("Nombre", "")
        if "Comercio al por menor, excepto" not in nombre:
            continue

        # Identificar magnitud
        col_name = None
        for key, col in MAGNITUDS.items():
            if key in nombre:
                col_name = col
                break
        if not col_name:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is not None and any_ is not None:
                if any_ not in results:
                    results[any_] = {"any": any_}
                results[any_][col_name] = val

    df = pd.DataFrame(list(results.values()))
    if not df.empty:
        df = df.sort_values("any").reset_index(drop=True)
        # Convertir unitats: milers EUR -> EUR per xifra, va i gastos
        for col in ["xifra_negoci", "valor_afegit", "gastos_personal"]:
            if col in df.columns:
                df[col] = df[col] * 1000  # milers EUR -> EUR
        # Hores: milers hores -> hores
        if "hores_treballades" in df.columns:
            df["hores_treballades"] = df["hores_treballades"] * 1000

    return df


def fetch_empreses_municipal():
    """
    Taula 4721: Empresas por municipio y actividad principal.
    NOMES te granularitat de seccio CNAE (G-I conjunta), no de divisio (47).
    Extreu per cada municipi: nombre Total d'empreses i empreses sector G-I
    (Comerc al por mayor i menor + reparacio vehicles + transport + hostaleria).
    Retorna: municipi, any, total_empreses, empreses_g_i.
    """
    data = _fetch_table(4721, nult=1)
    if not isinstance(data, list):
        return pd.DataFrame()

    SECTOR_GI = "Comercio al por mayor y al por menor; reparación de vehículos de motor y motocicletas; transporte y almacenamiento; hostelería"
    SUFFIX = ". Empresas. "

    # INE retorna 2 formats al camp Nombre:
    #   A: "{municipi}. Total. Total de empresas. {sector}. Empresas. "
    #   B: "{municipi}. {sector}. Total. Total de empresas. Empresas. "
    # El parser ha de tractar tots dos per no perdre municipis (Vic, Masnou, etc.).
    SECTORS = {"Total CNAE": "total_empreses", SECTOR_GI: "empreses_g_i"}
    sufixos = []
    for sector, col in SECTORS.items():
        sufixos.append((f". Total. Total de empresas. {sector}", col))  # format A
        sufixos.append((f". {sector}. Total. Total de empresas", col))  # format B

    mun_data = {}
    for s in data:
        nom = s.get("Nombre", "")
        if not nom.endswith(SUFFIX):
            continue
        rest = nom[:-len(SUFFIX)]

        municipi = None
        col = None
        for suf, c in sufixos:
            if rest.endswith(suf):
                municipi = rest[:-len(suf)].strip()
                col = c
                break
        if not municipi or municipi.startswith("Total Nacional"):
            continue

        obs = s.get("Data", [])
        if not obs:
            continue
        val = obs[0].get("Valor")
        any_ = obs[0].get("Anyo")
        if val is None:
            continue

        # Si ja existeix l'entrada (homonim), conservem la del municipi mes gran
        # (resolucio simple per duplicats com Sada Navarra vs Sada A Coruna).
        # Tambe cobreix el cas en que un mateix municipi vingui en format A i B.
        if municipi not in mun_data:
            mun_data[municipi] = {"municipi": municipi, "any": int(any_)}
        existing = mun_data[municipi].get(col)
        new_val = int(val)
        if existing is None or new_val > existing:
            mun_data[municipi][col] = new_val

    df = pd.DataFrame(list(mun_data.values()))
    return df


def fetch_renda_municipal():
    """
    Taula 30896: Atlas Distribucio Renda - Indicadors renda mitjana i mediana
    per municipi. Extreu nomes la renda neta media per llar (mes informativa
    per estimar capacitat de consum agregada).
    Retorna: municipi, any, renda_llar.
    """
    data = _fetch_table(30896, nult=1)
    if not isinstance(data, list):
        return pd.DataFrame()

    rows = []
    for s in data:
        nom = s.get("Nombre", "")
        # Format: "{municipi}. Dato base. Renta neta media por hogar. "
        if "Dato base. Renta neta media por hogar" not in nom:
            continue
        municipi = nom.split(".")[0].strip()
        if not municipi:
            continue
        obs = s.get("Data", [])
        if not obs:
            continue
        val = obs[0].get("Valor")
        any_ = obs[0].get("Anyo")
        if val is None:
            continue
        rows.append({
            "municipi": municipi,
            "any_renda": int(any_),
            "renda_llar": float(val),
        })

    return pd.DataFrame(rows)


def fetch_poblacio_municipal():
    """
    Taula 33167: Cifras oficiales del Padron per municipi (any nacional).
    Versio simplificada: extreu poblacio total per municipi de la T=33167.
    Si no funciona, recurrir a T=29005.
    Retorna: municipi, any, poblacio.
    """
    # Provem T=33167 primer
    for tid in [33167, 29005, 2855]:
        try:
            data = _fetch_table(tid, nult=1)
            if not isinstance(data, list) or not data:
                continue

            rows = []
            for s in data:
                nom = s.get("Nombre", "")
                # Buscar series amb "Total habitantes" o "Total. Total."
                if "Total habitantes" not in nom and "Personas. Total" not in nom:
                    continue
                # Filtrar nomes municipis (evitar provincies, ccaa, nacional)
                if "Total Nacional" in nom or " provincia" in nom.lower():
                    continue

                municipi = nom.split(".")[0].strip()
                if not municipi or municipi == "Total":
                    continue

                obs = s.get("Data", [])
                if not obs:
                    continue
                val = obs[0].get("Valor")
                any_ = obs[0].get("Anyo")
                if val is None:
                    continue
                rows.append({
                    "municipi": municipi,
                    "any_pob": int(any_),
                    "poblacio": int(val),
                })

            if rows:
                return pd.DataFrame(rows).drop_duplicates(subset="municipi")
        except Exception:
            continue

    return pd.DataFrame()


def fetch_eee_pyl():
    """
    Taula 36199: EEE Sector Comercio - Cuenta de resultados (P&L).
    Magnituds addicionals al T=36194 que permeten calcular el marge brut comptable:
      - cogs: Consumo de bienes y servicios para reventa (= cost de mercaderia venuda)
      - serveis_exteriors: Gastos en servicios exteriores (lloguers, energia, serveis externs)
      - sueldos_salaris: Sueldos y salarios (sense cotitzacions)
    Filtra nomes la serie agregada del CNAE 47 (Total Nacional).
    Unitats originals: milers EUR.
    """
    data = _fetch_table(36199, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    MAGNITUDS = {
        "Consumo de bienes y servicios para reventa": "cogs",
        "Gastos en servicios exteriores": "serveis_exteriors",
        "Sueldos y salarios": "sueldos_salaris",
        "Cifra de negocios": "xifra_negoci_pyl",
    }

    results = {}
    for serie in data:
        nombre = serie.get("Nombre", "")
        if "Total Nacional" not in nombre:
            continue
        if "Comercio al por menor, excepto" not in nombre:
            continue

        col = None
        for key, c in MAGNITUDS.items():
            if f". {key}." in nombre:
                col = c
                break
        if not col:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is None or any_ is None:
                continue
            if any_ not in results:
                results[any_] = {"any": int(any_)}
            results[any_][col] = val

    df = pd.DataFrame(list(results.values()))
    if df.empty:
        return df

    # Convertir milers EUR -> EUR
    for col in ["cogs", "serveis_exteriors", "sueldos_salaris", "xifra_negoci_pyl"]:
        if col in df.columns:
            df[col] = df[col] * 1000

    return df.sort_values("any").reset_index(drop=True)


def fetch_poblacio():
    """
    Població per CCAA i Nacional.
    Combina dues fonts:
      - Taula 2915 (Padrón): Nacional + CCAA (1996-2021)
      - Taula 56934 (Cifras de Población): Nacional (2022-2025)
    Per CCAA 2022-2025 s'estima amb la proporció del 2021 aplicada
    sobre el total nacional dels anys recents (error < 0.5%).
    """
    results = []

    # ── Taula 2915: Padrón (CCAA + Nacional fins 2021) ──
    data = _fetch_table(2915, nult=30)
    if isinstance(data, list):
        for serie in data:
            nombre = serie.get("Nombre", "")
            if "Total Nacional. Total municipios. Personas. Total" in nombre:
                terr = "espanya"
            elif "Personas. Total. Total municipios." in nombre:
                terr = nombre.split("Total municipios.")[-1].strip().rstrip(".")
            else:
                continue
            for obs in serie.get("Data", []):
                results.append({"territori": terr, "any": obs.get("Anyo"), "poblacio": obs.get("Valor")})

    # ── Taula 56934: Cifras de Población Nacional (2022-2025) ──
    anys_nac = {r["any"] for r in results if r["territori"] == "espanya"}
    try:
        data2 = _fetch_table(56934, nult=20)
        if isinstance(data2, list):
            for serie in data2:
                nombre = serie.get("Nombre", "")
                if "Total Nacional. Todas las edades. Total. Población. Número" in nombre:
                    by_year = {}
                    for o in serie.get("Data", []):
                        y = o.get("Anyo")
                        p = o.get("FK_Periodo", 0)
                        if y and (y not in by_year or p > by_year[y][1]):
                            by_year[y] = (o.get("Valor"), p)
                    for y, (v, _) in by_year.items():
                        if y not in anys_nac:
                            results.append({"territori": "espanya", "any": y, "poblacio": v})
                    break
    except Exception:
        pass

    df = pd.DataFrame(results)
    if df.empty:
        return df

    # ── Estimar CCAA per anys recents amb proporció 2021 ──
    ccaa_names = [t for t in df["territori"].unique() if t != "espanya"]
    last_padron_year = df[df["territori"].isin(ccaa_names)]["any"].max()
    esp_series = df[df["territori"] == "espanya"].set_index("any")["poblacio"]
    anys_nous = [y for y in esp_series.index if y > last_padron_year]

    if anys_nous and last_padron_year in esp_series.index:
        total_ref = esp_series[last_padron_year]
        for ccaa in ccaa_names:
            pob_ref = df[(df["territori"] == ccaa) & (df["any"] == last_padron_year)]["poblacio"].values
            if len(pob_ref) > 0:
                prop = pob_ref[0] / total_ref
                for y in anys_nous:
                    results.append({"territori": ccaa, "any": y, "poblacio": round(esp_series[y] * prop)})

    return pd.DataFrame(results)


def fetch_eee_comercio_ccaa():
    """
    Taula 76817: EEE Sector Comercio — magnituds regionalitzades.
    CNAE 47 per CCAA (2018-2024).
    Retorna: xifra_negoci, personal_ocupat, sous_salaris, inversio, locals
    per cada CCAA i Total Nacional.
    Unitats: milers EUR (xifra/sous/inversio), persones, unitats.
    """
    data = _fetch_table(76817, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    MAGNITUDS = {
        "Cifra de negocios": "xifra_negoci",
        "Sueldos y salarios": "sous_salaris",
        "Personal ocupado": "personal_ocupat",
        "Inversión en activos materiales": "inversio",
        "Número de locales": "locals",
    }

    TERR_NORM = {
        "Asturias, Principado de": "Asturias (Principado de)",
        "Balears, Illes": "Balears (Illes)",
        "Madrid, Comunidad de": "Madrid (Comunidad de)",
        "Murcia, Región de": "Murcia (Región de)",
        "Navarra, Comunidad Foral de": "Navarra (Comunidad Foral de)",
        "Rioja, La": "Rioja (La)",
        "Total Nacional": "espanya",
    }

    results = {}
    for serie in data:
        nombre = serie.get("Nombre", "")
        if "Comercio al por menor, excepto" not in nombre:
            continue

        terr_raw = nombre.split(".")[0].strip()
        if terr_raw in ("Ceuta", "Melilla"):
            continue
        terr = TERR_NORM.get(terr_raw, terr_raw)

        col_name = None
        for key, col in MAGNITUDS.items():
            if key in nombre:
                col_name = col
                break
        if not col_name:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is not None and any_ is not None:
                key = (terr, any_)
                if key not in results:
                    results[key] = {"territori": terr, "any": any_}
                results[key][col_name] = val

    df = pd.DataFrame(list(results.values()))
    if not df.empty:
        df = df.sort_values(["territori", "any"]).reset_index(drop=True)
        for col in ["xifra_negoci", "sous_salaris", "inversio"]:
            if col in df.columns:
                df[col] = df[col] * 1000

    return df


# ─── SUBSECTORS CNAE 47 (DIRCE + EAS) i COICOP (EPF) ───────────

CNAE_47_SUBSECTORS = {
    "471": "Establecimientos no especializados",
    "472": "Alimentación, bebidas y tabaco",
    "473": "Combustibles",
    "474": "Equipos TIC",
    "475": "Articles d'us domestic",
    "476": "Cultura i recreatius",
    "477": "Vestit, calcat i altres",
    "478": "Mercadillos",
    "479": "Venda no establerta (online)",
}

# Noms exactes a l'API INE - per fer matching contra les series d'EAS (T=76818)
CNAE_47_API_NAMES = {
    "471": "Comercio al por menor en establecimientos no especializados",
    "472": "Comercio al por menor de productos alimenticios, bebidas y tabaco en establecimientos especializados",
    "473": "Comercio al por menor de combustible para la automoción en establecimientos especializados",
    "474": "Comercio al por menor de equipos para las tecnologías de la información y las comunicaciones en establecimientos especializados",
    "475": "Comercio al por menor de otros artículos de uso doméstico en establecimientos especializados",
    "476": "Comercio al por menor de artículos culturales y recreativos en establecimientos especializados",
    "477": "Comercio al por menor de otros artículos en establecimientos especializados",
    "478": "Comercio al por menor en puestos de venta y en mercadillos",
    "479": "Comercio al por menor no realizado ni en establecimientos, ni en puestos de venta ni en mercadillos",
    "47":  "Comercio al por menor, excepto de vehículos de motor y motocicletas",
}

# CNAE 47 a 4 dígits — fills del grup d'alimentació (472). Noms exactes API INE (T=76818),
# per poder desglossar l'evolució de peixateries, carnisseries, fruiteries, forns, etc.
CNAE_472_API_NAMES = {
    "4721": "Comercio al por menor de frutas y hortalizas en establecimientos especializados",
    "4722": "Comercio al por menor de carne y productos cárnicos en establecimientos especializados",
    "4723": "Comercio al por menor de pescados y mariscos en establecimientos especializados",
    "4724": "Comercio al por menor de pan y productos de panadería, confitería y pastelería en establecimientos especializados",
    "4725": "Comercio al por menor de bebidas en establecimientos especializados",
    "4726": "Comercio al por menor de productos de tabaco en establecimientos especializados",
    "4729": "Otro comercio al por menor de productos alimenticios en establecimientos especializados",
}

# Etiqueta per a la columna 'nom' de la cache (la pàgina té les seves pròpies ca/es).
CNAE_472_SUBSECTORS = {
    "4721": "Fruiteries", "4722": "Carnisseries", "4723": "Peixateries",
    "4724": "Forns i pastisseries", "4725": "Begudes",
    "4726": "Estancs (tabac)", "4729": "Altres aliments",
}

# Etiquetes legibles (català) per a les branques del fitxer de marges per branca.
# Mapeig conceptual amb les branques que PATECO anomena N470-N479.
CNAE_47_MARGES_LABELS = {
    "471": "Establiments no especialitzats (súper i hiper)",
    "472": "Aliments, begudes i tabac (especialitzat)",
    "473": "Combustible (gasolineres)",
    "474": "Equips TIC",
    "475": "Equipament de la llar",
    "476": "Articles culturals i recreatius",
    "477": "Altres articles (moda, calçat, etc.)",
    "478": "Punts de venda i mercadillos",
    "479": "Comerç no en establiment (internet)",
    "47":  "Comerç al detall (total CNAE 47)",
}

COICOP_GROUPS = {
    "01": "Alimentos y bebidas no alcohólicas",
    "02": "Bebidas alcohólicas, tabaco y estupefacientes",
    "03": "Vestido y calzado",
    "04": "Vivienda, agua, electricidad, gas y otros combustibles",
    "05": "Muebles, artículos del hogar y artículos para el mantenimiento corriente del hogar",
    "06": "Sanidad",
    "07": "Transporte",
    "08": "Información y comunicaciones",
    "09": "Actividades recreativas, deporte y cultura",
    "10": "Servicios de educación",
    "11": "Restaurantes y servicios de alojamiento",
    "12": "Cuidado personal, protección social, y bienes y servicios diversos",
}


def fetch_dirce_subsectors():
    """
    Taula 73019: Empreses per condicio juridica, grups CNAE 2009 (3 digits) i estrato.
    Filtra series 'Nacional. Total. Total. 47X' per obtenir total empreses per
    cada subsector CNAE 47 (3 digits). Inclou tambe CNAE 47 total.
    Retorna: codi (471-479, 47), any, empreses.
    """
    data = _fetch_table(73019, nult=15)
    if not isinstance(data, list):
        return pd.DataFrame()

    results = []
    for serie in data:
        nombre = serie.get("Nombre", "")
        # Format: "Nacional. Total. Total. 47X Comercio..."
        if not nombre.startswith("Nacional. Total. Total."):
            continue
        rest = nombre.replace("Nacional. Total. Total.", "").strip()
        # Extreure codi CNAE (primer token numeric)
        tokens = rest.split(" ", 1)
        if not tokens or not tokens[0].rstrip(".").isdigit():
            continue
        codi = tokens[0].rstrip(".")
        # Nomes 47 i 47X (3 digits)
        if codi != "47" and not (len(codi) == 3 and codi.startswith("47")):
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is not None and any_ is not None:
                results.append({"codi": codi, "any": int(any_), "empreses": int(val)})

    return pd.DataFrame(results)


def fetch_eas_subsectors():
    """
    Taula 76818: EEE Comercio - Magnituds CNAE 47 a 3-4 digits (Total Nacional).
    Extreu les magnituds principals per cada subsector CNAE 47 (3 digits) i
    el total CNAE 47 mitjancant matching exacte per nom.
    Retorna columnes: codi, any, xifra_negoci, valor_afegit, personal_ocupat,
    inversio (en EUR i persones).
    Unitats originals INE: milers EUR (xifra/VA/inversio), persones.
    """
    data = _fetch_table(76818, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    MAGNITUDS = {
        "Cifra de negocios": "xifra_negoci",
        "Valor añadido a coste de los factores": "valor_afegit",
        "Personal ocupado": "personal_ocupat",
        "Inversión en activos materiales": "inversio",
        "Número de empresas": "n_empreses_eas",
    }
    # Inclou els 4 dígits del grup 472 perquè el desglossament d'alimentació tingui dades.
    NAME_TO_CODI = {v: k for k, v in {**CNAE_47_API_NAMES, **CNAE_472_API_NAMES}.items()}

    results = {}
    for serie in data:
        nombre = serie.get("Nombre", "")
        if not nombre.startswith("Total Nacional."):
            continue

        # Identificar magnitud
        magnitud = None
        for key, col in MAGNITUDS.items():
            if f". {key}." in nombre:
                magnitud = col
                break
        if not magnitud:
            continue

        # Identificar CNAE per matching exacte de nom (entre magnitud i "Dato base")
        # Format: "Total Nacional. {magnitud}. {NOM_CNAE}. Dato base."
        try:
            after_mag = nombre.split(f". {[k for k, v in MAGNITUDS.items() if v == magnitud][0]}.", 1)[1]
            nom_cnae = after_mag.rsplit(". Dato base", 1)[0].strip()
        except (IndexError, KeyError):
            continue

        codi = NAME_TO_CODI.get(nom_cnae)
        if codi is None:
            continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is None or any_ is None:
                continue
            key = (codi, int(any_))
            if key not in results:
                results[key] = {"codi": codi, "any": int(any_)}
            results[key][magnitud] = val

    df = pd.DataFrame(list(results.values()))
    if df.empty:
        return df

    # Convertir milers EUR -> EUR
    for col in ["xifra_negoci", "valor_afegit", "inversio"]:
        if col in df.columns:
            df[col] = df[col] * 1000

    return df.sort_values(["codi", "any"]).reset_index(drop=True)


def fetch_marges_branca(incloure_total=False):
    """
    Marge brut d'explotació sobre vendes per branca del comerç minorista.
    Font: EEE Comercio / Encuesta Anual de Comercio (INE, taula 76818),
    Total Nacional, CNAE 47 a 3 dígits. Sèrie anual des de 2018.

    marge_vendes_pct = Excedente bruto de explotación / Cifra de negocios * 100

    És el "gross operating rate" estàndard de les estadístiques estructurals
    d'empreses (EBE/xifra de negoci): quant de cada euro venut queda com a
    excedent d'explotació abans d'amortitzacions i resultat financer.

    Retorna columnes: any, cnae, branca, marge_vendes_pct.
    Nota: la branca 478 (mercadillos) es descarta. L'INE la publica, però té
    menys d'una persona ocupada per empresa: l'EBE hi inclou la remuneració del
    titular i el marge (22% el 2024) no és comparable amb la resta de branques.
    """
    data = _fetch_table(76818, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    NAME2CODI = {v: k for k, v in CNAE_47_API_NAMES.items()}
    MAGS = {"Excedente bruto de explotación": "ebe", "Cifra de negocios": "cn"}

    vals = {}  # (codi, any) -> {ebe, cn}
    for serie in data:
        nombre = serie.get("Nombre", "")
        if not nombre.startswith("Total Nacional."):
            continue
        magnitud = next((m for m in MAGS if f". {m}." in nombre), None)
        if magnitud is None:
            continue
        try:
            after = nombre.split(f". {magnitud}.", 1)[1]
            nom_cnae = after.rsplit(". Dato base", 1)[0].strip()
        except IndexError:
            continue
        codi = NAME2CODI.get(nom_cnae)
        if codi is None or codi == "478":
            continue
        for obs in serie.get("Data", []):
            v = obs.get("Valor")
            a = obs.get("Anyo")
            if v is None or a is None:
                continue
            vals.setdefault((codi, int(a)), {})[MAGS[magnitud]] = v

    rows = []
    for (codi, any_), d in vals.items():
        if not incloure_total and codi == "47":
            continue
        if "ebe" in d and "cn" in d and d["cn"]:
            rows.append({
                "any": any_,
                "cnae": codi,
                "branca": CNAE_47_MARGES_LABELS.get(codi, codi),
                "marge_vendes_pct": round(d["ebe"] / d["cn"] * 100, 1),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["cnae", "any"]).reset_index(drop=True)


def fetch_epf_coicop():
    """
    Taula 75003: EPF - Despesa per grups COICOP 2 digits. Preus constants.
    Filtra "Dato base. Gasto total. Gasto medio por hogar. Precios constantes."
    Retorna: codi_coicop (01-12), any, despesa_per_llar (EUR/llar/any).
    """
    data = _fetch_table(75003, nult=10)
    if not isinstance(data, list):
        return pd.DataFrame()

    NAME_TO_COICOP = {v: k for k, v in COICOP_GROUPS.items()}

    results = []
    for serie in data:
        nombre = serie.get("Nombre", "")
        # Format: "{NOM_GRUP}. Dato base. Gasto total. Gasto medio por hogar. Precios constantes."
        if "Dato base. Gasto total. Gasto medio por hogar. Precios constantes" not in nombre:
            continue
        nom_grup = nombre.split(". Dato base.", 1)[0].strip()
        if nom_grup == "Índice general":
            codi = "00"
        else:
            codi = NAME_TO_COICOP.get(nom_grup)
            if codi is None:
                continue

        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is not None and any_ is not None:
                results.append({"codi_coicop": codi, "any": int(any_), "despesa_per_llar": float(val)})

    return pd.DataFrame(results).sort_values(["codi_coicop", "any"]).reset_index(drop=True)


def fetch_cdmge():
    """
    Taula 37808: CDMGE — Medicion del comercio diario al por menor de grandes empresas.
    Estadistica experimental DIARIA de l'INE. Cobreix CNAE 47 grans empreses (mostra
    de retailers grans amb cobertura nacional). Sèrie 2019-actualitat.

    Retorna 5 indicadors per dia:
      - tasa_anual: tasa anual de vendes diaries acumulades (% vs mateix periode any anterior)
      - tasa_mensual: tasa mensual de vendes diaries acumulades
      - pct_sobre_mes: % diari ventas acumulades sobre total del mateix mes
      - pct_vs_anterior_anual: % vs total mateix mes any anterior
      - pct_vs_anterior_mensual: % vs total mes anterior

    Columnes: data (date), indicador (str), valor (float).
    """
    data = _fetch_table(37808, nult=3000, det=2)
    if not isinstance(data, list):
        return pd.DataFrame()

    INDICADOR_MAP = {
        "Tasa anual de las ventas diarias acumuladas": "tasa_anual",
        "Tasa mensual de las ventas diarias acumuladas": "tasa_mensual",
        "Porcentaje diario de ventas acumuladas sobre ventas totales del mismo mes": "pct_sobre_mes",
        "Porcentaje diario de ventas acumuladas al día i, sobre las ventas totales del mismo mes del año anterior": "pct_vs_anterior_anual",
        "Porcentaje diario de ventas acumuladas al día i, sobre las ventas totales del mes anterior": "pct_vs_anterior_mensual",
    }

    rows = []
    for serie in data:
        indicador = INDICADOR_MAP.get(serie.get("Nombre", ""))
        if not indicador:
            continue
        for obs in serie.get("Data", []):
            val = obs.get("Valor")
            if val is None:
                continue
            per = obs.get("Periodo") or {}
            any_ = obs.get("Anyo")
            dia = per.get("Dia_inicio")
            mes = per.get("Mes_inicio")
            if not (any_ and dia and mes):
                continue
            try:
                data_str = f"{int(any_):04d}-{int(mes):02d}-{int(dia):02d}"
            except (ValueError, TypeError):
                continue
            rows.append({
                "data": data_str,
                "indicador": indicador,
                "valor": float(val),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"]).sort_values(["indicador", "data"]).reset_index(drop=True)
    return df


def fetch_icm():
    """
    ICM — Índices de Comercio al por Menor (INE, base 2021=100).
    Sèrie mensual oficial del comerç al detall espanyol.

    Combina 6 taules wstempus:
      - 60096: cifra negoci preus constants — Total Nacional × branca CNAE
      - 59787: cifra negoci preus corrents — Total Nacional × especials agregats
      - 60110: cifra negoci preus corrents — per CCAA × branca general
      - 60111: cifra negoci preus constants — per CCAA × branca general
      - 60114: ocupació mensual — Total Nacional × general
      - 60115: ocupació mensual — Total Nacional × especials agregats

    Retorna DataFrame amb columnes:
      - serie_id (nom complet INE)
      - ambit ("nacional" o nom CCAA)
      - tipus ("real" / "nominal" / "ocupacio")
      - branca (text descriptiu de la branca CNAE 47)
      - indicador ("index" / "var_mensual" / "var_anual" / "var_mitjana_acum")
      - any (int)
      - mes (int 1-12)
      - data (pd.Timestamp, primer dia del mes)
      - valor (float)

    Documentació: https://www.ine.es/dyngs/INEbase/es/operacion.htm?
                  c=Estadistica_C&cid=1254736176900
    """
    # 60103: real × agrupacions (alimentació, equipament...), parella de la 59787
    # nominal; sense ella no es pot calcular el preu implícit de cada agrupació.
    ICM_TABLES = [60096, 59787, 60103, 60110, 60111, 60114, 60115]

    # La 60115 porta, a més del total, l'ocupació per mode de distribució amb la
    # mateixa branca. Aquí sobren (són a fetch_icm_distribucion): si es quedessin,
    # hi hauria cinc valors per mes sota una sola branca.
    MODES = {"Empresas unilocalizadas", "Pequeñas cadenas", "Grandes cadenas",
             "Grandes Superficies"}

    INDICADOR_MAP = {
        "Índice": "index",
        "Variación mensual": "var_mensual",
        "Variación anual": "var_anual",
        "Variación de la media en lo que va de año": "var_mitjana_acum",
    }

    def _classifica_tipus(nom):
        n = nom.lower()
        if "ocupación" in n or "ocupacion" in n:
            return "ocupacio"
        if "precios constantes" in n:
            return "real"
        if "precios corrientes" in n:
            return "nominal"
        return "altre"

    def _extreu_indicador(parts):
        # L'indicador és sempre l'últim segment net abans del punt final
        for p in reversed(parts):
            p_clean = p.strip()
            if p_clean in INDICADOR_MAP:
                return INDICADOR_MAP[p_clean]
        return None

    def _extreu_ambit(parts):
        first = parts[0].strip()
        if first.startswith("Total Nacional"):
            return "nacional"
        return first  # nom CCAA literal

    def _extreu_branca(parts):
        # La branca és el segment que conté 'Comercio' o un agrupat de codis
        # CNAE entre parèntesi. Si no en trobem, fallback al penúltim segment.
        for p in parts[2:-1]:  # Saltem ambit i tipus, deixem fora indicador final
            p_clean = p.strip()
            if (p_clean.startswith("Comercio") or
                    "Alimentación" in p_clean or "Equipo" in p_clean or
                    "Resto" in p_clean or "Salud" in p_clean):
                return p_clean
        return parts[-2].strip() if len(parts) >= 2 else ""

    rows = []
    for tid in ICM_TABLES:
        data = _fetch_table(tid, nult=120, det=2)
        if not isinstance(data, list):
            continue
        for serie in data:
            nombre = serie.get("Nombre", "").strip()
            if not nombre:
                continue
            # El nom acaba amb punt final; partim per ". " preservant cua
            parts = [p for p in nombre.rstrip(".").split(". ") if p.strip()]
            if len(parts) < 3:
                continue
            if MODES & {p.strip() for p in parts}:
                continue

            ambit = _extreu_ambit(parts)
            tipus = _classifica_tipus(nombre)
            branca = _extreu_branca(parts)
            indicador = _extreu_indicador(parts)
            if indicador is None or tipus == "altre":
                continue

            for obs in serie.get("Data", []):
                val = obs.get("Valor")
                if val is None:
                    continue
                any_ = obs.get("Anyo")
                per = obs.get("Periodo") or {}
                mes = per.get("Mes_inicio")
                try:
                    any_int = int(any_)
                    mes_int = int(mes)
                    data_str = f"{any_int:04d}-{mes_int:02d}-01"
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "serie_id": nombre,
                    "ambit": ambit,
                    "tipus": tipus,
                    "branca": branca,
                    "indicador": indicador,
                    "any": any_int,
                    "mes": mes_int,
                    "data": data_str,
                    "valor": float(val),
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"]).drop_duplicates(
        subset=["serie_id", "data", "indicador"]
    )
    # 60096 i 60103 publiquen totes dues el real del 47 sense 473, amb noms de
    # sèrie diferents: una sola fila per branca, àmbit, indicador i mes.
    df = df.drop_duplicates(subset=["ambit", "tipus", "branca", "indicador", "data"])
    df = df.sort_values(["tipus", "ambit", "branca", "indicador", "data"]).reset_index(drop=True)
    return df


def fetch_eaes():
    """
    EAES — Encuesta Anual de Estructura Salarial (INE, taula 28185).
    Salari brut anual mitjà per treballador a jornada equivalent. Cobreix
    industria + construcció + serveis (excloent ocupadors domèstics i
    organismes extraterritorials). Granularitat anual, 19 seccions CNAE.

    Filtra només:
      - Sexe: Total (no homes/dones)
      - Àmbit: Total Nacional
      - Indicador: Salario medio bruto (no percentiles)

    Retorna DataFrame amb columnes: sector, any, valor.

    Per comparativa amb sector G47 (calculat amb EEE), tenir en compte:
    EAES dóna xifra més alta perquè és jornada equivalent; EEE divideix
    massa salarial entre tots els ocupats (incloent parcials). A més,
    l'EAES només té el sector G complet (comerç al por mayor+menor+
    reparación vehicles), no G47 aïllat.
    """
    data = _fetch_table(28185, nult=10, det=2)
    if not isinstance(data, list):
        return pd.DataFrame()

    rows = []
    for s in data:
        nombre = s.get("Nombre", "")
        if not nombre.startswith("Total. "):
            continue
        rest = nombre[len("Total. "):]
        if "Total Nacional" not in rest or "Salario medio bruto" not in rest:
            continue
        sector = rest.split(". Dato base")[0].strip()
        for obs in s.get("Data", []):
            val = obs.get("Valor")
            any_ = obs.get("Anyo")
            if val is None or any_ is None:
                continue
            # L'EAES marca alguns valors com a no fiables amb negatius
            # (vegeu Industries extractives dones 2023). Els descartem.
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if v <= 0:
                continue
            rows.append({"sector": sector, "any": int(any_), "valor": v})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["sector", "any"]).reset_index(drop=True)


def fetch_icm_distribucion():
    """
    ICM per modo de distribución comercial (INE, base 2021=100).
    Substitueix la sèrie descatalogada "Índices de grandes superficies" (taula
    25982 històrica, fin 2023-12) amb el desglossament actual integrat a l'ICM:
    Empresas unilocalizadas, Pequeñas cadenas, Grandes cadenas, Grandes
    superficies. Granularitat mensual.

    Taules INE:
      - 60105 (cifra negoci precios corrents × modo distribución)
      - 75809 (cifra negoci precios constantes × modo distribución)
      - 60115 (ocupació mensual × modo distribución)

    Filtra ambit retail al total ("Comercio al por menor sin Estaciones de
    Servicio (47 sin 473)") — els subagregats alimentació/resto queden fora.

    Retorna DataFrame amb columnes:
      - serie_id (nom complet INE)
      - tipus ("real" / "nominal" / "ocupacio")
      - modo ("Empresas unilocalizadas" / "Pequeñas cadenas" / "Grandes cadenas" / "Grandes superficies" / "General")
      - indicador ("index" / "var_mensual" / "var_anual" / "var_mitjana_acum")
      - any, mes, data, valor
    """
    TABLES = [(60105, "nominal"), (75809, "real"), (60115, "ocupacio")]

    INDICADOR_MAP = {
        "Índice": "index",
        "Variación mensual": "var_mensual",
        "Variación anual": "var_anual",
        "Variación de la media en lo que va de año": "var_mitjana_acum",
    }
    AMBIT_TOTAL = "Comercio al por menor sin Estaciones de Servicio (47 sin 473)"
    MODOS = {
        "Empresas unilocalizadas", "Pequeñas cadenas",
        "Grandes cadenas", "Grandes Superficies", "General",
    }

    rows = []
    for tid, tipus in TABLES:
        data = _fetch_table(tid, nult=120, det=2)
        if not isinstance(data, list):
            continue
        for serie in data:
            nombre = serie.get("Nombre", "").strip()
            if not nombre:
                continue
            parts = [p.strip() for p in nombre.rstrip(".").split(". ") if p.strip()]
            # Filtra només l'ambit retail total
            if AMBIT_TOTAL not in parts:
                continue
            # Modo de distribució: el segment que coincideix amb la llista
            modo = next((p for p in parts if p in MODOS), None)
            if modo is None:
                continue
            # Indicador: l'últim segment que coincideix amb el mapa
            indicador = None
            for p in reversed(parts):
                if p in INDICADOR_MAP:
                    indicador = INDICADOR_MAP[p]
                    break
            if indicador is None:
                continue

            for obs in serie.get("Data", []):
                val = obs.get("Valor")
                if val is None:
                    continue
                any_ = obs.get("Anyo")
                per = obs.get("Periodo") or {}
                mes = per.get("Mes_inicio")
                try:
                    any_int = int(any_)
                    mes_int = int(mes)
                    data_str = f"{any_int:04d}-{mes_int:02d}-01"
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "serie_id": nombre,
                    "tipus": tipus,
                    "modo": modo,
                    "indicador": indicador,
                    "any": any_int,
                    "mes": mes_int,
                    "data": data_str,
                    "valor": float(val),
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = (df.dropna(subset=["data"])
            .drop_duplicates(subset=["serie_id", "data", "indicador"])
            .sort_values(["tipus", "modo", "indicador", "data"])
            .reset_index(drop=True))
    return df


# ─── TERRITORI: LOCALS DIRCE PER PROVÍNCIA I PER CCAA × GRUP ────────────
#
# Mesuren LOCALS (unitats locals), no empreses: una empresa amb tres botigues
# compta tres. No es poden comparar amb fetch_empreses() (T=39372).
#
# Els noms de territori de les taules del DIRCE no són estables entre
# activitats ("Coruña (A)" / "A Coruña"...): tot es filtra i s'uneix pels
# codis de MetaData (tip="AM"), mai pel nom. Els filtres tv= són ids interns
# de valor de l'INE; si mai canvien, la resposta ve buida i el processor cau
# al cache.

_TV_ESTRAT_TOTAL = "336:15723"          # Estrato de asalariados = Total
_TV_ACTIVITAT = {                        # Actividad principal (idValor)
    "47":  "338:17579", "471": "338:18228", "472": "338:21936",
    "473": "338:21937", "474": "338:18231", "475": "338:18232",
    "476": "338:18233", "477": "338:18234", "478": "338:18235",
    "479": "338:18236",
}
_CODI_ACTIVITAT = {                      # codi INE de MetaData -> CNAE
    "EHX": "47", "EHB": "471", "EHC": "472", "EHD": "473", "EHE": "474",
    "EHF": "475", "EHG": "476", "EHH": "477", "EHI": "478", "EHJ": "479",
}


def _meta(serie, variable):
    """Codi de MetaData d'una variable ('Provincias', 'Actividad principal'...)."""
    for m in serie.get("MetaData", []):
        if m.get("T3_Variable") == variable:
            return m.get("Codigo")
    return None


def _codi_geo(serie, variable_territori):
    """Codi del territori; '00' per al total nacional."""
    if _meta(serie, "Totales Territoriales") == "00":
        return "00"
    return _meta(serie, variable_territori)


def fetch_locals_provincia():
    """
    Taula 301: Locals per província, activitat principal (divisions CNAE 2009)
    i estrat d'assalariats. Divisió 47, estrat Total, 52 províncies + nacional.
    Retorna: codi_geo (INE 2 dígits, '00' = Espanya), any, locals_cnae47.
    """
    data = _fetch_table(301, nult=30, tip="AM",
                        tv=[_TV_ESTRAT_TOTAL, _TV_ACTIVITAT["47"]])
    if not isinstance(data, list):
        return pd.DataFrame()
    rows = []
    for serie in data:
        if (_meta(serie, "Actividad principal") != "EHX"
                or _meta(serie, "Estrato de asalariados") != "01"):
            continue
        codi = _codi_geo(serie, "Provincias")
        if not codi:
            continue
        for obs in serie.get("Data", []):
            if obs.get("Valor") is not None:
                rows.append({"codi_geo": codi, "any": obs.get("Anyo"),
                             "locals_cnae47": obs.get("Valor")})
    return pd.DataFrame(rows)


def fetch_locals_ccaa_grups():
    """
    Taula 294: Locals per CCAA, activitat principal (grups CNAE 2009) i estrat
    d'assalariats. Divisió 47 + grups 471-479, estrat Total, 19 CCAA + nacional.
    Retorna: codi_geo (INE CCAA 2 dígits, '00' = Espanya), any, cnae, locals.
    """
    data = _fetch_table(294, nult=30, tip="AM",
                        tv=[_TV_ESTRAT_TOTAL] + list(_TV_ACTIVITAT.values()))
    if not isinstance(data, list):
        return pd.DataFrame()
    rows = []
    for serie in data:
        cnae = _CODI_ACTIVITAT.get(_meta(serie, "Actividad principal"))
        if cnae is None or _meta(serie, "Estrato de asalariados") != "01":
            continue
        codi = _codi_geo(serie, "Comunidades y Ciudades Autónomas")
        if not codi:
            continue
        for obs in serie.get("Data", []):
            if obs.get("Valor") is not None:
                rows.append({"codi_geo": codi, "any": obs.get("Anyo"),
                             "cnae": cnae, "locals": obs.get("Valor")})
    return pd.DataFrame(rows)


def fetch_poblacio_provincia(nult=17):
    """
    Taula 29005: xifres oficials del padró per municipi, sumades per província
    (dos primers dígits del codi municipal). Les taules provincials del padró
    (2852 i germanes) s'aturen el 2021; aquesta arriba a l'últim any publicat.
    Verificat: Barcelona 2021 = 5.714.730, igual que la T=2852.
    nult=17 cobreix des del 2009 (la sèrie de locals comença el 2010).
    Retorna: codi_prov, any, poblacio, n_municipis.
    """
    data = _fetch_table(29005, nult=nult, tip="AM", tv=["18:451"])  # Sexo = Total
    if not isinstance(data, list):
        return pd.DataFrame()
    rows = []
    for serie in data:
        if _meta(serie, "Sexo") != "0":
            continue
        codi_mun = _meta(serie, "Municipios")
        if not codi_mun or len(codi_mun) != 5:
            continue
        for obs in serie.get("Data", []):
            if obs.get("Valor") is not None:
                rows.append({"codi_prov": codi_mun[:2], "any": obs.get("Anyo"),
                             "poblacio": obs.get("Valor")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (df.groupby(["codi_prov", "any"])
              .agg(poblacio=("poblacio", "sum"), n_municipis=("poblacio", "size"))
              .reset_index())


if __name__ == "__main__":
    print("Testejant API INE...")

    print("\n1. VAB per branques:")
    df = fetch_vab_ramas()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df.head())

    print("\n2. Empreses:")
    df = fetch_empreses()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df.head())

    print("\n3. EPA retail (ocupats/aturats/hores):")
    df = fetch_epa_retail()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df.head())

    print("\n4. EEE Comercio CCAA:")
    df = fetch_eee_comercio_ccaa()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df.head(10))
