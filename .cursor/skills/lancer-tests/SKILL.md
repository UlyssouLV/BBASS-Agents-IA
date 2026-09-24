---
name: lancer-tests
description: >-
  Run the pytest suites under role test-roots (agents/roles.yml).
  Use when the user types `/t` or says « lance les tests », or when another
  skill tells you to run lancer-tests. Do not commit. Do not close issues.
---

# Run package tests

`/` = this skill’s trigger. No options.

Follow the Tests convention in role **`agent-adapter`**. Do not invent a different test style.

Paths: **`agents/roles.yml`**.

## 1. Which packages

Role **`test-roots`**. From `git diff --name-only origin/main` plus `git status --short`:

- any path under a test-root → run pytest in that root

If none of those roots appear in the diff: run **every** test-root.

## 2. Run

For each selected root, from that directory, with **that** package’s venv:

```bash
.venv/bin/python -m pytest
```

(Windows: `.venv/Scripts/python.exe -m pytest`.)

If the venv is missing: stop and report. Do not invent another interpreter.

Any non-zero pytest → **fail**. Report the failures. Do not continue a caller’s later steps.

Done when every selected suite exited 0, or as soon as one failed.

## Not this skill

- Quality gate: `quality-gate` (`/qg`)
- Tests then gate: `verifier-la-fiabilite` (`/vf`)
- Close a child issue: `fermer-ticket-enfant` (`/cci`).
- Commit: `commit` (`/c`).
