---
name: ouvrir-semaine-de-travail
description: >-
  Create the current work-week folder and HTML under docs/suivi-avancement
  (attendus = versions planned this week). Use when the user types `/os`,
  or says « ouvre la semaine de travail », « ouvre la semaine ». Not for
  recording a shipped version (that is `/msa`) and not for Finalise.
---

# Ouvre la semaine de travail

Triggered by **`/os`** or **« ouvre la semaine de travail »**. Creates the lun→ven week folder + HTML from the canonical template. Does **not** commit. Does **not** regenerate a PDF until something is shipped (`/msa`).

Paths: **`agents/roles.yml`**. Convention: **`docs/suivi-avancement/README.md`**.

## 1. Dates

Fuseau **Europe/Paris**. Default: **current** Monday–Friday. If the user gives an explicit range (or a date inside a week), use that week instead.

Folder + file names: README (*Noms*). Month tokens: `jan` `fev` `mar` `avr` `mai` `juin` `juil` `aout` `sept` `oct` `nov` `dec`.

Done when: target folder name `semaine-<lun>-<ven>-<mois>-<année>` is known, and HTML name matches.

## 2. Refuse if it already exists

Under role **`suivi-avancement`**: if that folder exists → **stop**. One line. Do not overwrite. Suggest `/msa` if they meant to update a version.

## 3. Attendus (versions)

Default: read role **`roadmap`** — **Prochaine** + every **Ensuite** (titles + one-line Objectif).  
Override: versions listed in the user message (`/os 1.5.0 1.6.0`) win for the “attendus cette semaine” set; still mention other roadmap items under **Reste à implémenter** if useful.

If attendus came from the roadmap (no explicit list in the prompt): show the proposed list (**VX.Y.Z — titre**) and **wait for oui**. Explicit list in the prompt → no wait.

## 4. Write

1. Copy **`docs/suivi-avancement/template-semaine.html`** →  
   `docs/suivi-avancement/semaine-…/suivi-semaine-….html` (same dates).
2. Fill couverture, TOC, five `.jour` headings (lun→ven), **Reste à implémenter**, **Livré pour** (date du point = jeudi de la semaine unless the user says otherwise), and one `.version` stub per attendu (`id="version-X-Y-Z"`, badge `.prevu`, body = Objectif in functional language).
3. Do **not** invent day bullets for work not done (keep « À compléter. »).
4. Agenda : run `node docs/suivi-avancement/sync-agenda.mjs <dossier-semaine>` (soft-skip if `../Suivi` / Excel missing — README). Do **not** paste a static agenda by hand.
5. Do **not** `git commit`. Do **not** run `generer-pdf.mjs` yet (empty week → PDF optional; skip).

Done when: folder + HTML exist and match the README structure.

## Not this skill

- Ship a version into the HTML/PDF → `mettre-a-jour-suivi-avancement` (`/msa`)
- Finalise / release → `finaliser-la-version`
- Edit the roadmap → `/afr`
