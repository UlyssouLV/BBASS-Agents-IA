---
name: augmenter-la-feuille-de-route-dev
description: >-
  Read the dev roadmap, list planned versions, argue changes, and write
  versions the user asked for in that file’s format. Use when the user
  types `/afr` or says « Augmente la feuille de route de dev » /
  « Améliore la feuille de route de dev ». Not « Ouvre la version ».
  Do not implement. Do not merge.
---

# Augment the dev roadmap

Triggered by **`/afr`**, **« Augmente la feuille de route de dev »**, or **« Améliore la feuille de route de dev »**. `/` = this skill’s trigger. No hyphen options.

Git commit goes through **`commit`** (`/c`) only if the user asked to commit this turn. This skill does **not** `/c` on its own.

Paths: **`agents/roles.yml`**. Role **`roadmap`** is the **feuille de route de dev** (not a product marketing plan).

## Format

One job per version, product language:

```markdown
# Feuille de route de dev

## X.Y.Z — <titre, un job>

Un court paragraphe, un seul job.

## Plus tard — <titre>

Idée reportée, pas encore de semver.
```

An intro under the H1 is allowed (constraints that apply to several versions). Headings that `ouvrir-la-version` can find are **`## X.Y.Z — …`**. An existing H1 `# Feuille de route` is the same file; leave it or normalize to **`# Feuille de route de dev`** when writing.

## 1. Read

Read role **`roadmap`**.

List every **`X.Y.Z`** (title + job) and every **`Plus tard`**. Title-only / empty file → say the feuille de route de dev has no versions yet.

Done when that inventory matches the file.

## 2. Argue, then wait

In French: order, jobs that cover more than one job, missing versions, format drift. Propose concrete edits (add / rewrite / reorder). **Wait.**

Write nothing in this step.

## 3. Write what the user asked

When they confirm or name versions to add / change / move:

- Write **only** those edits, in the **Format** above.
- Keep versions they did not mention.
- Semver = `X.Y.Z`. A deferred idea without a number → **`## Plus tard — …`**.

Done when the file matches what they asked, or when they said to leave it as is.

## Not this skill

- Open a version (branch, spec, tickets, PR) → `ouvrir-la-version`
- Ship a version → `finaliser-la-version`
- Commit / push → `commit` (`/c`)
- Child TDD → `/implement` + `encadrer-implement`
