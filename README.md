# Renewable generation and electricity load in Belgium (Wallonia zoom)

| | |
|---|---|
| **Stack** | ![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white) ![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white) ![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white) ![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) |
| **Level** | Intermediate *(proposed — to confirm)* |
| **Data specialty** | BI / Data engineering |

## Objective

Measure how Belgian solar and wind generation covers national electricity load, and which weather factors best explain **Walloon** renewable output. The end product is a reproducible pipeline (APIs → DuckDB → analysis) and a Streamlit dashboard with a numbered recommendation for an energy-sector decision maker.

Elia publishes load at **Belgium** level only. Coverage (generation / load) is therefore national. Wallonia is the production and weather zoom, not a regional coverage ratio.

## Data

- **Elia Open Data** (no API key): historical 15-minute series — total load (`ods001`), solar (`ods032`), wind (`ods031`). Period: Sep 2023 – Aug 2026 (36 months, editable in `config/settings.toml`).
- **Copernicus ERA5** (CDS account + `~/.cdsapirc`): solar radiation and 10 m wind, spatially averaged over Belgium / Wallonia — no GIS.

Elia: `python -m renewables_wallonia.cli ingest-elia`
Copernicus: `python -m renewables_wallonia.cli ingest-copernicus` (queued; one NetCDF per month, resumable).
Warehouse: `python -m renewables_wallonia.cli build-warehouse` (DuckDB star schema in `data/processed/warehouse.duckdb`).
Analysis: `python -m renewables_wallonia.cli analyze` (four SQL questions → `data/processed/analysis/`). Write-up: [`docs/analyse.md`](docs/analyse.md).
Dashboard: `python -m renewables_wallonia.cli dashboard` (Streamlit).

## Result

On Sep 2023 – Aug 2026, solar + wind cover **27%** of Belgian load on average (median 24%). A summer midday hour reaches **~63%**; a winter evening hour **~19%**. Summer load peaks around noon and solar follows them; the tight hours are winter late afternoons (coverage ~1% on 0.7% of quarter-hours). Walloon PV and wind track ERA5 radiation and 10 m wind closely (r ≈ 0.92 and 0.88).

**Recommendation (dashboard):** put flexibility (demand, storage, imports) on the **winter 16–19 h** slot rather than extra PV for summer peaks. Streamlit: `python -m renewables_wallonia.cli dashboard`.

Write-up (French): [`docs/analyse.md`](docs/analyse.md).

## Reproduce

```bash
pip install -e ".[dev]"
python -m renewables_wallonia.cli --help
python -m renewables_wallonia.cli show-config
python -m renewables_wallonia.cli ingest-elia
python -m renewables_wallonia.cli ingest-copernicus
python -m renewables_wallonia.cli build-warehouse
python -m renewables_wallonia.cli analyze
python -m renewables_wallonia.cli dashboard
pytest
```

`ingest-elia` and `ingest-copernicus` write into `data/` (gitignored). Re-run with `--force` to replace files. Copernicus needs a CDS token in `%USERPROFILE%\.cdsapirc` and can sit in a queue for several minutes per month.

## Repo structure

```
config/settings.toml     # period, Elia datasets, ERA5 bbox — nothing hardcoded
data/raw/                # untouched API extracts (gitignored)
data/processed/          # era5_hourly.csv, warehouse.duckdb, analysis/ (gitignored)
sql/schema.sql           # DuckDB star schema + v_belgium_qh
sql/analysis/            # named SQL for the four business questions
src/renewables_wallonia/ # package (CLI + config + analysis + dashboard)
webapp/app.py            # Streamlit dashboard
tests/
```

See `ROADMAP.md` and `JOURNAL.md` (French, like the rest of the codebase).

## Presentations

- [Recruiter overview (EN)](docs/slides/presentation-recruteur-en.html)
- [Technical deep dive (EN)](docs/slides/presentation-technique-en.html)
- [Présentation grand public (FR)](docs/slides/presentation-recruteur-fr.html)
- [Présentation technique (FR)](docs/slides/presentation-technique-fr.html)
