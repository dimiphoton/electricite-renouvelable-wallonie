# Recommandation métier

Destinataire : un responsable planification ou flexibilité chez un
gestionnaire de réseau, un fournisseur ou une intercommunale.
Période : septembre 2023 – août 2026. Grain : quart d'heure belge
(Elia), heure pour la météo wallonne (ERA5).

Les calculs vivent dans `src/renewables_wallonia/dashboard.py`
(`build_recommendation`) et s'affichent en bandeau du dashboard
Streamlit.

## En une phrase

**Prioriser le flex (demande, stockage, import) et la capacité
disponible sur le créneau hivernal 16–19 h, plutôt qu'un surplus de
solaire pour les pics d'été.**

Les pics de midi en été sont déjà suivis par le photovoltaïque. Le
trou opérationnel est le début de soirée en hiver, quand la charge
est haute et que le solaire n'y est plus.

## Chiffres qui portent la reco

| Indicateur | Valeur | Lecture |
|---|---|---|
| Couverture moyenne Belgique (PV + éolien / charge) | **27,4 %** | socle, pas un plafond |
| Midi d'été (14 h) | **62,9 %** | le solaire travaille déjà |
| Créneau hivernal 16–19 h | **19,6 %** | le trou à traiter |
| Couverture aux 10 % d'heures d'été les plus chargées | **52,8 %** | 3,2× plus de PV qu'hors pic |
| Heures de stress (charge P90 **et** renouvelable P10) | **0,7 %** des quarts d'heure | rares |
| Couverture pendant ces heures | **1,3 %** | mais sévères |
| Part de ces heures entre 16 h et 19 h | **61 %** | le créneau n'est pas un détail |
| Corrélation PV / éolien belge | **r = −0,21** | trop faible pour combler le soir |

En été, le croisement « charge haute **et** renouvelable bas » n'apparaît
**jamais** si on classe les quantiles à l'intérieur de la saison. Ajouter
du PV pour les pointes de midi n'adresse pas le problème qui reste.

## Ce qu'un décideur peut faire

1. **Cibler le flex sur 16–19 h en hiver** : effacement, report de
   demande, stockage court, contrats d'import. C'est là que 61 % des
   quarts d'heure tendus se concentrent, avec une couverture d'environ
   20 %.
2. **Ne pas dimensionner du solaire supplémentaire pour les pics
   d'été.** Aux heures P90 de charge estivale, le PV produit déjà
   ~4 800 MW contre ~1 500 MW hors pic. Le midi est le bon moment du
   solaire, pas un déficit.
3. **Ne pas compter sur la complémentarité PV–éolien** pour effacer
   le soir d'hiver. L'éolien pèse 87 % du renouvelable en hiver, mais
   la corrélation avec le solaire reste faiblement négative : les deux
   filières ne se relaient pas assez.

## Ce que cette reco n'est pas

- Ce n'est **pas** un seuil réseau Elia. Les P90 / P10 sont des
  conventions d'analyse (`config/settings.toml`, section `[analysis]`).
- Ce n'est **pas** un appel à arrêter le solaire. Le PV fait son
  travail à midi en été. La reco dit où **mettre le prochain euro de
  flex**, pas où couper une filière.
- Ce n'est **pas** un taux de couverture wallon. La charge Elia n'existe
  qu'à l'échelle Belgique. La Wallonie éclaire le *pourquoi* météo
  (PV vs rayonnement r = 0,92 ; éolien vs vent 10 m r = 0,88), pas un
  bilan régional production / demande.
- Ce n'est **pas** une prévision. ERA5 est une réanalyse ; les séries
  Elia sont *measured & upscaled*.

Le détail des quatre questions et des limites est dans
[`analyse.md`](analyse.md). Le dashboard :
`python -m renewables_wallonia.cli dashboard`.
