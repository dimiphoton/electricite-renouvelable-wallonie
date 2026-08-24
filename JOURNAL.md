# Journal de développement

## 2026-08-24 — Dashboard Streamlit

- App `webapp/app.py` : une visualisation par question métier, plus
  une recommandation chiffrée (prioriser le flex 16–19 h l'hiver plutôt
  que du PV pour les pics d'été). CLI `dashboard`. Charts Plotly.
- Logique testée dans `src/renewables_wallonia/dashboard.py` (CSV
  d'analyse, repli DuckDB).

## 2026-08-24 — Analyse des 4 questions métier

- CLI `analyze` : SQL dans `sql/analysis/`, CSV dans
  `data/processed/analysis/`. Couverture moyenne 27,4 % ; midi d'été
  ~63 %, soir d'hiver ~19 %. Le PV suit les pics de midi en été
  (r = 0,64). Météo wallonne : r ≈ 0,92 (ssrd) et 0,88 (vent). Stress
  réseau rare (0,7 % des QH) et surtout hivernal.

## 2026-08-24 — Nettoyage et entrepôt DuckDB

- Schéma étoile (`sql/schema.sql`) : dim_datetime / région / source, faits
  charge, production, météo. Vue `v_belgium_qh`.
- Éolien : somme Elia+DSO par région, plus un total Belgique. Le solaire
  Belgique n'est pas resommé avec la Wallonie.
- ERA5 : ssrd converti en W/m² (accumulation horaire / 3600). Les NA Elia
  restent des NA.

## 2026-08-24 — Ingestion Elia et Copernicus

- CLI `ingest-elia` (CSV quart d'heure) et `ingest-copernicus` (ERA5
  mensuel, zip fusionné vent+rayonnement, moyenne spatiale Belgique /
  Wallonie).
- Données brutes gitignorées.

## 2026-08-24 — Socle du repo

- Package `renewables_wallonia`, config TOML, CLI `show-config`.
- Cadrage figé : couverture Belgique, zoom production Wallonie, DuckDB,
  Streamlit, 36 mois, pas de ML ni de SIG.
- Pas encore d'ingestion.

## 2026-08-24 — Initialisation du projet

- Repo créé à partir du template portfolio.
