-- Schéma DuckDB (étoile). Recréé à chaque `build-warehouse`.
-- Timestamps stockés en UTC. La saison et le week-end suivent l'heure de Bruxelles.

DROP VIEW IF EXISTS v_belgium_qh;
DROP TABLE IF EXISTS fact_weather;
DROP TABLE IF EXISTS fact_generation;
DROP TABLE IF EXISTS fact_load;
DROP TABLE IF EXISTS dim_datetime;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_source;

CREATE TABLE dim_region (
    region VARCHAR PRIMARY KEY
);

CREATE TABLE dim_source (
    source VARCHAR PRIMARY KEY
);

CREATE TABLE dim_datetime (
    datetime_utc TIMESTAMPTZ PRIMARY KEY,
    datetime_brussels TIMESTAMP NOT NULL,
    date_brussels DATE NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    season VARCHAR NOT NULL
);

CREATE TABLE fact_load (
    datetime_utc TIMESTAMPTZ NOT NULL,
    region VARCHAR NOT NULL,
    load_mw DOUBLE,
    dayahead_mw DOUBLE,
    PRIMARY KEY (datetime_utc, region),
    FOREIGN KEY (datetime_utc) REFERENCES dim_datetime (datetime_utc),
    FOREIGN KEY (region) REFERENCES dim_region (region)
);

CREATE TABLE fact_generation (
    datetime_utc TIMESTAMPTZ NOT NULL,
    region VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    measured_mw DOUBLE,
    dayahead_mw DOUBLE,
    capacity_mw DOUBLE,
    load_factor DOUBLE,
    PRIMARY KEY (datetime_utc, region, source),
    FOREIGN KEY (datetime_utc) REFERENCES dim_datetime (datetime_utc),
    FOREIGN KEY (region) REFERENCES dim_region (region),
    FOREIGN KEY (source) REFERENCES dim_source (source)
);

CREATE TABLE fact_weather (
    datetime_utc TIMESTAMPTZ NOT NULL,
    region VARCHAR NOT NULL,
    ssrd_j_m2 DOUBLE,
    ssrd_w_m2 DOUBLE,
    u10_ms DOUBLE,
    v10_ms DOUBLE,
    wind_speed_ms DOUBLE,
    PRIMARY KEY (datetime_utc, region),
    FOREIGN KEY (datetime_utc) REFERENCES dim_datetime (datetime_utc),
    FOREIGN KEY (region) REFERENCES dim_region (region)
);

-- Couverture Belgique au quart d'heure : NULL si charge, solaire ou éolien manquant.
CREATE VIEW v_belgium_qh AS
SELECT
    load.datetime_utc,
    load.load_mw,
    solar.measured_mw AS solar_mw,
    wind.measured_mw AS wind_mw,
    CASE
        WHEN solar.measured_mw IS NULL OR wind.measured_mw IS NULL
            THEN NULL
        ELSE solar.measured_mw + wind.measured_mw
    END AS renewable_mw,
    CASE
        WHEN load.load_mw IS NULL OR load.load_mw = 0
            OR solar.measured_mw IS NULL OR wind.measured_mw IS NULL
            THEN NULL
        ELSE (solar.measured_mw + wind.measured_mw) / load.load_mw
    END AS coverage_ratio
FROM fact_load AS load
LEFT JOIN fact_generation AS solar
    ON solar.datetime_utc = load.datetime_utc
    AND solar.region = 'Belgium'
    AND solar.source = 'solar'
LEFT JOIN fact_generation AS wind
    ON wind.datetime_utc = load.datetime_utc
    AND wind.region = 'Belgium'
    AND wind.source = 'wind'
WHERE load.region = 'Belgium';
