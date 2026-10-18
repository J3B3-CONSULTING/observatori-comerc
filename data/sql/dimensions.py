"""
Claus comunes per creuar fonts: territori i branca CNAE.

Cada font escriu el mateix territori o la mateixa branca a la seva manera
("Balears (Illes)" al DIRCE, "Balears, Illes" a l'ICM, "Espanya" a Eurostat,
"nacional" a l'ICM, "espanya" a l'EEE...). Aquí es fixa un codi canònic per a
cadascun i la llista d'etiquetes de cada font que hi porten. migrate.py omple
amb aquests codis les columnes geo_codi i cnae_codi de cada observació, i així
dues sèries de fonts diferents es poden ajuntar sense comparar textos.

Codis de territori
------------------
  pais:ES, pais:FR...    estat (codi Eurostat; Espanya inclosa)
  agr:EU27_2020, agr:EA20  agregats europeus
  ccaa:01..ccaa:19       comunitat autònoma (codi INE)
  prov:01..prov:52       província (codi INE)

Codis de branca
---------------
  G                      secció G sencera (engròs + detall + vehicles); només EPA
  47                     comerç al detall
  47_SENSE473            47 sense estacions de servei (agregat de l'ICM)
  471..479, 4711...      grups i classes CNAE 2009
  47_ALIM, 47_EQLLAR, 47_EQPERS, 47_SALUT, 47_RESTA
                         agrupacions pròpies de l'ICM (les classes que sumen
                         van a la descripció)
  47_STS_ALIM, 47_STS_NOALIM
                         agrupacions pròpies d'Eurostat (sts_trtu_m, codis G47_FOOD i
                         G47_NFOOD_X_G473): no es pressuposa que coincideixin amb les
                         de l'ICM (47_ALIM...), per això són codis a part

Si una font canvia una etiqueta, migrate.py falla i diu quina: és volgut.
Un join que perd files en silenci és pitjor que una migració aturada.
"""

# ─── Territori ───────────────────────────────────────────────────────────────

# codi INE de CCAA -> (nom canònic, etiquetes de les fonts)
_CCAA = {
    "01": ("Andalusia", ["Andalucía"]),
    "02": ("Aragó", ["Aragón"]),
    "03": ("Astúries", ["Asturias (Principado de)", "Asturias, Principado de"]),
    "04": ("Illes Balears", ["Balears (Illes)", "Balears, Illes"]),
    "05": ("Canàries", ["Canarias"]),
    "06": ("Cantàbria", ["Cantabria"]),
    "07": ("Castella i Lleó", ["Castilla y León"]),
    "08": ("Castella - la Manxa", ["Castilla - La Mancha"]),
    "09": ("Catalunya", ["Cataluña"]),
    "10": ("Comunitat Valenciana", ["Comunitat Valenciana"]),
    "11": ("Extremadura", ["Extremadura"]),
    "12": ("Galícia", ["Galicia"]),
    "13": ("Comunitat de Madrid", ["Madrid (Comunidad de)", "Madrid, Comunidad de"]),
    "14": ("Regió de Múrcia", ["Murcia (Región de)", "Murcia, Región de"]),
    "15": ("Navarra", ["Navarra (Comunidad Foral de)", "Navarra, Comunidad Foral de"]),
    "16": ("País Basc", ["País Vasco"]),
    "17": ("La Rioja", ["Rioja (La)", "Rioja, La"]),
    "18": ("Ceuta", ["Ceuta"]),
    "19": ("Melilla", ["Melilla"]),
}

