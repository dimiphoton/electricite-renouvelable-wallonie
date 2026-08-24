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

*Étapes 1–5 : ingestion, DuckDB, 4 questions SQL*

---

## Cadrage du problème

Question : dans quelle mesure le solaire et l'éolien couvrent-ils la charge, et quels facteurs météo expliquent la production wallonne ?

Contrainte Elia : la charge (`ods001`) n'a pas de maille régionale. Le taux de couverture se calcule à l'échelle **Belgique**. La Wallonie est le zoom production + météo (`ods032`, `ods031`).

Pas de ML, pas de SIG.

---

## Approche et méthodologie

Pipeline : API → fichiers bruts intouchables → DuckDB (étoile) → SQL à fenêtres (`PERCENT_RANK`, moyenne mobile 7 jours) → dashboard Streamlit.

Période : 36 mois. Pic d'été = P90 de la charge estivale. Stress = P90 charge **et** P10 renouvelable. Corrélation solaire « de jour » si `ssrd > 10 W/m²`.

Hypothèse : on ne somme jamais la maille Belgique et la maille Wallonie.

---

## Stack technique

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white) langage du portfolio, `tomllib` en stdlib

![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white) SQL analytique (`CORR`, fenêtres), un fichier, pas de serveur

![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white) dashboard à venir (Power BI possible plus tard)

![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white) nettoyage des séries (quart d'heure Elia, heure ERA5)

---

## Résultats (sept. 2023 – août 2026)

Couverture moyenne **27,4 %** (midi d'été 14 h : **62,9 %** ; soir d'hiver 18 h : **18,8 %**).

Pics d'été : solaire ×3,2 vs hors pic, r(PV, charge) = **0,64**. Max journalier de charge ~12 h, solaire ~13 h.

Wallonie : r(PV, ssrd) = **0,92** (jour 0,87) ; r(éolien, vent 10 m) = **0,88**.

Complémentarité PV/éolien r = **−0,21**. Stress (P90×P10) : **0,7 %** des QH, couverture 1,3 %, surtout hiver — **0 %** en été.

---

## Limites

- Charge nationale seulement : pas de « la Wallonie couvre sa demande »
- Production Elia = *measured & upscaled*, pas du comptage validé
- Éolien offshore : écarts documentés par Elia sur 2018–2023
- ERA5 = réanalyse (arrêt ~19 août 2026), vent à 10 m pas à hauteur de moyeu
- Quantiles de pic/stress = conventions, pas des seuils réseau Elia

---

## Code

- [`sql/analysis/`](../../sql/analysis/) — 4 questions nommées
- [`src/renewables_wallonia/analysis.py`](../../src/renewables_wallonia/analysis.py) — `analyze`
- [`docs/analyse.md`](../analyse.md) — findings
- [`sql/schema.sql`](../../sql/schema.sql) — étoile + `v_belgium_qh`
