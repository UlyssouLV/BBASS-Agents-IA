# Feuille de route de dev — standards

Source unique : **`feuille-de-route-dev.md`**.

Outils branchés dessus :

- skill `/afr` (`augmenter-la-feuille-de-route-dev`) — rôle `roadmap` dans `agents/roles.yml` ;
- skill `/cub` (`creer-un-bug`) — issue GitHub `bug` + entrée sous **Plus tard** ;
- script `docs-site/scripts/generer-feuille-de-route.mjs` → pages générées dans `docs/feuille-de-route/` (site de doc / accueil) — **ne pas confondre** avec ce dossier `docs/dev/feuille-de-route/` ;
- script `docs-site/scripts/generer-bugs.mjs` → section **Bugs connus** sur l’accueil + pages `docs/bugs/` (détail au clic, état complet / incomplet).

Ce n’est **pas** une spec (la spec naît à « Ouvre la version »).

## Structure du fichier

```text
# Feuille de route de dev
## Déjà livré          ← puces **X.Y.Z** — titre + résumé court
## Prochaine : X.Y.Z — Titre
## Ensuite : X.Y.Z — Titre   (répétable)
## Plus tard (pas encore numéroté)
### … sujets / bugs …
```

| Section | Rôle |
| --- | --- |
| **Déjà livré** | Versions shipped (une puce par `X.Y.Z`). |
| **Prochaine** | Exactement **une** version : la suivante à ouvrir. |
| **Ensuite** | Versions numérotées après la Prochaine, dans l’ordre. |
| **Plus tard** | Idées / bugs **sans** semver encore (ou reprise plus tard). |

À « Finalise la version » : la version livrée passe en **Déjà livré** ; la première **Ensuite** devient **Prochaine**.

## Conventions d’écriture des versions

### Numérotation

- Semver produit : `X.Y.Z` (ex. `1.4.4`, `1.5.0`).
- Titre de section : `## Prochaine : X.Y.Z — <titre>` ou `## Ensuite : X.Y.Z — <titre>`.
- Un **seul job** par version (un objectif métier clair).

### Numéro de développement et numéro produit

Deux suivis, un seul nom de version côté développement :

| | Numéro de développement | Numéro produit |
| --- | --- | --- |
| Où | ce fichier, specs, branches `vX.Y.Z-…`, issues, PR, commits, suivi d’avancement | tag et titre de la GitHub Release, `/sante`, « À propos » et mise à jour du poste, site de doc |
| Ordre | par thème ; deux séries peuvent arriver sur `main` en alternance | **toujours croissant**, dans l’ordre d’arrivée sur `main` |
| Fixé | à l’ouverture de la version | à « Finalise la version » |

Sens des chiffres (communs aux deux suivis) :

- **majeur** — rupture qui demande un geste à tous (réinstaller les postes, migrer des données à la main, mise en production définitive) ; décidé dans ce fichier, jamais calculé ;
- **mineur** — une **série** = un grand thème (1.4 recherche web, 1.5 Moduléo, 1.6 déploiement, 1.7 documentation, 1.8 serveur MCP Moduléo…) ;
- **correctif** — une étape de plus dans la série, une correction, ou une version arrivée après une série plus récente.

À « Finalise la version », le numéro produit se calcule ainsi :

1. **Rien de livré à l’utilisateur final** — le diff de la branche (`origin/main...HEAD`) ne touche aucun chemin du rôle **`livrables`** (`agents/roles.yml` : ce qui entre dans les images de la VM et dans le Paquet poste), hors tests et fichiers `.md` → **pas de Release**, donc pas de numéro produit. La version passe en **Déjà livré** sous son numéro de développement ; le site de doc se publie à la fusion.
2. **Numéro de développement plus grand que la dernière Release** `vX.Y.Z` (comparaison semver) → numéro produit = numéro de développement.
3. **Sinon** → numéro produit = dernière Release, correctif + 1. Titre de la Release : `VX.Y.Z — <titre>`, sans le numéro de développement, qui figure dans ses notes (`Développement : A.B.C (#<parent>)`).

Exemples : développement 1.5.2 finalisée après la Release 1.6.2 → produit **1.6.3** ; série 1.7.x de documentation → aucune Release ; 1.8.0 après 1.6.3 → **1.8.0** ; une 1.8.3 finalisée après la Release 1.9.0 → **1.9.1**.

Sur le site de doc, le Changelog montre le numéro produit. Une version à venir n’en a pas encore : la feuille de route du site la présente et l’adresse par son titre, sans numéro, et elle passe au Changelog une fois livrée.

Dans **Déjà livré**, la puce garde le numéro de développement et indique le numéro produit quand il diffère (`**1.5.2** — … Livrée en **1.6.3**.`) ou l’absence de Release (`Sans Release produit.`).

### Corps d’une version (Prochaine / Ensuite)

- **`Objectif.`** — ce que le collaborateur gagne (langage produit).
- **`Hors périmètre`** — ce qui est explicitement reporté (souvent vers une autre version).
- Optionnel : auth / orientation technique / recherche / tests, si utile avant le grilling.
- Pas de détail d’implémentation digne d’une spec ; les décisions figées peuvent pointer vers un ADR ou une issue.

