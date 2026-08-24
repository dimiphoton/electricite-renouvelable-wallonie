# Changelog

## [Non publié]

- Dashboard Streamlit plus éditorial : problématique en une question,
  cartes de cadrage, reco encadrée, insights avant les graphiques.
  Figures Plotly retravaillées (heatmap annotée, profils saisonniers,
  aires empilées été, complémentarité).
- README (EN), recommandation métier (`docs/recommandation.md`) et
  quatre présentations Marp FR/EN : reco flex hivernal 16–19 h vs PV
  d'été, visuels heure × saison.
- Dashboard Streamlit (`webapp/app.py`, CLI `dashboard`) : une
  visualisation par question métier et une recommandation chiffrée
  (flex hivernal 16–19 h vs PV d'été). Plotly, lecture des CSV
  d'`analyze`.
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
