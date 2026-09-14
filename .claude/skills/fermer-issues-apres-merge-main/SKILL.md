---
name: fermer-issues-apres-merge-main
description: >-
  When closing GitHub issues, gh issue close, marking a ticket done, finishing
  /implement, or after a pull request. Use whenever an issue might be closed or
  when the user asks about issue state vs main.
---

# Close issues only after merge to main

Feature work follows **one** cycle:

1. Create a **feature branch** (not `main`).
2. **Open** GitHub issues for that feature.
3. **Implement** on the branch (commits, tests). Issues stay **Open**.
4. Open a **PR** into `main`.
5. **Merge** the PR into `main`.
6. Then, and only then: **close the issues** that landed in that merge, and **delete the feature branch**.

`gh issue close` is forbidden when:

- code exists only on a feature branch
- tests pass / ticket "feels done"
- the user said commit or push to the feature branch
- a PR is still open

Exception: `wontfix` / user explicitly says close without merge (duplicate, abandoned).

After merge: close the related issues (`Fixes #n` in the PR body is enough if GitHub will auto-close on merge — prefer `Fixes` in the **PR**, not `gh issue close` before merge). Then delete the remote feature branch.
