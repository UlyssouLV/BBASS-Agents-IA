---
name: finaliser-la-version
description: >-
  When the user says « Finalise la version », « finalize the version »,
  « clôture la version », or asks to ship/squash-merge the current version
  PR, create the GitHub Release, and delete the feature branch. Reads the
  Sonar quality gate once on the PR HEAD before the tag. Not for a single
  child ticket or /implement.
---

# Finalise the version

Triggered by **« Finalise la version »** (or equivalent), only after the user accepted a **`/code-review`** of this branch. Do **not** run `/code-review` here. Release and squash go through **`creer-release`** (`/crel`) and **`fusionner-pr`** (`/mpr`), not inline. Docs commit goes through **`commit`** (`/c -a -p`). The quality gate is step 3, after that review and after the docs.

A version = one feature branch + one PR that ships a **set** of child issues (parent spec). Starting a version is skill `ouvrir-la-version`.

Do **not** `/implement` here. Do **not** `gh issue close` children here (they should already be Closed). Do **not** close the parent by hand — squash `Fixes` does that.

Paths: **`agents/roles.yml`**.

## 0. Locate the PR

Current branch must not be `main`. Resolve the open PR for this branch (`gh pr view`). If none, stop.

Infer **`X.Y.Z`** from the branch `vX.Y.Z-<slug>` or the PR title `VX.Y.Z — …`. If missing: ask and wait.

## 1. Every related issue is published

Related = listed in the PR body (`Fixes` / `Part of`) **and** children of the parent spec that are in scope for this PR. Ignore `wontfix` and issues the PR or parent spec mark as out of this version. See `agents/issue-tracker.md`.

**Published** = each in-scope **child** is **Closed**.

If any in-scope child is still **Open**: **stop**. List what’s missing. Do not tag, merge, or delete.

The **parent** spec may still be Open until squash. Leave it Open here.

If the PR body’s `Fixes` line would not close the **parent** on squash, **edit the PR body first** (`Fixes #n` once per issue; include `Fixes #<parent>`). Children already Closed are fine to leave in `Fixes` (no-op).

## 2. Docs must match this version (before tag and squash)

Read each role below (paths from `agents/roles.yml`), against the parent spec / ADRs / code that this PR actually ships:

- **`readme`** — matches what this version shipped. Extra README checks live in role **`agent-adapter`**; do not invent a layout.
- **`glossary`** — glossary and ADR links match the model (new terms, reversed decisions).
- **`agent-adapter`** — adapter still valid (hook, `/implement` close, Standards pointer); skills named there exist under `agents/skills/` (synced to the IDE adapters); implement / finalise cycle matches those skills; process docs still match (tracker, labels, domain).
- **`spec`** — spec for this version exists there.
- **`adr`** — new ADRs if decisions changed.
- **`roadmap`** — follow **`docs/dev/feuille-de-route/README.md`**: move **`X.Y.Z`** into **Déjà livré** (one bullet `**X.Y.Z** — titre : résumé…`); drop it from **Prochaine** / **Ensuite**; the first remaining **Ensuite** becomes the sole **Prochaine** (keep its Objectif / Hors périmètre). Drop claims this version has **not** delivered. Do not invent new versions; only reshuffle what is already listed. New version ideas → leave for **`/afr`**.
- **Bugs fixed by this version** (same docs commit as roadmap):
  1. From the open PR body, collect every `Fixes #<n>` / `Fix #<n>` / `Closes #<n>`.
  2. Keep only issues that still have label **`bug`** (`gh issue view <n> --json labels`). Also include any `#n` the parent **spec** / version narrative explicitly says this version closes, if it has label `bug` and is missing from the PR — then **edit the PR body** to add `Fixes #<n>` (same rule as step 1 for the parent).
  3. On role **`roadmap`**: delete each matching `### Bug — … (#n)` block under **Plus tard** (from that heading through the line before the next `###` / `##`). Already absent → OK.
  4. For each such `#n` still **Open**: `gh issue close <n> --comment "Corrigé en VX.Y.Z."` (use this version’s semver). Already Closed → one line, continue.
- **`suivi-avancement`** — HTML bilan for the **current calendar week** under that role (folder `semaine-…` that covers today’s date). None → one line, do **not** stop. Found → update that HTML for **`X.Y.Z`** (what shipped, **functional** language for a cabinet reader — no tool names, stack, or ticket ids in the day bullets), then regenerate the sibling `.pdf` next to the HTML (headless Chrome or Edge: `--print-to-pdf`, no header/footer). Do not create a week folder. Do not edit other weeks.

If anything is stale (except soft-skip on missing week HTML): **stop the release**. Update those files on the **feature branch**, then run skill **`commit`** as if the user had typed **`/c -a -p`**. Then re-read this section. Do **not** `/crel` or `/mpr` until this gate is green — the tag must include the docs (HTML + PDF when updated). Bug issue closes (step above) may run in that same docs turn; they do not require a second commit.

## 3. Quality gate

One read, on the PR `HEAD` after the docs commit. This analysis covers the branch, not one child. Do not reopen children. Do not add a label.

Load `.env` the same way **`quality-gate`** does. If any of that skill’s three `SONAR_*` keys is missing or empty → continue. One line that Sonar is skipped. Do not `/qg`. Do not `/cqg`.

Otherwise run **`quality-gate`** as if **`/qg -w`**.

- No analysis for `HEAD` after the wait → **stop**. Do not `/crel` or `/mpr`.
- **`OK`** → continue.
- Not **`OK`** (`ERROR`, `WARN`, …) → run skill **`corriger-quality-gate`** as if **`/cqg`**.
  - That skill stopped without a code change (policy / user needed) → **stop**. Do not `/crel` or `/mpr`.
  - Working tree dirty after the fix → run **`/t`** (fail → **stop**). Stage the files that fix touched and run skill **`commit`** as if **`/c -p`**. Then **`/qg -w`** once. Not **`OK`**, or no analysis this time → **stop**. Do not `/crel` or `/mpr`.

## 4. Release, then squash

Run skill **`creer-release`** as if the user had typed **`/crel vX.Y.Z`**. That skill owns title (`VX.Y.Z — <purpose>`) and notes layout. Wait until the release is visible.

Then run skill **`fusionner-pr`** as if the user had typed **`/mpr`**.

## 5. Annotate earlier versions

Read the spec section **Changements apportés aux versions antérieures** (format and blocks: `agents/issue-tracker.md`, *Changes to earlier versions* **and** the Critical newline rules there). `Aucun.` or no section → one line, go to step 6. Otherwise annotate each row's targets:

1. `gh release view <tag> --json body` — keep the existing notes.
2. Prepend each new `> **Modifié en VX.Y.Z** …` blockquote **with blank lines between blocks**, then a blank line, then the previous body starting at `## Pourquoi` (or whatever already headed the notes).
3. Write with `gh release edit <tag> --notes-file` (UTF-8 file). Never collapse the body to a single line.
4. Same block as a comment on each listed issue.

Never stop the version on this step: a target that fails is listed in the final reply.

## 6. Stop

Do not start the next version’s branch unless the user asks.

## Not this skill

- Release only → `creer-release` (`/crel`)
- Squash-merge only → `fusionner-pr` (`/mpr`)
- Commit / push → `commit` (`/c`)
- Child wrap → `encadrer-implement`
- Open a version → `ouvrir-la-version`
- Feuille de route de dev only → `augmenter-la-feuille-de-route-dev` (`/afr`)
