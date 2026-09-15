# AGENTS.md

## Agent skills

### Issue tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) plus lifecycle `awaiting-merge` (coded on a feature branch, still Open until `main`). See `docs/agents/triage-labels.md`.

### After `/implement`

Matt Pocock `/implement` for TDD. Then skill `encadrer-implement`: tests → commit + push + `awaiting-merge` (issue stays Open) → next unblocked child (`/clear` + `/implement`) **or**, if every PR child is done, `/code-review` once vs `main`.

### Finalise the version

When the user says **« Finalise la version »**: skill `finaliser-la-version`. Check every PR child is `awaiting-merge`, **then** GitHub Release (semver tag on the **feature branch** SHA, so `git log` of the tag still shows ticket history), **then** squash-merge the PR into `main` (one commit) and delete the feature branch.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`. `/code-review` Standards: start at `CLAUDE.md`.

## Git commits and pushes

After a green `/implement` of a child ticket, skill `encadrer-implement` **does** commit and push that ticket (no extra “say the word”). Still never force-push; never commit `.env`, `*.db`, `.venv`, or secrets.

Do **not** commit or push for other reasons unless the **current user message** explicitly asks.

## GitHub issues vs `main`

Cycle for every feature: **branch + PR → implement children on the branch → « Finalise la version » (Release tag on the feature SHA, squash-merge to `main`, delete the branch).** GitHub closes issues via `Fixes` on the squash.

Do **not** `gh issue close` because the work is done on a feature branch. Issues stay **Open** until that work is **merged into `main`**.
