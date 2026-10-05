# AGENTS.md

## Cycle

**« Ouvre la version »** → implement each child (close when tests are green) → human tests → **`/code-review`** → **« Finalise la version »** (quality gate, then **`/cqg`** if it is not `OK`). The **parent** spec closes via `Fixes` on the squash. Do **not** leave implemented children Open. Do **not** close the parent from `encadrer-implement`. New repo: **`/init`** / **« Initialise le repo »**.

- **« Initialise le repo »** (`/init`): skill `initialise-le-repo`
- **« Ouvre la version »** (must include **`X.Y.Z`**): skill `ouvrir-la-version`
- Child-ticket TDD: `/implement`, then skill `encadrer-implement`
- **« Finalise la version »**: skill `finaliser-la-version`

See `agents/README.md`.

## Tracker

Issues live as GitHub issues in this repo (`UlyssouLV/BBASS-Agents-IA`), managed via the `gh` CLI. See `agents/issue-tracker.md`.

Canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `agents/triage-labels.md`. No `awaiting-merge`.

## Domain

See `agents/domain.md`. File roles and path lookup: `agents/roles.yml`. `/code-review` **Standards**: start here (`AGENTS.md`).

## Tests

HTTP-boundary tests only (observable responses). Do not praise or require tests of internal function calls. Same convention as V1 and `docs/specs/`. Pytest: `/t`. Quality gate: `/qg` (`-w` waits up to 15 min for the CI analysis of this HEAD). Both: `/vf` / « Vérifie la fiabilité du code ». Fix a red gate: `/cqg`. `encadrer-implement` closes the child after the push and does not wait for Sonar. After human tests and an accepted `/code-review`, `finaliser-la-version` runs `/qg -w` once on the PR HEAD before the tag, then `/cqg` if the gate is not `OK`.

## Docs

« Finalise la version » extra checks (role **`agent-adapter`**):

- **`readme`**: « État actuel », lancement, comptes de test — no leftover previous-version branch names or « not built yet » for features this version delivered.
- **`roadmap`**: move **`X.Y.Z`** into **Déjà livré**; drop it from « Prochaine » / « Ensuite »; the next listed version becomes **Prochaine** (keep objectif / recherche).

## Git

Commit and push only when the **current user message** explicitly asks, **except** skill `encadrer-implement` after green tests (that skill is the permission: commit, push, close the child, drop `ready-for-agent`), skill `commit` (`/c`; `/c -p` pushes; `/c -p -f` is `--force-with-lease` only after **oui** on the next turn), skill `initialise-le-repo` (`/init`: `/c -a -p` on `main` is allowed, once), skill `ouvrir-pr` (`/opr`: push then `gh pr create` into `main`), skill `creer-release` (`/crel`: `gh release create` on the feature SHA), and skill `fusionner-pr` (`/mpr`: squash-merge into `main` and delete the branch). Never force-push otherwise. Never commit `.env`, `*.db`, `.venv`, or secrets.