# codi INE de província -> (nom, codi INE de CCAA)
_PROV = {
    "01": ("Araba/Álava", "16"), "02": ("Albacete", "08"), "03": ("Alacant", "10"),
    "04": ("Almeria", "01"), "05": ("Àvila", "07"), "06": ("Badajoz", "11"),
    "07": ("Illes Balears", "04"), "08": ("Barcelona", "09"), "09": ("Burgos", "07"),
    "10": ("Càceres", "11"), "11": ("Cadis", "01"), "12": ("Castelló", "10"),
    "13": ("Ciudad Real", "08"), "14": ("Còrdova", "01"), "15": ("A Coruña", "12"),
    "16": ("Conca", "08"), "17": ("Girona", "09"), "18": ("Granada", "01"),
    "19": ("Guadalajara", "08"), "20": ("Gipuzkoa", "16"), "21": ("Huelva", "01"),
    "22": ("Osca", "02"), "23": ("Jaén", "01"), "24": ("Lleó", "07"),
    "25": ("Lleida", "09"), "26": ("La Rioja", "17"), "27": ("Lugo", "12"),
    "28": ("Madrid", "13"), "29": ("Màlaga", "01"), "30": ("Múrcia", "14"),
    "31": ("Navarra", "15"), "32": ("Ourense", "12"), "33": ("Astúries", "03"),
    "34": ("Palència", "07"), "35": ("Las Palmas", "05"), "36": ("Pontevedra", "12"),
    "37": ("Salamanca", "07"), "38": ("Santa Cruz de Tenerife", "05"),
    "39": ("Cantàbria", "06"), "40": ("Segòvia", "07"), "41": ("Sevilla", "01"),
    "42": ("Sòria", "07"), "43": ("Tarragona", "09"), "44": ("Terol", "02"),
    "45": ("Toledo", "08"), "46": ("València", "10"), "47": ("Valladolid", "07"),
    "48": ("Bizkaia", "16"), "49": ("Zamora", "07"), "50": ("Saragossa", "02"),
    "51": ("Ceuta", "18"), "52": ("Melilla", "19"),
}

# codi Eurostat -> nom (el nom és també l'etiqueta que porten els CSV d'Eurostat)
_PAISOS = {
    "AT": "Austria", "BE": "Belgica", "BG": "Bulgaria", "CY": "Xipre",
    "CZ": "Txequia", "DE": "Alemanya", "DK": "Dinamarca", "EE": "Estonia",
    "EL": "Grecia", "ES": "Espanya", "FI": "Finlandia", "FR": "Franca",
    "HR": "Croacia", "HU": "Hongria", "IE": "Irlanda", "IT": "Italia",
    "LT": "Lituania", "LU": "Luxemburg", "LV": "Letonia", "MT": "Malta",
    "NL": "Paisos Baixos", "PL": "Polonia", "PT": "Portugal", "RO": "Romania",
    "SE": "Suecia", "SI": "Eslovenia", "SK": "Eslovaquia",
}
_AGREGATS = {"EU27_2020": "UE-27", "EA20": "Eurozona"}

# Etiquetes d'Espanya com a total nacional a les fonts estatals.
_ESPANYA_ALIES = ["Espanya", "espanya", "nacional"]


def _build_territori():
    rows, alies = [], {}
    for codi, nom in _PAISOS.items():
        rows.append(dict(geo_codi=f"pais:{codi}", nivell="pais", nom=nom,
                         geo_pare=None, codi_ine=None, codi_eurostat=codi))
        alies[nom] = f"pais:{codi}"
    for codi, nom in _AGREGATS.items():
        rows.append(dict(geo_codi=f"agr:{codi}", nivell="agregat", nom=nom,
                         geo_pare=None, codi_ine=None, codi_eurostat=codi))
        alies[nom] = f"agr:{codi}"
    for a in _ESPANYA_ALIES:
        alies[a] = "pais:ES"
    for codi, (nom, etiquetes) in _CCAA.items():
        rows.append(dict(geo_codi=f"ccaa:{codi}", nivell="ccaa", nom=nom,
                         geo_pare="pais:ES", codi_ine=codi, codi_eurostat=None))
        for e in etiquetes:
            alies[e] = f"ccaa:{codi}"
    for codi, (nom, ccaa) in _PROV.items():
        rows.append(dict(geo_codi=f"prov:{codi}", nivell="provincia", nom=nom,
                         geo_pare=f"ccaa:{ccaa}", codi_ine=codi, codi_eurostat=None))
    return rows, alies


DIM_TERRITORI, ALIES_TERRITORI = _build_territori()


# ─── Branca CNAE ─────────────────────────────────────────────────────────────

