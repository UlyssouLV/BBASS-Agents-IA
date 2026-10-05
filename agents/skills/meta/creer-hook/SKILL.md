---
name: creer-hook
description: >-
  Author a project hook under agents/hooks/<name>/ then wire it for Claude
  Code and Cursor. Use when the user types `/ch` or says « crée un hook ».
  Grill then confirm before writing. Not `/cs`. Not user-level ~/.hooks.
---

# Create a project hook

`/ch` is the same trigger as « crée un hook ».

Write **one** hook under `agents/hooks/<name>/`. Then wire **both** adapters. Do **not** write only `.claude/hooks/` or only `.cursor/hooks/`. Never `~/.claude/` or `~/.cursor/`.

`dispatch.py` copies **skills only**. This skill owns hook files and settings.

## 1. Gather

Use the current conversation if it already has: when it fires, what it does (block / allow / audit), which tools.

If any of that is missing: invoke **grill-with-docs**. Wait until that interview is finished. Do not invent the gaps.

Always **project** hooks.

## 2. Propose, then wait

**Even if there was no grill**, describe in French **before any write**:

- folder name `agents/hooks/<name>/`
- Claude event (e.g. `PreToolUse`) and Cursor event (e.g. `preToolUse`)
- matcher
- block vs pass-through vs audit
- what the user will see when it fires

**Wait** for an explicit **oui**. Anything else → do not write.

## 3. Write `agents/hooks/<name>/`

One script the two adapters will run from the **repo root** (prefer `python3 agents/hooks/<name>/hook.py`).

Claude Code (`PreToolUse`, matcher `Skill|Agent|Task`, …): JSON on stdin; **deny** = exit **2** + `decision: block` / `permissionDecision: deny` (see `agents/scripts/gate-code-review.py`).

Cursor (`.cursor/hooks.json` `version: 1`): JSON on stdin; **deny** = `"permission": "deny"` or exit **2**. Matcher = JavaScript regex on the tool name. `failClosed` only if a crash must block. Make a wrapper executable if Cursor needs a shebang file under `.cursor/hooks/` that execs the same Python.

Preserve unrelated hooks. Merge into `.claude/settings.json` **hooks** only (do not add plugins). Merge into `.cursor/hooks.json` without dropping other events.

Do not echo secrets.

## 4. Guide

Add (or replace if that heading already exists) one section in **`agents/docs/guide-hooks.md`**. Same shape as the peers already in that file:

- French title (`### <nom>`)
- **Source :** `agents/hooks/<nom>/…`
- **Claude :** event + matcher
- **Cursor :** event + matcher
- **Fait :** one line of what it blocks or allows

Do not put the hook inventory in `guide-skills.md` (`/ch` stays there as the command). Do not rewrite the rest of the hooks guide.

Done when `agents/hooks/<name>/` exists, **both** adapters are wired, **and** `guide-hooks.md` has that section.

## Not this skill

- Project skills → `creer-skill` (`/cs`)
- MCP configs
- Moving `gate-code-review.py` without `/ch` (inventory: `agents/docs/guide-hooks.md`)
