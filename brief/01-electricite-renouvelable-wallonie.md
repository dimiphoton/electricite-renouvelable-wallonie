# Analyse de la production renouvelable et de la charge électrique en Wallonie

*Projet ancre du portfolio — data analyst*

## Contexte et problématique

La Belgique accélère sa transition vers les énergies renouvelables, mais la production solaire et éolienne reste par nature intermittente et dépendante des conditions météorologiques. Pour un gestionnaire de réseau, un fournisseur d'énergie ou une intercommunale, comprendre le lien entre variabilité climatique, production renouvelable et charge du réseau est un enjeu opérationnel quotidien : anticiper les périodes de sur- ou sous-production, identifier les risques de tension sur le réseau.

Ce projet répond à une question simple mais centrale pour le secteur :

> Dans quelle mesure la production renouvelable belge couvre-t-elle la demande, et quels facteurs météorologiques expliquent le mieux les écarts observés ?

## Objectif

Construire une analyse de bout en bout — de l'ingestion des données brutes jusqu'à une recommandation exploitable — sur la relation entre production renouvelable, charge du réseau et variables climatiques.

## Compétences démontrées

- Ingestion de données via API (récupération automatisée, pas de téléchargement manuel)
- Nettoyage de séries temporelles à haute fréquence (valeurs manquantes, changements d'heure, unités)
- Modélisation en base SQL (tables faits/dimensions pour des séries temporelles)
- Requêtes SQL avec fenêtrage (moyennes mobiles, comparaisons période sur période)
- Analyse statistique (corrélation, décomposition saisonnière)
- Visualisation et dashboard interactif
- Storytelling et recommandation business

## Sources de données

- **Elia Open Data Portal** ([opendata.elia.be](https://opendata.elia.be)) : charge du réseau belge, production solaire et éolienne mesurée et prévisionnelle, historisées au quart d'heure.
- **Copernicus Climate Data Store** ([cds.climate.copernicus.eu](https://cds.climate.copernicus.eu)) : réanalyses climatiques (ensoleillement, vitesse du vent) sur la Belgique, utilisées comme variables explicatives — séries temporelles agrégées sur la zone belge/wallonne, sans traitement géospatial lourd (pas de SIG dans ce projet).

## Livrables attendus

1. Script(s) d'ingestion automatisée (Python) interrogeant les deux sources et stockant les données brutes.
2. Base de données (SQLite ou PostgreSQL) avec un schéma documenté.
3. Analyse répondant à 3-4 questions précises (ex. : la production solaire compense-t-elle les pics de charge estivaux ? quelle est la sensibilité de la production éolienne aux tempêtes ?).
4. Dashboard interactif (Power BI, Tableau Public ou Streamlit) présentant les KPI clés.
5. README avec contexte, méthodologie, limites, et une recommandation concrète formulée à destination d'un décideur métier.

## Structure de repo attendue

```
projet-electricite-wallonie/
├── README.md
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── ingestion.py
│   ├── clean.py
│   └── analysis.py
├── sql/
│   └── schema.sql
├── notebooks/
└── dashboard/
```

## Critères de qualité (definition of done)

- Le projet tourne de bout en bout sans intervention manuelle sur les données (hors clé API).
- Chaque visualisation du dashboard répond à une question explicite, formulée dans le README.
- Le README est compréhensible par quelqu'un qui ne connaît pas le secteur électrique.
- Au moins une conclusion est chiffrée et actionnable ("un décideur pourrait faire X sur base de Y").

## Pour aller plus loin (optionnel)

- Comparer plusieurs années pour évaluer une tendance de fond plutôt qu'un instantané.
- Ajouter un indicateur simple de "risque de tension réseau" basé sur l'écart production/charge.
