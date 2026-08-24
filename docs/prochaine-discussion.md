# Relais entre discussions

L'utilisateur n'utilise pas `@`. Ce fichier est le bâton : chaque
**nouveau chat Agent** le lit, fait **une** étape, puis le réécrit.

Cursor ne peut pas ouvrir un onglet à ta place. À la fin d'une étape,
l'agent doit dire clairement : ouvre un nouveau chat et envoie uniquement
le message ci-dessous.

## Ce que tu tapes (toujours le même texte)

```
prochaine étape
```

## État actuel

| | |
|---|---|
| Dernière étape close | 6 — Dashboard Streamlit |
| **Prochaine étape** | **7 — README, recommandation, présentations portfolio** |
| Branche | `feature/dashboard-streamlit` (à merger dans `main` sans `.cursor`) |
| Fichiers utiles | `ROADMAP.md`, `JOURNAL.md`, `brief/objectif.md`, `docs/decisions.md`, `docs/analyse.md`, `webapp/app.py`, `src/renewables_wallonia/dashboard.py` |

### Déjà en place (ne pas refaire)

- Pipeline API → DuckDB, CLI `analyze`, SQL dans `sql/analysis/`, conclusions dans `docs/analyse.md`.
- Dashboard Streamlit (`python -m renewables_wallonia.cli dashboard`) : une viz par question + reco chiffrée (flex 16–19 h hiver).
- Pas de ML, pas de SIG, pas de Power BI.

### À faire dans le prochain chat (étape 7 seulement)

- README public (EN), recommandation rédigée, quatre présentations Marp FR/EN.
- Ne pas enchaîner l'étape 8 (Power BI) dans le même chat.

---

## Prompt maître (l'agent suit ça dans chaque chat)

Tu es le **maître d'œuvre** de ce dépôt. L'humain a posé le cadrage dans
les markdowns et te laisse avancer. Il ne gère pas le contexte.

### Au démarrage

1. Lis tout seul, sans demander de `@` :
   `docs/prochaine-discussion.md`, `ROADMAP.md`, `JOURNAL.md`,
   `brief/objectif.md`, `docs/decisions.md`.
2. Si `brief/objectif.md` est déjà rempli, **ne recadre pas** le projet.
3. La mission de CE chat = la section « À faire dans le prochain chat »
   ci-dessus (en pratique : la première case non cochée de `ROADMAP.md`).
4. Annonce en 3 lignes : étape visée, ce que tu vas livrer, ce que tu
   ne feras pas. Puis exécute. Si l'utilisateur a écrit « prochaine étape »
   / « continue », c'est le feu vert : ne redemande pas confirmation.

### Pendant le chat

- Une case ROADMAP = un chat. Interdiction d'enchaîner l'étape suivante.
- Si le travail est trop gros (dashboard + README, 4 questions + 4 slides,
  etc.) : découpe, finis un morceau propre, mets à jour ce fichier.
- Si le compteur de contexte est haut ou que tu viens d'être compacté :
  arrête-toi proprement, mets à jour le relais, demande un **nouveau** chat.
- Ne demande jamais à l'utilisateur d'attacher des fichiers avec `@`.

### Fin de chat (obligatoire)

1. Coche la case dans `ROADMAP.md` seulement si c'est vraiment fini.
2. Ajoute une entrée courte dans `JOURNAL.md`.
3. Réécris **tout** le bloc « État actuel » de ce fichier : étape close,
   prochaine étape, fichiers utiles, « déjà en place », « à faire ».
4. Réponds à l'humain avec exactement cette structure :

```
Étape N terminée (ou : morceau N.x terminé).

Ouvre un nouveau chat Agent dans ce projet et envoie uniquement :

prochaine étape

Prochaine mission : …
```

### Interdits

- « J'enchaîne sur l'étape suivante tant que le compteur est bas. »
- Refaire le socle, l'ingestion ou l'entrepôt déjà cochés.
- Inventer du ML, du SIG, ou Power BI avant l'étape 8.
