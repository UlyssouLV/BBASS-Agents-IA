---
name: mettre-a-jour-le-pack
description: >-
  Inventory gaps between this project and workflow-agents-pack, propose path
  and convention migrations, wait for oui, then run update-from-pack plus
  those migrations. Use when the user types `/up`, or says « mets à jour le
  pack », « update le pack ». Not `/init`. Not first-time adopter-le-pack.
  Does not commit unless the user also asked `/c`.
---

# Mets à jour le pack (`/up`)

Triggered by **`/up`**, **« mets à jour le pack »**, or **« update le pack »**.  
`/` = this skill’s trigger. No hyphen options on `/up` itself (docs/suivi are chosen in the plan).

This skill **orchestrates** an intelligent upgrade. The bash script
`agents/scripts/update-from-pack.sh` remains the **sync-only** engine
(skills/hooks/scripts; templates are read from the pack, never copied). Migrations (paths, roles, tracker) come from
**`agents/docs/migrations-pack.md`** in the **pack source** (not only the
local copy, which may be stale).

Do **not** `/implement`. Do **not** merge. Do **not** force-push.  
Do **not** commit unless the **current** user message also asks for **`/c`**.

## 0. Guards

1. Cwd is the **project** root. If `agents/skills/` is missing → **stop**.  
   First install → `adopter-le-pack.sh` or `/init`, not this skill.
2. Read the migrations catalogue from the pack source (step 1):  
   `<pack>/agents/docs/migrations-pack.md`. Missing → **stop**.

## 1. Resolve pack source

1. If the user message gives an absolute/relative path to a
   `workflow-agents-pack` checkout that contains `agents/scripts/update-from-pack.sh`  
   → use it. Note its `git rev-parse HEAD` when available.
2. Else clone:

   ```bash
   TMP=$(mktemp -d)
   git clone --depth 1 https://github.com/UlyssouLV/workflow-agents-pack.git "$TMP"
   ```

   Pack root = `$TMP`. Record `git -C "$TMP" rev-parse --short HEAD`.  
   Delete `$TMP` at the end of the skill (success or stop after apply attempt).

Done when `PACK` path and `PACK_SHA` are known.

## 2. Inventory (read-only)

Against the **project** cwd, using the catalogue in
`<pack>/agents/docs/migrations-pack.md`, evaluate each id:

- `glossaire-path`, `feuille-path`, `roles-required`, `agents-tracker`,
  `adapter-cycle`, `skills-sync` (always applicable), `opt-docs`,
  `docs-site-sync`, `opt-suivi`

Also list skill folder names under `agents/skills/meta|process/` that exist
**only** in the project (not in the pack) — for information; never delete them.

Compare optionally `agents/.pack-sha` (if present) to `PACK_SHA` (one line).

Write nothing yet. Build the proposed action list in French.

## 3. Propose, then wait

Show a numbered list (or table): each **id**, one-line detection, one-line
action. For `opt-docs` / `opt-suivi`: ask **o/n** in the same proposal.

**Wait** for an explicit **oui** (whole word), or a subset like
« seulement glossaire-path, skills-sync, opt-docs o ».

Anything else → **stop**. Do not apply.

## 4. Apply (only what was accepted)

Order:

1. **Path / roles migrations** (`glossaire-path`, `feuille-path`, `roles-required`)  
   as specified in the catalogue.
2. **`agents-tracker`** — copy from pack:  
   `agents/issue-tracker.md`, `agents/triage-labels.md`.
3. **`adapter-cycle`** — merge Cycle + Tests (and CLAUDE « Fin d’un /implement »)  
   from pack `initialise-le-repo/references/` into project `AGENTS.md` /
   `.claude/CLAUDE.md` without wiping unrelated sections.
4. **`skills-sync`** (+ opt flags) from **project root**:

   ```bash
   bash "$PACK/agents/scripts/update-from-pack.sh" [--with-docs] [--with-suivi]
   ```

   Include `--with-docs` only if `opt-docs` was accepted as **o** or
   `docs-site-sync` was accepted. Include `--with-suivi` only if accepted as **o**.  
   That script already runs `dispatch.py` + `--check`. If it fails → **stop**
   and report; still try to remove the temp clone.
5. Write `agents/.pack-sha` with `PACK_SHA` (one line).
6. Collect the reminders listed under « Rappels du résumé `/up` » in the
   catalogue whose condition holds. They go in the reply (step 5).

## 5. Reply

French summary: applied ids, skipped ids, local-only skills left untouched,
`PACK_SHA`, the reminders from step 4.6 (a « À faire » list, never omitted
when one applies), and whether commit is still needed (`/c -a -p` on a feature
branch — or on `main` only if the user explicitly allows it for that repo).

## Not this skill

- First pack install → `adopter-le-pack.sh` / `/init`
- Sync-only without migration interview → run `update-from-pack.sh` yourself
- Feuille content rewrite → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Commit / push → `commit` (`/c`)
- Opening a version → `ouvrir-la-version`
