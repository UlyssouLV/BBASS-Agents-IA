---
name: lancer-claude
description: >-
  Starts a terminal and runs the Claude Code CLI (`claude`). Use when the user
  types /lancer-claude, asks to launch Claude Code from Cursor, or to spawn
  `claude` in a shell for tests under agents/.
disable-model-invocation: true
---

# Lancer Claude Code

Start Claude Code in a terminal. Do not implement tickets. Do not pass extra flags or a prompt.

## Steps

1. From the repo root, run `claude` with working directory `agents/` (the test sandbox).
2. Use the Shell tool. Set `block_until_ms` to `0` so the interactive TUI is not waited on.
3. If `claude` is not on PATH, try `claude.cmd` (Windows). If both fail, report the error and stop.

Do not `/clear`, do not `/implement`, do not write `.claude/prochaine-etape.md`.
