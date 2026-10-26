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
| **Priorité** | yes | `bloquant` \| `avant déploiement` \| `non prioritaire`, or `Informations manquantes`. |
| **Captures** | no | Images in the **current** chat (or paths the user named) that show the bug. |

If the user gave a partial bug: fill known fields, set every other body/metadata field to exactly **`Informations manquantes`**, and continue — do **not** block the create on incomplete data (état **incomplet**, see README).

If **titre court** is missing: ask and **wait**.

Done when titre is settled and every other field has a value or the jeton.

## 2. Captures (pièces jointes GitHub)

If the chat (or user paths) includes images meant as bug evidence:

1. Save them under **`docs/img/bugs/`** (create the folder). Filenames: short kebab ASCII (`mot-de-passe-masque-1.png`, …). Prefer PNG/JPEG/WebP/GIF (what `gh --attach` accepts).
2. Keep the local paths for step 3 (`--attach`). Do **not** rely on Markdown links to repo-relative paths alone — those do **not** show as issue attachments and often fail to render on the ticket until a push.
3. No images → skip this step (text-only bug is OK).

Do **not** commit here (skill `commit` / `/c` later if the user wants the files on git too). The GitHub upload is independent of the commit.

## 3. Create the GitHub issue

Title: `Bug — <titre court>`.

Labels: **`bug`** only (not `ready-for-agent` — this is not an implement child until scheduled into a version).

Body — **exact** headings below. Under **Constat**, after the text, add one Markdown image line **per** capture, using the **same basename** you will pass to `--attach` (so `gh` rewrites them to the uploaded asset):

```markdown
## Constat

<… or Informations manquantes>

![<alt court>](./<fichier>)

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
- Priorité : <bloquant|avant déploiement|non prioritaire|Informations manquantes>
```

Create with **`gh issue create`**:

- Always: `--title "…" --label bug --body "…"` (or `--body-file`).
- **When there are captures:** repeat **`--attach 'docs/img/bugs/<fichier>#<alt>'`** once per image (alt after `#`). This uploads a real GitHub issue attachment (visible on the ticket). Do **not** substitute “liens vers le dépôt” or “comment with URL only” when `--attach` is available.
- If `--attach` fails: **stop**, report the error, do **not** pretend the images are on the issue. Ask whether to retry or create text-only.

Capture the new `#n` and URL.

**Adding captures to an existing bug** (user asks after create): `gh issue edit <n> --attach 'path#alt'` (and optionally refresh the body so Constat references `./<fichier>`). Prefer edit over a comment when the evidence belongs in the bug record.

Done when the issue exists with label `bug`, that body shape, and every intended capture is attached (or there were none).

## 4. Update the feuille de route

Read role **`roadmap`**. Under **`## Plus tard (pas encore numéroté)`**, append one entry that matches **`docs/dev/feuille-de-route/README.md`** (*Bugs*), including `(#n)` and the same fields (Constat → Suivi), using **`Informations manquantes`** wherever the issue body does.

On the feuille, **do not** embed the binary images; point to the issue (`[#n](url)`) where the attachments live. Optionally note « captures en pièce jointe sur #n ».

Do not rewrite unrelated Plus tard entries. Do not invent a second Prochaine.

Done when the file has `### Bug — <titre court> (#n)` with the standard body.

## 5. Reply

Issue URL + `#n`, feuille updated, whether captures were **`--attach`**’d (and how many), and if any field is `Informations manquantes`: one line **incomplet** listing those fields. Remind: commit via **`/c`** if they want `docs/img/bugs/` on git too; scheduling into a version → **`/afr`**.

## Not this skill

- Child implement ticket under a version → `creer-ticket` (`/ct`)
- Schedule a bug into a version / remove from Plus tard → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Close a fixed bug (feuille + GitHub) → `finaliser-la-version` (PR must list `Fixes #<n>`)
- Open a version → `ouvrir-la-version`
- Commit / push → `commit` (`/c`)
- Human-test ticket close / changelog screenshots → `tests-humains` (`/th`) — bug evidence still goes through **`/cub`** with `--attach`
