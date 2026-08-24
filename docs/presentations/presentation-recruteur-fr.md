---
marp: true
theme: default
paginate: true
---

# Électricité renouvelable en Belgique
## Zoom production Wallonie

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*Portfolio — étapes 1 à 4 : données dans DuckDB*

---

## Le problème

Le solaire et le vent ne produisent pas de façon régulière : tout dépend du ciel et du vent.

Un gestionnaire de réseau ou un fournisseur a besoin de savoir **quand** cette production couvre la consommation belge, et **pourquoi** elle varie — surtout en Wallonie.

---

## Les données

Les chiffres officiels du réseau électrique belge (Elia), au quart d'heure, plus la météo Copernicus. Pas de carte : on compare des courbes dans le temps.

La consommation n'est publiée que pour **toute la Belgique**. La Wallonie est le zoom sur la production, pas un taux de couverture régional.

---

## Le résultat

Les données sont dans une base prête à interroger (DuckDB) : consommation, solaire, éolien, météo.

Le tableau de bord et la recommandation chiffrée viennent ensuite. Un premier ordre de grandeur : sur la période, solaire + éolien couvrent en moyenne **environ 27 %** de la consommation belge (à nuancer à l'analyse).
