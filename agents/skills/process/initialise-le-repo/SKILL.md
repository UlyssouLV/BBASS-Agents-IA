---
name: initialise-le-repo
description: >-
  Scaffold a new repo around the agents pack: directories, dispatch, Matt
  grill, README plus AGENTS.md and CLAUDE.md templates, then `/c -a -p`
  (allowed on main). Use when the user types `/init` or says « Initialise
  le repo ». Stop if a README already exists. Not « Ouvre la version ».
---

# Initialise the repo

Triggered by **`/init`** or **« Initialise le repo »**. `/` = this skill’s trigger. No hyphen options.

The pack **`agents/`** must already be in the repo. This skill does **not** create it. It scaffolds **around** it, then dispatches skills.

Do **not** `/implement`. Do **not** merge. Do **not** force-push. Git commit / push go through **`commit`** (`/c -a -p`), which may run on **`main`** only because the user message is this skill.

Paths: **`agents/roles.yml`**. After step 2, those paths are the pack layout in `references/roles.yml`.

## 0. Guards

1. `agents/scripts/dispatch.py` is missing → **stop**. The pack is not in this repo.
2. `README.md` already exists → **stop**. Already initialised. Do not overwrite.

## 1. Skeleton (missing paths only)

Create only what is absent. Never overwrite an existing file.

- `docs/dev/feuille-de-route-dev.md` — title `# Feuille de route` only
- `docs/specs/` (directory)
- `docs/adr/` (directory)
- `CONTEXT.md` — title `# Glossary` only

Copy `agents/scripts/gate-code-review.py` → `.claude/hooks/gate-code-review.py`.

Merge **only** the `hooks` object from `references/settings-hooks.json` into `.claude/settings.json` (create the file if needed). Do **not** add `enabledPlugins` / frontend-design.

Replace `agents/roles.yml` with `references/roles.yml` (pack paths). Do not invent `test-roots`.

## 2. Dispatch

```bash
python3 agents/scripts/dispatch.py
python3 agents/scripts/dispatch.py --check
```

If `--check` fails: **stop**. Fix the pack source, dispatch again. Do not hand-edit `.claude/skills/` or `.cursor/skills/`.

## 3. Grill

Call **grill-with-docs**. Topic: what this repo is for, what you will build. Rounds until the tree is empty. **Wait** for shared-understanding confirmation.

Do not write the README until that confirmation.

## 4. README + templates

Write role **`readme`** from the grill (French unless the user-facing docs will be English). What the project is, what you can do, how to start. Not a dump of the interview.

If missing, copy:

- `references/AGENTS.md` → `AGENTS.md`
- `references/CLAUDE.md` → `.claude/CLAUDE.md`

Do not overwrite those two if they already exist.

## 5. Commit

Run skill **`commit`** as if the user had typed **`/c -a -p`**. Still never `.env`, `*.db`, `.venv/`, secrets.

If there is no remote, the commit still counts; report a failed push and stop.

Done when `README.md` exists, dispatch `--check` is green, and HEAD has that init commit.

## Not this skill

- Open a version → `ouvrir-la-version`
- Tests → `lancer-tests` (`/t`)
- Quality gate → `quality-gate` (`/qg`)
- Tests then gate → `verifier-la-fiabilite` (`/vf`)
- « Finalise la version » → `finaliser-la-version`
