-- Esquema DuckDB per al chatbot de retail (base de dades de sèries temporals).
-- Format llarg/tidy: una fila per observació. Veure data/sql/series_registry.py
-- per la definició de cada sèrie i data/sql/migrate.py pel procés de migració.

CREATE TABLE IF NOT EXISTS series_metadata (
    serie_id     VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    description  VARCHAR NOT NULL,
    source       VARCHAR NOT NULL,   -- p.ex. "INE T=60096+59787+60110+60111" o "Eurostat ei_bsco_m"
    frequency    VARCHAR NOT NULL,   -- 'daily' | 'monthly' | 'quarterly' | 'annual'
    date_start   DATE,
    date_end     DATE,
    is_critical  BOOLEAN NOT NULL DEFAULT FALSE,
    is_derived   BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = model propi J3B3, no font externa
    is_public    BOOLEAN NOT NULL DEFAULT TRUE,   -- FALSE = no citable pel chatbot públic
    nota_trencament VARCHAR                       -- trencament de sèrie (p.ex. DIRCE 2023); NULL si no n'hi ha
);

-- Bases creades abans d'afegir nota_trencament (la de CI es regenera sencera).
ALTER TABLE series_metadata ADD COLUMN IF NOT EXISTS nota_trencament VARCHAR;

CREATE TABLE IF NOT EXISTS observations (
    serie_id      VARCHAR NOT NULL REFERENCES series_metadata(serie_id),
    date          DATE NOT NULL,
    frequency     VARCHAR NOT NULL,
    value         DOUBLE,
    unit          VARCHAR,
    dim_1         VARCHAR,           -- significat depen de serie_id (veure series_registry.py)
    dim_2         VARCHAR,
    dim_3         VARCHAR,           -- nomes ocupada per series amb 3 dimensions (p.ex. icm_*)
    source_table  VARCHAR,
    is_critical   BOOLEAN NOT NULL DEFAULT FALSE,
    is_derived    BOOLEAN NOT NULL DEFAULT FALSE,
    is_public     BOOLEAN NOT NULL DEFAULT TRUE,
    geo_codi      VARCHAR,           -- clau canònica de territori (dim_territori); veure data/sql/dimensions.py
    cnae_codi     VARCHAR            -- clau canònica de branca (dim_branca); NULL si la sèrie no és d'una branca
);

ALTER TABLE observations ADD COLUMN IF NOT EXISTS geo_codi VARCHAR;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS cnae_codi VARCHAR;
-- Avisos de qualitat de l'observació: codis de dim_avis separats per comes, NULL si cap.
-- Els derivats hereten la unió dels avisos de les observacions que fan servir.
ALTER TABLE observations ADD COLUMN IF NOT EXISTS avis VARCHAR;

CREATE TABLE IF NOT EXISTS dim_avis (
    avis_codi VARCHAR PRIMARY KEY,
    text      VARCHAR NOT NULL
);

-- Derivats (is_derived): com es calculen i de quines sèries surten.
ALTER TABLE series_metadata ADD COLUMN IF NOT EXISTS formula VARCHAR;
ALTER TABLE series_metadata ADD COLUMN IF NOT EXISTS fonts_origen VARCHAR;

CREATE INDEX IF NOT EXISTS idx_obs_serie_date ON observations(serie_id, date);

-- Claus comunes per creuar fonts (contingut a data/sql/dimensions.py).
CREATE TABLE IF NOT EXISTS dim_territori (
    geo_codi      VARCHAR PRIMARY KEY,   -- pais:ES, agr:EU27_2020, ccaa:09, prov:08
    nivell        VARCHAR NOT NULL,      -- 'pais' | 'agregat' | 'ccaa' | 'provincia'
    nom           VARCHAR NOT NULL,
    geo_pare      VARCHAR,               -- província -> CCAA -> pais:ES
    codi_ine      VARCHAR,
    codi_eurostat VARCHAR
);

-- Motor de fets (data/sql/fets.py): es regenera sencera a cada migració.
CREATE TABLE IF NOT EXISTS fets (
    fet_id           VARCHAR PRIMARY KEY,  -- regla:serie:territori:branca, estable entre migracions
    regla            VARCHAR NOT NULL,     -- extrem | ratxa | inflexio | ranking | divergencia | quadrant_branca | saturacio
    enunciat         VARCHAR NOT NULL,
    valor            DOUBLE,
    unitat           VARCHAR,
    comparacio       VARCHAR,              -- amb què es compara el valor, en text
    valor_referencia DOUBLE,
    data             DATE NOT NULL,        -- període del darrer valor que sosté el fet
    series           VARCHAR NOT NULL,     -- serie_id d'origen, separats per comes
    geo_codi         VARCHAR,
    cnae_codi        VARCHAR,
    avis             VARCHAR,              -- codis de dim_avis heretats, separats per comes
    rellevancia      DOUBLE                -- ordre orientatiu entre fets
);

CREATE TABLE IF NOT EXISTS dim_branca (
    cnae_codi     VARCHAR PRIMARY KEY,   -- G, 47, 471, 4711, 47_ALIM...
    nivell        VARCHAR NOT NULL,      -- 'seccio' | 'divisio' | 'grup' | 'classe' | 'agregat_icm'
    nom           VARCHAR NOT NULL,
    cnae_pare     VARCHAR
);
