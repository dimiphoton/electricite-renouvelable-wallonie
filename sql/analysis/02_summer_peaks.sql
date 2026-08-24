-- Q2 — Le solaire coïncide-t-il avec les pics de charge d'été ?
-- Paramètre : $peak_load_quantile (PERCENT_RANK de load_mw en été).

-- name: summer_peaks
WITH summer AS (
    SELECT
        v.load_mw,
        v.solar_mw,
        v.wind_mw,
        v.coverage_ratio,
        d.hour
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE d.season = 'summer'
      AND v.load_mw IS NOT NULL
      AND v.solar_mw IS NOT NULL
      AND v.wind_mw IS NOT NULL
),
ranked AS (
    SELECT
        *,
        PERCENT_RANK() OVER (ORDER BY load_mw) AS load_pct
    FROM summer
)
SELECT
    AVG(CASE WHEN load_pct >= $peak_load_quantile THEN solar_mw END) AS solar_mw_peak,
    AVG(CASE WHEN load_pct < $peak_load_quantile THEN solar_mw END) AS solar_mw_offpeak,
    AVG(CASE WHEN load_pct >= $peak_load_quantile THEN wind_mw END) AS wind_mw_peak,
    AVG(CASE WHEN load_pct < $peak_load_quantile THEN wind_mw END) AS wind_mw_offpeak,
    AVG(CASE WHEN load_pct >= $peak_load_quantile THEN load_mw END) AS load_mw_peak,
    AVG(CASE WHEN load_pct < $peak_load_quantile THEN load_mw END) AS load_mw_offpeak,
    AVG(CASE WHEN load_pct >= $peak_load_quantile THEN solar_mw / NULLIF(load_mw, 0) END)
        AS solar_load_share_peak,
    AVG(CASE WHEN load_pct < $peak_load_quantile THEN solar_mw / NULLIF(load_mw, 0) END)
        AS solar_load_share_offpeak,
    AVG(CASE WHEN load_pct >= $peak_load_quantile THEN coverage_ratio END) AS coverage_peak,
    AVG(CASE WHEN load_pct < $peak_load_quantile THEN coverage_ratio END) AS coverage_offpeak,
    CORR(solar_mw, load_mw) AS corr_solar_load,
    CORR(wind_mw, load_mw) AS corr_wind_load
FROM ranked;

-- name: solar_load_corr_by_season
SELECT
    d.season,
    CORR(v.solar_mw, v.load_mw) AS corr_solar_load,
    CORR(v.wind_mw, v.load_mw) AS corr_wind_load
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
WHERE v.solar_mw IS NOT NULL
  AND v.wind_mw IS NOT NULL
  AND v.load_mw IS NOT NULL
GROUP BY d.season
ORDER BY d.season;

-- name: summer_daily_peak_coincidence
-- Heure (Bruxelles) du max journalier de charge vs du max solaire.
WITH summer AS (
    SELECT
        v.load_mw,
        v.solar_mw,
        d.date_brussels,
        d.hour
    FROM v_belgium_qh AS v
    JOIN dim_datetime AS d USING (datetime_utc)
    WHERE d.season = 'summer'
      AND v.load_mw IS NOT NULL
      AND v.solar_mw IS NOT NULL
),
daily AS (
    SELECT
        date_brussels,
        ARG_MAX(hour, load_mw) AS hour_max_load,
        ARG_MAX(hour, solar_mw) AS hour_max_solar
    FROM summer
    GROUP BY date_brussels
)
SELECT
    COUNT(*) AS n_days,
    AVG((hour_max_load = hour_max_solar)::INTEGER) AS share_same_hour,
    AVG(ABS(hour_max_load - hour_max_solar)) AS mean_abs_hour_gap,
    MEDIAN(ABS(hour_max_load - hour_max_solar)) AS median_abs_hour_gap,
    AVG(hour_max_load) AS mean_hour_max_load,
    AVG(hour_max_solar) AS mean_hour_max_solar
FROM daily;

-- name: summer_hour_band
SELECT
    CASE
        WHEN d.hour BETWEEN 11 AND 15 THEN 'midday'
        WHEN d.hour BETWEEN 17 AND 20 THEN 'evening'
        ELSE 'other'
    END AS hour_band,
    AVG(v.load_mw) AS mean_load_mw,
    AVG(v.solar_mw) AS mean_solar_mw,
    AVG(v.wind_mw) AS mean_wind_mw,
    AVG(v.coverage_ratio) AS mean_coverage
FROM v_belgium_qh AS v
JOIN dim_datetime AS d USING (datetime_utc)
WHERE d.season = 'summer'
GROUP BY 1
ORDER BY 1;
