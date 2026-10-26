---
name: initialise-le-repo
description: >-
  Scaffold a new repo around the agents pack: directories, dispatch, Matt
  grill, README plus AGENTS.md and CLAUDE.md templates, then `/c -a -p`
  (allowed on main). Use when the user types `/init` or says « Initialise
  le repo ». Stop if a README already exists. Not « Ouvre la version ».
---

# Initialise the repo

Triggered by **`/init`** or **« Initialise le repo »**. `/` = this skill’s trigger. No hyphen options.

The pack **`agents/`** must already be in the repo. This skill does **not** create it. It scaffolds **around** it, then dispatches skills.

Do **not** `/implement`. Do **not** merge. Do **not** force-push. Git commit / push go through **`commit`** (`/c -a -p`), which may run on **`main`** only because the user message is this skill.

Paths: **`agents/roles.yml`**. After step 2, those paths are the pack layout in `references/roles.yml`.

## 0. Guards

1. `agents/scripts/dispatch.py` is missing → **stop**. The pack is not in this repo.
2. `README.md` already exists → **stop**. Already initialised. Do not overwrite.

## 1. Skeleton (missing paths only)

Create only what is absent. Never overwrite an existing file.

- `docs/dev/feuille-de-route/feuille-de-route-dev.md` — title `# Feuille de route de dev` only
- `docs/dev/feuille-de-route/` and `docs/dev/recherches/` (directories). If missing, copy `references/feuille-de-route/README.md` → `docs/dev/feuille-de-route/README.md` (writing standards for `/afr` / `/cub`).
- `docs/specs/` (directory)
- `docs/adr/` (directory)
- `docs/glossaire.md` — title `# Glossary` only

Copy `agents/scripts/gate-code-review.py` → `.claude/hooks/gate-code-review.py`.

Merge **only** the `hooks` object from `references/settings-hooks.json` into `.claude/settings.json` (create the file if needed). Do **not** add `enabledPlugins` / frontend-design.

Replace `agents/roles.yml` with `references/roles.yml` (pack paths). Do not invent `test-roots`. Do **not** add `suivi-avancement` here — that is step 6.

## 2. Dispatch

```bash
python3 agents/scripts/dispatch.py
python3 agents/scripts/dispatch.py --check
```

If `--check` fails: **stop**. Fix the pack source, dispatch again. Do not hand-edit `.claude/skills/` or `.cursor/skills/`.

## 3. Grill

Call **grill-with-docs**. Topic: what this repo is for, what you will build. Rounds until the tree is empty. **Wait** for shared-understanding confirmation.

Do not write the README until that confirmation.

## 4. README + templates

Write role **`readme`** from the grill (French unless the user-facing docs will be English). What the project is, what you can do, how to start. Not a dump of the interview.

If missing, copy:

- `references/AGENTS.md` → `AGENTS.md`
- `references/CLAUDE.md` → `.claude/CLAUDE.md`

Do not overwrite those two if they already exist.

## 5. SonarQube (o/n)

Ask in French, then **wait**:

> Utilisez-vous SonarQube pour ce projet ? **o/n**

- **n** / **non** → skip this section. `/qg` will stop later until credentials exist.
- **o** / **oui** → ask for **`SONAR_HOST_URL`**, **`SONAR_TOKEN`**, **`SONAR_PROJECT_KEY`**. **Wait.** Do not invent them. Do not echo the token back.

Then, without printing secret values:

1. Upsert those three keys in **`.env`** (create the file if needed). Never `git add` `.env`.
2. If **`.env.example`** has no `SONAR_` keys, append empty placeholders (`SONAR_HOST_URL=`, `SONAR_TOKEN=`, `SONAR_PROJECT_KEY=`). That file may be committed.
3. If `gh` can see a GitHub remote: `gh secret set` for the same three names (`printf '%s' "$value" | gh secret set NAME`). If `gh` fails (no remote, no admin): say so; **`.env` alone** is enough for `/qg` locally.

`/qg`, `/vf`, `/cqg`, and `finaliser-la-version` load `.env`. They do not read GitHub Actions secrets.

## 6. Suivi d’avancement (o/n)

Ask in French, then **wait**:

> Utilisez-vous un suivi d’avancement hebdomadaire (HTML) ? **o/n**

- **n** / **non** → skip. Skills `/os` / `/msa` remain dispatched but Finalise soft-skips when role `suivi-avancement` is absent.
- **o** / **oui** → scaffold (create only what is absent):
  1. `docs/suivi-avancement/` directory
  2. Copy `references/suivi-avancement/README.md` → `docs/suivi-avancement/README.md`
  3. Copy `references/suivi-avancement/template-semaine.html` → `docs/suivi-avancement/template-semaine.html`
  4. Add role **`suivi-avancement`** to `agents/roles.yml`:

     ```yaml
     suivi-avancement:
       paths:
         - docs/suivi-avancement/
     ```

     Place it after `roadmap` (or at the end of `roles:`). Do not invent other roles.

## 7. Documentation Docusaurus + GitHub Pages (o/n)

Ask in French, then **wait**:

> Publier une documentation Docusaurus sur GitHub Pages ? **o/n**

- **n** / **non** → skip. A later `agents/scripts/update-from-pack.sh --with-docs` can add it.
- **o** / **oui** → from the repo root, run the pack helper (same as update/adopter):

  ```bash
  bash agents/scripts/scaffold-docs-site.sh "$(pwd)"
  ```

  That copies `agents/templates/docs-site/`, fills owner/repo from `origin`, adds role **`docs-site`**, stubs under `docs/`, and `.github/workflows/deploy-docs.yml`. Do not invent Moduléo/poste scripts. Remind the user to enable **GitHub Pages → GitHub Actions** after the first push.

Then, **o** or **n**, delete the template copy that came with the pack:

```bash
rm -rf agents/templates
```

The project never reads it again (`update-from-pack.sh --with-docs` reads the template from the pack clone). Leaving it duplicates `docs-site/` for Sonar.

## 8. Commit

Run skill **`commit`** as if the user had typed **`/c -a -p`**. Still never `.env`, `*.db`, `.venv/`, secrets.

If there is no remote, the commit still counts; report a failed push and stop.

Done when `README.md` exists, dispatch `--check` is green, and HEAD has that init commit.

## Not this skill

- Open a version → `ouvrir-la-version`
- Tests → `lancer-tests` (`/t`)
- Quality gate → `quality-gate` (`/qg`)
- Tests then gate → `verifier-la-fiabilite` (`/vf`)
- « Finalise la version » → `finaliser-la-version`
