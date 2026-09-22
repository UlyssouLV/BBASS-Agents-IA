# AGENTS.md

## Cycle

**« Ouvre la version »** → implement each child (close when tests are green) → **« Finalise la version »**. The **parent** spec closes via `Fixes` on the squash. Do **not** leave implemented children Open. Do **not** close the parent from `encadrer-implement`.

- **« Ouvre la version »** (must include **`X.Y.Z`**): skill `ouvrir-la-version`
- Child-ticket TDD: `/implement`, then skill `encadrer-implement`
- **« Finalise la version »**: skill `finaliser-la-version`

See `agents/README.md`.

## Tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `agents/issue-tracker.md`.

Canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `agents/triage-labels.md`. No `awaiting-merge`.

## Domain

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `agents/domain.md`. `/code-review` **Standards**: start here (`AGENTS.md`).

## Tests

HTTP-boundary tests only (observable responses). Do not praise or require tests of internal function calls. Same convention as V1 and `docs/specs/`.

## Git

Commit and push only when the **current user message** explicitly asks, **except** skill `encadrer-implement` after green tests (that skill is the permission: commit, push, close the child, drop `ready-for-agent`), skill `commit` (`/c`; `/c -p` pushes; `/c -p -f` is `--force-with-lease` only after **oui** on the next turn), and skill `ouvrir-pr` (`/opr`: push then `gh pr create` into `main`). Never force-push otherwise. Never commit `.env`, `*.db`, `.venv`, or secrets.
