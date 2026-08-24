# Décisions

| Date | Décision | Alternative envisagée | Raison |
|---|---|---|---|
| 2026-08-24 | Couverture production/charge à l'échelle **Belgique**, zoom production **Wallonie** vs météo | Tout Wallonie, ou tout Belgique | La charge Elia (`ods001`) n'a pas de maille régionale ; solaire (`ods032`) et éolien (`ods031`) ont un champ `region` Wallonia. Calculer un taux de couverture wallon serait méthodologiquement faux. |
| 2026-08-24 | **DuckDB** comme base d'analyse | SQLite (plus universel) ou PostgreSQL (plus « prod ») | Pas de SIG prévu (brief). DuckDB reste un fichier local, sans serveur, et est plus confortable que SQLite pour le SQL analytique (fenêtres, parquet). PostgreSQL n'apporterait de la valeur que pour du géospatial. |
| 2026-08-24 | Dashboard **Streamlit** en livrable principal ; Power BI ensuite si le temps le permet | Power BI d'abord, ou les deux en parallèle | Tout reste dans le repo Python, reproductible sans compte Microsoft. Power BI reste un plus pour des postes BI belges, pas un prérequis du cœur. |
| 2026-08-24 | Horizon **3 ans**, datasets Elia **historiques** (pas le near real-time) | 2 ans (plus léger) ou 5 ans (tendance plus longue) | 3 ans couvre assez de saisonnalité pour un portfolio. Le NRT (ods002/086/087) est trop court pour l'analyse ; ods001/031/032 sont les archives. Au-delà de 3 ans, Copernicus alourdit et l'éolien offshore Elia a des écarts documentés 2018–2023. |
| 2026-08-24 | Pas de modèle ML dans le cœur | Régression / forecast de production | Le brief vise une analyse + recommandation, pas une prédiction. La valeur portfolio est le pipeline, le SQL et le storytelling. |
