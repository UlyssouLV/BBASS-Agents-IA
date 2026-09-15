---
name: fermer-issues-apres-merge-main
description: >-
  When closing GitHub issues, gh issue close, marking a ticket done, finishing
  /implement, applying awaiting-merge, after a pull request, or when tagging /
  GitHub Release / semver. Use whenever an issue might be closed, when the user
  asks about issue state vs main, developed-but-not-merged, or release vs PR.
---

# Close issues only after merge to main, then release

Feature work follows **one** cycle:

1. Create a **feature branch** (not `main`).
2. **Open** GitHub issues for that feature.
3. **Implement** on the branch (commits, tests). Issues stay **Open**. After `/implement`, skill `apres-implement-awaiting-merge` asks for confirmation then applies `awaiting-merge` (and removes ready-* labels). That is "developed, not merged" — not a GitHub close.
4. Open a **PR** into `main`.
5. **Merge** the PR into `main`.
6. **Close the issues** that landed in that merge (`Fixes #n` on the PR is enough), and **delete the feature branch**.
7. Create a **GitHub Release** on the **merge commit on `main`** (not on the deleted branch). The tag follows **semver** already used on the repo (`v1.0.0`, then `v1.0.1` / `v1.1.0` / `v2.0.0`). The release body lists what this version actually ships.

`gh issue close` is forbidden when:

- code exists only on a feature branch (use `awaiting-merge` instead)
- tests pass / ticket "feels done"
- the user said commit or push to the feature branch
- a PR is still open

Exception: `wontfix` / user explicitly says close without merge (duplicate, abandoned).

A **PR title** (e.g. `V1.0.0`) is not a release. A **GitHub Release** is a tag on `main` after merge. Deleting the feature branch does not remove that commit: tag `main`.

Do **not** `gh release create` / `git tag` unless the current user message asks to publish a release. After merge, propose the next tag and a draft notes body, then wait.

## Release notes

Write them for a human who did not watch the PR:

- Title: the tag (`v1.0.0`)
- Short summary (what this version is for)
- What landed (bullet list: features / fixes / docs — not a dump of commit subjects)
- Issues closed (`Fixes` from the PR)
- What is **not** in this version if it could be confused (e.g. #6 left open)

Prefer `gh release create vX.Y.Z --target <sha-on-main> --notes "..."` after `git fetch` so the SHA is the merge on `origin/main`.
