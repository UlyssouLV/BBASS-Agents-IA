---
name: quality-gate
description: >-
  Read the SonarQube / SonarCloud quality gate for the current HEAD SHA.
  Use when the user types `/qg` or says « quality gate » / « vérifie le
  quality gate », or when another skill tells you to run quality-gate.
  Do not fix code. Do not commit. Do not run pytest.
---

# Read the quality gate

`/` = this skill’s trigger. No hyphen options. Treat `/qg` as a whole token.

This path **is** permission to call the Sonar API **read-only**. Do not change code. Do not `git commit`. Never print `SONAR_TOKEN` or dump `.env`.

## 1. Credentials

From the repo root, load `.env` if it exists (`set -a; . ./.env; set +a`). Need:

- `SONAR_HOST_URL` (no trailing slash)
- `SONAR_TOKEN`
- `SONAR_PROJECT_KEY`

If any is missing: **stop**. Say to put those three in `.env` (gitignored). Do not invent a host or key. Do not commit `.env`.

## 2. HEAD vs last analysis

`HEAD` = `git rev-parse HEAD`.

Find the analysis whose `revision` is that SHA:

```bash
curl -sS -u "$SONAR_TOKEN:" \
  "$SONAR_HOST_URL/api/project_analyses/search?project=$SONAR_PROJECT_KEY&ps=20"
```

If no analysis matches `HEAD`: **stop**. The gate is not for this commit (analysis not run yet, or another SHA). Do not use an older analysis as a stand-in.

## 3. Gate status

```bash
curl -sS -u "$SONAR_TOKEN:" \
  "$SONAR_HOST_URL/api/qualitygates/project_status?projectKey=$SONAR_PROJECT_KEY"
```

Prefer a call scoped to that analysis when the API offers it (`analysisId`). `projectStatus.status` must be **`OK`**.

- **`OK`** → report green (SHA + status). Done.
- Anything else (`ERROR`, `WARN`, `NONE`, …) → **fail**. List failed conditions. Do not continue a caller’s later steps.

Done when the gate for **this** SHA is `OK`, or as soon as it is not.

## Not this skill

- Fix the gate: `corriger-quality-gate` (`/cqg`)
- Tests: `lancer-tests` (`/t`)
- Both: `verifier-la-fiabilite` (`/vf`)
