---
name: finaliser-la-version
description: >-
  When the user says « Finalise la version », « finalize the version »,
  « clôture la version », or asks to ship/squash-merge the current version
  PR, create the GitHub Release, and delete the feature branch. Not for a
  single child ticket or /implement.
---

# Finalise the version

Triggered by **« Finalise la version »** (or equivalent). Release and squash go through **`creer-release`** (`/crel`) and **`fusionner-pr`** (`/mpr`), not inline. Docs commit goes through **`commit`** (`/c -a -p`).

A version = one feature branch + one PR that ships a **set** of child issues (parent spec). Starting a version is skill `ouvrir-la-version`.

Do **not** `/implement` here. Do **not** `gh issue close` children here (they should already be Closed). Do **not** close the parent by hand — squash `Fixes` does that.

Paths: **`agents/roles.yml`**.

## 0. Locate the PR

Current branch must not be `main`. Resolve the open PR for this branch (`gh pr view`). If none, stop.

Infer **`X.Y.Z`** from the branch `vX.Y.Z-<slug>` or the PR title `VX.Y.Z — …`. If missing: ask and wait.

## 1. Every related issue is published

Related = listed in the PR body (`Fixes` / `Part of`) **and** children of the parent spec that are in scope for this PR. Ignore `wontfix` and issues the PR or parent spec mark as out of this version. See `agents/issue-tracker.md`.

**Published** = each in-scope **child** is **Closed**.

If any in-scope child is still **Open**: **stop**. List what’s missing. Do not tag, merge, or delete.

The **parent** spec may still be Open until squash. Leave it Open here.

If the PR body’s `Fixes` line would not close the **parent** on squash, **edit the PR body first** (`Fixes #n` once per issue; include `Fixes #<parent>`). Children already Closed are fine to leave in `Fixes` (no-op).

## 2. Docs must match this version (before tag and squash)

Read each role below (paths from `agents/roles.yml`), against the parent spec / ADRs / code that this PR actually ships:

- **`readme`** — matches what this version shipped. Extra README checks live in role **`agent-adapter`**; do not invent a layout.
- **`glossary`** — glossary and ADR links match the model (new terms, reversed decisions).
- **`agent-adapter`** — adapter still valid (hook, `/implement` close, Standards pointer); skills named there exist under `agents/skills/` (synced to the IDE adapters); implement / finalise cycle matches those skills; process docs still match (tracker, labels, domain).
- **`spec`** — spec for this version exists there.
- **`adr`** — new ADRs if decisions changed.
- **`roadmap`** — **`X.Y.Z`** is recorded as delivered; upcoming versions stay listed; drop claims this version has **not** delivered. Do not invent new versions; only reshuffle what is already listed.

If anything is stale: **stop the release**. Update those files on the **feature branch**, then run skill **`commit`** as if the user had typed **`/c -a -p`**. Then re-read this section. Do **not** `/crel` or `/mpr` until this gate is green — the tag must include the docs.

## 3. Release, then squash

Run skill **`creer-release`** as if the user had typed **`/crel vX.Y.Z`**. That skill owns title (`VX.Y.Z — <purpose>`) and notes layout. Wait until the release is visible.

Then run skill **`fusionner-pr`** as if the user had typed **`/mpr`**.

## 4. Stop

Do not start the next version’s branch unless the user asks.

## Not this skill

- Release only → `creer-release` (`/crel`)
- Squash-merge only → `fusionner-pr` (`/mpr`)
- Commit / push → `commit` (`/c`)
- Child wrap → `encadrer-implement`
- Open a version → `ouvrir-la-version`
- Feuille de route de dev only → `augmenter-la-feuille-de-route-dev` (`/afr`)
