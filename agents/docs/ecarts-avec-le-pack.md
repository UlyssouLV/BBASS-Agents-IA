# Écarts avec le pack

Modifications faites dans ce dépôt sur des fichiers qui viennent de `workflow-agents-pack`. Un `/up` (`update-from-pack.sh`) **écrase** les skills et hooks du pack : tant qu’une ligne est **à reporter**, la reporter d’abord dans le pack, puis passer son statut à **reporté**.

| Date | Sujet | Fichiers du dépôt | Où dans le pack | Statut |
| --- | --- | --- | --- | --- |
| 2026-10-29 | Numéro de développement / numéro produit | voir ci-dessous | voir ci-dessous | à reporter |

## 2026-10-29 — Numéro de développement / numéro produit

**Pourquoi.** Deux séries (1.7.x documentation, 1.8.x serveur MCP Moduléo) avancent en parallèle et arrivent sur `main` en alternance. Le numéro de la feuille de route (développement) ne peut plus servir tel quel de numéro de Release : le poste et la VM verraient la version reculer (1.8.0 puis 1.7.2). Le numéro produit, toujours croissant, est calculé à « Finalise la version » ; pas de Release quand rien n’atteint l’utilisateur final.

**Règle.** `docs/dev/feuille-de-route/README.md`, section *Numéro de développement et numéro produit*.

| Fichier du dépôt | Changement | Équivalent dans le pack |
| --- | --- | --- |
| `agents/skills/process/finaliser-la-version/SKILL.md` | Étape 0 : arrêt si la branche est en retard sur la base ; calcul du numéro produit `P` (règles 1 à 3, rôle `livrables`). Étape 2 : puce Déjà livré (`Livrée en P.` / `Sans Release produit.`), clôture des bugs `Corrigé en V<P>.`. Étape 4 : pas de `/crel` quand `P` = aucun, sinon `/crel vP` avec `(développement X.Y.Z)` ; aperçus vérifiés sur `vP`. Étape 5 : `Modifié en V<P>`. Description du skill. | même skill |
| `agents/skills/meta/creer-release/SKILL.md` | Garde 2 : un tag passé en message prime sur la branche (numéro produit ≠ numéro de développement `D`). Titre : suffixe ` (développement D)`. Ticket de tests humains cherché sous `VD`. | même skill |
| `agents/issue-tracker.md` | *Release notes* : titre au numéro produit, suffixe développement, pas de Release sans `livrables`. | `initialise-le-repo/references` si le fichier y est modèle |
| `agents/roles.yml` | Nouveau rôle `livrables` (chemins qui entrent dans les images VM et le Paquet poste). Valeurs propres à ce dépôt. | Pack : rôle **optionnel** ; absent → règle 1 ignorée (toujours une Release), comportement actuel du pack. |
| `docs/dev/feuille-de-route/README.md` | Section *Numéro de développement et numéro produit*. | `initialise-le-repo/references/feuille-de-route/README.md` |
| `AGENTS.md` | Paragraphe « Version numbers » sous *Cycle*. | `initialise-le-repo/references/AGENTS.md` |

Copies `.claude/skills/` et `.cursor/skills/` régénérées par `python agents/scripts/dispatch.py`.

**Constaté au passage (pack).** Les skills `creer-release`, `finaliser-la-version`, `ouvrir-la-version`, `ouvrir-pr`, `ouvrir-branche`, `fusionner-pr` et `commit` renvoient à `agents/docs/integration-channel.md`, absent de ce dépôt.
