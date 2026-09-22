---
name: lancer-tests
description: >-
  Run the HTTP-boundary pytest suites for vm-centrale and/or poste.
  Use when the user types `/t` or says « lance les tests », or when another
  skill tells you to run lancer-tests. Do not commit. Do not close issues.
---

# Run package tests

`/` = this skill’s trigger. No options.

HTTP-boundary tests only (see `AGENTS.md` **Tests**). Do not add or praise tests of internal function calls.

## 1. Which packages

From `git diff --name-only origin/main` plus `git status --short`:

- any path under `vm-centrale/` → run **vm-centrale**
- any path under `poste/` → run **poste**

If neither appears: run **both**.

## 2. Run

For each selected package, from that package directory, with **that** package’s venv:

```bash
.venv/bin/python -m pytest
```

(Windows: `.venv/Scripts/python.exe -m pytest`.)

If the venv is missing: stop and report. Do not invent another interpreter.

Any non-zero pytest → **fail**. Report the failures. Do not continue a caller’s later steps.

Done when every selected suite exited 0, or as soon as one failed.

## Not this skill

- Close a child issue: `fermer-ticket-enfant` (`/cci`).
- Commit: `commit` (`/c`).
