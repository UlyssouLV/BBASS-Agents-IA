---
name: mettre-a-jour-suivi-avancement
description: >-
  Update the current calendar week’s suivi HTML for a shipped version X.Y.Z
  and regenerate the sibling PDF. Use when the user types `/msa`, says
  « mets à jour le suivi d’avancement », or when finaliser-la-version
  runs this step. Does not create the week folder (that is `/os`).
---

# Mets à jour le suivi d’avancement

Triggered by **`/msa`**, **« mets à jour le suivi d’avancement »**, or by **`finaliser-la-version`**. Records **`X.Y.Z`** in the current week HTML (functional language) and regenerates the PDF. Does **not** commit. Does **not** create a week folder.

Paths: **`agents/roles.yml`**. Convention: **`docs/suivi-avancement/README.md`**.

## 0. Version

Infer **`X.Y.Z`** from the user message, or from the open version branch / PR (`vX.Y.Z-…`) when called from finaliser. If missing: ask and **wait**.

## 1. Locate the week HTML

Under role **`suivi-avancement`**, find folder `semaine-…` whose lun–ven range (Europe/Paris) **contains today** (parse rule: same as `docs-site/scripts/capturer-travail-realise.mjs`).

Inside that folder: first `suivi-semaine-*.html` (flexible name — README).

**None** → one line soft-skip: no week file; remind **`/os`** / « ouvre la semaine de travail ». Do **not** stop a parent finaliser release. Do not invent a folder.

Done when: HTML path known, or soft-skip done.

## 2. Update the HTML for `X.Y.Z`

Follow **`docs/suivi-avancement/README.md`** (*Structure HTML*, *Langage*):

1. TOC: ensure an entry `#version-X-Y-Z` under Descriptif des versions.
2. Bloc `.version#version-X-Y-Z`: create if missing; set badge to  
   `Déployé le JJ/MM/AAAA à HH:MM` (`.deploye`, drop `.prevu`); body = what shipped in **functional** cabinet language (no stack, no tool package names, no `#ticket` in day bullets / version body).
3. **Travail réalisé**: add a bullet on **today’s** `.jour` (or the ship day if the user gives it).
4. **Livré pour** / recap: fold `X.Y.Z` into the “livré” side.
5. **Reste à implémenter**: remove `X.Y.Z` if listed as still todo.

Do **not** edit other weeks. Do **not** rewrite the whole HTML without need.

## 3. PDF

From repo root:

```bash
node docs/suivi-avancement/generer-pdf.mjs <chemin-du-html-ou-dossier-semaine>
```

If the script fails (PDF locked, no Chrome/Edge, …): **stop**. HTML may already be updated — say so in one line and tell the user how to fix (close the PDF, install Chrome/Edge, rerun the command). Do not invent another print method.

Done when: HTML updated and PDF regenerated (or soft-skip in step 1).

## Not this skill

- Create the week → `ouvrir-semaine-de-travail` (`/os`)
- Commit / push → `commit` (`/c`)
- Finalise / tag / merge → `finaliser-la-version`
