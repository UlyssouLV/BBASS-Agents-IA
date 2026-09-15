# Claude Code

This file is the coding-standards entry for `/code-review` (Standards axis). There is no `CODING_STANDARDS.md`.

## When reviewing Standards

Read, in order:

1. `docs/agents/domain.md` — which domain docs to load, glossary and ADR rules
2. `CONTEXT.md` — required vocabulary (`Compte`, `pôle`, `compte administrateur`, …)
3. `docs/adr/` — ADRs that touch the diff (contradictions must be named, not silently overridden)
4. `AGENTS.md` — issues stay Open until merge to `main`; no commit/push unless the user asked

## Tests

HTTP-boundary tests only (observable responses). Do not praise or require tests of internal function calls. Same convention as V1 and `docs/specs/`.

## When to run `/code-review`

Not after each `/implement`. Once vs `main` when the PR’s child tickets are done. See skill `code-review-avant-pr`.

## Out of this file

GitHub tracker, labels, `/implement` lifecycle: `AGENTS.md` and `docs/agents/`. Product spec for the Spec review axis: the originating issue plus `docs/specs/`.
