# Claude Code

## Fin d’un `/implement` (enfant)

La dernière action du plugin `/implement` est, dans ce dépôt, le skill **`encadrer-implement`** (`/t`, `/c -p`, `/qg -w`, `/cqg` si le gate est rouge, `/cci`).

Un hook (`.claude/hooks/gate-code-review.py`) refuse le skill `/code-review` tant que le message utilisateur courant ne le demande pas, **sauf** « Finalise la version ». Pour un review vs `main` hors Finalise, tape `/code-review` toi-même.

## When reviewing Standards

`/code-review` **Standards** starts at repo-root `AGENTS.md` (tests, git, cycle), then `agents/domain.md`. This file is the Claude adapter, not the coding-standards entry. There is no `CODING_STANDARDS.md`.

## Out of this file

Tracker, labels, cycle Ouvre / Implement / Finalise: `AGENTS.md` and `agents/`. Product spec for the Spec review axis: the originating issue plus role **`spec`** (`agents/roles.yml`).
