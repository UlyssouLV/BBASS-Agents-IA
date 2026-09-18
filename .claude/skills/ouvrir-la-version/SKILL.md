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

## 3b. Inventory of invariants (wait)

From **this** spec and the ADRs it cites, list phrases with « jamais », « uniquement », or « ne doit pas ». For each line: *already locked by a test or hook* **or** *prompt-only*.

Done when every such phrase from **this** spec is in that list (zero rows is valid: say so).

**Wait.** The human picks **zero or one** invariant for a new deterministic gate (confidentiality / account integrity). Do **not** write hooks or CI in this skill unless they named that invariant this turn. UX-only versions often pick zero.

## 4. Branch, then **immediate** init commit + push

`git fetch origin`. From `origin/main`, create and checkout `vX.Y.Z-<slug>`. If that name exists, stop and ask.

**Immediately:** write on **this** branch only:

- `docs/specs/` for this version (the `/to-spec` body)
- `CONTEXT.md` / `AGENTS.md` / `CLAUDE.md` / `docs/agents/` / `docs/adr/` only if this version actually changes them (new ADR; never rewrite old ADR history)

First commit = **initialisation de la version**. `git push -u origin HEAD`. **`main` stays unchanged.**

Never `.env` / `*.db` / `.venv`.

## 5. `/to-tickets` — propose, invert, **then** create

You are not wrong: next is **`/to-tickets`**. Follow its quiz: numbered tickets, what each delivers, **vertical** slices if possible.

Then the **inverted-ticket** pass, **before** any `gh issue create`. For every proposed child→child edge, an agent with **only** the blocked ticket’s body implements it **before** the blocker. Write one line:

- **real dependency:** what **breaks** (missing import, missing model, test that cannot be written, missing route) — or
- **comfort order:** why it feels nicer; **drop the GitHub edge**.

Parent **blocked by every child** is a merge gate, not a code dependency: do not put it in this list.

Show (1) tickets with **only real** edges, (2) the implementation order (no open real blocker first; lowest number among that set), (3) dropped comfort edges.

Done when every proposed child→child edge is in (2) or (3), and every line in (2) names a concrete break.

**Wait for an explicit yes.** Then `gh issue create` each child (`Part of #<parent>`, `ready-for-agent`). Each real edge appears in the child body as `Blocked by: #n — sans #n : <what breaks>`. Also set **GitHub native** blocked-by (see `docs/agents/issue-tracker.md`: POST `issues/<n>/dependencies/blocked_by` with JSON integer `issue_id` = the blocker’s **database id`):

- **Between children**, only the **real** edges from the yes’d list.
- **Parent blocked by every child**: POST `issues/<parent>/dependencies/blocked_by` once per child. The parent spec stays **Blocked** until every child is **Closed**. Then `gh issue edit <parent> --remove-label "ready-for-agent"`. The parent is never an `/implement` ticket.

A body `Blocked by: #n` line without **sans #n** is only a fallback for native API failure. Closing a blocker must update the GitHub Blocking / Blocked by UI. Do not create tickets before that yes. Do not `/implement`.

## 6. Pull request

Push the branch if needed. Open a PR **into `main`**, same shape as recent squash-merged PRs (e.g. #31):

- Title: `VX.Y.Z — <purpose in one line>`
- `## Summary` (what this version is)
- `Fixes #<parent>` and `Fixes #<child>` **one keyword per issue** (needed later at squash)
- `## Test plan` (checkboxes)

Draft is OK until the user wants it ready.

## 7. Hand off to implement

Write `.claude/prochaine-etape.md` (gitignored; overwrite):

```
commande: /implement #<first>
issue: <first>
parent: <parent>
branche: <feature branch>
sha: <HEAD>
```

`#first` is the first unblocked **child** (not the parent). Then tell the user, in French: **`/clear`** (or a new chat), then **only** `/prochaine-etape`. Wait. Do not start `/implement` in this same window after a long grill.

## Not this skill

- « Finalise la version » → `finaliser-la-version`
- Child-ticket TDD → `/implement` + `encadrer-implement`
