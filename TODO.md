# TODO

Llistat de tasques pendents al projecte. No incloure aquí l'estat operatiu del dia a dia (això va a les memòries del repo Claude).

## Motor de coneixement: creuar fonts abans del xatbot

**Origen**: anàlisi del 2026-10-10. El motor té 31 datasets i 106 sèries a DuckDB, però les set funcions de `data/sql/query.py` treballen sèrie a sèrie. Avui el creuament només el fa una persona (newsletter) o un script fet a mà (`analisi/comertia_*.py`). Si el xatbot surt ara, consultarà sèries, no en traurà coneixement. Ordre acordat: claus comunes, derivats, motor de fets, fonts noves; el xatbot, després.

### ~~1. Claus comunes de territori i branca~~ FET 2026-10-10

- `data/sql/dimensions.py`: codis canònics de territori (`pais:ES`, `agr:EU27_2020`, `ccaa:09`, `prov:08`) i de branca (`G`, `47`, `471`…`4791`, agrupacions de l'ICM `47_ALIM`…), amb totes les etiquetes de cada font.
- DuckDB: taules `dim_territori` i `dim_branca`, i columnes `geo_codi` i `cnae_codi` a `observations` (104.505 files, totes amb territori; les que no són d'una branca CNAE, com l'IPC o les targetes, amb `cnae_codi` NULL).
- `migrate.py::CLAUS` diu on és el territori i la branca de cada sèrie. Una sèrie sense regla o una etiqueta nova fa fallar la migració. Al workflow diari, el pas de DuckDB va després del commit de dades, perquè una fallada no deixi el dashboard sense actualitzar.
- Comprovació: la suma de locals per província (T=301) quadra amb la de CCAA (T=294) a les 304 parelles CCAA × any.

### 2. Indicadors derivats — primera tanda FETA 2026-10-10

`data/sql/derivats.py`: 12 sèries `der_*` calculades per `migrate.py` després de les de base, amb `formula` i `fonts_origen` a `series_metadata`. Avisos de qualitat per observació (columna `avis`, textos a `dim_avis`, definits a `dimensions.DIM_AVIS`); els derivats hereten la unió dels avisos de les dades que fan servir, i `query.py` els retorna amb el text dins de `metadata["avisos"]`.

Fets: vendes per local, per ocupat i per habitant (reals, per CCAA); ocupats per local; deflactor implícit de l'ICM per branca i la seva diferència amb l'IPC del grup; productivitat aparent mensual; variació de la mitjana anual de l'ICM real i nominal (per branca i CCAA); modes de distribució relatius a les empreses d'un local; pes del comerç electrònic sobre les vendes; targeta contra ICM. Verificats contra càlcul independent i contra les variacions publicades per l'INE.

Correccions de base trobades pel camí:
- 22 sèries de l'INE (EEE per CCAA, productivitat, subsectors) eren en euros però etiquetades "M EUR" a DuckDB.
- `fetch_icm()` barrejava l'ocupació per mode de distribució (T=60115) amb el total del 47 sense 473: cinc valors per mes sota la mateixa branca. El KPI d'ocupació de "Pols mensual" mostrava les grans superfícies (+1,4% a l'agost del 2026) en lloc del total (0,0%). Ara es descarten els modes (són a `icm_distribucion`).
- Afegida la T=60103 (ICM real per agrupacions: alimentació, equipament personal i de la llar, salut, resta), parella de la 59787 nominal.

Pendents de la llista:

| Derivat | Creuament | Què falta |
|---|---|---|
| Quadrant creixement × marge per branca | `der_icm_real_var_anual` + marges INE | Les dues sèries ja comparteixen `cnae_codi`; la classificació va al motor de fets |
| Quota del comerç sobre la despesa de les llars per grup | EPF + EAS | Cal el nombre de llars (INE, Encuesta Continua de Hogares) |
| Saturació: densitat contra vendes per CCAA | locals per 1.000 hab + `der_vendes_per_habitant_real` | Les dues sèries ja comparteixen `geo_codi`; la lectura va al motor de fets |
| Divergència amb el CDMGE | CDMGE + ICM + TPV | Aclarir què mesura cada indicador del CDMGE abans d'agregar-lo a trimestres |

### 3. Motor de fets — primera versió FETA 2026-10-11

`data/sql/fets.py`: set regles deterministes que `migrate.py` executa després dels derivats. Escriuen la taula `fets` (enunciat redactat, valor, comparació, valor de referència, sèries d'origen, claus, avisos heretats, rellevància), que es regenera sencera a cada migració. `query.py` hi afegeix `get_facts` (filtres per regla, `geo_codi`, `cnae_codi` i sèrie; cada fet porta fonts i text dels avisos) i `get_derived` (catàleg de derivats o valors per clau comuna). Amb les dades del 10/10 surten 80 fets.

| Regla | Què detecta | Llindar |
|---|---|---|
| extrem | darrer valor més alt o més baix des de fa N anys | 2 anys, comparació estricta |
| ratxa | períodes seguits amb el mateix signe | 6 mesos, 3 trimestres o 3 anys |
| inflexio | canvi de signe després d'una ratxa | ratxa prèvia de 3 mesos o 2 trimestres; valor nou de 0,5 o més |
| ranking | salt de posició d'una CCAA, i qui encapçala o tanca | 3 llocs; Ceuta i Melilla fora |
| divergencia | dues fonts que s'separen | targeta − ICM 5%; deflactor − IPC 2% |
| quadrant_branca | creixement de vendes reals × marge (EBE/vendes) contra la mediana de branques | banda de 0,5 al voltant de la mediana |
| saturacio | locals per 1.000 hab. × vendes per habitant contra Espanya | banda del 3%; avís nou `lloc_de_venda` |

Sèries vigilades (extrem, ratxa, inflexió): `VIGILADES` a `fets.py`. Per afegir-ne una, una línia amb filtres i etiqueta.

Pendent:
- Connectar els fets a la tesi de la portada, a la newsletter i a les candidates a predicció (avui només els llegeix `query.py`).
- ~~Rànquing de creixement anual amb massa salts~~ FET 2026-10-23: salt mínim de 5 llocs per a `der_icm_real_var_anual` (de 10 fets a 6) i rellevància 0,25 per a qui encapçala o tanca igual que l'any anterior (10 de 12). Fets totals: de 82 a 78. La resta de llindars, revisar-los quan hi hagi un parell de mesos més de fets.
- Regla de divergència CDMGE contra ICM, quan s'aclareixi què mesura cada indicador del CDMGE (taula del pas 2).

### 4. Fonts noves oficials i gratuïtes

Per ordre: afiliació a la Seguretat Social per activitat (VERIFICAT 2026-10-18: els datasets oberts són per província i secció, no divisió 47, i amb trencament CNAE 2009/2025 el gener del 2026; només serviria com a secció G amb avís `seccio_g`; recomanació: no incorporar), ~~Eurostat `sts_trtu_m` amb el desglossament del G47~~ FET 2026-10-18 (`europa_retail_branques.csv`: G47, 47 sense carburant, alimentació, no alimentari, 4711, 472, 479, 4791; ES, UE-27, EA20, DE, FR, IT, PT; Espanya no transmet tèxtil ni farmàcia des del 2023-12, per això no hi són; vigilades alimentació i no alimentari a `VIGILADES` i vista per branca a Comparativa Europa, pestanya mensual; les etiquetes de branca només són en català), ~~Central de Balances del Banco de España per sector i mida~~ DESCARTADA 2026-10-18 (les Ràtios Sectorials Europees només tenen distribució HTML a app.bde.es/rss_www, sense CSV ni API, llicència no indicada, nivell de CNAE no documentat; el marge per branca ja el cobreix `marges_branca_ine`), ~~Atlas de Distribució de Renda de les Llars (INE)~~ JA INCORPORAT (T=30896 a `municipal.csv`), FRONTUR/EGATUR per CCAA, estadística cadastral de superfície comercial per municipi.

### 5. Fonts de pagament o amb llicència (motor intern, no dashboard)

Decisió del Jordi. Per ordre: aprofitar a fons SABI si ja hi ha accés; llicència de CaixaBank Research (consum amb targeta per sector); Alimarket (cens de superfícies amb m²); Idealista/data (lloguers de locals). Kantar i NielsenIQ, no ara.

---

## ICM per CCAA: sèrie en brut, no CVEC — no quadra amb Idescat

**Origen**: detectat 2026-08-02 comparant Catalunya/Balears (juny 2026) amb l'ICD d'Idescat (https://www.idescat.cat/pub/?id=icd).

**Problema**: `fetch_icm()` (`data/fetchers/ine.py:1042`, taules INE 60096/59787/60110/60111) usa la sèrie **en brut**, sense ajustar per estacionalitat i efecte calendari. Ho delata la pròpia magnitud: variació mensual de +4,4/+4,5% en un sol mes (Catalunya, juny 2026), impossible en una sèrie ja desestacionalitzada. Idescat, en canvi, publica per Catalunya la seva pròpia sèrie **CVEC** (corregida d'efectes estacionals i de calendari) i els números no coincideixen:

| Catalunya, juny 2026, sense estacions de servei | Nosaltres (brut) | Idescat (CVEC) |
|---|---|---|
| Real, interanual | −0,4% | −2,6% |
| Nominal, interanual | +1,9% | −0,2% |

**Inconsistència interna**: `fetch_icm_distribucion()` (taula INE 75809, usada a `pages/0b_ICM.py` pestanya 4, "modos de distribució") **sí** és CVEC — el nom de sèrie INE porta explícitament "Datos ajustados de estacionalidad y calendario". És a dir, dins el mateix dashboard convivim amb dues bases d'ajust diferents: la pestanya 3 (CCAA, `df_ccaa` a `pages/0b_ICM.py:397`) en brut, la pestanya 4 (modos) ajustada.

**Causa arrel**: l'INE no publica oficialment una taula CCAA ja desestacionalitzada (60110/60111 només donen la sèrie bruta). Idescat calcula el seu propi ajust regional; no és una taula pública reutilitzable directament via API INE.

**Opcions pendents de decidir**:
1. ~~Etiquetar la pestanya 3 (mapa CCAA) com "dades sense desestacionalitzar"~~ FET 2026-10-23: nota de l'exhibit i font diuen "sèrie original", amb l'avís que no és comparable amb l'ICD d'Idescat. Les opcions 2-4 continuen obertes.
2. Substituir per variació interanual únicament a la UI (pateix menys per calendari que la mensual, tot i no eliminar-lo del tot).
3. Explorar si Idescat exposa la seva sèrie CVEC via API pública reutilitzable (només Catalunya, no la resta de CCAA — no resoldria el rànquing sencer).
4. Aplicar un ajust propi (STL/X13 via `statsmodels`) — més feina i risc de introduir un mètode no oficial, a evitar si es pot.

**Nota**: el rànquing relatiu entre CCAA el mateix mes probablement es manté prou robust (l'efecte calendari és comú a totes), però el **valor exacte del percentatge** no s'ha de presentar com a comparable amb fonts CVEC (Idescat, premsa, Comertia).

---

## ~~Multi-idioma per subdomini~~ FET 2026-10-02

**Estat**: fet. Els redirects 301 de cPanel ja hi eren des del juliol, però l'app no llegia `?lang` i el subdomini català s'obria en castellà. Ara `setup_lang()` el llegeix a la primera càrrega de la sessió; després mana el selector. Sense paràmetre, el defecte segueix sent castellà (no `ca` com deia l'esquema d'aquí sota), que és el que vol el subdomini castellà, que redirigeix sense paràmetre.

**Objectiu**: quan un usuari entra per `observatorio-comercio.j3b3.com`, el dashboard ha de carregar en castellà; quan entra per `observatori-comerc.j3b3.com` (o `observatori-comerc.streamlit.app`), en català.

**Solució acordada — Opció A (query param al redirect 301):**

1. Configuració al hosting WordPress (htaccess o panel de redirects):
   - `observatorio-comercio.j3b3.com` → `301 https://observatori-comerc.streamlit.app/?lang=es`
   - `observatori-comerc.j3b3.com` → `301 https://observatori-comerc.streamlit.app/?lang=ca`

2. Canvi a `style.py:setup_lang()`: al primer load llegir `st.query_params.get("lang")` i, si val `ca` o `es`, escriure-ho a `st.session_state.lang` abans del selector manual. Esquema indicatiu:
   ```python
   if "lang" not in st.session_state:
       param = st.query_params.get("lang")
       st.session_state.lang = param if param in ("ca", "es") else "ca"
   ```

3. Validació local:
   - `streamlit run app.py` amb `?lang=es` → carregar pestanyes en castellà
   - `streamlit run app.py` amb `?lang=ca` → carregar pestanyes en català
   - Sense param → default `ca`

**Opcionals després del primer release**:
- Netejar el query param de la URL després del primer load amb `st.query_params.clear()` per UX més neta. Risc: si l'usuari recarrega dur perd la decisió i cau al default.
- Sincronitzar amb el selector manual perquè el canvi d'idioma manual actualitzi també el query param.

**Alternatives descartades**:
- Cookie al redirect via JS — cookies cross-domain entre `j3b3.com` i `streamlit.app` no funcionen.
- Dos deploys separats — Streamlit Cloud free plan permet només una app per repo public.
- CNAME directe amb Host header — Streamlit Cloud free no accepta custom domains.
- `document.referrer` — referrer-policy modern el suprimeix sovint, no fiable.

**Implementació**: 5-10 min canvis codi + verificació local + canvi a redirects WP. Commit separat (no barrejar amb feines de dades o UI).

---

## ~~Racionalitzar la navegació~~ FET 2026-06-13 (commit 1fe2a61)

**Origen**: diagnosi UX 2026-06-12.

- Fusionar `7_Europa.py` i `7_Comparativa_Europa.py` (solapament de contingut significatiu).
- Agrupar el sidebar en 4–5 blocs (ex: Pols · Radiografia · Europa · Anàlisi · Sobre nosaltres) amb capçaleres de secció.
- Afegir bloc d'orientació a `0_Inici.py` per a visitants nous ("si véns per primer cop, comença aquí").
- Eliminar el formulari de newsletter duplicat (apareix al sidebar i al footer).
- Completar el micro-copy en castellà que queda hardcoded fora del sistema i18n.

**Estimació**: 1 dia.

---

## Arquitectura d'informació v2

**Origen**: la nav de 2026-06-13 (7 seccions) tenia fronteres borroses (Pols/Radiografia/Anàlisi).

**Opció A — FET 2026-07-06** (working tree, pendent de desplegar): reagrupar+reanomenar a **6 seccions per pregunta del visitant** a `app.py`, sense fusionar pàgines ni canviar URLs:
- **L'actualitat**: Pols diari · ICM · El Pulso · Premsa
- **El sector**: PIB i VAB · Empreses · Ocupació · Productivitat · Subsectors
- **Canal i concentració**: E-commerce · Estructura · Líders
- **El territori**: Europa · Territori · Municipis (local)
- **Sobre**: Metodologia

**Opció B — pendent** (fer DINS el rollout premium, ~1-1,5 dia): fusionar pàgines afins via pestanyes per baixar de ~16 a ~11 pàgines:
- Pols diari + ICM → una sola pàgina "El pols del comerç" (pestanyes diari/mensual).
- Empreses + Ocupació + Productivitat → una "Empreses, ocupació i productivitat".
- E-commerce + Estructura → una "Consum i canal".
Canvia URLs → afegir redireccions o revisar enllaços interns/externs. Aprofitar per repensar cada pàgina fusionada amb el patró premium (no fer-ho dos cops).

---

## Capa comuna de dades (`data/loader.py`)

**Origen**: diagnosi arquitectura 2026-06-12.

Avui cada pàgina llegeix els CSV directament amb `pd.read_csv`. Crear `data/loader.py` amb una funció `load_dataset(name)` que totes les pàgines usin. Beneficis:
- Facilita reutilitzar el codi a l'Observatori Catalunya sense duplicar lògica.
- Punt únic per aplicar @st.cache_resource persistent (en lloc dels @st.cache_data per sessió actuals).
- Preparació per a una futura API de dades (canvi de `source="csv"` a `source="api"` sense tocar cap pàgina).

**Estimació**: mig dia.

**Corpus per al RAG** (afegit 2026-10-19): les dades geogràfiques de la Fase 3 ja porten `geo_codi` i `nota_trencament`. El primer pas tècnic pendent és fer de `data/loader.py` la capa d'accés unificada al corpus (DuckDB + parquet), que servirà d'entrada a la capa RAG. Avui el corpus només es consulta sèrie a sèrie amb `data/sql/query.py`. **Prioritat**: quan es reprengui la Fase 2.

---

## Territori: locals DIRCE (Fase 3, tancada 2026-10-19)

**Origen**: bloc de locals per província (T=301) i per CCAA × grup 471-479 (T=294), fusionat a main el 2026-09-27.

Pendent:
- **DIRCE en CNAE-2025** (edició prevista el desembre del 2026): afegir l'any de referència de la nova edició (previsiblement 2026) a `TRENCAMENTS_DIRCE` de `data/config.py` i tornar a mapejar els grups 471-479 amb la correspondència oficial CNAE-2025 / NACE Rev. 2.1. **Prioritat alta**: si s'oblida, la matriu de subsectors de la pestanya Territori quedarà desfasada.
- **Rànquing de variació provincial**: ajustar les etiquetes perquè no es creuin amb la línia de referència d'Espanya entre −1,7% i −2,3%. Prioritat baixa.
- **Trencament del 2023**: verificar-ne la causa quan l'INE en publiqui la nota metodològica i actualitzar el text de `data/config.py` (ara consta com a "canvi metodològic no verificat"). Prioritat baixa fins que surti la nota.

---

## Marges per branca des de l'Encuesta Anual de Comercio (INE)

**Estat**: Fase 1 FETA. Font localitzada i descarregada; queda el reg automàtic.

**Fet**: la font és l'**EEE Comercio / Encuesta Anual de Comercio** de l'INE, taula **76818** (Total Nacional, CNAE 47 a 3 dígits), que publica EBE i xifra de negoci per branca. El marge = EBE/xifra de negoci × 100. Creat `data/marges_branca_ine.csv` (branques 471–479 excepte 478, anys 2018–2024, `verificat=True`) via `ine.py::fetch_marges_branca()`, documentat a `data/marges_branca_ine.md`.

**Consumidors**: el pipeline de la newsletter (j3b3-newsletter) ja apunta `marges_origen` a `marges_branca_ine.csv`; l'estimació PATECO (`marges_branca.csv`) queda marcada com a substituïda.

**Reg automàtic**: FET. `processor.py::process_marges_branca()` (pas 7b de `process_all()`) regenera `data/cache/marges_branca_ine.csv` al workflow diari, mateix patró que EAS (reescriu si l'API torna dades, manté cache si falla). Vigilat a `DATASETS_VIGILATS` (bloc Novetats). El fitxer ha passat de `data/` arrel a `data/cache/`.

**Pendent**:
- ~~**Branca 478 (mercadillos)**~~ RESOLT 2026-10-23: l'INE sí la publica; faltava per un error de nom a `CNAE_47_API_NAMES` ("y en mercadillos"). Ara entra a `subsectors_eas` (pàgina Subsectors). Dels marges es descarta expressament (menys d'una persona ocupada per empresa: l'EBE inclou la remuneració del titular, 22,2% el 2024). Detall a `data/marges_branca_ine.md`.
- **Definició de marge**: l'INE dona EBE/vendes (gross operating rate); PATECO usa una definició pròpia que dona xifres més altes en algunes branques. Confirmar si per als lliurables interessa replicar la definició de PATECO (marge comercial brut vendes−compres) o mantenir la de l'INE.

---

## ~~Neteja tècnica~~ FET 2026-06-13 (commit 5a387f9)

**Origen**: diagnosi motor intern i arquitectura 2026-06-12.

- **Dependències mortes**: `streamlit-authenticator`, `bcrypt` i `pyyaml` estan a `requirements.txt` però no s'usen (vestigi d'un pla d'autenticació antic). Treure.
- **`icm.csv` a Parquet**: 13 MB → ~1 MB, càrrega inicial de sessió molt més ràpida. `pandas.read_parquet` és un canvi de dues línies.
- **Centralitzar codis de taula INE/Eurostat**: crear `DATA_SOURCES = {…}` a `data/config.py` amb tots els codis (ara dispersos per `fetchers/ine.py`, `processor.py` i pàgines). Quan INE retiri una taula, el canvi és en un sol lloc.
- **Codis de taula al commit message**: quan es canviï una taula, anotar-ho explícitament al missatge de commit per auditar l'historial.

**Estimació**: mig dia.

---

## Millores CSS per a mòbil (incremental)

**Origen**: diagnosi UX 2026-06-12.

Streamlit posa un sostre dur a la responsivitat. Millores realistes sense canviar de plataforma:
- Augmentar mida de font base a mòbil (`@media (max-width: 768px)`).
- Ocultar elements secundaris (subtítols de secció, notes metodològiques) a pantalles petites.
- Revisar que els gràfics Plotly tinguin `config={"responsive": True}` i alçada mínima adequada.

**Decisió prèvia necessària**: revisar l'analítica Plausible (quan estigui activa) per saber quant tràfic mòbil hi ha realment abans d'invertir-hi temps.

**Estimació**: mig dia, un cop hi hagi dades d'ús.

---

## Logo professional (decisió ajornada post-llançament)

**Estat**: bloquejat fins post 1 juny.

L'intent de logo "Observatorio del Comercio Minorista" del 2026-05-15 es va revertir tant al dashboard com al newsletter. Els assets generats (commit `b573c3b`) queden a `brand/` com a referència, però el producte no els usa ara mateix. La marca és tipogràfica fins que es prengui decisió posterior al llançament. No reactivar res relacionat amb el logo sense decisió explícita.

---

## Indicador Comertia: contrast intern (fet 2026-08-08, obert el que se'n derivi)

**Què hi ha**: `data/fetchers/comertia.py` (sèrie mensual de l'Indicador Comertia des de
les seves notes de premsa, via l'API de WordPress de comertia.net) i
`analisi/comertia_xcorr.py` (test de correlació creuada amb desfasaments contra l'ICM de
l'INE). Cap dels dos entra al pipeline diari.

**Regla de publicació**: les dades són de Comertia. La sortida va a `data/raw/comertia/`,
ignorat pel git, i el repo públic no conté cap xifra seva. Res d'això surt al dashboard
ni al newsletter sense permís explícit de Comertia.

**Resultat del test** (35 mesos, set. 2023 – jul. 2026): l'Indicador Comertia és
**coincident, no avançat**, contra el que ells afirmen als seus PDF. En primeres
diferències el màxim és a k=0 (r=+0,56 amb Espanya nominal, p=0,001) i a k=+1 cau a zero
o a negatiu; el test de Granger no li troba cap aportació sobre els retards propis de la
sèrie oficial; la direcció del canvi mensual coincideix el 70% dels mesos el mateix mes i
el 41-47% un mes després. El biaix de nivell mitjà contra les sèries nominals és zero:
el forat sistemàtic de ~2 punts contra les reals és tot efecte preus. El seu valor real
és el calendari, no la predicció: publiquen amb una mediana de 5 dies des del tancament
del mes, unes tres setmanes abans que l'INE.

**Pendents**:
1. ~~Refer el test quan surti l'ICM de juliol~~ **FET 2026-09-06**: sèrie i eix 1 refets
   amb juliol de 2026. Veure "Estat a 2026-09-06" aquí sota.
2. Els mesos sense nota de premsa s'omplen a mà a `data/raw/comertia/overrides.json`
   llegint el gràfic del PDF del mes següent. Cada mes nou, comprovar si cal.
3. Comertia revisa xifres sense avisar: algun mes el valor de la nota de premsa i el del
   gràfic del PDF del mes següent no coincideixen. Si mai es cita res, citar la nota de
   premsa, que és text i no píxel.
4. **Bloquejant si la col·laboració tira endavant**: el pendent de CVEC d'aquí sobre.
   El marc de referència de Comertia és Idescat, i la nostra sèrie catalana és bruta.

### Estat a 2026-09-06

**Comertia no publica cap nota de premsa des del 5 de juny de 2026** (verificat aquell
dia contra `wp-json/wp/v2/posts`, el RSS de `/feed/` i l'endpoint de cerca; també s'ha
comprovat que no hi ha cap tipus de contingut a part d'`entrades` i `socios`, o sigui que
no s'han mogut a un altre lloc del web). L'última és la del maig (+2,1%, publicada el
5 de juny) i el post més recent del web, de qualsevol mena, és aquell mateix. **El
fetcher funciona: les notes de juny i juliol no existeixen.** Per això aquests dos mesos
entren a `indicador_comertia.csv` amb `font=grafic_pdf` i sense data de publicació,
llegits del gràfic de l'`Indicador_Comertia_Juliol_2026.pdf`. Cobertura actual: 58 mesos
(2020-12 → 2026-07), 53 de nota de premsa i 5 de gràfic.

**El que s'ha aturat és el web, no l'Indicador.** Comprovat el 2026-09-06 a la premsa:
l'Indicador de juny (+6,7%) i el de juliol (+7,6%) han sortit publicats amb normalitat.
El de juliol el recullen ViaEmpresa, El Nacional (ON Economia) i Ràdio Balaguer el
**5 d'agost de 2026**, amb declaracions del president, Ignasi Pietx, i amb el detall
sectorial de sempre (oci i cultura +25,2%, equipament de la llar +14,4%) més absentisme
i vacants. O sigui que segueixen fent la nota i enviant-la als mitjans; el que han deixat
de fer és penjar-la al seu web. L'argument de les tres setmanes d'avantatge sobre l'INE
es manté dret.

Conseqüències per a la col·laboració:
- L'avantatge temporal segueix sent real, però **el canal que llegim ja no és el canal
  principal**. Si la sèrie ha de continuar, el fetcher haurà de sortir de
  `comertia.net` i llegir la repercussió a premsa (el feed `google_comertia` de
  `modules/press.py` ja la capta) o rebre el PDF directament d'ells, que és una de les
  coses que la col·laboració resoldria.
- Juny i juliol són píxel a `indicador_comertia.csv` (`font=grafic_pdf`), però els dos
  valors **es poden corroborar en text** amb els articles del 5 d'agost. Si mai es
  citen, citar la premsa i no el gràfic.
- **Agost de 2025 RESOLT (2026-10-02)**: es manté el 2,3. Els PDF de juliol i d'agost de 2026 el donen tots dos; el 2,7 d'El Punt Avui és l'única font discrepant.
- A 2026-09-06 **no consta enlloc l'Indicador de l'agost de 2026**, que per cadència
  (mediana de 5 dies) tocaria cap al 5 de setembre. Comprovar-ho abans del dia 15.

**Eix 1 refet amb juliol** (`analisi/comertia_posicio_competitiva.py`, finestra 2023-09 →
2026-07, 35 mesos): el diagnòstic no canvia de signe però es suavitza. Grans cadenes
+8,0% de mitjana contra +5,1% de Comertia; Comertia les bat en 8 de 35 mesos (abans 7 de
34: el juliol és un mes seu, +7,6% contra +6,4%). L'escletxa mesurada dins la finestra
passa de **2,7 a 2,1 punts** i l'encadenada pels tres anys mòbils, de 9,1 a 8,7. Part del
moviment ve de revisions de l'INE sobre el juny (grans cadenes 5,4 → 5,5; Catalunya
2,6 → 3,8). **Si es porta l'escletxa a un lliurable, cal actualitzar-la: la xifra vigent
és 2,1 punts, no 2,7.**

Avís de mètode sobre aquesta xifra: `index_relatiu()` encadena `I(t) = I(t−12)·(1+g(t))`,
o sigui dotze cadenes anuals paral·leles, una per mes de calendari. El valor terminal
depèn de quin mes tanca la finestra i es mou uns quants punts en canviar de mes sense que
hi hagi passat res. Presentar-lo tot sol el fa fràgil; si ha d'anar a un document, val més
acompanyar-lo d'una mitjana mòbil de dotze mesos del diferencial.

### Estat a 2026-10-02 (preparació de la reunió)

Reunió pendent de data amb **Elisabet Vilalta**, directora general (han acceptat parlar). Preparats l'argumentari (Word, OneDrive `OBSERVATORI/COMERTIA/`) i l'exemple interactiu (`analisi/comertia_demo_reunio.py` → `data/raw/comertia/exemple_interactiu_comertia.html`, amb còpia a la mateixa carpeta d'OneDrive). L'agost de 2026 (+5,2%) ve del PDF que va passar el Jordi; el PDF dona revisions sense avís de l'abril (7,2→7,4), el maig (2,1→1,5) i el juliol (7,6→6,8). `overrides.json` accepta ara entrades amb font i `substitueix` (el fetcher les aplica per sobre de la nota). Amb l'agost: diferencial MM12 contra grans cadenes −2,9 punts, negatiu els 25 mesos; contra petites cadenes, +4,2. **L'escletxa acumulada dins la finestra salta de 2,1 a 7,3 punts afegint un sol mes: no fer-la servir.**

**Gràfic de suport per a la reunió** (afegit 2026-09-06): `diferencial()` i
`_svg_diferencial()` a `analisi/comertia_posicio_competitiva.py` donen el diferencial
mensual contra les grans cadenes i la seva mitjana mòbil de dotze mesos, amb sortida a
`data/raw/comertia/diferencial_mm12.svg` i dues columnes noves a
`posicio_competitiva.csv`. És la lectura que no depèn de cap any base ni de quin mes
tanca la finestra. El que explica: 24 punts de mitjana mòbil i **els 24 per sota de
zero**; el forat es va tancar fins a −0,2 punts el maig del 2025 i s'ha tornat a obrir
fins a −4,1 el març del 2026, i ara és de −3,2. Que mai creuï el zero és el que aguanta
el diagnòstic quan un mes solt els va a favor, com el juliol (+1,2).
