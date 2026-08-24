# Décisions

| Date | Décision | Alternative envisagée | Raison |
|---|---|---|---|
| 2026-08-24 | Couverture production/charge à l'échelle **Belgique**, zoom production **Wallonie** vs météo | Tout Wallonie, ou tout Belgique | La charge Elia (`ods001`) n'a pas de maille régionale ; solaire (`ods032`) et éolien (`ods031`) ont un champ `region` Wallonia. Calculer un taux de couverture wallon serait méthodologiquement faux. |
| 2026-08-24 | **DuckDB** comme base d'analyse | SQLite (plus universel) ou PostgreSQL (plus « prod ») | Pas de SIG prévu (brief). DuckDB reste un fichier local, sans serveur, et est plus confortable que SQLite pour le SQL analytique (fenêtres, parquet). PostgreSQL n'apporterait de la valeur que pour du géospatial. |
| 2026-08-24 | Dashboard **Streamlit** en livrable principal ; Power BI ensuite si le temps le permet | Power BI d'abord, ou les deux en parallèle | Tout reste dans le repo Python, reproductible sans compte Microsoft. Power BI reste un plus pour des postes BI belges, pas un prérequis du cœur. |
| 2026-08-24 | Horizon **3 ans**, datasets Elia **historiques** (pas le near real-time) | 2 ans (plus léger) ou 5 ans (tendance plus longue) | 3 ans couvre assez de saisonnalité pour un portfolio. Le NRT (ods002/086/087) est trop court pour l'analyse ; ods001/031/032 sont les archives. Au-delà de 3 ans, Copernicus alourdit et l'éolien offshore Elia a des écarts documentés 2018–2023. |
| 2026-08-24 | Éolien : somme Elia+DSO par région, plus un total Belgique | Garder les 5 séries séparées dans les faits | La couverture nationale a besoin d'un total. Les 5 séries (Federal offshore, Flanders/Wallonia × Elia/DSO) sont des morceaux disjoints. |
| 2026-08-24 | `ssrd_w_m2` = accumulation ERA5 / 3600 | Garder uniquement les J/m² | ERA5 `ssrd` est en J/m² sur l'heure ; le W/m² se compare plus naturellement à la production solaire. |
| 2026-08-24 | Pic d'été = P90 de la charge estivale ; stress = P90 charge **et** P10 renouvelable | Top 5 % / moyenne + 2 σ | Des quantiles lisibles, réglables dans `[analysis]`, sans hypothèse gaussienne. |
| 2026-08-24 | Corrélation solaire « de jour » si `ssrd > 10 W/m²` | Toutes les heures | Les nuits à zéro gonfleraient r sans rien dire du gisement. |
| 2026-08-24 | Saisonnalité par `GROUP BY` + moyenne mobile 7 jours | Décomposition STL (`statsmodels`) | Suffit pour les 4 questions ; évite une dépendance de plus avant le dashboard. |
| 2026-08-24 | Charts **Plotly** dans Streamlit | Altair (déjà fourni par Streamlit) | Heatmap heure × saison et densités PV/ERA5 plus lisibles ; hover utile pour un dashboard métier. |
