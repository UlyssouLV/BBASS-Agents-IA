---
name: fusionner-pr
description: >-
  Squash-merge the current branch’s PR into the integration base (main by
  default, or base_branch from agents/integration-channel.yml) and delete
  the feature branch. Use when the user types `/mpr` or says « fusionne
  le PR », or when another skill tells you to run fusionner-pr. Do not
  create a release. Do not force-push. Not « Finalise la version ».
---

# Squash-merge the current PR

`/` = this skill’s trigger. No hyphen options.

**Base:** resolve per `agents/docs/integration-channel.md` (*Résolution*). Default **base** = `main`.

`/mpr` **is** permission to mark the PR ready and `gh pr merge --squash --delete-branch` into **base**. No merge commit. No rebase-merge. No force-push to **base**. Do not `git commit`. Do not create a tag or Release (skill `creer-release` / `/crel`). Do **not** delete **base** (only the PR head / feature branch).

## 1. Guards

1. `git branch --show-current` is **protected** (base, `main`, `master`) → stop.
2. Resolve the open PR for this branch (`gh pr view`). If none: stop. If its base is not **base**: stop and say so.
3. Record `HEAD` SHA **before** the merge (the SHA any release tag must keep).

## 2. Merge

1. PR Ready for review (not Draft): undraft if needed.
2. `gh pr merge --squash --delete-branch`.
3. Confirm **base** has **one** new squash commit for this PR (`git fetch` then log on `origin/<base>`).

## 3. Tags stay on the old SHA

If a release tag pointed at the pre-merge `HEAD`, it must **still** point there. Do **not** move it onto the squash commit (that would lose the ticket-by-ticket history).

Done when the PR is merged, the feature branch is gone on the remote, **base** still exists, and existing release tags still point at the old SHA. Reply with the PR URL, the squash SHA on **base**, and the base name.

## Not this skill

- GitHub Release: `creer-release` (`/crel`).
- Whole version ship: `finaliser-la-version`.
- Open a PR: `ouvrir-pr` (`/opr`).
