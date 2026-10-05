---
name: corriger-quality-gate
description: >-
  After a red Sonar quality gate, fix the code until the failed conditions
  are addressed or the remaining issues need the user. Use when the user
  types `/cqg` or says « Corriger le quality gate », or when
  encadrer-implement finds a red `/qg`. Do not merge. Do not tag. Do not
  `/qg` again on the same HEAD SHA.
---

# Fix the quality gate

Triggered by **`/cqg`** or **« Corriger le quality gate »**. `/` = this skill’s trigger. No hyphen options.

Git commit goes through **`commit`** (`/c`) only if the user asked to commit this turn, or a caller skill already gave `/c`. This skill does **not** `/c` on its own.

## 1. Read the gate

Run skill **`quality-gate`** as if the user had typed **`/qg`**.

- Green → say so and **stop**. Nothing to fix.
- Missing credentials / no analysis for `HEAD` → **stop** (that skill already said why).
- Red (`ERROR`, `WARN`, …) → keep the failed conditions. Go to step 2.

## 2. Fix

Change only what the failed conditions require (code, tests, or config the gate actually names). Do not drive-by refactors.

If a condition is a product/policy choice (coverage floor, duplication budget) you cannot meet without the user: **stop** and ask. Do not weaken the gate in Sonar to pass.

## 3. After the fix

`/qg` is SHA-scoped. The same `HEAD` still has the same analysis.

- Working tree unchanged → the gate is still the one step 1 reported. Stop.
- Files changed → **stop**. Tell the caller (or the user) to `/c` then `/qg` (use `/qg -w` after a push). Do not run `/qg` again on this SHA.

Done when `/qg` was already green, after one fix pass, or after a stop that needs the user.

## Not this skill

- Read-only gate: `quality-gate` (`/qg`)
- Tests: `lancer-tests` (`/t`)
- Tests then gate: `verifier-la-fiabilite` (`/vf`)
- Implement wrap (wait, `/cqg`, commit, re-check): `encadrer-implement`
