# AGENTS.md

## Agent skills

### Issue tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Git commits and pushes

Do **not** run `git commit`, `git push`, or `gh` commands that publish unless the **current user message** explicitly asks to commit, push, or publish.

Finishing a ticket, tests passing, or `/implement` is **not** permission to commit. Show the summary, list files, and wait: "Ready to commit — say the word."

## GitHub issues vs `main`

Cycle for every feature: **branch → open issues → implement on the branch → PR → merge to `main` → close the branch and close the issues.**

Do **not** `gh issue close` because the work is done on a feature branch. Issues stay **Open** until that work is **merged into `main`**. Prefer `Fixes #n` on the **PR** so GitHub closes them at merge. See skill `fermer-issues-apres-merge-main`.
