---
marp: true
theme: default
paginate: true
---

# Production renouvelable vs charge — technique

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*Étapes 1–4 : ingestion, nettoyage, DuckDB*

---

## Cadrage du problème

Question : dans quelle mesure le solaire et l'éolien couvrent-ils la charge, et quels facteurs météo expliquent la production wallonne ?

Contrainte Elia : la charge (`ods001`) n'a pas de maille régionale. Le taux de couverture se calcule à l'échelle **Belgique**. La Wallonie est le zoom production + météo (`ods032`, `ods031`).

Pas de ML, pas de SIG.

---

## Approche et méthodologie

Pipeline : API → fichiers bruts intouchables → DuckDB (étoile) → SQL à fenêtres → dashboard Streamlit.

Période : 36 mois (`config/settings.toml`). Timestamps stockés en UTC, affichés en `Europe/Brussels`.

Hypothèse : on ne somme jamais la maille Belgique et la maille Wallonie (le solaire belge inclut déjà la Wallonie).

---

## Stack technique

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white) langage du portfolio, `tomllib` en stdlib

![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white) SQL analytique, un fichier, pas de serveur (vs SQLite trop limité / PostgreSQL inutile sans SIG)

![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white) dashboard reproductible dans le repo (Power BI possible plus tard)

![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) nettoyage des séries (quart d'heure Elia, heure ERA5)

---

## Métriques et justification

Vue SQL `v_belgium_qh` : **taux de couverture** = (PV + éolien) / charge, NA si une série manque.

Contrôle de sanity (pas encore l'analyse métier) : moyenne ~27 %, max ~108 % (le renouvelable peut dépasser la charge à certains quarts d'heure).

Reste à calculer : corrélation météo wallonne, complémentarité solaire/éolien par saison.

---

## Limites (déjà identifiées)

- Charge nationale seulement : pas de « la Wallonie couvre sa demande »
- Production Elia = *measured & upscaled*, pas du comptage validé
- Éolien offshore : écarts documentés par Elia sur 2018–2023
- ERA5 = réanalyse, pas des stations au sol

---

## Code

- [`sql/schema.sql`](../../sql/schema.sql) — étoile + `v_belgium_qh`
- [`src/renewables_wallonia/data/clean.py`](../../src/renewables_wallonia/data/clean.py) — nettoyage
- [`src/renewables_wallonia/data/warehouse.py`](../../src/renewables_wallonia/data/warehouse.py) — `build-warehouse`
- [`src/renewables_wallonia/cli.py`](../../src/renewables_wallonia/cli.py) — ingest + entrepôt
