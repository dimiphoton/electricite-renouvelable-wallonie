---
marp: true
theme: default
paginate: true
---

# Renewable generation vs load — technical

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*Steps 1–5: ingest, DuckDB, four SQL questions*

---

## Problem framing

Question: to what extent do solar and wind cover load, and which weather factors explain Walloon generation?

Elia constraint: load (`ods001`) has no regional grain. Coverage is computed at **Belgium** level. Wallonia is the production + weather zoom (`ods032`, `ods031`).

No ML, no GIS.

---

## Approach and methodology

Pipeline: APIs → immutable raw files → DuckDB (star schema) → window SQL (`PERCENT_RANK`, 7-day moving average) → Streamlit dashboard.

Period: 36 months. Summer peak = P90 of summer load. Stress = P90 load **and** P10 renewable. Daytime solar correlation if `ssrd > 10 W/m²`.

Assumption: never sum the Belgium grain with the Wallonia grain.

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white) portfolio language, `tomllib` in the stdlib

![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white) analytical SQL (`CORR`, windows), one file, no server

![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white) dashboard next (Power BI optional later)

![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) time-series cleaning (Elia 15-min, ERA5 hourly)

---

## Results (Sep 2023 – Aug 2026)

Mean coverage **27.4%** (summer 14:00: **62.9%**; winter 18:00: **18.8%**).

Summer peaks: solar ×3.2 vs off-peak, r(PV, load) = **0.64**. Daily load max ~12:00, solar ~13:00.

Wallonia: r(PV, ssrd) = **0.92** (daytime 0.87); r(wind, 10 m speed) = **0.88**.

PV/wind complementarity r = **−0.21**. Stress (P90×P10): **0.7%** of quarter-hours, 1.3% coverage, mostly winter — **0%** in summer.

---

## Limitations

- National load only: no “Wallonia covers its own demand”
- Elia generation is *measured & upscaled*, not validated metering
- Offshore wind: Elia-documented gaps in 2018–2023
- ERA5 is reanalysis (ends ~19 Aug 2026); 10 m wind, not hub height
- Peak/stress quantiles are conventions, not Elia grid thresholds

---

## Code

- [`sql/analysis/`](../../sql/analysis/) — four named questions
- [`src/renewables_wallonia/analysis.py`](../../src/renewables_wallonia/analysis.py) — `analyze`
- [`docs/analyse.md`](../analyse.md) — findings (French)
- [`sql/schema.sql`](../../sql/schema.sql) — star schema + `v_belgium_qh`
