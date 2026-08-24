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
![Plotly](https://img.shields.io/badge/Plotly-charts-3F4F75?logo=plotly&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*Pipeline API → analyse → dashboard, avec une reco chiffrée*

---

## Le problème

Le solaire et le vent ne produisent pas de façon régulière : tout dépend du ciel et du vent.

Un gestionnaire de réseau ou un fournisseur a besoin de savoir **quand** cette production couvre la consommation belge — et **où placer le prochain effort**, plutôt que d'ajouter du solaire au hasard.

---

## Les données

Les chiffres officiels du réseau belge (Elia), au quart d'heure, plus la météo Copernicus. Pas de carte : on compare des courbes dans le temps.

La consommation n'est publiée que pour **toute la Belgique**. La Wallonie est le zoom sur la production, pas un taux de couverture régional.

---

## Le résultat (3 ans)

Solaire + éolien couvrent en moyenne **27 %** de la consommation belge.

Le midi d'été est déjà bien couvert. Le trou, c'est le **début de soirée en hiver**.

![w:1050](../../pictures/presentations/couverture-heure-saison.png)

---

## Recommandation

Mettre la flexibilité (déplacer la demande, stocker, importer) sur le créneau **16 h–19 h en hiver**, pas un surplus de panneaux pour les pics d'été.

![w:1050](../../pictures/presentations/recommandation-hiver.png)

Dashboard : `python -m renewables_wallonia.cli dashboard`
