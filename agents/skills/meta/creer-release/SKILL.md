---
name: creer-release
description: >-
  Create a GitHub Release on the current feature-branch SHA (not main).
  Use when the user types `/crel` or says « crée une release », or when
  another skill tells you to run creer-release with vX.Y.Z. Do not squash
  or merge. Not « Finalise la version ».
---

# Create a GitHub Release

`/` = this skill’s trigger. No hyphen options. Treat `/crel` as a whole token. The rest of the message is the tag (`vX.Y.Z` or `X.Y.Z`) plus optional purpose / notes.

`/crel` **is** permission to `gh release create` **targeting the current branch SHA**. Do not merge. Do not delete the branch. Do not `git commit`. Do not force-push. Do not retag an existing `vX.Y.Z`.

Paths: **`agents/roles.yml`**.

## 1. Guards

1. `git branch --show-current` is `main` or `master` → stop.
2. Tag: from the message, or from the branch name `vX.Y.Z-<slug>`. Normalize to `vX.Y.Z`. If missing: ask and **wait**. Do not invent a bump.
3. `git fetch`. `git tag -l 'vX.Y.Z'` or `gh release view vX.Y.Z` already exists → stop. Never retag.

## 2. Target

Tip of the **current** branch = `HEAD`. If an open PR exists for this branch, `HEAD` must match the PR head. If it does not: stop.

Target = that SHA (or the branch name while it still exists), **not** `main`. Squash would drop this history.

## 3. Title

`--title` is **one line**, same shape as the version PR:

`VX.Y.Z — <purpose>`

Purpose = the rest of the user / caller message after the tag, else the PR title after `VX.Y.Z —`, else the parent spec’s one-job sentence. Do not use a commit-subject dump as the title.

## 4. Notes (body)

`--notes` are for a human who did **not** watch the PR. **French** (unless this repo’s user-facing docs are English). Not a dump of `git log` subjects. **Keep this layout** — never invent new top-level headings for a commit sweep.

Always this layout (omit a section only if it would be empty **and** you said so in **Hors périmètre**):

```markdown
## Pourquoi

<problem / parent spec, one short paragraph>

## Ce qu’on peut faire maintenant

<features in product language, what a user can do>

## Historique des tickets

- PR : https://github.com/<owner>/<repo>/pull/<n>
- Commits : https://github.com/<owner>/<repo>/pull/<n>/commits

Tickets (`Fixes`) : #… #…

## Hors périmètre

<what is not in this version if it could be confused>

Spec : https://github.com/<owner>/<repo>/blob/vX.Y.Z/<spec-path>

ADRs de cette version (liens **sur ce tag**, pas `main`) :

- https://github.com/<owner>/<repo>/blob/vX.Y.Z/<adr-path>

Issues laissées de côté (PR / spec hors périmètre) : #…
```

`<spec-path>` = parent spec under role **`spec`** (usually `docs/specs/…`). Link **on this tag**, not `main`. Always this one-line shape: `Spec : <url>`.

`<adr-path>` = files under role **`adr`**.

### Fill order

1. Draft from the PR body (`Fixes`, summary), parent spec, and role **`adr`** files added on this branch. If the caller already passed notes, **fit them into these headings** — do not replace the layout with a free-form blob.
2. **Gap pass (commits only to complete, not to rewrite).** Read `git log origin/main..HEAD --oneline` (or the PR commits). Compare to the draft. Add only what is **missing** from the notes and useful to a human: a real capability the spec/PR omitted, or a bugfix beyond the parent `Fixes`. Fold each gap into the existing headings — usually **Ce qu’on peut faire maintenant** (product wording) or **Historique des tickets** (extra `#n` if a ticket exists). Do **not** paste commit subjects, hashes, or a « changelog commits » section. Do **not** duplicate points already covered by the spec/PR. Skip chore / noise (typos, lockfile-only, WIP) unless they change what a user can do.

Owner/repo from `git remote`. PR number from `gh pr view` for this branch.

## 5. Create

```bash
gh release create vX.Y.Z --target <sha-or-branch> --title "VX.Y.Z — <purpose>" --notes "$(cat <<'EOF'
<notes markdown>
EOF
)"
```

The tag must be **pushed** and the release **visible** before any squash. After the branch is deleted, `git log vX.Y.Z` still shows the development commits.

Done when GitHub shows the release with that title, that body, and the tag on the feature SHA. Reply with the tag and URL.

## Not this skill

- Squash-merge / delete branch: `fusionner-pr` (`/mpr`).
- Whole version ship: `finaliser-la-version`.
