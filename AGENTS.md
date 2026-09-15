# AGENTS.md

## Agent skills

### Issue tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) plus lifecycle `awaiting-merge` (coded on a feature branch, still Open until `main`). See `docs/agents/triage-labels.md`.

### After `/implement`

Matt Pocock `/implement` for TDD. Then skill `encadrer-implement`: tests → commit + push + `awaiting-merge` (issue stays Open) → next unblocked child (`/clear` + `/implement`) **or**, if every PR child is done, `/code-review` once vs `main`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`. `/code-review` Standards: start at `CLAUDE.md`.

## Git commits and pushes

After a green `/implement` of a child ticket, skill `encadrer-implement` **does** commit and push that ticket (no extra “say the word”). Still never force-push; never commit `.env`, `*.db`, `.venv`, or secrets.

Do **not** commit or push for other reasons unless the **current user message** explicitly asks.

## GitHub issues vs `main`

Cycle for every feature: **branch → open issues → implement on the branch → PR → merge to `main` → close the branch and close the issues → GitHub Release (semver tag on that `main` commit).**

Do **not** `gh issue close` because the work is done on a feature branch. Issues stay **Open** until that work is **merged into `main`**. Prefer `Fixes #n` on the **PR** so GitHub closes them at merge.
