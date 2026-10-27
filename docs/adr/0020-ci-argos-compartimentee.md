# CI ArgOS : workflows compartimentés, référence tag/Release, pas de commit bot

Jusqu'à la V1.5.x, la CI GitHub Actions mélangeait pytest vm-centrale, pytest poste et le scan SonarCloud dans **un seul job** ([`sonar.yml`](../../.github/workflows/sonar.yml)). Le site de doc déployait sur Pages **et** poussait encore des aperçus README sur `main` via `github-actions[bot]` ([`deploy-docs.yml`](../../.github/workflows/deploy-docs.yml)). La V1.6.0 ([spec](../specs/v1.6.0-ci-versions-verifiees.md)) aligne le dépôt sur le modèle **ArgOS** :

- **un workflow par compartiment** (tests vm, tests poste, build front, build docs, Sonar), avec **path filters** et un chemin **skip→vert** pour que les checks required du ruleset ne restent pas « pending » ;
- **Sonar démarre en premier** (analyse **CI**, pas Automatic Analysis), **sans** attendre les rapports de couverture pytest — les jobs de tests restent la preuve d'exécution ;
- le **dist** front reste **committé** ([ADR-0010](./0010-front-poste-react-typescript-vite.md)) ; la CI **échoue** s'il dérive du résultat de `npm run build` ;
- **référence d'une version** = tag Git + GitHub Release `vX.Y.Z` ; la CI prouve que le SHA est vert ;
- après « Finalise la version », **aucun bot** n'écrit sur `main` : `deploy-docs` = build + Pages seulement ; les aperçus README sont produits sur la **branche de version** (skill `finaliser-la-version`) et entrent dans le squash.

Alternatives écartées :

- **Un seul `ci.yml` monolithique** : plus simple à ouvrir, mais trop lent et opaque (contraire à l'objectif « compartimenter pour gagner du temps »).
- **Attendre la couverture avant Sonar** : retarde le signal qualité ; la couverture pourra revenir plus tard sans changer le découpage des jobs.
- **Arrêter de committer le dist** (artefact CI seulement) : casserait l'install poste sans Node (ADR-0010) — reporté éventuel 1.6.2, pas ici.
- **Registry / Artifactory / images Docker en 1.6.0** : packaging CD et postes = 1.6.1 / 1.6.2.

## Consequences

- Les workflows CI de la 1.6.0 entrent dans le **squash** de la version (pas de commit bot après Finalise).
- Un **ruleset** GitHub doit exiger le squash-merge et les checks des compartiments (voir guide ci-dessous).
- `sonar-project.properties` ne doit plus exiger des `coverage-*.xml` absents au moment du scan.
- `/qg` continue de lire le quality gate Sonar via l'API ; inchangé.

## Guide — ruleset GitHub (squash-merge + checks)

Geste **humain** (admin du dépôt). Pas d'issue dédiée.

1. Ouvre le dépôt sur GitHub → **Settings** → **Rules** → **Rulesets** → **New branch ruleset** (ou édite celui qui cible `main`).
2. **Enforcement status** : Active. **Target branches** : `main` (ou « Default » / include `refs/heads/main`).
3. **Restrict deletions** / **Block force pushes** : activés (recommandé).
4. **Require a pull request before merging** : activé ; autoriser seulement **Squash** comme méthode de merge (désactiver merge commit et rebase si l'UI le permet, ou n'autoriser que squash).
5. **Require status checks to pass** : activé. Ajouter les checks dont les noms correspondent aux **jobs** des workflows 1.6.0, typiquement :
   - le job Sonar (ex. `SonarQube Cloud` / nom exact affiché sur une PR) ;
   - `tests-vm-centrale` (ou le nom du job dans `tests-vm-centrale.yml`) ;
   - `tests-poste` ;
   - `build-front` ;
   - `build-docs`.
6. Vérifier sur une PR dont certains paths ne matchent pas : les jobs skippés doivent apparaître **verts** (pattern skip→vert), sinon le merge reste bloqué.
7. Sauver le ruleset. Tester en ouvrant une PR draft : sans checks verts (ou skip verts), le squash doit être refusé.

Les noms exacts des checks se lisent dans l'onglet **Checks** d'une PR après le premier push des workflows 1.6.0.

## Guide — SonarCloud CI-only (pas Automatic Analysis)

1. Ouvre [SonarCloud](https://sonarcloud.io) → organisation `ulyssoulv` → projet `UlyssouLV_BBASS-Agents-IA`.
2. **Administration** (ou **Project Settings**) → **Analysis Method** / **Automatic Analysis**.
3. Si **Automatic Analysis** est activée : **désactive-la**. L'analyse doit venir uniquement du workflow GitHub Actions (`SONAR_TOKEN`).
4. Confirme qu'une PR déclenche bien un scan via Actions et que `/qg` retrouve l'analyse du SHA.
