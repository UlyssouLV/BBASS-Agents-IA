---
name: ouvrir-pr
description: >-
  Push the current branch and open a GitHub PR into main. Use when the
  user types `/opr` or says « ouvre une PR » / « ouvre une pull request »,
  or when another skill tells you to run ouvrir-pr with a title and body.
  `-draft` opens a draft PR. Do not merge. Do not force-push. Not `/ob`. Not « Finalise la version ».
---

# Open a pull request

`/opr` **is** permission to `git push` the **current** branch (`-u origin HEAD` if it has no upstream) and `gh pr create` into `main`. No force-push. Do not merge. Do not delete the branch. Do not `git commit` (skill `commit` / `/c`).

`/` = this skill’s trigger. `-` = options. Treat `/opr` and `-draft` as whole tokens.

## 1. Guards

1. `git branch --show-current` is `main` or `master` → stop.
2. If a PR for this branch into `main` already exists: print its URL and stop. Do not open a second one.

## 2. Title and body

Take title and body from the rest of the user message (or from the calling skill).

If they are missing:

- **Title:** subject of `git log -1 --format='%s'`
- **Body:** `## Summary` plus the commit subjects of `git log origin/main..HEAD --format='%s'` (or one line if that is empty)

If **`-draft`** is present, create a draft. Otherwise a ready PR.

Keep `Fixes #<n>` lines **verbatim** when the asker (or calling skill) gave them — one keyword per issue. Do not invent issue numbers.

## 3. Push, then create

1. `git push` the current branch (`-u origin HEAD` if no upstream). No force.
2. `gh pr create --base main` with that title and body (HEREDOC). Match recent squash-merged PRs: `## Summary`, `## Test plan` (checkboxes) if the body did not already include them.

Done when the command prints a PR URL. Reply with that URL.

## Not this skill

- Create the branch: skill `ouvrir-branche` (`/ob`).
- Squash-merge / release: skill `finaliser-la-version` / `fusionner-pr` (`/mpr`) / `creer-release` (`/crel`).
- Whole version cycle: skill `ouvrir-la-version`.
