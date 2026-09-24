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

**Options :** aucune.

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

### Créer une release

**Commande :** `/crel`

**Options :** aucune.

**Corps :** `vX.Y.Z` (ou `X.Y.Z`), éventuellement le purpose.

Crée la GitHub Release **sur le SHA de la branche courante**, pas `main`. Titre `VX.Y.Z — …`. Notes : Pourquoi / Ce qu’on peut faire / Historique (PR + Fixes) / Hors périmètre (ADR sur le tag). Ne retaggue pas. Pas de merge. Équivalent : « crée une release ».

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

Grill + spec, puis **`/ob`**, écriture de la spec, **`/c -a -p`**, tickets, **`/opr -draft`**, puis propose le premier `/implement`. Skill `ouvrir-la-version`.

**Exemple :**

```
Ouvre la version 1.3.0
```



### Encadrer `/implement`

**Commande :** `/implement #<n>`

**Options :** le numéro d’issue enfant GitHub.

**Corps :** inutile en général (le ticket suffit).

TDD du ticket (plugin `/implement`). La **fin** : **`/t`**, **`/c -p`**, **`/cci #<n>`**, puis le suivant ou **Finalise la version**. Skill `encadrer-implement`. Ne pas l’appeler à la place de `/implement`.

**Exemple :**

```
/implement #42
```



### Finaliser la version

**Commande :** `Finalise la version`

**Options :** aucune.

**Corps :** inutile.

Enfants Closed + docs à jour (`/c -a -p` si besoin), puis **`/crel`**, puis **`/mpr`**. Skill `finaliser-la-version`.

**Exemple :**

```
Finalise la version
```

