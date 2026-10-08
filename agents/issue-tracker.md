# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## Bugs (standalone)

Used by `creer-un-bug` (`/cub`). A **bug** is not a version child (`/ct`):

- Title: `Bug — <short description>`.
- Label: **`bug`** only (not `ready-for-agent` until the bug is scheduled into a version and turned into implement work).
- Body: fixed `##` headings — Constat, Reproductibilité, Impact, Cause probable, À corriger, Hors périmètre, Métadonnées — see `docs/dev/feuille-de-route/README.md` (*Bugs*). Same fields go under **Plus tard** on the feuille de route.
- Missing facts: exact token `Informations manquantes` (do not invent). Derived states **complet** / **incomplet** — same README.
- Scheduling into a version: `/afr` removes the `### Bug — … (#n)` block from **Plus tard** (objectif de version). Do not close the issue yet.
- Closing / fixing: version PR includes `Fixes #<n>` ; **`finaliser-la-version`** deletes any leftover Plus tard block and `gh issue close <n>` with `Corrigé en VX.Y.Z.` — not `/cub`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Version parent and children

Used by `ouvrir-la-version` (`/to-tickets`) and by any later child under an open parent (human-test follow-ups). A **single** later child is skill `creer-ticket` (`/ct`): it creates the child, checks the ticket fits the local version spec file, sets the parent GitHub issue body from that file, then syncs the three links below and any open PR’s `Fixes` lines. Three links, each with a job:

1. **`Part of #<parent>`** at the top of the child body — text marker for `fermer-ticket-enfant` / `encadrer-implement`.
2. **GitHub sub-issue** — what the UI uses for the parent progress **Y/Z**. After `gh issue create`, attach the child:
   `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues --input -` with JSON `{"sub_issue_id": <child-db-id>}` (`sub_issue_id` = `gh api repos/<owner>/<repo>/issues/<child> --jq .id`, an **integer**, not the `#number`). Check with `sub_issues_summary` on the parent (`total` / `completed`). A body `Part of` line alone does **not** update that counter.
3. **Native blocked-by** — implementation order and the live gate. Same shape as below: parent blocked by every child; children may block each other. Closing a child updates the gate; it also increments `sub_issues_summary.completed`.

Never `/implement` the parent. Closing children is `encadrer-implement` / `fermer-ticket-enfant`; the parent closes via squash `Fixes #<parent>`.

### Child ticket body (canonical — Matt `/to-tickets`)

**Going forward**, every child issue body uses this exact shape (English headings from Matt Pocock `/to-tickets`). Do **not** invent French equivalents (`Ce qu'il livre`, `Critères d'acceptation`, `Tests attendus`, …). Do **not** rewrite closed historical tickets.

```markdown
Part of #<parent>

## What to build

<What this ticket delivers — one vertical slice, product language where possible.
 Concrete enough to implement without re-reading the whole spec.>

## Acceptance criteria

- [ ] <observable criterion>
- [ ] <…>
- [ ] Suite pytest verte.

## Blocked by

- Aucun
```

- **`Part of #<parent>`** — first line, always (even if a `## Parent` block also appears from Matt’s quiz).
- **`## What to build`** — required. Not a dump of the parent spec.
- **`## Acceptance criteria`** — required. Checkbox list (`- [ ]`). Include the green-pytest criterion when this repo’s HTTP-boundary tests apply.
- **`## Blocked by`** — required section. `- Aucun` when no peer blockers; otherwise one `- #<n>` per blocking **child**. Native GitHub `blocked_by` edges are still set by the skills; this section is the human-readable mirror (and fallback).
- Optional only if Matt’s quiz produced them: `## Implementation decisions` (keep short). No other top-level `##` headings by default.
- Label on create: **`ready-for-agent`**. Not a `bug` issue (bugs → `/cub`).

When `/to-tickets` or the user drafts free-form content: **reshape** into this template before `gh issue create`.

### Human-test child

Created by **`ouvrir-la-version`** after the `/to-tickets` implementation children (not by `/implement`, not by `/ct` for normal work). One per version.

- **Title:** `Tests humains — VX.Y.Z`
- **Label on create:** **`ready-for-human`** only (never `ready-for-agent`). Never `/implement` this issue.
- **Links:** same three links as any child (`Part of`, sub-issue, parent blocked by this child). **`## Blocked by`** lists **every** implementation child of the version (native `blocked_by` the same way).
- **Body** — Matt headings plus three required extra sections:

