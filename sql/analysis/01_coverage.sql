-- Q1 — Taux de couverture belge selon l'heure et la saison.
-- Paramètres : $coverage_mid_threshold, $coverage_high_threshold

-- name: coverage_overall
SELECT
    COUNT(*) AS n_qh,
    COUNT(coverage_ratio) AS n_coverage,
    AVG(coverage_ratio) AS mean_coverage,
    MEDIAN(coverage_ratio) AS median_coverage,
    QUANTILE_CONT(coverage_ratio, 0.1) AS p10_coverage,
    QUANTILE_CONT(coverage_ratio, 0.9) AS p90_coverage,
    MIN(coverage_ratio) AS min_coverage,
    MAX(coverage_ratio) AS max_coverage,
    AVG((coverage_ratio > $coverage_mid_threshold)::INTEGER) AS share_above_mid,
    AVG((coverage_ratio > $coverage_high_threshold)::INTEGER) AS share_above_high
FROM v_belgium_qh;

-- name: coverage_by_season
SELECT
    d.season,
    COUNT(*) AS n_qh,
    AVG(v.coverage_ratio) AS mean_coverage,
    MEDIAN(v.coverage_ratio) AS median_coverage,
    QUANTILE_CONT(v.coverage_ratio, 0.1) AS p10_coverage,
    QUANTILE_CONT(v.coverage_ratio, 0.9) AS p90_coverage,
    AVG(v.load_mw) AS mean_load_mw,
    AVG(v.solar_mw) AS mean_solar_mw,
    AVG(v.wind_mw) AS mean_wind_mw
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
GROUP BY d.season
ORDER BY d.season;

-- name: coverage_by_hour_season
SELECT
    d.season,
    d.hour,
    AVG(v.coverage_ratio) AS mean_coverage,
    AVG(v.load_mw) AS mean_load_mw,
    AVG(v.solar_mw) AS mean_solar_mw,
    AVG(v.wind_mw) AS mean_wind_mw
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
GROUP BY d.season, d.hour
ORDER BY d.season, d.hour;

-- name: coverage_by_weekend
SELECT
    d.is_weekend,
    AVG(v.coverage_ratio) AS mean_coverage,
    MEDIAN(v.coverage_ratio) AS median_coverage
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
GROUP BY d.is_weekend
ORDER BY d.is_weekend;

-- name: coverage_daily_ma7
-- Moyenne mobile 7 jours de la couverture journalière (fenêtre SQL).
WITH daily AS (
    SELECT
        d.date_brussels,
        AVG(v.coverage_ratio) AS coverage
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE v.coverage_ratio IS NOT NULL
    GROUP BY d.date_brussels
)
SELECT
    date_brussels,
    coverage,
    AVG(coverage) OVER (
        ORDER BY date_brussels
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS coverage_ma7
FROM daily
ORDER BY date_brussels;
