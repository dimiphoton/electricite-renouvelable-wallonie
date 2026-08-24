# Changelog

## [Non publié]

- Ingestion Copernicus ERA5 : NetCDF mensuels + série horaire agrégée
  (`ingest-copernicus`), bbox Belgique puis moyenne Wallonie, sans SIG.
- Ingestion Elia : export CSV (charge, solaire, éolien) via
  `python -m renewables_wallonia.cli ingest-elia`, fichiers dans
  `data/raw/elia/` (idempotent, `--force` pour écraser).
- Socle du repo : package `renewables_wallonia`, configuration TOML,
  CLI (`show-config`), structure `data/` / `sql/`. Pas encore d'ingestion.
- Initialisation du projet à partir du template portfolio.
