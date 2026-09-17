---
name: ouvrir-la-version
description: >-
  When the user says « Ouvre la version », « ouvre la version vX.Y.Z »,
  « open the version », or asks to start a new version branch and PR.
  Not for /implement, not for « Finalise la version ».
---

# Open a version

Triggered by **« Ouvre la version »**. The user **must** give a semver **`X.Y.Z`** (e.g. `1.2.0`). If they omit it, ask and **wait** — do not invent a number.

This path **is** permission to commit **docs** on the new **feature branch**, `git push -u`, and `gh pr create`. Never `.env`, `*.db`, `.venv`, secrets. No force-push. Do **not** `/implement` here. Do **not** merge. Do **not** `git commit` on **`main`**.

## 0. Working tree on `main`

If `main` has uncommitted changes (docs, skills, roadmap, leftover from the previous version, anything simple): **do not ask**. **Do not commit them to `main`.** Carry them onto `vX.Y.Z-…` (they stay in the working tree when you `checkout -b`) and include them in the **init commit** of that branch. Never stash « to keep main clean » in order to commit on `main` afterwards.

## 1. Purpose

Read **`docs/suivi-avancement/feuille-de-route-dev.md`**. If that file already describes version **`X.Y.Z`** (heading « Prochaine : X.Y.Z », « Ensuite : X.Y.Z », or equivalent):

- That section **is** the purpose (one job, product language). State it back in one sentence, then go to step 2. Do **not** ask « what is this version for? ».
- The file is a roadmap, not a spec: grilling may still refine it. Do not invent a different job.

If **`X.Y.Z` is absent** from that file: ask **what is this version for?** (one job, in product language) and **wait**.

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

**Wait for an explicit yes** on that list. Then `gh issue create` each child (`Part of #<parent>`, `ready-for-agent`). Also set **GitHub native** blocked-by (see `docs/agents/issue-tracker.md`: POST `issues/<n>/dependencies/blocked_by` with JSON integer `issue_id` = the blocker’s **database id**):

- **Between children**, as the quiz said (ticket B blocked by ticket A).
- **Parent blocked by every child**: POST `issues/<parent>/dependencies/blocked_by` once per child. The parent spec stays **Blocked** until every child is **Closed**. Then `gh issue edit <parent> --remove-label "ready-for-agent"`. The parent is never an `/implement` ticket.

A body `Blocked by: #n` line is only a fallback. Closing a blocker must update the GitHub Blocking / Blocked by UI. Do not create tickets before that yes. Do not `/implement`.

## 6. Pull request

Push the branch if needed. Open a PR **into `main`**, same shape as recent squash-merged PRs (e.g. #31):

- Title: `VX.Y.Z — <purpose in one line>`
- `## Summary` (what this version is)
- `Fixes #<parent>` and `Fixes #<child>` **one keyword per issue** (needed later at squash)
- `## Test plan` (checkboxes)

Draft is OK until the user wants it ready.

## 7. Hand off to implement

Propose: **`/clear`**, then **`/implement #<first>`** where `#first` is the first unblocked **child** (not the parent). Wait. Do not start `/implement` in this same window after a long grill.

## Not this skill

- « Finalise la version » → `finaliser-la-version`
- Child-ticket TDD → `/implement` + `encadrer-implement`
