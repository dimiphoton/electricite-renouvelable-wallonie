-- Q4 — Complémentarité solaire/éolien et creux production vs pics de charge.
-- Paramètres : $stress_load_quantile, $stress_renewable_quantile

-- name: complementarity_overall
SELECT
    CORR(solar_mw, wind_mw) AS corr_solar_wind,
    AVG(solar_mw / NULLIF(renewable_mw, 0)) AS solar_share_of_renewable,
    AVG(wind_mw / NULLIF(renewable_mw, 0)) AS wind_share_of_renewable
FROM v_belgium_qh
WHERE solar_mw IS NOT NULL AND wind_mw IS NOT NULL;

-- name: complementarity_by_season
SELECT
    d.season,
    CORR(v.solar_mw, v.wind_mw) AS corr_solar_wind,
    AVG(v.solar_mw / NULLIF(v.renewable_mw, 0)) AS solar_share_of_renewable,
    AVG(v.wind_mw / NULLIF(v.renewable_mw, 0)) AS wind_share_of_renewable
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
WHERE v.solar_mw IS NOT NULL AND v.wind_mw IS NOT NULL
GROUP BY d.season
ORDER BY d.season;

-- name: complementarity_wallonia
SELECT
    CORR(s.measured_mw, w.measured_mw) AS corr_solar_wind
FROM fact_generation AS s
JOIN fact_generation AS w
    ON s.datetime_utc = w.datetime_utc
    AND s.region = w.region
WHERE s.region = 'Wallonia'
  AND s.source = 'solar'
  AND w.source = 'wind';

-- name: stress_overall
-- Stress = charge dans le haut du classement ET renouvelable dans le bas.
WITH ranked AS (
    SELECT
        v.coverage_ratio,
        d.season,
        d.hour,
        PERCENT_RANK() OVER (ORDER BY v.load_mw) AS load_pct,
        PERCENT_RANK() OVER (ORDER BY v.renewable_mw) AS renewable_pct
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE v.coverage_ratio IS NOT NULL
)
SELECT
    COUNT(*) AS n_qh,
    COUNT(*) FILTER (
        WHERE load_pct >= $stress_load_quantile
          AND renewable_pct <= $stress_renewable_quantile
    ) AS n_stress,
    AVG((
        load_pct >= $stress_load_quantile
        AND renewable_pct <= $stress_renewable_quantile
    )::INTEGER) AS share_stress,
    AVG(
        CASE
            WHEN load_pct >= $stress_load_quantile
             AND renewable_pct <= $stress_renewable_quantile
            THEN coverage_ratio
        END
    ) AS mean_coverage_stress,
    AVG(
        CASE
            WHEN load_pct >= $stress_load_quantile
             AND renewable_pct <= $stress_renewable_quantile
            THEN hour
        END
    ) AS mean_hour_stress
FROM ranked;

-- name: stress_by_season
WITH ranked AS (
    SELECT
        v.coverage_ratio,
        d.season,
        PERCENT_RANK() OVER (PARTITION BY d.season ORDER BY v.load_mw) AS load_pct,
        PERCENT_RANK() OVER (PARTITION BY d.season ORDER BY v.renewable_mw) AS renewable_pct
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE v.coverage_ratio IS NOT NULL
)
SELECT
    season,
    AVG((
        load_pct >= $stress_load_quantile
        AND renewable_pct <= $stress_renewable_quantile
    )::INTEGER) AS share_stress,
    AVG(
        CASE
            WHEN load_pct >= $stress_load_quantile
             AND renewable_pct <= $stress_renewable_quantile
            THEN coverage_ratio
        END
    ) AS mean_coverage_stress
FROM ranked
GROUP BY season
ORDER BY season;

-- name: stress_by_hour
WITH ranked AS (
    SELECT
        v.coverage_ratio,
        d.hour,
        PERCENT_RANK() OVER (ORDER BY v.load_mw) AS load_pct,
        PERCENT_RANK() OVER (ORDER BY v.renewable_mw) AS renewable_pct
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE v.coverage_ratio IS NOT NULL
)
SELECT
    hour,
    COUNT(*) FILTER (
        WHERE load_pct >= $stress_load_quantile
          AND renewable_pct <= $stress_renewable_quantile
    ) AS n_stress,
    AVG(
        CASE
            WHEN load_pct >= $stress_load_quantile
             AND renewable_pct <= $stress_renewable_quantile
            THEN coverage_ratio
        END
    ) AS mean_coverage_stress
FROM ranked
GROUP BY hour
ORDER BY hour;