# codi -> (nom canònic, nivell, codi pare, etiquetes de les fonts)
_BRANCA = {
    "G": ("Comerç a l'engròs i al detall; reparació de vehicles (secció G)", "seccio", None, []),
    "47": ("Comerç al detall (CNAE 47)", "divisio", "G", [
        "G47",
        "Comercio al por menor, excepto de vehículos de motor y motocicletas",
        "CNAE 47 total", "Comerç al detall (total CNAE 47)"]),
    "47_SENSE473": ("Comerç al detall sense estacions de servei", "agregat_icm", "47", [
        "G47_X_G473",
        "Comercio al por menor sin Estaciones de Servicio (47 sin 473)"]),
    "471": ("Establiments no especialitzats (súper i hiper)", "grup", "47", [
        "Comercio al por menor en establecimientos no especializados",
        "Establecimientos no especializados",
        "Establiments no especialitzats (súper i hiper)"]),
    "4711": ("No especialitzats amb predomini d'alimentació", "classe", "471", [
        "G4711",
        "Comercio al por menor en establecimientos no especializados, con predominio en "
        "productos alimenticios, bebidas y tabaco"]),
    "4719": ("Altres no especialitzats (grans magatzems)", "classe", "471", [
        "Otro comercio al por menor en establecimientos no especializados"]),
    "472": ("Aliments, begudes i tabac (especialitzat)", "grup", "47", [
        "G472",
        "Comercio al por menor de productos alimenticios, bebidas y tabaco en "
        "establecimientos especializados",
        "Alimentación, bebidas y tabaco",
        "Aliments, begudes i tabac (especialitzat)"]),
    "4721": ("Fruiteries", "classe", "472", ["Fruiteries"]),
    "4722": ("Carnisseries", "classe", "472", ["Carnisseries"]),
    "4723": ("Peixateries", "classe", "472", ["Peixateries"]),
    "4724": ("Forns i pastisseries", "classe", "472", ["Forns i pastisseries"]),
    "4725": ("Begudes", "classe", "472", ["Begudes"]),
    "4726": ("Estancs (tabac)", "classe", "472", ["Estancs (tabac)"]),
    "4729": ("Altres aliments", "classe", "472", ["Altres aliments"]),
    "473": ("Combustible (gasolineres)", "grup", "47", [
        "Comercio al por menor de combustible para la automoción en establecimientos "
        "especializados",
        "Combustibles", "Combustible (gasolineres)"]),
    "474": ("Equips TIC", "grup", "47", [
        "Comercio al por menor de equipos para las tecnologías de la información y las "
        "comunicaciones en establecimientos especializados",
        "Equipos TIC", "Equips TIC"]),
    "475": ("Equipament de la llar", "grup", "47", [
        "Comercio al por menor de otros artículos de uso doméstico en establecimientos "
        "especializados",
        "Articles d'us domestic", "Equipament de la llar"]),
    "476": ("Articles culturals i recreatius", "grup", "47", [
        "Comercio al por menor de artículos culturales y recreativos en establecimientos "
        "especializados",
        "Cultura i recreatius", "Articles culturals i recreatius"]),
    "477": ("Altres articles (moda, calçat, farmàcia...)", "grup", "47", [
        "Comercio al por menor de otros artículos en establecimientos especializados",
        "Vestit, calcat i altres", "Altres articles (moda, calçat, etc.)"]),
    "478": ("Parades i mercats ambulants", "grup", "47", [
        "Comercio al por menor en puestos de venta y en mercadillos",
        "Mercadillos", "Punts de venda i mercadillos"]),
    "479": ("Venda fora d'establiment (internet, correu...)", "grup", "47", [
        "G479",
        "Comercio al por menor no realizado ni en establecimientos, ni en puestos de "
        "venta ni en mercadillos",
        "Venda no establerta (online)", "Comerç no en establiment (internet)"]),
    "4791": ("Venda per correu o internet", "classe", "479", [
        "G4791",
        "Comercio al por menor por correspondencia o Internet"]),
    # Agrupacions de l'ICM: no són nodes CNAE, el pare és el 47.
    "47_ALIM": ("Alimentació (4711+472)", "agregat_icm", "47", [
        "Alimentación (4711+472)"]),
    "47_EQLLAR": ("Equipament de la llar (4743+4752+4754+4759+4763)", "agregat_icm", "47", [
        "Equipo del hogar (4743+4752+4754+4759+4763)"]),
    "47_EQPERS": ("Equipament personal (4751+4771+4772)", "agregat_icm", "47", [
        "Equipo personal (4751+4771+4772)"]),
    "47_SALUT": ("Salut (4773+4774+4775)", "agregat_icm", "47", [
        "Salud (4773+4774+4775)"]),
    "47_RESTA": ("Resta (4719+474+475+476+477+478+479)", "agregat_icm", "47", [
        "Resto (4719+474+475+476+477+478+479)"]),
    "47_STS_ALIM": ("Alimentació, begudes i tabac segons Eurostat", "agregat_sts", "47", [
        "G47_FOOD"]),
    "47_STS_NOALIM": ("No alimentari sense carburant segons Eurostat", "agregat_sts", "47", [
        "G47_NFOOD_X_G473"]),
}


