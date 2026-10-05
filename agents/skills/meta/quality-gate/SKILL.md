---
name: quality-gate
description: >-
  Read the SonarQube / SonarCloud quality gate for the current git HEAD,
  via the Sonar branch or pull request that lists that commit. Use when
  the user types `/qg` or `/qg -w`, says « quality gate » / « vérifie le
  quality gate », or when another skill tells you to run quality-gate.
  `-w` polls those lists until HEAD appears. Do not fix code. Do not
  commit. Do not run pytest.
---

# Read the quality gate

`/` = this skill’s trigger. `-` = options. Treat `/qg` and `-w` as whole tokens.

This path **is** permission to call the Sonar API **read-only**. Do not change code. Do not `git commit`. Never print `SONAR_TOKEN` or dump `.env`.

## 1. Credentials

From the repo root, load `.env` if it exists (`set -a; . ./.env; set +a`). Need:

- `SONAR_HOST_URL` (no trailing slash)
- `SONAR_TOKEN`
- `SONAR_PROJECT_KEY`

If any is missing or empty: **stop now**. Say to put those three in `.env` (gitignored). Do not invent a host or key. Do not commit `.env`. **`-w` does not poll** when this step stops.

## 2. Current ref

```bash
BRANCH=$(git branch --show-current)
HEAD=$(git rev-parse HEAD)
```

Empty `BRANCH` (detached HEAD) → **stop**.

A SHA **matches** `HEAD` when the two strings are equal, or one is a prefix of the other (at least 7 characters). Sonar may store a full hash; `git rev-parse --short` is not the lookup key.

## 3. Which Sonar ref has this commit?

The living analysis is on these lists, not on `project_analyses/search` (that list can stay on an old `revision` while the gate is already green).

```bash
curl -sS -u "$SONAR_TOKEN:" -G \
  "$SONAR_HOST_URL/api/project_pull_requests/list" \
  --data-urlencode "project=$SONAR_PROJECT_KEY"

curl -sS -u "$SONAR_TOKEN:" -G \
  "$SONAR_HOST_URL/api/project_branches/list" \
  --data-urlencode "project=$SONAR_PROJECT_KEY"
```

Pick **one** ref, in this order:

1. A pull request whose `commit.sha` (or `commit`) **matches** `HEAD`. Remember `pullRequest=<key>`.
2. Else a branch whose `name` is `BRANCH` and whose `commit.sha` (or `commit`) **matches** `HEAD`. Remember `branch=<name>`.
3. Else if `gh pr view --json number -q .number` is a number, keep `pullRequest=<n>` only once that PR’s commit **matches** `HEAD`. A PR that still shows an older commit is not this analysis yet.

A `component not found` on `branch=$BRANCH` is normal for a short-lived branch that Sonar only knows as a PR. Continue with the PR list.

- **Without `-w`:** no ref whose commit **matches** `HEAD` → **stop**.
- **With `-w`:** repeat **these two list calls** every **15 s**, up to **12** times (3 min). Stop the poll as soon as a ref’s commit **matches** `HEAD`. Still none after 12 tries → **stop**.

## 4. Gate status

```bash
curl -sS -u "$SONAR_TOKEN:" -G \
  "$SONAR_HOST_URL/api/qualitygates/project_status" \
  --data-urlencode "projectKey=$SONAR_PROJECT_KEY" \
  --data-urlencode "pullRequest=$PR"
# or --data-urlencode "branch=$BRANCH" when step 3 chose a branch
```

Scope **must** be the ref from step 3 (`pullRequest` or `branch`). A `projectKey`-only call is `main`. Do not use `analysisId` from `project_analyses/search` (it can be the previous commit on that PR).

`projectStatus.status` must be **`OK`**. Report the ref (PR number or branch), the matched SHA, and the status.

- **`OK`** → green. Done.
- Anything else (`ERROR`, `WARN`, `NONE`, …) → **fail**. List failed conditions. Do not continue a caller’s later steps.

Done when the gate for **this HEAD** (on its Sonar PR or branch) is `OK`, or as soon as it is not (or no list entry matches `HEAD`).

## Not this skill

- Fix the gate: `corriger-quality-gate` (`/cqg`)
- Tests: `lancer-tests` (`/t`)
- Both: `verifier-la-fiabilite` (`/vf`)
