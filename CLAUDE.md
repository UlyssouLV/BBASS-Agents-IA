# Claude Code

## Fin d’un `/implement` (enfant)

La dernière action du plugin `/implement` est, dans ce dépôt, le skill **`encadrer-implement`** : pytest vert → commit → push → fermer l’enfant → proposer `/clear` puis `/implement` du suivant, **ou** demander les tests humains puis « Finalise la version ».

Un hook (`.claude/hooks/gate-code-review.py`) refuse le skill `/code-review` tant que le message utilisateur courant ne le demande pas. Pour un vrai review vs `main`, tape `/code-review` toi-même.

## When reviewing Standards

This file is the coding-standards entry for `/code-review` (Standards axis). There is no `CODING_STANDARDS.md`.

Read, in order:

1. `docs/agents/domain.md` — which domain docs to load, glossary and ADR rules
2. `CONTEXT.md` — required vocabulary (`Compte`, `pôle`, `compte administrateur`, …)
3. `docs/adr/` — ADRs that touch the diff (contradictions must be named, not silently overridden)
4. `AGENTS.md` — close each child after a green `/implement`; `/implement` commit/push/close is skill `encadrer-implement` only

## Tests

HTTP-boundary tests only (observable responses). Do not praise or require tests of internal function calls. Same convention as V1 and `docs/specs/`.

## Out of this file

GitHub tracker, labels, `/implement` lifecycle: `AGENTS.md` and `docs/agents/`. Product spec for the Spec review axis: the originating issue plus `docs/specs/`.
