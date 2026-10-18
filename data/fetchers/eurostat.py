"""
Client API per Eurostat.
Documentació: https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access
"""
import requests
import pandas as pd

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

COUNTRIES = [
    "EU27_2020", "EA20", "BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL",
    "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT",
    "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE",
]

COUNTRY_NAMES = {
    "EU27_2020": "UE-27", "EA20": "Eurozona", "BE": "Belgica", "BG": "Bulgaria",
    "CZ": "Txequia", "DK": "Dinamarca", "DE": "Alemanya", "EE": "Estonia",
    "IE": "Irlanda", "EL": "Grecia", "ES": "Espanya", "FR": "Franca",
    "HR": "Croacia", "IT": "Italia", "CY": "Xipre", "LV": "Letonia",
    "LT": "Lituania", "LU": "Luxemburg", "HU": "Hongria", "MT": "Malta",
    "NL": "Paisos Baixos", "AT": "Austria", "PL": "Polonia", "PT": "Portugal",
    "RO": "Romania", "SI": "Eslovenia", "SK": "Eslovaquia", "FI": "Finlandia",
    "SE": "Suecia",
}


def _fetch_eurostat(dataset, params):
    """Descarrega dades de l'API REST d'Eurostat.
    params pot ser un dict o una llista de tuples (per parametres repetits com geo).
    """
    url = f"{BASE_URL}/{dataset}"

    # Convertir a llista de tuples per suportar parametres repetits
    if isinstance(params, dict):
        # Si geo es una llista, expandir-la
        param_list = []
        for k, v in params.items():
            if isinstance(v, list):
                for item in v:
                    param_list.append((k, item))
            else:
                param_list.append((k, v))
        params = param_list

    params.append(("format", "JSON"))
    params.append(("lang", "en"))

    resp = requests.get(url, params=params, timeout=120)
    if resp.status_code != 200:
        print(f"Eurostat error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def _parse_eurostat_json(data):
    """
    Parseja el format JSON-stat d'Eurostat a un DataFrame.
    """
    if not data or "value" not in data:
        return pd.DataFrame()

    dims = data.get("dimension", {})
    sizes = data.get("size", [])
    dim_ids = data.get("id", [])
    values = data.get("value", {})

    # Construir mapeig d'índex a combinació de dimensions
    dim_labels = {}
    for dim_id in dim_ids:
        dim_info = dims.get(dim_id, {})
        cat = dim_info.get("category", {})
        idx = cat.get("index", {})
        label = cat.get("label", {})
        # Ordenar per índex
        sorted_keys = sorted(idx.items(), key=lambda x: x[1])
        dim_labels[dim_id] = [k for k, v in sorted_keys]

    rows = []
    total = 1
    for s in sizes:
        total *= s

    for flat_idx_str, val in values.items():
        flat_idx = int(flat_idx_str)
        row = {}
        remainder = flat_idx
        for i in range(len(dim_ids) - 1, -1, -1):
            dim_size = len(dim_labels[dim_ids[i]])
            pos = remainder % dim_size
            remainder //= dim_size
            row[dim_ids[i]] = dim_labels[dim_ids[i]][pos]
        row["valor"] = val
        rows.append(row)

    return pd.DataFrame(rows)


def fetch_vab_cnae47():
    """
    Dataset nama_10_a64: VAB del CNAE 47 per país (preus corrents i encadenats).
    """
    params = {
        "nace_r2": "G47",
        "na_item": "B1G",  # Value added, gross
        "unit": "CP_MEUR",  # Current prices, million euro
        "geo": COUNTRIES,  # Llista -> parametres repetits
    }

    data = _fetch_eurostat("nama_10_a64", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["vab_meur"] = pd.to_numeric(df["valor"], errors="coerce")

    return df[["pais", "pais_codi", "any", "vab_meur"]].dropna()


def fetch_vab_total():
    """
    Dataset nama_10_a64: VAB total per país (per calcular pes CNAE 47).
    """
    params = {
        "nace_r2": "TOTAL",
        "na_item": "B1G",
        "unit": "CP_MEUR",
        "geo": COUNTRIES,
    }

    data = _fetch_eurostat("nama_10_a64", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["vab_total_meur"] = pd.to_numeric(df["valor"], errors="coerce")

    return df[["pais", "pais_codi", "any", "vab_total_meur"]].dropna()


def fetch_ppp():
    """
    Dataset prc_ppp_ind: Paritats de poder adquisitiu i índexs de preus.
    """
    params = {
        "na_item": "PLI_EU27_2020",  # Price level indices
        "ppp_cat": "A0101",  # Actual individual consumption
        "geo": COUNTRIES,
    }

    data = _fetch_eurostat("prc_ppp_ind", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["index_preus"] = pd.to_numeric(df["valor"], errors="coerce")

    return df[["pais", "pais_codi", "any", "index_preus"]].dropna()


def fetch_empreses_ue():
    """
    Dataset bd_size: Nombre d'empreses CNAE 47 per país.
    """
    params = {
        "nace_r2": "G47",
        "indic_sb": "V11910",  # Number of enterprises
        "sizeclas": "TOTAL",
        "geo": COUNTRIES,
    }

    data = _fetch_eurostat("bd_size", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["empreses"] = pd.to_numeric(df["valor"], errors="coerce")

    return df[["pais", "pais_codi", "any", "empreses"]].dropna()


NUTS2_ES = [
    "ES11", "ES12", "ES13", "ES21", "ES22", "ES23", "ES24",
    "ES30", "ES41", "ES42", "ES43", "ES51", "ES52", "ES53",
    "ES61", "ES62", "ES70",
]

NUTS2_NAMES = {
    "ES11": "Galicia", "ES12": "Asturias (Principado de)",
    "ES13": "Cantabria", "ES21": "País Vasco",
    "ES22": "Navarra (Comunidad Foral de)", "ES23": "Rioja (La)",
    "ES24": "Aragón", "ES30": "Madrid (Comunidad de)",
    "ES41": "Castilla y León", "ES42": "Castilla - La Mancha",
    "ES43": "Extremadura", "ES51": "Cataluña",
    "ES52": "Comunitat Valenciana", "ES53": "Balears (Illes)",
    "ES61": "Andalucía", "ES62": "Murcia (Región de)",
    "ES70": "Canarias",
}


def fetch_vab_regional_gi():
    """
    Dataset nama_10r_3gva: VAB secció G-I (comerç+transport+hostaleria)
    per CCAA espanyoles (NUTS2) + total nacional ES. Preus corrents, M EUR.
    """
    params = [("unit", "CP_MEUR"), ("nace_r2", "G-I")]
    for code in NUTS2_ES:
        params.append(("geo", code))
    params.append(("geo", "ES"))

    data = _fetch_eurostat("nama_10r_3gva", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "nuts2"})
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["vab_gi_meur"] = pd.to_numeric(df["valor"], errors="coerce")
    df["territori"] = df["nuts2"].map(NUTS2_NAMES).fillna(df["nuts2"])
    df.loc[df["nuts2"] == "ES", "territori"] = "espanya"

    return df[["territori", "nuts2", "any", "vab_gi_meur"]].dropna()


def fetch_vab_regional_total():
    """
    Dataset nama_10r_3gva: VAB TOTAL per CCAA espanyoles (NUTS2) + nacional.
    Preus corrents, M EUR. Per calcular el pes del CNAE 47 sobre el PIB de cada CCAA.
    """
    params = [("unit", "CP_MEUR"), ("nace_r2", "TOTAL")]
    for code in NUTS2_ES:
        params.append(("geo", code))
    params.append(("geo", "ES"))

    data = _fetch_eurostat("nama_10r_3gva", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "nuts2"})
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["vab_total_meur"] = pd.to_numeric(df["valor"], errors="coerce")
    df["territori"] = df["nuts2"].map(NUTS2_NAMES).fillna(df["nuts2"])
    df.loc[df["nuts2"] == "ES", "territori"] = "espanya"

    return df[["territori", "nuts2", "any", "vab_total_meur"]].dropna()


def fetch_vab_nacional_g47():
    """
    Dataset nama_10_a64: VAB CNAE G47 nomes per Espanya. Preus corrents, M EUR.
    Per calcular la ratio G47/GI a nivell nacional.
    """
    params = {
        "nace_r2": "G47",
        "na_item": "B1G",
        "unit": "CP_MEUR",
        "geo": ["ES"],
    }
    data = _fetch_eurostat("nama_10_a64", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any"})
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["vab_g47_meur"] = pd.to_numeric(df["valor"], errors="coerce")

    return df[["any", "vab_g47_meur"]].dropna()


def fetch_retail_volume_monthly():
    """
    Dataset sts_trtu_m: volum de vendes mensual del comerç minorista (G47).
    Indicador VOL_SLS (volume of sales), ajustat estacional i calendari (SCA).
    Es retorna el nivell index (base 2021=100). La variacio interanual es
    calcula al processor a partir d'aquest index.
    Publicacio mensual amb retard ~45 dies.

    Ampliat 2026-05 als 27 estats UE perque la comparativa europea del
    dashboard pugui oferir qualsevol pais (es necessitava EL i altres
    per a la ponencia 2026).
    """
    countries = COUNTRIES  # 27 estats UE + UE-27 + Eurozona
    params = [
        ("nace_r2", "G47"),
        ("indic_bt", "VOL_SLS"),
        ("s_adj", "SCA"),
        ("unit", "I21"),
    ]
    for c in countries:
        params.append(("geo", c))

    data = _fetch_eurostat("sts_trtu_m", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "periode", "TIME_PERIOD": "periode", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["index_volum"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["index_volum"])

    return df[["pais", "pais_codi", "periode", "index_volum"]].reset_index(drop=True)


# Desglossament del G47 a sts_trtu_m: codi NACE d'Eurostat -> etiqueta.
# G47_FOOD i els G47_NF_* són agregats propis d'Eurostat (no són nodes CNAE);
# G47_X_G473 és el 47 sense carburant, equivalent al 47 sense 473 de l'ICM.
# G47_NF_CLTH i G47_NF_HLTH no s'hi inclouen: Espanya deixa de transmetre'ls el 2023-12.
RETAIL_BRANQUES = {
    "G47": "Comerç al detall (total)",
    "G47_X_G473": "Comerç al detall sense carburant",
    "G47_FOOD": "Alimentació, begudes i tabac",
    "G47_NFOOD_X_G473": "No alimentari (sense carburant)",
    "G4711": "No especialitzats amb predomini d'alimentació",
    "G472": "Alimentació especialitzada",
    "G479": "Venda fora d'establiment",
    "G4791": "Venda per correu o internet",
}
# Països del desglossament: Espanya, agregats europeus i els quatre grans veïns.
RETAIL_BRANQUES_PAISOS = ["ES", "EU27_2020", "EA20", "DE", "FR", "IT", "PT"]


def fetch_retail_volume_branques():
    """
    Dataset sts_trtu_m: volum de vendes mensual del comerç al detall per branca
    (alimentació, no alimentari, internet...), mateix indicador que
    fetch_retail_volume_monthly (VOL_SLS, SCA, base 2021=100).
    """
    params = [("indic_bt", "VOL_SLS"), ("s_adj", "SCA"), ("unit", "I21")]
    params += [("nace_r2", c) for c in RETAIL_BRANQUES]
    params += [("geo", c) for c in RETAIL_BRANQUES_PAISOS]

    data = _fetch_eurostat("sts_trtu_m", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "periode", "TIME_PERIOD": "periode", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["nace_codi"] = df["nace_r2"]
    df["branca"] = df["nace_codi"].map(RETAIL_BRANQUES)
    df["index_volum"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["index_volum"])

    return df[["pais", "pais_codi", "nace_codi", "branca", "periode",
               "index_volum"]].reset_index(drop=True)


# Radiografia de digitalització del comerç (G47), enquesta TIC d'Eurostat.
# (dataset, indic_is, params_extra, etiqueta_ca, etiqueta_es)
_DIG_INDICADORS = [
    ("isoc_ec_eseln2", "E_AESELL", [], "Venda electrònica", "Venta electrónica"),
    ("isoc_eb_ain2", "E_AI_TANY", [("size_emp", "GE10")],
     "Intel·ligència artificial", "Inteligencia artificial"),
    ("isoc_cicce_usen2", "E_CC", [("size_emp", "GE10")], "Núvol (cloud)", "Nube (cloud)"),
]


def fetch_digitalitzacio_comerc():
    """
    Radiografia de la digitalització del comerç al detall (NACE G47): %
    d'empreses que adopten cada tecnologia (venda electrònica, IA, núvol),
    ES vs UE-27, sèrie anual. Enquesta TIC d'Eurostat (datasets isoc_*).
    Nota: IA i núvol cobreixen empreses de 10+ ocupats (exclou micro/autònoms).
    Substitueix l'antic fetch d'e-commerce sol. Ampliable amb més indicadors.
    """
    frames = []
    for dataset, indic, extra, lab_ca, lab_es in _DIG_INDICADORS:
        params = [("nace_r2", "G47"), ("indic_is", indic), ("unit", "PC_ENT"),
                  ("geo", "ES"), ("geo", "EU27_2020")] + extra
        try:
            data = _fetch_eurostat(dataset, params)
            df = _parse_eurostat_json(data)
        except Exception:
            df = pd.DataFrame()
        if df.empty:
            continue
        df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
        # Defensiu: si encara hi ha múltiples classes de mida, quedar-nos amb 10+
        if "size_emp" in df.columns and df["size_emp"].nunique() > 1:
            df = df[df["size_emp"] == "GE10"]
        df["any"] = pd.to_numeric(df["any"], errors="coerce")
        df["pct"] = pd.to_numeric(df["valor"], errors="coerce")
        df["tech"] = lab_ca
        df["tech_es"] = lab_es
        frames.append(df[["pais_codi", "any", "tech", "tech_es", "pct"]])

    if not frames:
        return pd.DataFrame()
    res = pd.concat(frames, ignore_index=True)
    res["pais"] = res["pais_codi"].map(COUNTRY_NAMES)
    return (res.dropna(subset=["any", "pct"])
            [["pais", "pais_codi", "any", "tech", "tech_es", "pct"]]
            .reset_index(drop=True))


# Sexe de la LFS (lfsa_egan22d)
_OCU_SEXE = {"T": "Total", "M": "Homes", "F": "Dones"}
# Rangs LFS a demanar. La taula de NACE detallat només publica rangs amplis o
# acumulats; les franges fines es construeixen per diferència (vegeu _OCU_BANDES).
_OCU_RAW = ["Y15-24", "Y15-39", "Y25-49", "Y50-59", "Y50-64", "Y_GE65"]
# Franges fines resultants, en ordre jove -> gran (partició de 15+ anys)
_OCU_BANDES = ["15-24", "25-39", "40-49", "50-59", "60-64", "65+"]


def fetch_ocupacio_comerc():
    """
    Dataset lfsa_egan22d (EU-LFS): persones ocupades al comerç al detall (NACE
    G47) per sexe i franja d'edat, en milers. ES vs UE-27, sèrie anual.
    Radiografia de qui treballa al sector: pes femení i relleu generacional.
    La taula de NACE detallat només dóna rangs amplis/acumulats; aquí es
    construeixen 6 franges fines per diferència (15-24, 25-39, 40-49, 50-59,
    60-64, 65+). La nacionalitat NO és creuable amb NACE a la LFS (mostra
    insuficient); per això aquí només sexe i edat.
    """
    params = [
        ("nace_r2", "G47"),
        ("unit", "THS_PER"),
        ("geo", "ES"),
        ("geo", "EU27_2020"),
    ]
    params += [("sex", s) for s in _OCU_SEXE]
    params += [("age", a) for a in _OCU_RAW]
    data = _fetch_eurostat("lfsa_egan22d", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Pivotar per construir les franges fines per diferència de rangs acumulats
    piv = df.pivot_table(index=["pais_codi", "any", "sex"],
                         columns="age", values="valor").reset_index()

    def _c(code):
        return piv[code] if code in piv.columns else 0

    bandes = {
        "15-24": _c("Y15-24"),
        "25-39": _c("Y15-39") - _c("Y15-24"),
        "40-49": _c("Y25-49") - (_c("Y15-39") - _c("Y15-24")),
        "50-59": _c("Y50-59"),
        "60-64": _c("Y50-64") - _c("Y50-59"),
        "65+":   _c("Y_GE65"),
    }

    rows = []
    base = piv[["pais_codi", "any", "sex"]]
    for nom, serie in bandes.items():
        tmp = base.copy()
        tmp["edat"] = nom
        tmp["ocupats_milers"] = serie
        rows.append(tmp)
    res = pd.concat(rows, ignore_index=True)

    res["pais"] = res["pais_codi"].map(COUNTRY_NAMES)
    res["sexe"] = res["sex"].map(_OCU_SEXE)
    # Diferències poden donar valors lleugerament negatius per arrodoniment LFS
    res["ocupats_milers"] = res["ocupats_milers"].clip(lower=0)

    return (res[["pais", "pais_codi", "any", "sex", "sexe", "edat", "ocupats_milers"]]
            .dropna(subset=["any", "ocupats_milers", "sexe", "edat"])
            .reset_index(drop=True))


# Component ei_bsco_m -> columna. BS-CSMCI és l'indicador compost (expectatives,
# mitjana de 4 components a 12 mesos vista). Els altres 4 permeten distingir
# situació actual (últims 12 mesos) d'expectatives (propers 12 mesos).
_CONFIANCA_INDIC = {
    "BS-CSMCI": "index_confianca",
    "BS-FS-LY": "situacio_actual_financera",
    "BS-GES-LY": "situacio_actual_economica",
    "BS-FS-NY": "expectatives_financera",
    "BS-GES-NY": "expectatives_economica",
}


def fetch_confianza_consumidor():
    """
    Dataset ei_bsco_m: enquesta de confiança del consumidor harmonitzada a
    nivell UE (Business and Consumer Surveys, coordinada per la Comissió
    Europea / DG ECFIN). NO existeix cap taula pròpia de l'INE per aquest
    indicador — verificat cercant "confianza"/"consumidor" a les 112
    operacions estadístiques de l'INE (wstempus): cap coincidència rellevant.
    Espanya hi participa com a país enquestat, però la sèrie es publica a
    Eurostat, no a INEbase.

    Valors en balanç de respostes (-100 a +100: % positives menys % negatives).
    Sèrie ES des de gener de 1980, ajustada estacionalment (s_adj=SA).

    Retorna columnes: any, mes, periode (YYYY-MM), index_confianca
    (indicador compost, expectatives a 12 mesos), situacio_actual_financera,
    situacio_actual_economica, expectatives_financera, expectatives_economica.
    """
    params = [("geo", "ES"), ("s_adj", "SA"), ("unit", "BAL")]
    params += [("indic", i) for i in _CONFIANCA_INDIC]

    data = _fetch_eurostat("ei_bsco_m", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "periode", "TIME_PERIOD": "periode"})
    df["component"] = df["indic"].map(_CONFIANCA_INDIC)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["component", "valor"])

    piv = df.pivot_table(index="periode", columns="component", values="valor", aggfunc="first").reset_index()
    piv.columns.name = None
    periode_parts = piv["periode"].str.split("-", expand=True)
    piv["any"] = pd.to_numeric(periode_parts[0], errors="coerce")
    piv["mes"] = pd.to_numeric(periode_parts[1], errors="coerce")

    cols = ["any", "mes", "periode"] + [c for c in _CONFIANCA_INDIC.values() if c in piv.columns]
    return (piv[cols]
            .dropna(subset=["any", "mes"])
            .sort_values(["any", "mes"])
            .reset_index(drop=True))


# ─── BUSINESS DEMOGRAPHY (BSD) ────────────────────────────────
# bd_size: demografia empresarial CNAE G47 anual.
# Sèrie 2009-2023 viva, comparativa ES vs UE-27 vs grans economies.

BSD_COUNTRIES = ["EU27_2020", "ES", "DE", "FR", "IT", "PT", "NL", "PL"]

BSD_INDIC_TOTAL = [
    "ENT_NR",            # Nombre d'empreses
    "ENT_BRTHR_PC",      # Taxa naixement (%)
    "ENT_DTHR_PC",       # Taxa defunció (%)
    "ENT_BRTHR_DTHR_PC", # Churn = rotació (%)
    "GRW_ENT_PC",        # Creixement net població empresarial (%)
    "EMP_NR",            # Persones ocupades
    "SAL_NR",            # Assalariats
]


def fetch_bsd_total():
    """
    bd_size: indicadors estructurals G47 totals (sizeclas=TOTAL, age=TOTAL).
    Retorna sèrie temporal ES + UE27 + top economies per als 7 indicadors clau.
    """
    params = [
        ("nace_r2", "G47"),
        ("age", "TOTAL"),
        ("sizeclas", "TOTAL"),
    ]
    for c in BSD_COUNTRIES:
        params.append(("geo", c))
    for i in BSD_INDIC_TOTAL:
        params.append(("indic_sbs", i))

    data = _fetch_eurostat("bd_size", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["pais", "pais_codi", "any", "indic_sbs", "valor"]].dropna()


def fetch_bsd_sizeclas():
    """
    bd_size: distribució per mida d'empresa (sizeclas 0, 1-4, 5-9, GE10) per G47.
    Retorna ENT_NR i EMP_NR per als 27 estats UE + agregats (UE-27, Eurozona).
    Cobertura: sèrie completa des de 2021 (marc metodològic UE 2019/2152).
    """
    params = [
        ("nace_r2", "G47"),
        ("age", "TOTAL"),
        ("indic_sbs", "ENT_NR"),
        ("indic_sbs", "EMP_NR"),
    ]
    for c in COUNTRIES:
        params.append(("geo", c))
    for s in ["0", "1-4", "5-9", "GE10"]:
        params.append(("sizeclas", s))

    data = _fetch_eurostat("bd_size", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["pais", "pais_codi", "any", "indic_sbs", "sizeclas", "valor"]].dropna()


def fetch_bsd_survival():
    """
    bd_size: supervivència empresarial per cohort (age Y1, Y2) per G47.
    Indicador ENT_SRVLR_BRTH_PC = % d'empreses nascudes en l'any t-N que sobreviuen any t.
    Y3-Y5 tenen massa buits per ES; només Y1-Y2 robustos.
    """
    params = [
        ("nace_r2", "G47"),
        ("sizeclas", "TOTAL"),
        ("geo", "ES"),
        ("geo", "EU27_2020"),
        ("indic_sbs", "ENT_SRVLR_BRTH_PC"),
    ]
    for a in ["Y1", "Y2"]:
        params.append(("age", a))

    data = _fetch_eurostat("bd_size", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["pais"] = df["pais_codi"].map(COUNTRY_NAMES)
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["survival_pc"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["pais", "pais_codi", "any", "age", "survival_pc"]].dropna()


def fetch_estructura_consum():
    """
    nama_10_fcs: despesa en consum final de les llars per durabilitat (preus
    corrents, M EUR). Permet calcular la quota de BÉNS vs SERVEIS del consum,
    base de la tesi estructural ("el comerç es redistribueix, no s'enfonsa").
      - P311_S14 béns duradors · P312_S14 semiduradors · P313_S14 no duradors
      - P314_S14 serveis
    Béns = P311+P312+P313; Serveis = P314. Retorna ES i EU/EA per a comparativa.
    """
    items = ["P311_S14", "P312_S14", "P313_S14", "P314_S14"]
    params = [("unit", "CP_MEUR"), ("geo", "ES"), ("geo", "EA20")]
    for it in items:
        params.append(("na_item", it))

    data = _fetch_eurostat("nama_10_fcs", params)
    df = _parse_eurostat_json(data)
    if df.empty:
        return df

    df = df.rename(columns={"time": "any", "TIME_PERIOD": "any", "geo": "pais_codi"})
    df["any"] = pd.to_numeric(df["any"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["any", "valor", "na_item"])

    rows = []
    for (codi, any_), g in df.groupby(["pais_codi", "any"]):
        v = g.set_index("na_item")["valor"]
        if not set(items) <= set(v.index):
            continue
        bens = float(v[["P311_S14", "P312_S14", "P313_S14"]].sum())
        serveis = float(v["P314_S14"])
        tot = bens + serveis
        if tot <= 0:
            continue
        rows.append({
            "pais_codi": codi,
            "pais": COUNTRY_NAMES.get(codi, codi),
            "any": int(any_),
            "bens_meur": round(bens, 1),
            "serveis_meur": round(serveis, 1),
            "bens_share": round(bens / tot * 100, 2),
            "serveis_share": round(serveis / tot * 100, 2),
        })
    return pd.DataFrame(rows).sort_values(["pais_codi", "any"]).reset_index(drop=True)


if __name__ == "__main__":
    print("Testejant API Eurostat...")

    print("\n1. VAB CNAE 47 per país:")
    df = fetch_vab_cnae47()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df[df["pais_codi"] == "ES"].head())

    print("\n2. PPP:")
    df = fetch_ppp()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df[df["pais_codi"] == "ES"].head())

    print("\n3. BSD total (bd_size) G47:")
    df = fetch_bsd_total()
    print(f"   {len(df)} registres")
    if not df.empty:
        print(df[(df["pais_codi"] == "ES") & (df["any"] == 2023)])
