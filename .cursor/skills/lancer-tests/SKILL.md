---
name: lancer-tests
description: >-
  Run the test suites under role test-roots (agents/roles.yml). Detect the
  runner in each root (pytest+venv, else npm test). Use when the user types
  `/t` or says « lance les tests », or when another skill tells you to run
  lancer-tests. Do not commit. Do not close issues.
---

# Run package tests

`/` = this skill’s trigger. No options.

If role **`agent-adapter`** has a Tests section, apply those extra rules. Do not invent a different test style.

Paths: **`agents/roles.yml`**.

## 1. Which packages

Role **`test-roots`**. From `git diff --name-only origin/main` plus `git status --short`:

- any path under a test-root → run that root

If none of those roots appear in the diff: run **every** test-root.

## 2. Detect the runner

In **each** selected root, inspect only files in that root. First match wins:

1. **pytest-venv** — `pytest` appears in `pyproject.toml`, `pytest.ini`, or `setup.cfg`, **and** `.venv/bin/python` or `.venv/Scripts/python.exe` exists.
2. **npm-test** — `package.json` has `scripts.test`.

`pytest` declared but the venv interpreter is missing → **stop**. Do not invent another interpreter.

Neither match → **stop**. Report the root and that the test model is unknown. Do not invent a runner.

## 3. Run

From that root:

- pytest-venv: `.venv/bin/python -m pytest` (Windows: `.venv/Scripts/python.exe -m pytest`)
- npm-test: `npm test`

Any non-zero exit → **fail**. Report the failures. Do not continue a caller’s later steps.

Done when every selected suite exited 0, or as soon as one failed. Say which runner each root used.

## Not this skill

- Quality gate: `quality-gate` (`/qg`)
- Tests then gate: `verifier-la-fiabilite` (`/vf`)
- Close a child issue: `fermer-ticket-enfant` (`/cci`).
- Commit: `commit` (`/c`).
