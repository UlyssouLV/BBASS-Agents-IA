# Guide des skills

À coller (ou dire) à Cursor ou Claude Code. Une ligne de **commande**, des **options** si besoin, puis éventuellement un **corps** (le reste du message).

`/` = commande (un skill). `-` = option de cette commande (`/c -a -p`, pas `/c /a /p`).

`meta/` = fonctions primaires. `process/` = recettes qui s’appellent entre elles.

---

## Meta

### Créer un skill

**Commande :** `/cs`

**Options :** aucune.

**Corps :** ce que le skill doit faire, quand il se déclenche, `meta` ou `process` si tu le sais déjà.

Écrit un `SKILL.md` sous `agents/skills/` **après confirmation** (même sans grill), le copie vers `.claude/skills/` et `.cursor/skills/`, et ajoute l’entrée dans `agents/docs/guide-skills.md`. Équivalent : « crée un skill ».

**Exemple :**

```
/cs
Un skill qui propose un message de lint après un pytest rouge.
Trigger : « explique l'échec des tests ». Meta.
```

### Créer un hook

**Commande :** `/ch`

**Options :** aucune.

**Corps :** quand le hook doit tirer, ce qu’il bloque ou laisse passer.

Grill si besoin, **décrit le hook et attend un oui**, puis écrit `agents/hooks/<nom>/`, câble Claude **et** Cursor, et ajoute l’entrée dans `agents/docs/guide-hooks.md`. Équivalent : « crée un hook ».

**Exemple :**

```
/ch
Bloquer /code-review sauf si l’utilisateur l’a demandé, ou Finalise la version.
```

### Message de commit

**Commande :** `/mc`

**Options :** `-d` — ajoute un corps (description) au message.

**Corps :** inutile ; le skill lit le diff `HEAD` ↔ working tree.

Propose un **titre** de commit (français, le pourquoi). Ne commit pas. Avec `-d` : trois blocs copiables (titre ; description ; titre + ligne vide + description). Équivalent : « trouve un message de commit ».

**Exemple :**

```
/mc
```

```
/mc -d
```



### Lister les skills

**Commande :** `/sl`

**Options :** aucune.

**Corps :** inutile ; le skill scanne `agents/skills/`, `.claude/skills/` et `.cursor/skills/`.

Tableau : chaque skill, bucket `meta`/`process` s’il est sous `agents/`, présence Claude / Cursor. Liste les écarts (adaptateur seul, source sans copie). Équivalent : « récapitule les skills ».

**Exemple :**

```
/sl
```

### Lancer les tests

**Commande :** `/t`

**Options :** aucune.

**Corps :** inutile ; le skill choisit les dossiers du rôle **`test-roots`** selon le diff.

Détecte le runner par racine (pytest + venv, sinon `npm test`). Inconnu → stop. Extra Tests : rôle **`agent-adapter`**. Échec → stop. Équivalent : « lance les tests ».

**Exemple :**

```
/t
```

### Quality gate

**Commande :** `/qg`

**Options :** `-w` attend que l’analyse CI du SHA `HEAD` apparaisse (jusqu’à 15 min).

**Corps :** inutile ; le skill lit le Quality Gate Sonar du SHA `HEAD`.

Lecture seule (`SONAR_HOST_URL`, `SONAR_TOKEN`, `SONAR_PROJECT_KEY` dans `.env`). Gate pas `OK` → stop. Ne corrige pas. Équivalent : « vérifie le quality gate ».

**Exemple :**

```
/qg
```

### Ouvrir une branche

**Commande :** `/ob`

**Options :** aucune.

**Corps :** le nom de la branche. S’il manque, le skill demande et attend.

Crée et checkout la branche depuis `origin/main`, en emportant le working tree. Pas de commit, pas de push. Stop si le nom existe. Équivalent : « ouvre une branche ».

**Exemple :**

```
/ob v1.3.0-carte
```



