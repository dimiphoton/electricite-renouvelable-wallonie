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

*Étape 1 : cadrage, package, configuration*

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

![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) séries temporelles, prévu aux étapes nettoyage / analyse

---

## Métriques et justification

Pas encore calculées. Prévues :

- **Taux de couverture** = (PV + éolien) / charge, Belgique, par heure et saison
- **Corrélation** production wallonne vs rayonnement / vent ERA5
- **Complémentarité** solaire vs éolien (heure, saison)

Ces métriques répondent à une question métier ; ce ne sont pas des scores de modèle.

---

## Limites (déjà identifiées)

- Charge nationale seulement : pas de « la Wallonie couvre sa demande »
- Production Elia = *measured & upscaled*, pas du comptage validé
- Éolien offshore : écarts documentés par Elia sur 2018–2023
- ERA5 = réanalyse, pas des stations au sol

---

## Code

- [`config/settings.toml`](../../config/settings.toml) — période, datasets, bbox
- [`src/renewables_wallonia/config.py`](../../src/renewables_wallonia/config.py) — chargement typé
- [`src/renewables_wallonia/cli.py`](../../src/renewables_wallonia/cli.py) — `show-config`
