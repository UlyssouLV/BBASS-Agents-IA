---
name: demander-avant-commit
description: >-
  Before any git commit, git push, or staging for a commit. Use when finishing
  an issue, when tests pass, when about to run git commit / git push, or when
  the user talks about committing, pushing, or publishing to GitHub.
---

# Demander avant de committer

Never run `git add` + `git commit`, `git commit`, or `git push` unless the **latest user message** clearly asks for it (e.g. "commit", "push", "valide le commit").

Not permission:

- ticket implemented / tests green
- `/implement` or `/code-review` done
- "the work is ready"
- auto-push from a previous habit

Instead:

1. Summarize what changed.
2. List files that would be committed (no `.env`, no secrets, no `.venv`).
3. Ask: ready to commit? Wait for an explicit yes.

If they only said "commit", still do not `git push` unless they also said push.
