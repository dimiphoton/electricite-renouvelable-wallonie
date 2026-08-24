# Objectif du projet

- **But** : analyser, sur 3 ans, dans quelle mesure le solaire et l'éolien
  couvrent la charge électrique belge, et quels facteurs météorologiques
  expliquent le mieux la production renouvelable wallonne — jusqu'à une
  recommandation chiffrée pour un décideur métier, présentée dans un
  dashboard Streamlit.
- **Origine** : brief de portfolio data analyst
  (`brief/01-electricite-renouvelable-wallonie.md`), projet ancre.
- **Contraintes de départ** :
  - sources imposées : Elia Open Data (charge, solaire, éolien) et
    Copernicus CDS (réanalyses climatiques) ;
  - ingestion automatisée via API, pas de téléchargement manuel (hors
    clé Copernicus) ;
  - pas de SIG / traitement géospatial lourd — les variables météo sont
    des séries temporelles agrégées sur la Belgique ou la Wallonie ;
  - pas de modèle prédictif ML dans le cœur du projet ;
  - la charge Elia n'existe qu'au niveau belge : le taux de couverture
    production/charge se calcule à l'échelle Belgique ; la Wallonie est
    le zoom production + météo ;
  - livrable principal : dashboard Streamlit ; Power BI possible ensuite
    si le temps le permet.
