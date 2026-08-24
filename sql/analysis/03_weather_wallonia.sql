-- Q3 — Corrélation production wallonne vs ERA5 (PV ↔ ssrd, éolien ↔ vent 10 m).
-- Les séries Elia sont au quart d'heure : moyenne horaire avant jointure ERA5.
-- Paramètre : $daytime_ssrd_w_m2

-- name: wallonia_weather
WITH solar AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS solar_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'solar'
    GROUP BY 1
),
wind AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS wind_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'wind'
    GROUP BY 1
),
joined AS (
    SELECT
        s.solar_mw,
        wi.wind_mw,
        w.ssrd_w_m2,
        w.wind_speed_ms
    FROM fact_weather AS w
    JOIN solar AS s ON s.hour_utc = w.datetime_utc
    JOIN wind AS wi ON wi.hour_utc = w.datetime_utc
    WHERE w.region = 'Wallonia'
),
ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY solar_mw) AS solar_rank,
        RANK() OVER (ORDER BY ssrd_w_m2) AS ssrd_rank,
        RANK() OVER (ORDER BY wind_mw) AS wind_rank,
        RANK() OVER (ORDER BY wind_speed_ms) AS speed_rank
    FROM joined
)
SELECT
    COUNT(*) AS n_hours,
    CORR(solar_mw, ssrd_w_m2) AS corr_solar_ssrd,
    CORR(
        CASE WHEN ssrd_w_m2 > $daytime_ssrd_w_m2 THEN solar_mw END,
        CASE WHEN ssrd_w_m2 > $daytime_ssrd_w_m2 THEN ssrd_w_m2 END
    ) AS corr_solar_ssrd_day,
    CORR(solar_rank, ssrd_rank) AS spearman_solar_ssrd,
    CORR(wind_mw, wind_speed_ms) AS corr_wind_speed,
    CORR(wind_mw, POWER(wind_speed_ms, 3)) AS corr_wind_speed_cubed,
    CORR(wind_rank, speed_rank) AS spearman_wind_speed
FROM ranked;

-- name: wallonia_weather_by_season
WITH solar AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS solar_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'solar'
    GROUP BY 1
),
wind AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS wind_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'wind'
    GROUP BY 1
),
joined AS (
    SELECT
        d.season,
        s.solar_mw,
        wi.wind_mw,
        w.ssrd_w_m2,
        w.wind_speed_ms
    FROM fact_weather AS w
    JOIN dim_datetime AS d ON d.datetime_utc = w.datetime_utc
    JOIN solar AS s ON s.hour_utc = w.datetime_utc
    JOIN wind AS wi ON wi.hour_utc = w.datetime_utc
    WHERE w.region = 'Wallonia'
)
SELECT
    season,
    COUNT(*) AS n_hours,
    CORR(solar_mw, ssrd_w_m2) AS corr_solar_ssrd,
    CORR(
        CASE WHEN ssrd_w_m2 > $daytime_ssrd_w_m2 THEN solar_mw END,
        CASE WHEN ssrd_w_m2 > $daytime_ssrd_w_m2 THEN ssrd_w_m2 END
    ) AS corr_solar_ssrd_day,
    CORR(wind_mw, wind_speed_ms) AS corr_wind_speed
FROM joined
GROUP BY season
ORDER BY season;
