---
name: creer-skill
description: >-
  Author a project skill under agents/skills/meta/ or agents/skills/process/ then dispatch it to Claude Code
  and Cursor. Use when the user wants to create, write, or add a skill, or says
  « crée un skill ». Not for hooks, MCP, or editing AGENTS.md alone.
---

# Create a project skill

Write **one** `SKILL.md` under `agents/skills/meta/` or `agents/skills/process/`. Then copy it to the IDE adapters with the repo script. Do **not** write a skill directly into `.claude/skills/` or `.cursor/skills/`.

## 1. Gather

Use the current conversation if it already has the job, the trigger, and what done looks like.

If anything needed to write the skill is missing: invoke Matt Pocock **`grill-with-docs`**. Wait until that interview is finished. Do not invent the gaps.

If the user gives exact wording for the body, use it **verbatim**.

Peers: look at existing skills in `agents/skills/` and `.claude/skills/` for tone and shape.

Always project-scoped. Never `~/.cursor/skills/` or `~/.claude/skills/`.

## 2. Write `agents/skills/<bucket>/<name>/SKILL.md`

- **`meta/`** — primary capabilities of the coding agents (this skill; later: commit, etc.). They do not orchestrate other project skills.
- **`process/`** — composed recipes that call other skills (e.g. the version cycle: `ouvrir-la-version`, `encadrer-implement`, `finaliser-la-version`).
- If the bucket is unclear, ask. Do not invent it.
- Folder name = frontmatter `name`: lowercase, hyphens, max 64 characters.
- `description`: third person, **what** + **when**. Triggers live here, not restated as a list in the body.
- Body: ordered steps, each with a done-when. Point at repo docs instead of pasting them.
- Optional siblings in the same folder: `references/`, `scripts/`. Keep `SKILL.md` the recipe.

Match this repo’s skills (`ouvrir-la-version`, `encadrer-implement`, `finaliser-la-version`): short, imperative, French trigger phrases when the human says them in French.

## 3. Dispatch

From the repo root:

```bash
python3 agents/scripts/dispatch.py
python3 agents/scripts/dispatch.py --check
```

If `--check` fails: stop. Do not hand-edit `.claude/skills/` or `.cursor/skills/` to “fix” it; fix the source and dispatch again.

Done when the new folder exists under `agents/skills/meta/` or `agents/skills/process/` **and** `--check` is green.

## Not this skill

- Claude/Cursor **hooks** or MCP configs.
- Rewriting `AGENTS.md` / `.claude/CLAUDE.md` unless the new skill needs a one-line pointer there.
