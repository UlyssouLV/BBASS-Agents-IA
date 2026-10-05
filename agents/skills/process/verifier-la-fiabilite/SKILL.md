---
name: verifier-la-fiabilite
description: >-
  Run `/t` then `/qg`. Use when the user types `/vf` or says « Vérifie la
  fiabilité du code ». Do not commit. Do not close issues. Do not fix the
  gate (that is `/cqg`).
---

# Verify code reliability

Triggered by **`/vf`** or **« Vérifie la fiabilité du code »**. `/` = this skill’s trigger. No hyphen options.

Do **not** `git commit`. Do **not** `gh issue close`. Do **not** start `/cqg` unless the user asked.

## 1. Tests

Run skill **`lancer-tests`** as if the user had typed **`/t`**. If it fails: **stop**. Do not run `/qg`.

## 2. Quality gate

Run skill **`quality-gate`** as if the user had typed **`/qg`**. If it fails: **stop**. Propose **`/cqg`** if they want the code fixed; wait.

Done when `/t` and `/qg` both succeeded, or as soon as one failed.

## Not this skill

- Tests only → `lancer-tests` (`/t`)
- Gate only → `quality-gate` (`/qg`)
- Fix the gate → `corriger-quality-gate` (`/cqg`)
- Commit → `commit` (`/c`)
