# Feuille de route de dev — standards

Source unique : **`feuille-de-route-dev.md`**.

Outils branchés dessus :

- skill `/afr` (`augmenter-la-feuille-de-route-dev`) — rôle `roadmap` dans `agents/roles.yml` ;
- script `docs-site/scripts/generer-feuille-de-route.mjs` → pages générées dans `docs/feuille-de-route/` (site de doc / accueil) — **ne pas confondre** avec ce dossier `docs/dev/feuille-de-route/`.

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

### Corps d’une version (Prochaine / Ensuite)

- **`Objectif.`** — ce que le collaborateur gagne (langage produit).
- **`Hors périmètre`** — ce qui est explicitement reporté (souvent vers une autre version).
- Optionnel : auth / orientation technique / recherche / tests, si utile avant le grilling.
- Pas de détail d’implémentation digne d’une spec ; les décisions figées peuvent pointer vers un ADR ou une issue.

### Déjà livré

- Une ligne : `**X.Y.Z** — titre : résumé…` avec liens utiles (`#issue`, spec, ADR) si déjà connus.
- Bug connu **livré avec** la version : le mentionner ici **et** le reporter en **Plus tard** / Bug tant qu’il n’est pas corrigé.

## Bugs

Les bugs non encore numérotés en version vivent sous **`## Plus tard (pas encore numéroté)`**.

### Titre

```markdown
### Bug — <description courte> (#n)
```

- Préfixe **`Bug —`** obligatoire (repérable, distinct d’une idée produit).
- Lien issue GitHub (`#n`) dès qu’elle existe ; label `bug` côté tracker.
- Si pas encore d’issue : `### Bug — <description>` et créer l’issue dès que possible.

### Corps

1. **Constat** — quand / comment on l’a vu (test humain, version, date).
2. **À corriger** — intention produit (pas le patch).
3. **Suivi** — lien issue ; priorité relative (« avant déploiement postes », « non prioritaire en dev », etc.).
4. **Hors périmètre** si besoin.

Exemple :

```markdown
### Bug — données d’un compte visibles par un autre compte (#161)

Constat (test humain 1.4.3, 2026-10-07) : …

À corriger dans une version ultérieure : …

Suivi : [#161](…) (`bug`). Non prioritaire tant que le logiciel reste en développement.
```

Quand le bug est pris en charge : le retirer de **Plus tard** (ou le cocher comme repris) et l’intégrer à une version **Prochaine** / **Ensuite**, comme pour toute autre entrée.

## Recherches

Les notes de recherche amont sont dans [`../recherches/`](../recherches/) (ex. tarification Mistral), pas dans ce fichier.
