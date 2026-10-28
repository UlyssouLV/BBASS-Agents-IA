---
name: lancer-tests
description: >-
  Run the test suites under role test-roots (agents/roles.yml), scoped to
  changed files when possible. Detect the runner in each root (pytest+venv,
  else npm test, else cargo test). Use when the user types `/t` or `/t -a`, or says « lance
  les tests », or when another skill tells you to run lancer-tests.
  `-a` forces every test-root full suite. Do not commit. Do not close issues.
---

# Run package tests

`/` = this skill’s trigger. `-` = options. Treat `/t` and `-a` as whole tokens.

If role **`agent-adapter`** has a Tests section, apply those extra rules. Do not invent a different test style.

Paths: **`agents/roles.yml`**. Role **`test-roots`** must resolve; else **stop** (do not invent roots).

## 0. Option `-a`

If **`-a`** is present: skip scoping. Run **every** test-root with its **full** suite (step 3 with no path args for pytest; `npm test` and `cargo test --workspace` as usual). Go to step 2.

## 1. Which files, then which packages

**Changed files** (hybrid):

1. If `git status --short` is **non-empty** → paths from the working tree and index (parse status; include modified, added, deleted, renames — use the new path for renames).
2. Else → `git diff --name-only origin/main...HEAD`.
3. If that list is empty → treat as “no scoped files” (step below falls through to every root).

**Select test-roots:**

- Any changed path that lies under a `test-roots` entry → that root is selected.
- If **no** selected root → select **every** test-root (safe fallback).

Done when the set of roots to run is known. Report whether the file list came from the working tree or from `origin/main...HEAD`.

## 2. Detect the runner

In **each** selected root, inspect only files in that root. First match wins:

1. **pytest-venv** — `pytest` appears in `pyproject.toml`, `pytest.ini`, or `setup.cfg`, **and** `.venv/bin/python` or `.venv/Scripts/python.exe` exists.
2. **npm-test** — `package.json` has `scripts.test`.
3. **cargo-test** — `Cargo.toml` exists at the root and `cargo` is on `PATH` (or `~/.cargo/bin/cargo`).

`pytest` declared but the venv interpreter is missing → **stop**. Do not invent another interpreter.

`Cargo.toml` present but no `cargo` → **stop**. Tell the user to install Rust (rustup).

No match → **stop**. Report the root and that the test model is unknown. Do not invent a runner.

## 3. Scope pytest paths (skipped when `-a`)

For each **pytest-venv** root, build the pytest argument list from changed files under that root:

1. Collect changed paths under this root (relative to the root when passing to pytest).
2. **Already a test file** — include it if its name matches `test_*.py` or `*_test.py`, **or** it lives under a `tests/` or `test/` directory segment. File must still exist on disk (deleted → skip that path).
3. **Source → tests** — for other `*.py` files (not `__init__.py`), let `stem` = filename without `.py`. Search **under this root only** for existing files:
   - any path matching `**/test_<stem>.py` or `**/<stem>_test.py`
   - mirror under `tests/` or `test/`: e.g. `src/pkg/foo.py` → `tests/pkg/test_foo.py`, `tests/test_foo.py`, `test/pkg/test_foo.py` (check what exists; do not invent)
4. Deduplicate. Only paths that **exist** count.

**Run mode for this root:**

- At least one existing test path → `.venv/.../python -m pytest <those paths>`
- Zero matches (including: only non-Python / docs / config touched, or no test file found) → **full suite** of the root: `.venv/.../python -m pytest` with no path args. Say that the scope fell back to the full suite.

For **npm-test** roots: always `npm test` (no path filter).

For **cargo-test** roots: always `cargo test --workspace` (no path filter).

## 4. Run

From that root:

- pytest-venv: `.venv/bin/python -m pytest` … (Windows: `.venv/Scripts/python.exe -m pytest`) with the args from step 3 (or none if `-a` / fallback).
- npm-test: `npm test`
- cargo-test: `cargo test --workspace`

Any non-zero exit → **fail**. Report the failures. Do not continue a caller’s later steps.

Done when every selected suite exited 0, or as soon as one failed. Say which runner each root used and whether pytest was **scoped** or **full**.

## Not this skill

- Quality gate: `quality-gate` (`/qg`)
- Tests then gate: `verifier-la-fiabilite` (`/vf`)
- Close a child issue: `fermer-ticket-enfant` (`/cci`).
- Commit: `commit` (`/c`).