### Ouvrir une pull request

**Commande :** `/opr`

**Options :** `-draft` — ouvre un brouillon.

**Corps :** titre + summary / `Fixes` si tu les as ; sinon titre = dernier commit.

Push la branche courante (pas de force) et ouvre un PR vers `main`. Refuse `main`. Équivalent : « ouvre une PR ».

**Exemple :**

```
/opr
```

```
/opr -draft
VX.Y.Z — un job
Fixes #12
Fixes #13
```

### Créer un ticket

**Commande :** `/ct`

**Options :** aucune.

**Corps :** titre + ce que le ticket livre ; `#parent` si besoin ; éventuellement `Blocked by #n`.

Crée **un** enfant GitHub (`Part of`, sub-issue, parent bloqué par l’enfant). Avant : le ticket tient dans `docs/specs/vX.Y.Z-*.md`. Après : le corps de l’issue parente GitHub = ce fichier ; si une PR ouverte cite déjà le parent, ajoute les `Fixes #n` manquants. Pas de nouvelle PR. Équivalent : « crée un ticket ». Skill `creer-ticket`.

**Exemple :**

```
/ct #12
Titre : garde-fou chiffres manquants après reverse
Le reverse d’un message avec chiffres doit rejouer le garde-fou avant envoi.
Blocked by #40
```

### Créer un bug

**Commande :** `/cub`

**Options :** aucune.

**Corps :** titre court + constat, reproductibilité, impact, cause probable, à corriger ; métadonnées (version trouvée, contexte, date, priorité). Hors périmètre optionnel.

Crée **une** issue GitHub (`Bug — …`, label `bug`, corps à titres fixes) et l’entrée sous **Plus tard** de la feuille de route (`docs/dev/feuille-de-route/`). Standards : `docs/dev/feuille-de-route/README.md` (jeton `Informations manquantes` si une case manque → bug **incomplet**). Pas de commit. Pas de promo en Prochaine/Ensuite (`/afr`). Équivalents : « crée un bug », « ajoute un bug », « documente un bug ». Skill `creer-un-bug`.

**Exemple :**

```
/cub
Titre : bascule de conversation pendant qu’une réponse est en cours
Constat : le fil affiché ne suit pas la sidebar…
Reproductibilité : envoyer un message, cliquer une autre conversation
Impact : mauvais fil affiché
Cause probable : état React non synchronisé avec la sélection
À corriger : synchroniser le fil même si une requête est en vol
Trouvé dans : 1.4.3
Contexte : test humain
Priorité : avant déploiement postes
```

### Créer une release

**Commande :** `/crel`

**Options :** aucune.

**Corps :** `vX.Y.Z` (ou `X.Y.Z`), éventuellement le purpose.

Crée la GitHub Release **sur le SHA de la branche courante**, pas `main`. Titre `VX.Y.Z — …`. Notes : Pourquoi / Ce qu’on peut faire / Historique (PR + Fixes) / Hors périmètre (ADR sur le tag) — **même format** ; l’historique de commits ne sert qu’à **combler les manques** (feature ou bug absents de la spec/PR), jamais en dump de subjects. Ne retaggue pas. Pas de merge. Équivalent : « crée une release ».

**Exemple :**

```
/crel v1.3.0
```

### Fusionner le PR

**Commande :** `/mpr`

**Options :** aucune.

**Corps :** inutile.

Squash-merge du PR de la branche courante dans `main`, suppression de la branche. Ne déplace pas le tag de release. Équivalent : « fusionne le PR ».

**Exemple :**

```
/mpr
```

---



## Process

### Initialise le repo

**Commande :** `/init` ou `Initialise le repo`

**Options :** aucune.

**Corps :** inutile ; le skill grille à quoi sert le repo.

