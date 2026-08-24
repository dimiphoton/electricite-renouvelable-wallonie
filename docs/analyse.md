# Analyse métier — 4 questions

Période : septembre 2023 – août 2026 (heure de Bruxelles).
Commande : `python -m renewables_wallonia.cli analyze`
(requiert `data/processed/warehouse.duckdb`).

Les tables CSV et `headlines.json` sont régénérées dans
`data/processed/analysis/` (gitignoré). Les requêtes vivent dans
`sql/analysis/`.

## Méthode

| Question | Grain | Règle |
|---|---|---|
| Q1 Couverture | Quart d'heure Belgique | `(PV + éolien) / charge`, NA si une série manque |
| Q2 Pics d'été | Été (juin–août) | Pic = P90 de la charge estivale (`PERCENT_RANK`) |
| Q3 Météo Wallonie | Heure | Moyenne des 4 quarts d'heure Elia, jointure ERA5 |
| Q4 Complémentarité | Quart d'heure | Corrélation PV/éolien ; stress = charge P90 **et** renouvelable P10 |

Le filtre « jour » de Q3 (`ssrd > 10 W/m²`) évite que les nuits à zéro
gonflent la corrélation solaire. ERA5 s'arrête vers le 19 août 2026
(retard de réanalyse) : Q3 a un peu moins d'heures que Q1–Q2.

Pas de décomposition STL : la saisonnalité est lue par `GROUP BY`
saison × heure, plus une moyenne mobile 7 jours de la couverture
journalière (fenêtre SQL).

## Q1 — Couverture belge selon l'heure et la saison

Solaire + éolien couvrent en moyenne **27,4 %** de la charge belge
(médiane 24,2 % ; P10–P90 : 3,6 %–56,4 %). Environ **15 %** des quarts
d'heure dépassent 50 % ; **0,05 %** dépassent 100 % (le renouvelable
peut excéder la charge).

| Saison | Couverture moyenne | Charge | Solaire | Éolien |
|---|---|---|---|---|
| Été | 31,3 % | plus basse | plus haut | plus bas |
| Hiver | 23,7 % | plus haute | plus bas | plus haut |
| Printemps | 29,3 % | | | |
| Automne | 25,3 % | | | |

Un **midi d'été (14 h)** : **62,9 %**. Un **soir d'hiver (18 h)** :
**18,8 %**. La moyenne mobile 7 jours de la couverture journalière
oscille entre **2,6 %** et **48 %** : le mix n'est pas un socle stable.

## Q2 — Le solaire coïncide-t-il avec les pics de charge d'été ?

**Oui, pour les pics de midi — pas pour le soir.**

En Belgique, le maximum journalier de charge en été tombe vers **12 h**,
le maximum solaire vers **13 h** (écart médian : 1 h). Aux 10 % de
quarts d'heure les plus chargés de l'été, le solaire produit **4 817 MW**
contre **1 515 MW** hors pic (×3,2). La couverture y passe de 29 % à
**53 %**. Corrélation solaire–charge : **r = 0,64** en été, **0,34** en
hiver. L'éolien est même un peu *plus faible* aux pics d'été : c'est le
PV qui suit la demande.

Nuance : le créneau **11–15 h** affiche 60 % de couverture, le
**17–20 h** seulement 31 %. Le solaire aide le pic de midi, pas la
pointe de début de soirée.

## Q3 — Météo et production wallonne

Sur ~26 000 heures communes Elia × ERA5 :

- PV wallon vs rayonnement descendant : **r = 0,92** (jour : **0,87** ;
  Spearman 0,93)
- Éolien wallon vs vent à 10 m : **r = 0,88** (le cube du vent fait
  moins bien : 0,79 — la hauteur 10 m n'est pas celle des moyeux)

Le rayonnement et le vent ERA5, même moyennés sur une bbox, expliquent
très bien la production wallonne. Ce n'est pas un modèle de prévision :
c'est un diagnostic de sensibilité.

## Q4 — Complémentarité et creux

Solaire et éolien belges sont **faiblement complémentaires**
(**r = −0,21**). L'éolien pèse **87 %** du renouvelable en hiver, le
solaire **44 %** en été.

Les heures « tendues » (charge dans le P90 **et** renouvelable dans le
P10) sont rares : **0,7 %** des quarts d'heure (689), avec une
couverture moyenne de **1,3 %**. Elles se concentrent en fin
d'après-midi / soirée, surtout en hiver (**1,1 %** des QH d'hiver si on
classe à l'intérieur de la saison). **En été, ce croisement n'arrive
jamais** : quand la charge est haute, le renouvelable ne l'est pas en
creux.

## Recommandation

Rédaction complète : [`recommandation.md`](recommandation.md).

Un décideur gagne plus à traiter le **créneau hivernal 16–19 h**
(couverture **19,6 %**) qu'à ajouter du solaire pour les pics d'été
(midi 14 h : **62,9 %** ; 3,2× plus de PV aux heures P90 de charge).
**61 %** des quarts d'heure de stress (charge P90 et renouvelable P10)
tombent entre 16 h et 19 h. La complémentarité PV/éolien
(r = −0,21) ne comble pas ce trou.

## Limites

- Charge nationale seulement : pas de « la Wallonie couvre sa demande ».
- Production Elia = *measured & upscaled*, pas du comptage validé.
  Quelques valeurs légèrement négatives existent ; elles sont laissées
  telles quelles.
- ERA5 = réanalyse, pas des stations au sol ; vent à 10 m.
- Les quantiles de « pic » et de « stress » sont des conventions
  (`config/settings.toml`, section `[analysis]`), pas des seuils
  réseau d'Elia.
