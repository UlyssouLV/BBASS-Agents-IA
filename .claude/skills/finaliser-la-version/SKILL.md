---
name: finaliser-la-version
description: >-
  When the user says « Finalise la version », « finalize the version »,
  « clôture la version », or asks to ship/squash-merge the current version
  PR, create the GitHub Release, and delete the feature branch. Not for a
  single child ticket or /implement.
---

# Finalise the version (end of a PR)

Triggered by **« Finalise la version »** (or equivalent). This **is** permission to create a Release, squash-merge the PR into `main`, and delete the feature branch — **after** the checks below pass.

A version = one feature branch + one PR that ships a **set** of child issues (parent spec). Starting a version (create branch/PR) is **out of this skill**.

## 0. Locate the PR

Current branch must not be `main`. Resolve the open PR for this branch (`gh pr view`). If none, stop.

## 1. Every related issue is published

Related = listed in the PR body (`Fixes` / `Part of`) **and** open children of the parent spec (e.g. #13) that are in scope for this PR. Ignore `wontfix` and issues explicitly out of the version (e.g. #6).

**Published** = each child is `awaiting-merge` (still Open) or already Closed because it landed on `main`.

If any in-scope child is still `ready-for-agent` / `ready-for-human` / `needs-info`: **stop**. List what’s missing. Do not tag, merge, or delete.

When every in-scope **child** is `awaiting-merge`, label the **parent spec** (e.g. #13) the same way: Open, `awaiting-merge`, remove `ready-for-agent`. That is “the version’s spec is complete on the branch”, not a GitHub close.

If the PR body’s `Fixes` line would not close every in-scope child **and the parent** on squash, **edit the PR body first** (`Fixes #n` repeated per issue, not a single `Fixes #1 #2`). Include `Fixes #13` (or whatever the parent number is).

Do **not** `gh issue close` by hand.

## 2. Tag + Release **before** squash (keeps branch history)

`main` will get **one** squash commit; that graph **drops** the ticket-by-ticket history.

1. `git fetch`. Tip of the **feature branch** = `HEAD` (must match the PR head).
2. Next **semver** tag: list `git tag -l 'v*'` / `gh release list`. Bump for this version (`v1.1.0` after `v1.0.0`, etc.). Never retag an existing `vX.Y.Z`.
3. Create the GitHub Release **targeting the feature branch SHA** (or `--target <branch>` while the branch still exists), **not** `main`:

   `gh release create vX.Y.Z --target <sha-or-branch> --title "…" --notes "…"`

Notes are for a human who did not watch the PR (French unless the repo’s user-facing docs are English):

- What this version is for (problem / parent spec).
- What you can **do** now (features, not a dump of commit subjects).
- Child issues included (`Fixes`).
- What is **not** in this version if it could be confused.

The tag must be **pushed** and the release **visible** before step 3. After the branch is deleted, `git log vX.Y.Z` still shows the development commits.

## 3. Squash-merge, then delete the branch

1. PR Ready for review (not Draft).
2. `gh pr merge --squash --delete-branch` (or GitHub squash + delete the head branch). **Not** a merge commit. **Not** rebase-merge.
3. Confirm `main` has **one** new commit for this PR; the Release tag still points at the **old** feature SHA.

No force-push to `main`. Do not move `vX.Y.Z` onto the squash commit (that would **lose** the history the tag is for).

## 4. Stop

Do not start the next version’s branch unless the user asks.
