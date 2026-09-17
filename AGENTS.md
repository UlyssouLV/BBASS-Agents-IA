# AGENTS.md

## Agent skills

### Issue tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`. No `awaiting-merge`.

### After `/implement`

Matt Pocock `/implement` for TDD. **Next action** (the plugin’s closing step, in this repo): skill `encadrer-implement` — tests → commit + push + **close the child** and **remove `ready-for-agent`** → next unblocked Open child (`/clear` + `/implement`) **or**, if every PR child is Closed, ask the user to **test functionally** then **« Finalise la version »**. A repo hook blocks `/code-review` unless the current user message asks for it.

### Ouvre the version

When the user says **« Ouvre la version »** (must include **`X.Y.Z`**): skill `ouvrir-la-version`. Purpose from **`docs/suivi-avancement/feuille-de-route-dev.md`** when that version is already listed (otherwise ask) → `/grill-with-docs` → `/to-spec` (parent issue; **no spec files on `main`**) → **branch from `main` → immediate init commit+push** (uncommitted leftover on `main` goes on that branch, **never** a commit on `main` ; `docs/specs` + doc updates) → `/to-tickets` (propose, **yes**, then create with **native** blocked-by **and parent blocked by every child**, then drop `ready-for-agent` on the parent) → PR → propose `/clear` and `/implement` the first unblocked **child**.

### Finalise the version

When the user says **« Finalise la version »**: skill `finaliser-la-version`. Check every PR **child** is **Closed**, **docs** (`README.md`, `CONTEXT.md`, `CLAUDE.md`, `AGENTS.md`, `docs/` including **`docs/suivi-avancement/feuille-de-route-dev.md`**) match the version, **then** GitHub Release (semver tag on the **feature branch** SHA), **then** squash-merge into `main` and delete the feature branch.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`. `/code-review` Standards: start at `CLAUDE.md`.

## Git commits and pushes

After a green `/implement` of a child ticket, skill `encadrer-implement` **does** commit, push, remove `ready-for-agent`, and close that child (no extra “say the word”). Still never force-push; never commit `.env`, `*.db`, `.venv`, or secrets.

Do **not** commit or push for other reasons unless the **current user message** explicitly asks.

## GitHub issues vs `main`

Cycle: **« Ouvre la version »** (grill + spec, then branch + tickets + PR) → implement children (**close each child** when tests are green) → **« Finalise la version »** (docs gate, Release tag on the feature SHA, squash-merge to `main`, delete the branch). The **parent** spec closes via `Fixes` on the squash.

Do **not** leave implemented children Open. Close them so dependents unblock. Do **not** close the parent from `encadrer-implement`.
