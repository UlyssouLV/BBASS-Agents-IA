---
name: encadrer-implement
description: >-
  After /implement, when tests pass or fail, when about to /code-review or
  spawn Standards/Spec subagents, when closing a finished child ticket, or
  when choosing the next child issue on a PR. Wraps Matt Pocock /implement
  for this repo: tests, then commit+push+close the issue and remove
  ready-for-agent, then next ticket
  or one branch review.
---

# Wrap `/implement` (Matt Pocock)

Use the plugin **`/implement`** for TDD and the ticket body. **This skill owns the end of the run.** If the plugin says to `/code-review` after one child issue, **skip it**.

Closing a finished **child** ticket is required: GitHub **Blocked by** / **Blocking** only unblocks dependents when the blocker is **Closed**.

## 1. Tests

When the ticket code is in:

- Run the full pytest suite for each package you touched (`vm-centrale` and/or `poste`), with that package’s venv.
- If **any** test fails: stop. No commit, no push, no close. Report the failures.

## 2. Tests green → commit, push, close, drop `ready-for-agent`

This path **is** permission to `git commit`, `git push`, `gh issue edit --remove-label`, and `gh issue close` for **this child**.

1. Stage only the ticket files. Never `.env`, `*.db`, `.venv/`, secrets.
2. Commit with a short message that says **why** (repo style: French, one or two sentences).
3. `git push` the current feature branch (`-u origin HEAD` if it has no upstream). No force-push.
4. On the **child** you just implemented, remove `ready-for-agent` then close:

   `gh issue edit <n> --remove-label "ready-for-agent"`

   If GitHub says the label is already absent, continue.

   `gh issue close <n> --comment "Implémenté sur <branch> (<sha>). Tests verts."`

   Do not add `wontfix`. Do not use a label for “coded but not on main”. There is no `awaiting-merge`. A Closed child must not keep `ready-for-agent`.

Do **not** close the **parent** spec issue here (e.g. #13). Squash-merge `Fixes #<parent>` does that.

## 3. More child tickets on this PR?

Find the parent (`## Parent` / `Part of #n` on the issue you just finished). List **open** children of that parent.

- **Done:** Closed.
- **Still to build:** Open, `ready-for-agent` (and not `wontfix`).

A remaining ticket is **unblocked** when GitHub reports no open blockers (`issue_dependencies_summary.blocked_by` is 0), or every issue in a fallback **Blocked by** body line is Closed.

**If at least one unblocked child remains:**

- Do **not** run `/code-review`.
- Propose the **next** unblocked child (lowest issue number among unblocked `ready-for-agent`).
- Ask the user to `/clear` then `/implement #<next>`. Wait. Do not start the next implement in this same compacted window.

**If no remaining children** (all PR children are Closed):

- Run **`/code-review` once**, fixed point **`main`** (full branch diff). Standards sources: `CLAUDE.md`.
- Then stop unless the user asks to undraft/merge the PR.

## Not this skill

- Opening or merging the PR, GitHub Release, deleting the branch: skill `finaliser-la-version` (« Finalise la version »).
- Re-implementing Closed children.
- `needs-triage` work (e.g. #6) that is not a child of this PR.