def _build_branca():
    rows, alies = [], {}
    for codi, (nom, nivell, pare, etiquetes) in _BRANCA.items():
        rows.append(dict(cnae_codi=codi, nivell=nivell, nom=nom, cnae_pare=pare))
        alies[codi] = codi      # les fonts que ja porten el codi (locals T=294)
        for e in etiquetes:
            alies[e] = codi
    return rows, alies


DIM_BRANCA, ALIES_BRANCA = _build_branca()


# ─── Avisos de qualitat ──────────────────────────────────────────────────────
# Viatgen amb cada observació (columna avis) i els derivats els hereten, perquè
# un càlcul fet amb una dada amb reserves no surti net.

DIM_AVIS = [
    dict(avis_codi="dirce_2023",
         text="Posterior al trencament de sèrie del DIRCE del 2023: no és comparable "
              "amb els anys anteriors. Cap variació que travessi el 2023 es pot "
              "presentar sense aquest avís."),
    dict(avis_codi="icm_brut",
         text="ICM en brut, sense corregir d'estacionalitat ni de calendari. Només "
              "són interpretables les variacions interanuals i les mitjanes anuals; "
              "no quadra amb sèries corregides (CVEC d'Idescat, Eurostat)."),
    dict(avis_codi="vab_ccaa_estimat",
         text="VAB per CCAA estimat per J3B3 a partir de ràtios nacionals o de la "
              "comptabilitat regional: no és una dada publicada per l'INE."),
    dict(avis_codi="seccio_g",
         text="Secció G sencera (comerç a l'engròs, al detall i reparació de "
              "vehicles): l'INE no la desglossa per al CNAE 47."),
    dict(avis_codi="tpv_totes_activitats",
         text="Compres amb targeta en TPV de totes les activitats (restauració, "
              "transport, serveis...), no només del comerç al detall."),
    dict(avis_codi="deflactor_general",
         text="Deflactat amb l'IPC general, no amb un índex de preus propi del "
              "comerç ni de la branca: és una aproximació."),
    dict(avis_codi="abast_diferent",
         text="Ràtio entre dues fonts que no mesuren el mateix univers: serveix per a "
              "l'ordre de magnitud i la tendència, no com a xifra exacta."),
    dict(avis_codi="lloc_de_venda",
         text="Les vendes es compten on es ven, no on viuen els compradors: el turisme "
              "i la centralitat comercial pugen les vendes per habitant d'una comunitat "
              "sense que n'hi hagi més demanda local."),
]


# ─── Resolució ───────────────────────────────────────────────────────────────

class ClauDesconeguda(ValueError):
    """Una etiqueta d'una font no té codi canònic."""


def resol(valors, alies, prefix="", que="valor"):
    """Tradueix una sèrie d'etiquetes a codis. Falla amb la llista d'etiquetes
    que no es reconeixen, perquè un join no perdi files sense dir res."""
    claus = valors.astype(str).map(lambda v: f"{prefix}{v}")
    codis = claus.map(alies)
    falten = sorted(set(claus[codis.isna() & valors.notna()]))
    if falten:
        raise ClauDesconeguda(f"{que} sense codi canònic: {falten}. "
                              "Afegeix-les a data/sql/dimensions.py.")
    return codis


# Codis INE numèrics (els CSV de locals porten '00' = Espanya i el codi a 2 xifres).
ALIES_PROV_INE = {"00": "pais:ES", **{c: f"prov:{c}" for c in _PROV}}
ALIES_CCAA_INE = {"00": "pais:ES", **{c: f"ccaa:{c}" for c in _CCAA}}
