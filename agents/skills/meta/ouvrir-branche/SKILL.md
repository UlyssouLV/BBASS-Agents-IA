---
name: ouvrir-branche
description: >-
  Create and check out a git branch from origin/main, carrying the
  uncommitted working tree. Use when the user types `/ob` or says
  « ouvre une branche », or when another skill tells you to run
  ouvrir-branche with a branch name. Do not commit. Do not push.
  Not `/opr`. Not « Ouvre la version ».
---

# Open a branch

`/ob` **is** permission to `git fetch` and create/checkout a branch. It is **not** permission to commit or push. Never stash in order to commit on `main`. Do not switch to a different existing feature branch to “save” work.

Treat `/ob` as a whole token (slash + letters).

## 1. Name

The branch name is the rest of the user message after `/ob` (or the name the calling skill passed). Trim whitespace.

If it is missing: ask for a name and **wait**. Do not invent one.

If a local or remote branch of that name already exists: stop and ask. Do not reuse it.

## 2. Carry the working tree off `main`

Uncommitted files stay in the working tree through `checkout -b`. Do **not** `git commit` on `main` / `master`. Do **not** stash « to keep main clean ».

Committed work that exists only on the current feature branch (not on `origin/main`) does **not** come along: the new branch starts at `origin/main`.

## 3. Create

From the repo root:

1. `git fetch origin`
2. Create and checkout `<name>` from `origin/main` (uncommitted changes come with you).

If checkout fails (conflicts with `origin/main`, etc.): stop and report. Do not force.

Done when `git branch --show-current` is `<name>` and `main` has no new commit. Reply with the branch name.

## Not this skill

- Commit / push: skill `commit` (`/c`, `/c -a -p`).
- Open a PR: skill `ouvrir-pr` (`/opr`).
- Whole version cycle: skill `ouvrir-la-version`.
