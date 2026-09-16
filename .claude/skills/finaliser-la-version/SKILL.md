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

A version = one feature branch + one PR that ships a **set** of child issues (parent spec). Starting a version is skill `ouvrir-la-version` (« Ouvre la version »).

## 0. Locate the PR

Current branch must not be `main`. Resolve the open PR for this branch (`gh pr view`). If none, stop.

## 1. Every related issue is published

Related = listed in the PR body (`Fixes` / `Part of`) **and** children of the parent spec that are in scope for this PR. Ignore `wontfix` and issues explicitly out of the version (e.g. #6).

**Published** = each in-scope **child** is **Closed** (closed by `encadrer-implement` after green tests, or already on `main`).

If any in-scope child is still **Open**: **stop**. List what’s missing. Do not tag, merge, or delete.

The **parent** spec may still be Open until squash. Leave it Open here.

If the PR body’s `Fixes` line would not close the **parent** on squash, **edit the PR body first** (`Fixes #n` once per issue; include `Fixes #<parent>`). Children already Closed are fine to leave in `Fixes` (no-op).

Do **not** `gh issue close` children at this step (they should already be Closed). Do **not** close the parent by hand — squash `Fixes` does that.

## 1b. Docs must match this version (before tag and squash)

Read, against the parent spec / ADRs / code that this PR actually ships:

- `README.md` — « État actuel », lancement, comptes de test : no leftover previous-version branch names or « not built yet » for features this version delivered.
- `CONTEXT.md` — glossary and ADR links match the model (new terms, reversed V1 decisions).
- `CLAUDE.md` — Standards pointers still valid (files exist; `/code-review` rules still true).
- `AGENTS.md` — skills named here exist under `.claude/skills/`; implement / finalise cycle matches those skills.
- `docs/` — spec for this version under `docs/specs/` ; new ADRs under `docs/adr/` if decisions changed ; `docs/agents/` does not point at deleted skills.

If anything is stale: **stop the release**. Update those files on the **feature branch**, commit (French why-message), `git push`. Never `.env` / `*.db` / `.venv`. Then re-read this section. Do **not** create the tag or squash until this gate is green — the tag must include the docs.

## 2. Tag + Release **before** squash (keeps branch history)

`main` will get **one** squash commit; that graph **drops** the ticket-by-ticket history.

1. `git fetch`. Tip of the **feature branch** = `HEAD` (must match the PR head).
2. Next **semver** tag: list `git tag -l 'v*'` / `gh release list`. Bump for this version (`v1.1.0` after `v1.0.0`, etc.). Never retag an existing `vX.Y.Z`.
3. Create the GitHub Release **targeting the feature branch SHA** (or `--target <branch>` while the branch still exists), **not** `main`:

   `gh release create vX.Y.Z --target <sha-or-branch> --title "…" --notes "…"`

Notes are for a human who did not watch the PR (French unless the repo’s user-facing docs are English):

- What this version is for (problem / parent spec).
- What you can **do** now (features, not a dump of commit subjects).
- **Link to the PR** (`https://github.com/<owner>/<repo>/pull/<n>` and `/commits`) so the ticket-by-ticket history is one click after squash.
- Child issues included (`Fixes`).
- What is **not** in this version if it could be confused. For each ADR named, a **markdown link** to the file on this tag (`https://github.com/<owner>/<repo>/blob/vX.Y.Z/docs/adr/NNNN-….md`). Same for leftover issues (`#6`).

The tag must be **pushed** and the release **visible** before step 3. After the branch is deleted, `git log vX.Y.Z` still shows the development commits.

## 3. Squash-merge, then delete the branch

1. PR Ready for review (not Draft).
2. `gh pr merge --squash --delete-branch` (or GitHub squash + delete the head branch). **Not** a merge commit. **Not** rebase-merge.
3. Confirm `main` has **one** new commit for this PR; the Release tag still points at the **old** feature SHA.

No force-push to `main`. Do not move `vX.Y.Z` onto the squash commit (that would **lose** the history the tag is for).

## 4. Stop

Do not start the next version’s branch unless the user asks.
