---
name: creer-skill
description: >-
  Author a project skill under agents/skills/meta/ or agents/skills/process/ then dispatch it to Claude Code
  and Cursor. Use when the user wants to create, write, or add a skill, says
  « crée un skill », or types `/cs`. Not `/ch`. Not MCP, or editing AGENTS.md alone.
---

# Create a project skill

Write **one** `SKILL.md` under `agents/skills/meta/` or `agents/skills/process/`. Then copy it to the IDE adapters with the repo script. Do **not** write a skill directly into `.claude/skills/` or `.cursor/skills/`.

`/cs` is the same trigger as « crée un skill ».

## 1. Gather

Use the current conversation if it already has the job, the trigger, and what done looks like.

If anything needed to write the skill is missing: invoke Matt Pocock **`grill-with-docs`**. Wait until that interview is finished. Do not invent the gaps.

If the user gives exact wording for the body, use it **verbatim**.

Peers: look at existing skills in `agents/skills/` and `.claude/skills/` for tone and shape.

Always project-scoped. Never `~/.cursor/skills/` or `~/.claude/skills/`.

## 2. Propose, then wait

**Even if there was no grill**, describe in French **before any write**:

- folder name and `meta` / `process`
- trigger (`/` and/or phrase)
- what the skill does, step by step
- what it will **not** do

**Wait** for an explicit **oui**. Anything else → do not write.

## 3. Write `agents/skills/<bucket>/<name>/SKILL.md`

- **`meta/`** — primary capabilities of the coding agents (this skill; `message-de-commit`; etc.). They do not orchestrate other project skills.
- **`process/`** — composed recipes that call other skills (e.g. the version cycle; `commit`, which calls `message-de-commit`).
- If the bucket is unclear, ask. Do not invent it.
- Folder name = frontmatter `name`: lowercase, hyphens, max 64 characters.
- `description`: third person, **what** + **when**. Triggers live here, not restated as a list in the body.
- Body: ordered steps, each with a done-when. Point at repo docs instead of pasting them. Repo paths: one line `Paths: **agents/roles.yml**.` — do not copy the lookup/stop rules; they live in that file.
- Optional siblings in the same folder: `references/`, `scripts/`. Keep `SKILL.md` the recipe.

Match this repo’s skills (`ouvrir-la-version`, `encadrer-implement`, `finaliser-la-version`): short, imperative, French trigger phrases when the human says them in French.

## 4. Dispatch

From the repo root:

```bash
python3 agents/scripts/dispatch.py
python3 agents/scripts/dispatch.py --check
```

If `--check` fails: stop. Do not hand-edit `.claude/skills/` or `.cursor/skills/` to “fix” it; fix the source and dispatch again.

## 5. Guide

Add (or replace if that heading already exists) one section in `agents/docs/guide-skills.md`. Same shape as the peers already in the file:

- French title (`### …`)
- **Commande :**
- **Options :**
- **Corps :**
- one line of what it does
- **Exemple :** a fenced block of what the user would type

Put it under `## Meta` or `## Process` to match the bucket. Do not rewrite the rest of the guide.

Done when the new folder exists under `agents/skills/meta/` or `agents/skills/process/`, `--check` is green, **and** the guide has that section.

## Not this skill

- Claude/Cursor **hooks** → `creer-hook` (`/ch`)
- MCP configs.
- Rewriting files in role **`agent-adapter`** (`agents/roles.yml`) unless the new skill needs a one-line pointer there.