```markdown
Part of #<parent>

## What to build

Plan et trace des tests humains pour VX.Y.Z (pas d’implémentation agent).

## Acceptance criteria

- [ ] Plan de tests proposé après le dernier ticket d’implémentation
- [ ] Scénarios joués / non joués documentés
- [ ] Résultats (et images si fournies) publiés sur ce ticket
- [ ] Brouillon « Ce qu’on peut faire maintenant » prêt pour la release

## Blocked by

- #<impl-1>
- #<impl-2>

## Plan de tests

_(rempli par `encadrer-implement` après le dernier enfant `ready-for-agent`)_

## Résultats

_(rempli par `/th`)_

## Ce qu’on peut faire maintenant

_(brouillon produit pour la release ; images sous `docs/img/changelog/vX.Y.Z/`)_
```

- At version open: create with empty Plan / Résultats / product draft (placeholders above).
- After the last implementation child closes: `encadrer-implement` writes the concrete plan into `## Plan de tests`.
- After the human reports: skill **`tests-humains`** (`/th`) fills Résultats + product section, commits screenshots if any, removes `ready-for-human`, closes the issue. Partial plans are OK (document non-joués). Closing this child is **`/th`**, not `/cci`.

## Changes to earlier versions

A version may change behaviour that an earlier version shipped (a renamed tool, a raised limit, a replaced mechanism). The record is one section of the version spec (role `spec`), written by `ouvrir-la-version` and read by `finaliser-la-version`:

```markdown
## Changements apportés aux versions antérieures

| Version | Élément | Avant | Après | À annoter |
| --- | --- | --- | --- | --- |
| 1.4.0 | Boucle d'outils | 3 appels principaux par message | 5 | `v1.4.0`, #117, #119 |
```

- One row per changed behaviour. **À annoter**: the earlier release tag and the earlier issues (spec, child) that describe the old behaviour.
- Nothing changed → the section holds the single line `Aucun.` Missing section = `Aucun.`

After the squash-merge, each row becomes one block, prepended to the earlier release notes (`gh release edit <tag> --notes-file`) and posted as a comment on each listed issue (`gh issue comment`):

```markdown
> **Modifié en VX.Y.Z** ([#<parent>](<parent url>)) — <Élément>
> Avant : <Avant>
> Après : <Après>
```

**Critical (docs site):** when prepending to release notes, keep **Markdown structure intact**:

1. Each annotation is its own blockquote paragraph (three `>` lines), blocks separated by a blank line.
2. After the **last** annotation block, always insert a **blank line**, then the existing notes starting at `## Pourquoi` (never glue `Après : … ## Pourquoi` on one line).
3. Read the current notes first (`gh release view <tag> --json body`). Write back via `--notes-file` (full body), never a one-line paste that collapses newlines.
4. The docs changelog (`generer-changelog.mjs`) only extracts `## Pourquoi` and `## Ce qu'on peut faire maintenant` — broken newlines empty the functional docs page.

Skip a target that already holds the block for `VX.Y.Z` and that element. `Aucun.`, a missing section, or a failed annotation never blocks a release: report it in one line and continue.

## Release notes (canonical — `/crel`)

**Going forward**, every GitHub Release body uses this layout (skill `creer-release`). French. Do not invent alternate top-level headings.

```markdown
## Pourquoi

<problem / parent spec, one short paragraph>

## Ce qu'on peut faire maintenant

<features in product language — prefer the Closed human-test child’s section (text + images under `docs/img/changelog/vX.Y.Z/`) when present>

## Historique des tickets

- PR : https://github.com/<owner>/<repo>/pull/<n>
- Commits : https://github.com/<owner>/<repo>/pull/<n>/commits

Tickets (`Fixes`) : #<parent> #<enfant> …

## Hors périmètre

<what is not in this version>

Spec : https://github.com/<owner>/<repo>/blob/vX.Y.Z/<spec-path>

ADRs de cette version (liens **sur ce tag**, pas `main`) :

- https://github.com/<owner>/<repo>/blob/vX.Y.Z/<adr-path>

Issues laissées de côté (PR / spec hors périmètre) : #…
```

Title: `VX.Y.Z — <purpose>`. Tag on the **feature SHA**, not `main`. Optional leading `> **Modifié en …**` annotation blocks (from a later version) may sit **above** `## Pourquoi`, each separated by blank lines as above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (same `POST …/sub_issues` as version children above). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<blocked>/dependencies/blocked_by --input -` and JSON `{"issue_id": <blocker-db-id>}` (`issue_id` must be an **integer**, not a string). `<blocker-db-id>` is `gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`. GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). After `/to-tickets`, the **parent spec** is blocked by **every child**; each child may also be blocked by other children. Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is **Closed**. After a green `/implement`, close the child (`encadrer-implement`) without waiting for the quality gate, so this graph updates. Never `/implement` the parent.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
