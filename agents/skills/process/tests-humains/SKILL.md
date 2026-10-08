---
name: tests-humains
description: >-
  Record human-test results for the version’s ready-for-human child, commit
  optional screenshots, update the issue body, and close it. Use when the user
  types `/th`, says « tests humains », or reports which scenarios they ran
  after the plan from encadrer-implement. Not `/implement`. Not `/cci`.
---

# Tests humains (`/th`)

Triggered by **`/th`** or when the user reports human-test results for the current version (after `encadrer-implement` proposed the plan). This path **is** permission to edit and close the **human-test child** only, and to commit screenshots via skill **`commit`**.

Paths: **`agents/roles.yml`**. Ticket shape: **`agents/issue-tracker.md`** (*Human-test child*).

## 1. Find the ticket

Infer **`X.Y.Z`** from the branch `vX.Y.Z-<slug>` or the open PR title. If missing: ask and **wait**.

Find the open child titled **`Tests humains — VX.Y.Z`** with label **`ready-for-human`** (parent via `Part of`). If none Open: say so and stop. If several: ask which `#n` and wait.

## 2. Read the human report

From the **current user message** (and images attached in this chat):

- Which plan scenarios were **played** (pass / fail / notes)
- Which were **not played** (short reason OK)
- Product bullets for **Ce qu’on peut faire maintenant** if the human stated them; otherwise draft them from the played scenarios + parent spec (product language)

Partial plans are OK. Do not invent failures the human did not report.

If the message has no results at all: ask what they ran and **wait**. Do not close.

## 3. Screenshots (optional)

If the chat includes images meant as evidence:

1. Save them under **`docs/img/changelog/vX.Y.Z/`** (create the folder). Filenames: short kebab ASCII (`scenario-1.png`, …).
2. Run skill **`commit`** as if the user had typed **`/c -a -p`** (message about preuves / changelog images for this version).

No images → skip this step. Text-only results are enough to close.

## 4. Update the issue body

`gh issue edit <n> --body` with the full *Human-test child* shape:

- Keep `Part of`, What to build, Acceptance criteria (check off what is done), Blocked by
- **`## Plan de tests`**: same scenarios; checkboxes reflect played / left unchecked or annotated as non-joué
- **`## Résultats`**: what was played, outcomes, non-joués
- **`## Ce qu’on peut faire maintenant`**: product bullets; for each screenshot, a Markdown image pointing at the repo path (e.g. `![…](../../img/changelog/vX.Y.Z/….png)` relative to a future `docs/changelog/…` page, or the same style as other `docs/img/` references in this repo)

## 5. Close

1. `gh issue edit <n> --remove-label "ready-for-human"` (absent → continue)
2. `gh issue close <n>` with comment: `Tests humains documentés sur <branch> (<sha>).`

Do **not** use `/cci`. Do not close the parent. Do not `/implement`.

## 6. Hand off

Tell the user in French: ticket `#n` Closed; next **`/code-review`**, then **Finalise la version** if the review is accepted.

## Not this skill

- Propose the plan after the last implement → `encadrer-implement`
- Close an implementation child → `fermer-ticket-enfant` (`/cci`)
- Release / squash → `finaliser-la-version`
- Commit only → `commit` (`/c`)
