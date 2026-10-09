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

Paths: **`agents/roles.yml`**. Roadmap writing standards: **`docs/dev/feuille-de-route/README.md`** (this skill does **not** edit the roadmap — adding / renumbering versions is **`/afr`**).

## 1. Purpose

Read role **`roadmap`**. Look for **`X.Y.Z`** as **`## Prochaine : X.Y.Z — …`** or **`## Ensuite : X.Y.Z — …`** (or a **Déjà livré** bullet — then stop: already shipped).

If that file already describes version **`X.Y.Z`**:

- That section **is** the purpose: take **`Objectif.`** (one job, product language). State it back in one sentence, then go to step 2. Do **not** ask « what is this version for? ».
- The file is a roadmap, not a spec: grilling may still refine it. Do not invent a different job.
- Prefer opening the current **Prochaine**. If the user names an **Ensuite**, say so in one line and continue only if they confirm.

If **`X.Y.Z` is absent** from that file: tell them to add it with **`/afr`** (standards in the README), **or** ask **what is this version for?** (one job, product language) and **wait** — do not invent a number or rewrite the feuille here.

## 2. `/grill-with-docs` (conversation only if you are on `main`)

Call **grill-with-docs**. Rounds until the tree is empty. **Wait** for shared-understanding confirmation.

If the current branch is **`main`**: do **not** write roles **`spec`**, **`glossary`**, or **`adr`** to disk yet (that would dirty `main`). Keep decisions in the conversation.

## 3. `/to-spec` (content first)

Matt’s next step is **`/to-spec`**. Synthesize the full spec (problem, solution, user stories, implementation/testing, out of scope), plus **Changements apportés aux versions antérieures** in the format of `agents/issue-tracker.md` (*Changes to earlier versions*): `Aucun.` when this version changes nothing an earlier version shipped. Publish the **parent GitHub issue** (`ready-for-agent`). Do not overwrite a previous version’s spec issue.

Still **do not** commit that spec onto `main`.

## 4. Branch, write, init commit

Run skill **`ouvrir-branche`** as if the user had typed **`/ob vX.Y.Z-<slug>`**. Slug = kebab-case of the purpose (ASCII). If that skill stops because the name exists: ask and wait.

Then write on **this** branch only:

- role **`spec`** for this version (the `/to-spec` body)
- roles **`glossary`**, **`agent-adapter`**, **`adr`** only if this version actually changes them (new ADR; never rewrite old ADR history)

Then run skill **`commit`** as if the user had typed **`/c -a -p`**. That commit **is** the initialisation de la version. `main` stays unchanged.

## 5. `/to-tickets` — propose, **then** create

You are not wrong: next is **`/to-tickets`**. Follow its quiz: numbered tickets, **Blocked by**, what each delivers, **vertical** slices if possible.

For **every** `Blocked by #n`, the quiz must classify the edge **before** you show the list:

- `vraie dépendance` — say **what breaks** if a fresh agent implements the blocked ticket first (missing type, test that cannot be written, route that does not exist…).
- `ordre de confort` — say **why nothing breaks** if the order is inverted.

Do **not** invent an extra `#` to make the graph look denser. Parallel work (`- Aucun` on both) is valid. An edge with no “what breaks” is not ready.

Show the **implementation order**: tickets with no open blockers first (lowest number among that set). Include the one-line justification next to each edge.

**Wait for an explicit yes** on that list. Then for **each** implementation child, in order:

1. `gh issue create` with label `ready-for-agent` and body in the **canonical Matt shape** from `agents/issue-tracker.md` (*Child ticket body*): first line `Part of #<parent>`, then `## What to build`, `## Acceptance criteria` (checkboxes), `## Blocked by` (`- Aucun`, or `- #<n> — vraie dépendance : …` / `- #<n> — ordre de confort : …`). **Stop** if any peer edge is a bare `- #<n>` without that clause. If `/to-tickets` drafted French or free-form headings, **reshape** to those English headings before create. Do not use `Ce qu'il livre` / `Critères d'acceptation` / `Tests attendus` for new tickets.
2. Attach it as a **GitHub sub-issue** of the parent (POST `issues/<parent>/sub_issues`, JSON integer `sub_issue_id` = the child’s **database id**) — this is what shows **Y/Z** on the parent. See `agents/issue-tracker.md` (*Version parent and children*).
3. Set **GitHub native** blocked-by (POST `issues/<n>/dependencies/blocked_by`, JSON integer `issue_id` = the blocker’s **database id`):
   - **Between children**, as the quiz said.
   - **Parent blocked by every child**, once per child.

Then create **one human-test child** (format: `agents/issue-tracker.md`, *Human-test child*):

1. Title `Tests humains — VX.Y.Z`. Label **`ready-for-human`** only (never `ready-for-agent`). Body skeleton: Matt headings + empty `## Plan de tests` / `## Résultats` / `## Ce qu’on peut faire maintenant` placeholders. `## Blocked by` = **every** implementation child just created, each as `ordre de process` (see `agents/issue-tracker.md`). Do not add extra blockers.
2. Attach as a **GitHub sub-issue** of the parent (same POST as above).
3. Native blocked-by: this ticket blocked by **each** implementation child; **parent** blocked by this ticket as well.

Then `gh issue edit <parent> --remove-label "ready-for-agent"`. Confirm the parent’s `sub_issues_summary.total` equals the number of implementation children **plus** the human-test child. The parent is never an `/implement` ticket. The human-test child is never `/implement`.

A body `Part of` line alone does **not** create the sub-issue link. The `## Blocked by` section mirrors native deps (fallback if the API is unavailable). Do not create tickets before that yes. Do not `/implement`.

## 6. Pull request

Run skill **`ouvrir-pr`** as if the user had typed **`/opr -draft`** with:

- Title: `VX.Y.Z — <purpose in one line>`
- `## Summary` (what this version is)
- `Fixes #<parent>` and `Fixes #<child>` **one keyword per issue** (include the human-test child)
- If this version **fixes** known roadmap bugs: also `Fixes #<bug>` for each GitHub issue with label **`bug`** that this version closes (so `finaliser-la-version` can remove them from **Plus tard** and close them)
- `## Test plan` (checkboxes) — may point at the human-test issue; the detailed plan is filled later by `encadrer-implement`

## 7. Hand off to implement

Propose: **`/clear`**, then **`/implement #<first>`** where `#first` is the first unblocked **implementation** child (`ready-for-agent`, not the human-test child, not the parent). Wait. Do not start `/implement` in this same window after a long grill.

## Not this skill

- Feuille de route de dev only (list / argue / write versions) → `augmenter-la-feuille-de-route-dev` (`/afr`)
- Branch only → `ouvrir-branche` (`/ob`)
- Commit / push → `commit` (`/c`)
- PR only → `ouvrir-pr` (`/opr`)
- « Finalise la version » → `finaliser-la-version`
- Child-ticket TDD → `/implement` + `encadrer-implement`
