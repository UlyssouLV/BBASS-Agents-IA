---
name: creer-un-bug
description: >-
  Create a GitHub bug issue (label bug) and add it under Plus tard on the
  dev roadmap, in the standard bug format. Use when the user types `/cub`
  or says « crée un bug », « ajoute un bug », or « documente un bug ».
  Not `/ct`. Not `/afr`. Not « Ouvre la version ».
---

# Create a bug

`/` = this skill’s trigger. No hyphen options. Treat `/cub` as a whole token.

`/cub` **is** permission to `gh issue create` (label `bug`) and to edit role
**`roadmap`**. Do not merge. Do not commit. Do not `/implement`. Do not move
the bug into **Prochaine** / **Ensuite** (that is `/afr`).

Paths: **`agents/roles.yml`**. Writing standards (feuille **and** issue body):
**`docs/dev/feuille-de-route/README.md`** (*Bugs*). Tracker: **`agents/issue-tracker.md`**.

One bug per invocation. Again → `/cub` again.

## 1. Inputs

From the user message. **Do not invent.**

| Field | Required | Notes |
| --- | --- | --- |
| **Titre court** | yes (real text) | Without the `Bug —` prefix (the skill adds it). Never `Informations manquantes`. |
| **Constat** | yes | What was seen. Prefer real text; if the user truly has none → ask once, else `Informations manquantes`. |
| **Reproductibilité** | yes | Steps / conditions, or `Non déterminé`, or `Informations manquantes`. |
| **Impact** | yes | Who / what breaks, or `Informations manquantes`. |
| **Cause probable** | yes | Hypothesis, or `Inconnue`, or `Informations manquantes`. |
| **À corriger** | yes | Product intent, or `Informations manquantes`. |
| **Hors périmètre** | yes | Default `Aucun.` if the user said nothing on scope. |
| **Trouvé dans** | yes | `X.Y.Z`, or `inconnu`, or `Informations manquantes`. |
| **Contexte** | yes | `test humain` \| `usage` \| `revue` \| …, or `Informations manquantes`. |
| **Date** | yes | `YYYY-MM-DD` (Europe/Paris). If omitted but other facts imply a day, use it; else today’s date **only if** the user is filing now; else `Informations manquantes`. |
| **Priorité** | yes | `bloquant` \| `avant déploiement postes` \| `non prioritaire en dev`, or `Informations manquantes`. |

If the user gave a partial bug: fill known fields, set every other body/metadata field to exactly **`Informations manquantes`**, and continue — do **not** block the create on incomplete data (état **incomplet**, see README).

If **titre court** is missing: ask and **wait**.

Done when titre is settled and every other field has a value or the jeton.

## 2. Create the GitHub issue

Title: `Bug — <titre court>`.

Labels: **`bug`** only (not `ready-for-agent` — this is not an implement child until scheduled into a version).

Body — **exact** headings below (stable for a future docs-site parser):

```markdown
## Constat

<… or Informations manquantes>

## Reproductibilité

<…>

## Impact

<…>

## Cause probable

<…>

## À corriger

<…>

## Hors périmètre

<… or Aucun.>

## Métadonnées

- Trouvé dans : <X.Y.Z|inconnu|Informations manquantes>
- Contexte : <…|Informations manquantes>
- Date : <YYYY-MM-DD|Informations manquantes>
- Priorité : <bloquant|avant déploiement postes|non prioritaire en dev|Informations manquantes>
```

`gh issue create --title "…" --label bug --body "…"`. Capture the new `#n` and URL.

Done when the issue exists with label `bug` and that body shape.

## 3. Update the feuille de route

Read role **`roadmap`**. Under **`## Plus tard (pas encore numéroté)`**, append one entry that matches **`docs/dev/feuille-de-route/README.md`** (*Bugs*), including `(#n)` and the same fields (Constat → Suivi), using **`Informations manquantes`** wherever the issue body does.

Do not rewrite unrelated Plus tard entries. Do not invent a second Prochaine.

Done when the file has `### Bug — <titre court> (#n)` with the standard body.

## 4. Reply

Issue URL + `#n`, feuille updated, and if any field is `Informations manquantes`: one line **incomplet** listing those fields (for the future docs-site completeness view). Remind: commit via **`/c`** if they want it on git; scheduling into a version → **`/afr`**.

## Not this skill

- Child implement ticket under a version → `creer-ticket` (`/ct`)
- Schedule a bug into a version / remove from Plus tard → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Close a fixed bug (feuille + GitHub) → `finaliser-la-version` (PR must list `Fixes #<n>`)
- Open a version → `ouvrir-la-version`
- Commit / push → `commit` (`/c`)
