---
name: encadrer-implement
description: >-
  After /implement, when tests pass or fail, when about to /code-review or
  spawn Standards/Spec subagents, when labelling awaiting-merge, or when
  choosing the next child issue on a PR. Wraps Matt Pocock /implement for
  this repo: tests, then commit+push+awaiting-merge, then next ticket or
  one branch review.
---

# Wrap `/implement` (Matt Pocock)

Use the plugin **`/implement`** for TDD and the ticket body. **This skill owns the end of the run.** If the plugin says to `/code-review` after one child issue, **skip it**.

Do **not** `gh issue close` because a ticket is coded. Issues stay **Open** until merge to `main` (`Fixes` on the PR). See `docs/agents/triage-labels.md`.

## 1. Tests

When the ticket code is in:

- Run the full pytest suite for each package you touched (`vm-centrale` and/or `poste`), with that package’s venv.
- If **any** test fails: stop. No commit, no push, no label change. Report the failures.

## 2. Tests green → commit, push, label

This path **is** permission to `git commit` and `git push` (unlike a random “the work is ready”).

1. Stage only the ticket files. Never `.env`, `*.db`, `.venv/`, secrets.
2. Commit with a short message that says **why** (repo style: French, one or two sentences).
3. `git push` the current feature branch (`-u origin HEAD` if it has no upstream). No force-push.
4. Keep the GitHub issue **Open**. Add `awaiting-merge`. Remove `ready-for-agent` and `ready-for-human` if present (omit a `--remove-label` that would 404). Do not add `wontfix`.

Skip labelling the **parent** spec issue (e.g. #13) until every child for that PR is on the branch.

## 3. More child tickets on this PR?

Find the parent (`## Parent` / `Part of #n` on the issue you just finished). List **open** children of that parent.

- **Done:** `awaiting-merge` (or already merged/closed on `main`).
- **Still to build:** `ready-for-agent` (and not `wontfix`).

A remaining ticket is **unblocked** when every issue named under **Blocked by** is done (treat a “Blocked by #1” *slice index* as the matching child if GitHub numbers differ — prefer an explicit `#14` style id when present).

**If at least one unblocked child remains:**

- Do **not** run `/code-review`.
- Propose the **next** unblocked child (lowest issue number among unblocked `ready-for-agent`).
- Ask the user to `/clear` then `/implement #<next>`. Wait. Do not start the next implement in this same compacted window.

**If no remaining children** (all PR children are `awaiting-merge` or on `main`):

- Run **`/code-review` once**, fixed point **`main`** (full branch diff). Standards sources: `CLAUDE.md`.
- Then stop unless the user asks to undraft/merge the PR.

## Not this skill

- Opening or merging the PR, GitHub Release, deleting the branch: skill `finaliser-la-version` (« Finalise la version »).
- Re-implementing `awaiting-merge` tickets.
- `needs-triage` work (e.g. #6) that is not a child of this PR.
