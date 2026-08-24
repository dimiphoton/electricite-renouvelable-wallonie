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

*Step 1: framing, package, configuration*

---

## Problem framing

Question: to what extent do solar and wind cover load, and which weather factors explain Walloon generation?

Elia constraint: load (`ods001`) has no regional grain. Coverage is computed at **Belgium** level. Wallonia is the production + weather zoom (`ods032`, `ods031`).

No ML, no GIS.

---

## Approach and methodology

Pipeline: APIs → immutable raw files → DuckDB (star schema) → window SQL → Streamlit dashboard.

Period: 36 months (`config/settings.toml`). Timestamps stored in UTC, displayed in `Europe/Brussels`.

Assumption: never sum the Belgium grain with the Wallonia grain (Belgian solar already includes Wallonia).

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white) portfolio language, `tomllib` in the stdlib

![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white) analytical SQL, one file, no server (vs SQLite too limited / PostgreSQL pointless without GIS)

![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white) reproducible in-repo dashboard (Power BI optional later)

![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) time series, planned for cleaning / analysis

---

## Metrics and rationale

Not computed yet. Planned:

- **Coverage ratio** = (PV + wind) / load, Belgium, by hour and season
- **Correlation** of Walloon generation vs ERA5 radiation / wind
- **Complementarity** of solar vs wind (hour, season)

These answer a business question; they are not model scores.

---

## Limitations (already known)

- National load only: no “Wallonia covers its own demand”
- Elia generation is *measured & upscaled*, not validated metering
- Offshore wind: Elia-documented gaps in 2018–2023
- ERA5 is reanalysis, not ground stations

---

## Code

- [`config/settings.toml`](../../config/settings.toml) — period, datasets, bbox
- [`src/renewables_wallonia/config.py`](../../src/renewables_wallonia/config.py) — typed loader
- [`src/renewables_wallonia/cli.py`](../../src/renewables_wallonia/cli.py) — `show-config`
