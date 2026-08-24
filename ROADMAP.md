# Roadmap

**Domaine** : mix data engineering + BI (séries temporelles, SQL
dimensionnel, dashboard). Pas de machine learning ni de SIG dans le
cœur du projet.

**Objectif final** : pipeline reproductible (API → DuckDB → analyse) et
dashboard Streamlit avec une recommandation métier chiffrée. Power BI
en option, après le livrable Streamlit.

Périmètre validé : **couverture Belgique** (production renouvelable /
charge) + **zoom production Wallonie** vs météo. Période : **3 ans**.

- [x] Étape 1 — Socle du repo (package, config, structure `data/` / `sql/`)
- [x] Étape 2 — Ingestion Elia (charge, solaire, éolien historiques)
- [x] Étape 3 — Ingestion Copernicus ERA5 (rayonnement, vent, agrégés zone)
- [x] Étape 4 — Nettoyage des séries + schéma DuckDB (faits / dimensions)
- [ ] Étape 5 — Analyse des 4 questions métier (SQL + stats)
- [ ] Étape 6 — Dashboard Streamlit
- [ ] Étape 7 — README, recommandation, présentations portfolio
- [ ] Étape 8 *(optionnel)* — Power BI et/ou indicateur de risque réseau
