---
name: lister-skills
description: >-
  List every project skill on disk and where it is available (agents/,
  Claude, Cursor). Use when the user types `/sl` or says « récapitule les
  skills » / « skill list ». Do not read agents/docs/guide-skills.md as
  the inventory. Not for creating or dispatching skills.
---

# List project skills

Scan the three skill trees on disk. Print where each skill lives. Do **not** open `agents/docs/guide-skills.md`.

Treat `/sl` as a whole token (slash + letters).

## 1. Collect

From the repo root, find every folder that contains a `SKILL.md`:

1. `agents/skills/` — identity = that folder’s name; record `meta` or `process` from the parent of the skill folder
2. `.claude/skills/` — identity = folder name
3. `.cursor/skills/` — identity = folder name

Ignore `~/.claude/skills/` and `~/.cursor/skills/`. Union the names.

Done when you have three sets of names, plus a bucket (`meta` / `process` / **absent**) for each name under `agents/`.

## 2. Report

In French, one table (or equivalent aligned list), one row per skill name, sorted. Columns:

- **nom**
- **agents/** — `meta`, `process`, or **non**
- **Claude** — yes if `.claude/skills/<nom>/SKILL.md` exists
- **Cursor** — yes if `.cursor/skills/<nom>/SKILL.md` exists

Then an **écarts** block, only the non-empty lines:

- in `agents/skills/` but missing from Claude and/or Cursor
- in Claude and/or Cursor but **not** under `agents/skills/` (say which adapter)

Do not invent availability from how an IDE might also load the other adapter. Columns are filesystem only.

Done when every `SKILL.md` folder appears once and the écarts match the sets.

## Not this skill

- Authoring a skill: `creer-skill` (`/cs`).
- Copying source to adapters: `python3 agents/scripts/dispatch.py`.
