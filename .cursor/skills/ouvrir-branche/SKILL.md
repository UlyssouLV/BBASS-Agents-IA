---
name: ouvrir-branche
description: >-
  Create and check out a git branch from the integration base (origin/main
  by default, or origin/<base_branch> when agents/integration-channel.yml
  exists), carrying the uncommitted working tree. Use when the user types
  `/ob` or says « ouvre une branche », or when another skill tells you to
  run ouvrir-branche with a branch name. Do not commit. Do not push.
  Not `/opr`. Not « Ouvre la version ».
---

# Open a branch

`/ob` **is** permission to `git fetch` and create/checkout a branch. It is **not** permission to commit or push. Never stash in order to commit on the integration **base**. Do not switch to a different existing feature branch to “save” work.

Treat `/ob` as a whole token (slash + letters).

**Base:** resolve per `agents/docs/integration-channel.md` (*Résolution*). Default **base** = `main`.

## 1. Name

The branch name is the rest of the user message after `/ob` (or the name the calling skill passed). Trim whitespace.

If it is missing: ask for a name and **wait**. Do not invent one.

If a local or remote branch of that name already exists: stop and ask. Do not reuse it.

If the name equals **base** or `main` / `master`: stop. Do not create a branch with a protected name.

## 2. Carry the working tree off the base

Uncommitted files stay in the working tree through `checkout -b`. Do **not** `git commit` on **base** / `main` / `master`. Do **not** stash « to keep base clean ».

Committed work that exists only on the current feature branch (not on `origin/<base>`) does **not** come along: the new branch starts at `origin/<base>`.

## 3. Create

From the repo root:

1. `git fetch origin`
2. Create and checkout `<name>` from `origin/<base>` (uncommitted changes come with you).

If checkout fails (conflicts with `origin/<base>`, etc.): stop and report. Do not force.

Done when `git branch --show-current` is `<name>` and **base** has no new commit. Reply with the branch name and the base used.

## Not this skill

- Commit / push: skill `commit` (`/c`, `/c -a -p`).
- Open a PR: skill `ouvrir-pr` (`/opr`).
- Whole version cycle: skill `ouvrir-la-version`.
