---
name: ouvrir-la-version
description: >-
  When the user says « Ouvre la version », « ouvre la version vX.Y.Z »,
  « open the version », or asks to start a new version branch and PR.
  Not for /implement, not for « Finalise la version ».
---

# Open a version

Triggered by **« Ouvre la version »**. The user **must** give a semver **`X.Y.Z`** (e.g. `1.2.0`). If they omit it, ask and **wait** — do not invent a number.

This path **is** permission to commit **docs** on the new feature branch, `git push -u`, and `gh pr create`. Never `.env`, `*.db`, `.venv`, secrets. No force-push. Do **not** `/implement` here. Do **not** merge.

## 1. Purpose

Ask: **what is this version for?** (one job, in product language). Wait.

## 2. `/grill-with-docs` (conversation only if you are on `main`)

Call **grill-with-docs**. Rounds until the tree is empty. **Wait** for shared-understanding confirmation.

If the current branch is **`main`**: do **not** write `docs/specs`, `CONTEXT.md`, or ADRs to disk yet (that would dirty `main`). Keep decisions in the conversation.

## 3. `/to-spec` (content first)

Matt’s next step is **`/to-spec`**. Synthesize the full spec (problem, solution, user stories, implementation/testing, out of scope). Publish the **parent GitHub issue** (`ready-for-agent`). Do not overwrite a previous version’s spec issue.

Still **do not** commit that spec onto `main`.

## 4. Branch, then **immediate** init commit + push

`git fetch origin`. From `origin/main`, create and checkout `vX.Y.Z-<slug>`. If that name exists, stop and ask.

**Immediately:** write on **this** branch only:

- `docs/specs/` for this version (the `/to-spec` body)
- `CONTEXT.md` / `AGENTS.md` / `CLAUDE.md` / `docs/agents/` / `docs/adr/` only if this version actually changes them (new ADR; never rewrite old ADR history)

First commit = **initialisation de la version**. `git push -u origin HEAD`. **`main` stays unchanged.**

Never `.env` / `*.db` / `.venv`.

## 5. `/to-tickets` — propose, **then** create

You are not wrong: next is **`/to-tickets`**. Follow its quiz: numbered tickets, **Blocked by**, what each delivers, **vertical** slices if possible.

Show the **implementation order**: tickets with no open blockers first (lowest number among that set).

**Wait for an explicit yes** on that list. Then `gh issue create` each child (`Part of #<parent>`, `ready-for-agent`). Also set **GitHub native** blocked-by (see `docs/agents/issue-tracker.md`: POST `issues/<child>/dependencies/blocked_by` with the blocker’s **database id**). A body `Blocked by: #n` line is only a fallback. Closing a blocker must update the GitHub Blocking / Blocked by UI. Do not create tickets before that yes. Do not `/implement`.

## 6. Pull request

Push the branch if needed. Open a PR **into `main`**, same shape as recent squash-merged PRs (e.g. #31):

- Title: `VX.Y.Z — <purpose in one line>`
- `## Summary` (what this version is)
- `Fixes #<parent>` and `Fixes #<child>` **one keyword per issue** (needed later at squash)
- `## Test plan` (checkboxes)

Draft is OK until the user wants it ready.

## 7. Hand off to implement

Propose: **`/clear`**, then **`/implement #<first>`** where `#first` is the first unblocked child (no blockers, or all blockers already created and none waiting on code — at open, that is “Blocked by: None”). Wait. Do not start `/implement` in this same window after a long grill.

## Not this skill

- « Finalise la version » → `finaliser-la-version`
- Child-ticket TDD → `/implement` + `encadrer-implement`
