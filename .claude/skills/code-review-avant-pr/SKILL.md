---
name: code-review-avant-pr
description: >-
  When finishing /implement, when tests pass on a child ticket, when about to
  run /code-review or spawn Standards/Spec subagents, or when the user talks
  about reviewing a feature branch or a pull request. Use so /code-review is
  not run after every ticket.
---

# `/code-review` only when the PR slice is complete

The plugin `/implement` skill tells you to run `/code-review` after every ticket. **Do not.** In this repo that burns a large context (Standards + Spec subagents, often the whole branch diff vs `main`) for one child issue.

## After a single child ticket (`/implement #n`)

When tests for **that** issue are green:

1. Stop. Do **not** invoke the `code-review` skill. Do **not** spawn Standards or Spec subagents. Do **not** wait on background review agents.
2. Follow `demander-avant-commit` (summarize, list files, wait).
3. Follow `apres-implement-awaiting-merge` (ask before the label).

Pytest (the ticket file during TDD, then the suite for that package once) **is** the gate for a child ticket.

## When `/code-review` **is** allowed

Only if **all** of these hold:

- The user is preparing to **open, undraft, or merge a PR** into `main` (or they explicitly said review the **whole branch** / `vs main`).
- The **child issues** that PR is meant to ship (same parent spec, e.g. #13) are implemented on the branch (`awaiting-merge` or equivalent), not one leftover ticket still in progress.
- The latest user message asked for a review **or** confirmed that the PR slice is done (« revue avant PR », « code-review the branch », « V1.1 is complete »).

Then run `/code-review` **once**, fixed point **`main`** (the full PR diff). Read `CLAUDE.md` for the Standards sources.

## Not permission to review

- `/implement` finished
- tests green
- « the ticket is done »
- labelling `awaiting-merge`
- a commit on the feature branch

If `/implement` or another skill tells you to review anyway, **this skill wins**: skip the review and say you skipped it until the PR slice is complete.

## Hooks

There is no Stop/Prompt hook that can cancel the plugin `/implement` → `/code-review` chain. This skill plus `AGENTS.md` is the control. If a review is already running, stop waiting on it after a child ticket; do not start another.