### Déjà livré

- Une ligne : `**X.Y.Z** — titre : résumé…` avec liens utiles (`#issue`, spec, ADR) si déjà connus.
- Bug connu **livré avec** la version : le mentionner ici **et** le reporter en **Plus tard** / Bug tant qu’il n’est pas corrigé.

## Bugs

Création standardisée : skill **`/cub`** (`creer-un-bug`) — issue GitHub **et** entrée feuille. Ne pas inventer un format parallèle.

Les bugs non encore numérotés en version vivent sous **`## Plus tard (pas encore numéroté)`**.

### Titre

```markdown
### Bug — <description courte> (#n)
```

- Préfixe **`Bug —`** obligatoire (repérable, distinct d’une idée produit).
- Lien issue GitHub (`#n`) dès qu’elle existe ; label **`bug`** côté tracker (pas `ready-for-agent`).
- Titre d’issue = même libellé : `Bug — <description courte>`.
- Nouvel bug → **`/cub`** (crée l’issue puis écrit la feuille). Pas d’entrée feuille sans `#n` pour un bug nouveau.

### Corps (feuille **et** issue — mêmes titres, parsables pour le site de doc)

Ordre fixe — **chaque** rubrique est toujours présente :

1. **Constat** — ce qui a été vu.
2. **Reproductibilité** — étapes / conditions ; ou `Non déterminé` (on a cherché, pas reproductible clairement) ; ou jeton ci-dessous.
3. **Impact** — qui / quoi est cassé.
4. **Cause probable** — hypothèse ; ou `Inconnue` (examiné, pas d’hypothèse) ; ou jeton ci-dessous.
5. **À corriger** — intention produit (pas le patch).
6. **Hors périmètre** — ou `Aucun.`
7. **Métadonnées** (issue) / **Suivi** (feuille) :
   - Trouvé dans : `X.Y.Z` \| `inconnu` \| jeton
   - Contexte : `test humain` \| `usage` \| `revue` \| … \| jeton
   - Date : `YYYY-MM-DD` \| jeton
   - Priorité : `bloquant` \| `avant déploiement postes` \| `non prioritaire en dev` \| jeton
   - Sur la feuille : lien `[#n](url)` (`bug`) + les mêmes puces / ligne Suivi.

#### Jeton `Informations manquantes`

Exactement cette chaîne (casse comprise) quand une info **n’est pas encore fournie**. **Ne pas inventer.**

- Distinct de `Non déterminé` / `Inconnue` / `inconnu` : ceux-là sont des réponses **assumées** ; le jeton = case encore vide.
- Un bug peut donc être **complet** ou **incomplet** (états dérivés, utiles au site de doc) :
  - **complet** — aucune rubrique / métadonnée ne contient le jeton ;
  - **incomplet** — au moins une occurrence de `Informations manquantes` → la liste des champs concernés = ce qu’il manque avant de résoudre / d’afficher « prêt ».
- Titre court (`Bug — …`) : toujours un vrai libellé (pas le jeton).
- `#n` : obligatoire pour tout bug listé (créer l’issue d’abord si besoin).

**Issue GitHub** — titres `##` exacts :

```markdown
## Constat
## Reproductibilité
## Impact
## Cause probable
## À corriger
## Hors périmètre
## Métadonnées
```

**Feuille** — sous le `### Bug — … (#n)`, mêmes rubriques en gras puis **Suivi**.

Exemple feuille (**complet**) :

```markdown
### Bug — données d’un compte visibles par un autre compte (#161)

**Constat :** …

**Reproductibilité :** …

**Impact :** …

**Cause probable :** …

**À corriger :** …

**Hors périmètre :** Aucun.

**Suivi :** [#161](…) (`bug`). Trouvé dans : 1.4.3 · Contexte : test humain · Date : 2026-10-07 · Priorité : non prioritaire en dev.
```

Exemple rubrique manquante :

```markdown
**Cause probable :** Informations manquantes
```

Quand le bug est **pris en charge** (planifié) : via **`/afr`**, **retirer** le bloc `### Bug — … (#n)` de **Plus tard** et en faire (ou l’inclure dans) l’**Objectif** d’une **Prochaine** / **Ensuite**. Ne pas laisser le bug listé en Plus tard une fois numéroté.

Quand le bug est **corrigé** (version livrée) : skill **`finaliser-la-version`** —

1. la PR porte `Fixes #<n>` pour chaque issue `bug` résolue par cette version ;
2. le bloc `### Bug — … (#n)` est absent de **Plus tard** (déjà retiré à la planification, sinon le skill le retire) ;
3. l’issue GitHub `#n` est **Closed** (commentaire de clôture avec `VX.Y.Z` si besoin).

Après ça, `generer-bugs` ne le liste plus sur le site de doc.

## Recherches

Les notes de recherche amont sont dans [`../recherches/`](../recherches/) (ex. tarification Mistral), pas dans ce fichier.
