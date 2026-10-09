---
name: encadrer-implement
description: >-
  Green pytest after a child GitHub ticket, or the implement plugin's closing
  step: `/t`, `/c -p`, `/cci #<n>`, then the next unblocked ready-for-agent
  child, or fill the human-test plan and point to `/th`, or (all Closed)
  `/code-review` then Finalise. Do not wait for the quality gate. Do not run
  `/code-review` here. Load this as soon as /implement tests pass.
---

# Wrap `/implement`

Use the plugin **`/implement`** for TDD and the ticket body. **This skill owns the end of the run.** The plugin’s last line is a review step; in this repo that last line is **this skill, from Tests onward**.

Git, tests, and closing the child go through the skills below, not inline. The quality gate is not this skill. Do **not** close the **parent** spec (squash `Fixes #<parent>` does that). Do **not** `/implement` the parent.

## 1. Tests

Run skill **`lancer-tests`** as if the user had typed **`/t`**. If it fails: **stop**. No commit, no close.

## 2. Commit and push

Stage **only** the ticket files. Never `.env`, `*.db`, `.venv/`, secrets. Do **not** pass `-a`.

Then run skill **`commit`** as if the user had typed **`/c -p`**.

Do **not** `/qg`, `/qg -w`, or `/cqg`. Do **not** leave the child Open while Sonar runs. Do **not** add a label for that wait. The gate is one read of the PR `HEAD`, in `finaliser-la-version`.

## 3. Close the child

Run skill **`fermer-ticket-enfant`** as if the user had typed **`/cci #<n>`** (`<n>` = the child just implemented). No `-t` (tests already ran). That skill refuses if `<n>` is not a child.

## 4. More child tickets on this PR?

Find the parent (`## Parent` / `Part of #n` on the issue you just finished). List **open** children of that parent.

- **Done:** Closed.
- **Still to build:** Open, `ready-for-agent` (and not `wontfix`).
- **Human tests:** Open, `ready-for-human` (title `Tests humains — …`). Never `/implement`.

A remaining ticket is **unblocked** when GitHub reports no open blockers (`issue_dependencies_summary.blocked_by` is 0), or every issue in a fallback **Blocked by** body line is Closed. See `agents/issue-tracker.md`.

**If at least one unblocked `ready-for-agent` child remains:**

- Propose the **next** unblocked child (lowest issue number among unblocked `ready-for-agent`).
- In that proposal, quote the `## Blocked by` clause of that child (the `vraie dépendance` / `ordre de confort` line) in one sentence, so the human can say what would have broken.
- Ask the user to `/clear` then `/implement #<next>`. Wait. Do not start the next implement in this same compacted window.

**Else if an open `ready-for-human` human-test child remains** (format: `agents/issue-tracker.md`, *Human-test child*):

1. Build a **concrete** numbered test plan in product language from the parent spec and the Closed implementation children (what a human can click / verify). Partial runs are allowed later.
2. `gh issue edit` that issue: replace `## Plan de tests` with checkboxes for each scenario (leave `## Résultats` and `## Ce qu’on peut faire maintenant` for `/th`).
3. Stop after telling the user, in French (adapt `#n` / PR):

   Tous les tickets d’implémentation sont Closed. Plan de tests humains proposé sur #<n>. Jouez ce que vous voulez (plan partiel OK). Quand c’est fait, lancez **`/th`** avec les résultats (et des captures si vous en avez). Ne lancez pas `/code-review` tant que #<n> est Open.

4. Do **not** propose `/code-review` or Finalise here. Do not merge, tag, or start the next version.

**Else if all in-scope children are Closed** (including the human-test child):

- Stop after telling the user, in French, exactly this handoff (adapt only the parent/PR numbers if useful):

  Tous les tickets sont Closed (implémentation et tests humains). Lancez `/code-review`. Si la revue est bonne, lancez le skill **Finalise la version** (`finaliser-la-version`) : le quality gate est lu à ce moment-là, et s’il n’est pas OK c’est `/cqg`, pas la release.

- Do not merge, tag, or start the next version.

## Not this skill

- Tests only → `lancer-tests` (`/t`)
- Commit / push → `commit` (`/c`)
- Read-only gate → `quality-gate` (`/qg`)
- Fix the gate only → `corriger-quality-gate` (`/cqg`)
- Close a child only → `fermer-ticket-enfant` (`/cci`)
- Human-test results / close → `tests-humains` (`/th`)
- Opening or merging the PR, GitHub Release, deleting the branch → `finaliser-la-version`
- Re-implementing Closed children
- `needs-triage` work that is not a child of this PR
- A two-axis review vs `main`: only if the human typed `/code-review` this turn
