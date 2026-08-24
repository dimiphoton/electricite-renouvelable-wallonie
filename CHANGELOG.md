# Changelog

## [Non publié]

- Analyse métier (`analyze`) : 4 questions SQL (couverture saison/heure,
  pics d'été, météo wallonne, complémentarité), synthèse dans
  `docs/analyse.md`.
- Entrepôt DuckDB (étoile) : `build-warehouse`, vue `v_belgium_qh`
  (taux de couverture Belgique, NA si une série manque).
- Ingestion Copernicus ERA5 : NetCDF mensuels + série horaire agrégée
  (`ingest-copernicus`), bbox Belgique puis moyenne Wallonie, sans SIG.
- Ingestion Elia : export CSV (charge, solaire, éolien) via
  `python -m renewables_wallonia.cli ingest-elia`, fichiers dans
  `data/raw/elia/` (idempotent, `--force` pour écraser).
- Socle du repo : package `renewables_wallonia`, configuration TOML,
  CLI (`show-config`), structure `data/` / `sql/`. Pas encore d'ingestion.
- Initialisation du projet à partir du template portfolio.
