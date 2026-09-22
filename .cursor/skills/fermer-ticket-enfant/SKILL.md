---
name: fermer-ticket-enfant
description: >-
  Close a GitHub child issue and drop ready-for-agent. Use when the user
  types `/cci` or says « ferme le ticket enfant », or when another skill
  tells you to run fermer-ticket-enfant with `#n`. `-t` runs lancer-tests
  (`/t`) first and aborts the close on failure. Never close the parent spec.
---

# Close a child issue

`/` = this skill’s trigger. `-` = options. Treat `/cci` and `-t` as whole tokens. Order does not matter.

This path **is** permission to `gh issue edit --remove-label` and `gh issue close` for **that child only**. Do not merge. Do not commit (skill `commit` / `/c`).

## 1. Number

The child number is `#n` / `n` in the user message (or the number the calling skill passed).

If it is missing: ask and **wait**. Do not invent one.

## 2. Child, not parent

`gh issue view <n>`. If the body has no **`Part of #<parent>`** and no **`## Parent`**: **stop**. That `n` is not a child (likely the spec). Do not close it.

If the issue is already Closed: say so and stop.

## 3. Tests (`-t` only)

If **`-t`** is present: run skill **`lancer-tests`** as if the user had typed **`/t`**. If that skill fails: **stop**. Do not close.

Without `-t`: skip tests.

## 4. Label, then close

1. `gh issue edit <n> --remove-label "ready-for-agent"` — if GitHub says the label is already absent, continue.
2. `gh issue close <n>` with comment:
   - after `-t`, **or** if the calling skill already ran `/t` successfully this turn: `Implémenté sur <branch> (<sha>). Tests verts.`
   - otherwise: `Implémenté sur <branch> (<sha>).`
   Branch = `git branch --show-current`. SHA = `git rev-parse --short HEAD`.

Do not add `wontfix`. Do not close any other issue.

Done when `gh issue view <n> --json state` is `CLOSED` and `ready-for-agent` is gone.

## Not this skill

- Tests only: `lancer-tests` (`/t`).
- Full `/implement` wrap (next ticket / Finalise): `encadrer-implement`.
- Squash-merge: `finaliser-la-version`.
