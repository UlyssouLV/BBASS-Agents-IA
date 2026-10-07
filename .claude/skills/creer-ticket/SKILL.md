---
name: creer-ticket
description: >-
  Create one GitHub child issue under a version parent, verify the version
  spec file is unchanged and that the ticket fits it, then sync sub-issue /
  blocked-by and the open PR Fixes lines. Use when the user types `/ct` or
  says « crée un ticket ». Not « Ouvre la version ». Not `/cci`. Not `/opr`.
---

# Create a child ticket

`/` = this skill’s trigger. No hyphen options. Treat `/ct` as a whole token.

`/ct` **is** permission to `gh issue create`, attach the sub-issue, set native
`blocked_by`, and `gh pr edit` the open version PR’s body when one exists.
Do not merge. Do not commit. Do not open a new PR. Do not rewrite the spec
file or the parent issue narrative.

Paths: **`agents/roles.yml`**. Tracker detail: **`agents/issue-tracker.md`**
(*Version parent and children*).

One child per invocation. Later children: run `/ct` again.

## 1. Inputs

From the user message:

- **Title** — required. If missing: ask and **wait**.
- **Body** — what the ticket delivers. If missing: ask and **wait**. Do not invent.
- **`#parent`** — optional. If absent: resolve the open PR for the current
  branch (`gh pr view`); take the parent from its `Fixes #<n>` that is the
  version spec (the issue that has the other `Fixes` as children / is not
  itself a `Part of` child). Zero or more than one open PR for this branch →
  **stop** and ask for `#parent`.
- **`Blocked by #n`** — optional. If present, that child becomes a native
  blocker of the new issue. If absent: only parent ← child.

A ticket with **no** parent is out of scope: ask for `#parent` and **wait**.

## 2. Spec gate (before create)

Resolve **`X.Y.Z`** from the branch `vX.Y.Z-<slug>`, the PR title
`VX.Y.Z — …`, or the parent title. Find the role **`spec`** file for that
version under `docs/specs/` (`vX.Y.Z-*.md`). Missing file / ambiguous match →
**stop**.

**Unchanged file:** compare the working-tree file to the blob at the **oldest**
commit on the current branch that **added** it:

`git log origin/main..HEAD --reverse --diff-filter=A --format=%H -- <spec-path>`

Take the first SHA. `git diff <sha> -- <spec-path>` must be empty (also vs
`HEAD` and the working tree). Any diff → **stop**. Show the diff. Do not
create the issue. Do not edit the PR.

**Fits the spec:** the title + body must not contradict what that file
promises and must not add behaviour the file does not describe. If they do
not fit → **stop**. Quote the conflicting / missing passage. Do not create.

Done when both checks pass.

## 3. Create the child

1. `gh issue create` with label `ready-for-agent`, title from the message,
   body starting with `Part of #<parent>` then the provided body.
2. Attach as GitHub **sub-issue** of the parent (`POST …/issues/<parent>/sub_issues`,
   `sub_issue_id` = child’s database **id**). See `agents/issue-tracker.md`.
3. Native **blocked-by**: parent blocked by this child
   (`POST …/issues/<parent>/dependencies/blocked_by`, `issue_id` = child’s
   database **id**). If the message had `Blocked by #n`, also block the new
   child by that issue’s database id.

Confirm `sub_issues_summary.total` on the parent increased by one.

## 4. Sync the PR (if any)

Find the open PR into `main` whose body already has `Fixes #<parent>`.

- **None** → create is done; say so. Do not `/opr`.
- **More than one** → **stop** and ask which PR. Child and links already exist.
- **Exactly one** → edit its body: add a `Fixes #<n>` line for every parent
  sub-issue that is not `wontfix` and is missing from the body (including
  the child just created). Keep existing lines and the rest of the body
  verbatim. One `Fixes` keyword per issue.

Done when that PR lists `Fixes` for the parent and every in-scope child.
Reply with the child URL and what changed (links / PR lines).

## Not this skill

- Opening a version and the first ticket batch → `ouvrir-la-version`
- Closing a child → `fermer-ticket-enfant` (`/cci`)
- Opening a PR → `ouvrir-pr` (`/opr`)
- `/implement` or wrapping it → `encadrer-implement`
- Standalone issues with no version parent
