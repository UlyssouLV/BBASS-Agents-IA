---
name: encadrer-implement
description: >-
  Green pytest after a child GitHub ticket, or the implement plugin's closing
  step: `/t`, `/c -p`, `/cci #<n>`, then the next unblocked child or ask the
  user to test then Finalise la version. Load this as soon as /implement
  tests pass.
---

# Wrap `/implement`

Use the plugin **`/implement`** for TDD and the ticket body. **This skill owns the end of the run.** The plugin’s last line is a review step; in this repo that last line is **this skill, from Tests onward**.

Git, tests, and closing the child go through the skills below, not inline. Do **not** close the **parent** spec (squash `Fixes #<parent>` does that). Do **not** `/implement` the parent.

## 1. Tests

Run skill **`lancer-tests`** as if the user had typed **`/t`**. If it fails: **stop**. No commit, no close.

## 2. Commit and push

Stage **only** the ticket files. Never `.env`, `*.db`, `.venv/`, secrets. Do **not** pass `-a`.

Then run skill **`commit`** as if the user had typed **`/c -p`**.

## 3. Close the child

Run skill **`fermer-ticket-enfant`** as if the user had typed **`/cci #<n>`** (`<n>` = the child just implemented). No `-t` (tests already ran). That skill refuses if `<n>` is not a child.

## 4. More child tickets on this PR?

Find the parent (`## Parent` / `Part of #n` on the issue you just finished). List **open** children of that parent.

- **Done:** Closed.
- **Still to build:** Open, `ready-for-agent` (and not `wontfix`).

A remaining ticket is **unblocked** when GitHub reports no open blockers (`issue_dependencies_summary.blocked_by` is 0), or every issue in a fallback **Blocked by** body line is Closed. See `agents/issue-tracker.md`.

**If at least one unblocked child remains:**

- Propose the **next** unblocked child (lowest issue number among unblocked `ready-for-agent`).
- Ask the user to `/clear` then `/implement #<next>`. Wait. Do not start the next implement in this same compacted window.

**If no remaining children** (all PR children are Closed):

- Stop after telling the user, in French, exactly this handoff (adapt only the parent/PR numbers if useful):

  Tous les tickets ont été implémentés. Veuillez faire des tests pour valider que tout est fonctionnel ; lorsque ce sera bon, lancez le skill **Finalise la version** (`finaliser-la-version`).

- Do not merge, tag, or start the next version.

## Not this skill

- Tests only → `lancer-tests` (`/t`)
- Commit / push → `commit` (`/c`)
- Close a child only → `fermer-ticket-enfant` (`/cci`)
- Opening or merging the PR, GitHub Release, deleting the branch → `finaliser-la-version`
- Re-implementing Closed children
- `needs-triage` work that is not a child of this PR
- A two-axis review vs `main`: only if the human typed `/code-review` this turn