Crée le squelette (`docs/dev/`, specs, ADR, `CONTEXT.md`), dispatch, grill, README + modèles, demande Sonar **o/n** (`.env` + `gh secret set` si oui), commit `/c -a -p` (y compris sur `main`). Stop si un README existe déjà. Skill `initialise-le-repo`.

**Exemple :**

```
/init
```

```
Initialise le repo
```

### Vérifie la fiabilité du code

**Commande :** `/vf` ou `Vérifie la fiabilité du code`

**Options :** aucune.

**Corps :** inutile.

Lance **`/t`** puis **`/qg`**. Premier échec → stop. Ne corrige pas le gate. Skill `verifier-la-fiabilite`.

**Exemple :**

```
/vf
```

```
Vérifie la fiabilité du code
```

### Corriger le quality gate

**Commande :** `/cqg` ou `Corriger le quality gate`

**Options :** aucune.

**Corps :** inutile.

Lit **`/qg`**, corrige ce que le gate exige, relit **`/qg`** une fois. Pas de boucle. Skill `corriger-quality-gate`.

**Exemple :**

```
/cqg
```

### Commit

**Commande :** `/c`

**Options :** `-a` — tout le working tree, pas seulement l’index. `-p` — push après le commit. `-p -f` — `--force-with-lease` après confirmation **oui** au message suivant.

**Corps :** inutile ; le skill relit le diff via `/mc -d` (bloc 3 = message).

Commit sur la branche courante (HEAD ↔ working tree). Défaut = fichiers déjà stagés. Refuse `main` / `master`, **sauf** `/init`. Secrets exclus. Équivalent process : skill `commit`.

**Exemple :**

```
/c
```

```
/c -a -p
```

```
/c -p -f
```

### Fermer un ticket enfant

**Commande :** `/cci`

**Options :** `-t` — lance `/t` d’abord ; échec = pas de close.

**Corps :** `#n` de l’enfant. S’il manque, le skill demande et attend.

Retire `ready-for-agent` et ferme l’issue. Refuse s’il n’y a pas `Part of` / `## Parent` (probable spec). Équivalent : « ferme le ticket enfant ».

**Exemple :**

```
/cci #42
```

```
/cci -t #42
```

### Ouvrir la version

**Commande :** `Ouvre la version`

**Options :** semver obligatoire `X.Y.Z` (ex. `1.3.0`).

**Corps :** seulement si la version n’est pas déjà dans le rôle **`roadmap`** — à quoi elle sert (un job).

Grill + spec, puis **`/ob`**, écriture de la spec, **`/c -a -p`**, tickets (chaque enfant : `Part of`, **sub-issue** GitHub pour le compteur Y/Z du parent, `blocked_by`), **`/opr -draft`**, puis propose le premier `/implement`. Skill `ouvrir-la-version`.

**Exemple :**

```
Ouvre la version 1.3.0
```



### Encadrer `/implement`

**Commande :** `/implement #<n>`

**Options :** le numéro d’issue enfant GitHub.

**Corps :** inutile en général (le ticket suffit).

TDD du ticket (plugin `/implement`). La **fin** : **`/t`**, **`/c -p`**, **`/cci #<n>`**, puis le suivant. Au dernier ticket : tests humains, puis **`/code-review`**, puis **Finalise la version**. Skill `encadrer-implement`. Ne pas l’appeler à la place de `/implement`.

**Exemple :**

```
/implement #42
```



### Finaliser la version

**Commande :** `Finalise la version`

**Options :** aucune.

**Corps :** inutile.

Après une **`/code-review`** acceptée : enfants Closed + docs à jour (`readme`, `roadmap`, **`suivi-avancement`** HTML+PDF de la semaine courante si présent — `/c -a -p` si besoin), puis **`/qg -w`** (puis **`/cqg`** si le gate n’est pas `OK`), puis **`/crel`**, puis **`/mpr`**. Skill `finaliser-la-version`. Ne relance pas `/code-review`.

**Exemple :**

```
Finalise la version
```

