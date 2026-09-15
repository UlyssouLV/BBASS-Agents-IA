---
name: apres-implement-awaiting-merge
description: >-
  After /implement or finishing a ticket on a feature branch. Ask for
  confirmation, then set GitHub issue labels to awaiting-merge (Open, not
  closed). Use when /implement is done, tests pass for an issue, the user
  says the ticket is implemented, or when applying awaiting-merge.
---

# After /implement: ask, then `awaiting-merge`

When implementation of a **child issue** is done on the feature branch (code + tests), do **not** close the issue and do **not** change labels until the user confirms.

This is the "developed, not merged" state. Close happens only at merge to `main` (`Fixes #n` on the PR). See `fermer-issues-apres-merge-main` and `docs/agents/triage-labels.md`.

## After the implementation summary

1. Name the issue number(s) this work belongs to.
2. Ask, then **wait** (same bar as `demander-avant-commit` — `/implement` done is **not** permission):

> Ready to mark #<n> as `awaiting-merge` (Open, remove `ready-for-agent`)? Say the word.

3. Only if the **latest user message** clearly says yes (e.g. "oui", "ok pour awaiting-merge", "marque #10"): run `gh` below.
4. Still do **not** commit or push unless they asked for that separately.
5. Do **not** run `/code-review` here. See skill `code-review-avant-pr`.

## Correct GitHub state (after yes)

Keep the issue **Open**.

```
gh issue view <n> --json labels --jq "[.labels[].name]"
gh issue edit <n> --add-label awaiting-merge
```

If `ready-for-agent` and/or `ready-for-human` are present, remove them:

```
gh issue edit <n> --remove-label ready-for-agent
gh issue edit <n> --remove-label ready-for-human
```

Skip a `--remove-label` if that label is absent (`gh` errors otherwise).

Do **not** add `wontfix`. Do **not** `gh issue close`.

## Do not label

- Parent / map issues (e.g. spec #1) until **every** child for that merge is on the branch.
- Issues not actually implemented in this work.
- `needs-triage` / `needs-info` tickets you did not finish (e.g. #6).
