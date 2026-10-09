---
name: creer-ticket
description: >-
  Create one GitHub child issue under a version parent, check the ticket fits
  the local version spec, sync that file onto the parent GitHub issue body,
  then sync sub-issue / blocked-by and the open PR Fixes lines. Use when the
  user types `/ct` or says « crée un ticket ». Not « Ouvre la version ».
  Not `/cci`. Not `/opr`.
---

# Create a child ticket

`/` = this skill’s trigger. No hyphen options. Treat `/ct` as a whole token.

`/ct` **is** permission to `gh issue create`, attach the sub-issue, set native
`blocked_by`, set the **parent** issue body from the local role **`spec`**
file, and `gh pr edit` the open version PR’s body when one exists.
Do not merge. Do not commit. Do not open a new PR. Do not rewrite the local
spec file.

Paths: **`agents/roles.yml`**. Tracker detail: **`agents/issue-tracker.md`**
(*Version parent and children* — **Child ticket body**).

One child per invocation. Later children: run `/ct` again.

The local `docs/specs/vX.Y.Z-*.md` is the source of truth for the parent
narrative. The GitHub parent issue body must match it after this skill runs.

**Body format (mandatory):** Matt `/to-tickets` template in
`agents/issue-tracker.md` — `Part of #<parent>`, then `## What to build`,
`## Acceptance criteria`, `## Blocked by`. English headings only. If the user
gave free-form text: reshape into that template; do not invent criteria.

## 1. Inputs

From the user message:

- **Title** — required. If missing: ask and **wait**.
- **What to build** / acceptance criteria — required (may arrive as a free
  body). If missing: ask and **wait**. Do not invent.
- **`#parent`** — optional. If absent: resolve the open PR for the current
  branch (`gh pr view`); take the parent from its `Fixes #<n>` that is the
  version spec (the issue that has the other `Fixes` as children / is not
  itself a `Part of` child). Zero or more than one open PR for this branch →
  **stop** and ask for `#parent`.
- **`Blocked by #n`** — optional. If present, that child becomes a native
  blocker of the new issue. The body line **must** be
  `- #<n> — vraie dépendance : <ce qui casse>` or
  `- #<n> — ordre de confort : <pourquoi l’ordre est seulement préféré>`
  (`agents/issue-tracker.md`). If the user gave a bare `Blocked by #n`
  without that clause: **ask and wait** — do not invent the reason, do not
  create. If absent: body `## Blocked by` → `- Aucun`; only parent ← child
  on GitHub. Never add a `#` that the user did not name.

A ticket with **no** parent is out of scope: ask for `#parent` and **wait**.

## 2. Spec gate (before create)

Resolve **`X.Y.Z`** from the branch `vX.Y.Z-<slug>`, the PR title
`VX.Y.Z — …`, or the parent title. Find the role **`spec`** file for that
version under `docs/specs/` (`vX.Y.Z-*.md`). Missing file / ambiguous match →
**stop**.

**Fits the spec:** the title + body must not contradict what that file
promises and must not add behaviour the file does not describe. If they do
not fit → **stop**. Quote the conflicting / missing passage. Do not create.

A local file that already differs from the parent GitHub body (e.g. human-test
corrections) is fine: step 4 will push the file onto GitHub. Do **not** stop
only because the file changed since the branch’s first add commit.

Done when the ticket fits the file.

## 3. Create the child

1. Build the body exactly as *Child ticket body* in `agents/issue-tracker.md`
   (reshape the user’s content into `What to build` / `Acceptance criteria` /
   `Blocked by`). First line: `Part of #<parent>`.
2. `gh issue create` with label `ready-for-agent`, title from the message,
   that body.
3. Attach as GitHub **sub-issue** of the parent (`POST …/issues/<parent>/sub_issues`,
   `sub_issue_id` = child’s database **id**). See `agents/issue-tracker.md`.
4. Native **blocked-by**: parent blocked by this child
   (`POST …/issues/<parent>/dependencies/blocked_by`, `issue_id` = child’s
   database **id**). If the message had `Blocked by #n`, also block the new
   child by that issue’s database id.

Confirm `sub_issues_summary.total` on the parent increased by one.

## 4. Sync the parent GitHub body

`gh issue edit <parent> --body-file <spec-path>` with the role **`spec`** file
from step 2 (working tree).

Compare before/after (or re-read): if the body already matched the file, say
so. Otherwise report that the parent issue body was updated from the file.

Done when the parent issue body equals that file’s contents.

## 5. Sync the PR (if any)

Find the open PR into `main` whose body already has `Fixes #<parent>`.

- **None** → create is done; say so. Do not `/opr`.
- **More than one** → **stop** and ask which PR. Child, links, and parent body
  already exist / are synced.
- **Exactly one** → edit its body: add a `Fixes #<n>` line for every parent
  sub-issue that is not `wontfix` and is missing from the body (including
  the child just created). Keep existing lines and the rest of the body
  verbatim. One `Fixes` keyword per issue.

Done when that PR lists `Fixes` for the parent and every in-scope child.
Reply with the child URL and what changed (parent body / links / PR lines).

## Not this skill

- Opening a version and the first ticket batch → `ouvrir-la-version`
- Closing a child → `fermer-ticket-enfant` (`/cci`)
- Opening a PR → `ouvrir-pr` (`/opr`)
- `/implement` or wrapping it → `encadrer-implement`
- Standalone issues with no version parent
- Editing the local spec file (the human or another flow writes it first)
