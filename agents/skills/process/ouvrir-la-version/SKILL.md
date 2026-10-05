---
name: ouvrir-la-version
description: >-
  When the user says « Ouvre la version », « ouvre la version vX.Y.Z »,
  « open the version », or asks to start a new version branch and PR.
  Not for /implement, not for « Finalise la version ».
---

# Open a version

Triggered by **« Ouvre la version »**. The user **must** give a semver **`X.Y.Z`** (e.g. `1.2.0`). If they omit it, ask and **wait** — do not invent a number.

Do **not** `/implement` here. Do **not** merge. Do **not** `git commit` on **`main`**. Git branch / commit / PR go through the skills below, not inline.

Paths: **`agents/roles.yml`**.

## 1. Purpose

Read role **`roadmap`**. If that file already describes version **`X.Y.Z`**:

- That section **is** the purpose (one job, product language). State it back in one sentence, then go to step 2. Do **not** ask « what is this version for? ».
- The file is a roadmap, not a spec: grilling may still refine it. Do not invent a different job.

If **`X.Y.Z` is absent** from that file: ask **what is this version for?** (one job, in product language) and **wait**.

## 2. `/grill-with-docs` (conversation only if you are on `main`)

Call **grill-with-docs**. Rounds until the tree is empty. **Wait** for shared-understanding confirmation.

If the current branch is **`main`**: do **not** write roles **`spec`**, **`glossary`**, or **`adr`** to disk yet (that would dirty `main`). Keep decisions in the conversation.

## 3. `/to-spec` (content first)

Matt’s next step is **`/to-spec`**. Synthesize the full spec (problem, solution, user stories, implementation/testing, out of scope). Publish the **parent GitHub issue** (`ready-for-agent`). Do not overwrite a previous version’s spec issue.

Still **do not** commit that spec onto `main`.

## 4. Branch, write, init commit

Run skill **`ouvrir-branche`** as if the user had typed **`/ob vX.Y.Z-<slug>`**. Slug = kebab-case of the purpose (ASCII). If that skill stops because the name exists: ask and wait.

Then write on **this** branch only:

- role **`spec`** for this version (the `/to-spec` body)
- roles **`glossary`**, **`agent-adapter`**, **`adr`** only if this version actually changes them (new ADR; never rewrite old ADR history)

Then run skill **`commit`** as if the user had typed **`/c -a -p`**. That commit **is** the initialisation de la version. `main` stays unchanged.

## 5. `/to-tickets` — propose, **then** create

You are not wrong: next is **`/to-tickets`**. Follow its quiz: numbered tickets, **Blocked by**, what each delivers, **vertical** slices if possible.

Show the **implementation order**: tickets with no open blockers first (lowest number among that set).

**Wait for an explicit yes** on that list. Then `gh issue create` each child (`Part of #<parent>`, `ready-for-agent`). Set **GitHub native** blocked-by per `agents/issue-tracker.md` (POST `issues/<n>/dependencies/blocked_by`, JSON integer `issue_id` = the blocker’s **database id`):

- **Between children**, as the quiz said.
- **Parent blocked by every child**, once per child. Then `gh issue edit <parent> --remove-label "ready-for-agent"`. The parent is never an `/implement` ticket.

A body `Blocked by: #n` line is only a fallback. Do not create tickets before that yes. Do not `/implement`.

## 6. Pull request

Run skill **`ouvrir-pr`** as if the user had typed **`/opr -draft`** with:

- Title: `VX.Y.Z — <purpose in one line>`
- `## Summary` (what this version is)
- `Fixes #<parent>` and `Fixes #<child>` **one keyword per issue**
- `## Test plan` (checkboxes)

## 7. Hand off to implement

Propose: **`/clear`**, then **`/implement #<first>`** where `#first` is the first unblocked **child** (not the parent). Wait. Do not start `/implement` in this same window after a long grill.

## Not this skill

- Feuille de route de dev only (list / argue / write versions) → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Branch only → `ouvrir-branche` (`/ob`)
- Commit / push → `commit` (`/c`)
- PR only → `ouvrir-pr` (`/opr`)
- « Finalise la version » → `finaliser-la-version`
- Child-ticket TDD → `/implement` + `encadrer-implement`
