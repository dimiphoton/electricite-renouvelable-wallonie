# Journal de développement

## 2026-08-24 — Merge dans main

- `feature/readme-presentations` mergée dans `main` sans `.cursor/`.
- Pipeline, dashboard Streamlit, reco, README et présentations sont
  sur la branche publique.

## 2026-08-24 — Polish Streamlit

- `webapp/app.py` : question décideur en titre, trois cartes de cadrage
  (mesure, Belgique vs Wallonie, période), KPIs et reco encadrée,
  un insight par onglet.
- Graphiques Plotly : heatmap annotée, courbes saisonnières, profils
  d'été empilés vs charge, complémentarité horaire.

## 2026-08-24 — README, recommandation, présentations

- README public (EN) : quatre questions du dashboard, reco chiffrée,
  visuels, limites, reproduction.
- `docs/recommandation.md` : flex sur 16–19 h l'hiver (couverture
  19,6 %, 61 % des QH de stress), pas de PV extra pour les pics d'été.
- Quatre présentations Marp FR/EN (recruteur + technique), à jour du
  dashboard.

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
