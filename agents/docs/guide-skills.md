# Guide des skills

À coller (ou dire) à Cursor ou Claude Code. Une ligne de **commande**, des **options** si besoin, puis éventuellement un **corps** (le reste du message).

`meta/` = fonctions primaires. `process/` = recettes qui s’appellent entre elles.

---

## Meta

### Créer un skill

**Commande :** `/cs`

**Options :** aucune.

**Corps :** ce que le skill doit faire, quand il se déclenche, `meta` ou `process` si tu le sais déjà.

Écrit un `SKILL.md` sous `agents/skills/`, le copie vers `.claude/skills/` et `.cursor/skills/`, et ajoute l’entrée dans `agents/docs/guide-skills.md`. Équivalent : « crée un skill ».

**Exemple :**

```
/cs
Un skill qui propose un message de lint après un pytest rouge.
Trigger : « explique l'échec des tests ». Meta.
```

### Message de commit

**Commande :** `/mc`

**Options :** `/d` — ajoute un corps (description) au message.

**Corps :** inutile ; le skill lit le diff `HEAD` ↔ working tree.

Propose un **titre** de commit (français, le pourquoi). Ne commit pas. Avec `/d` : trois blocs copiables (titre ; description ; titre + ligne vide + description). Équivalent : « trouve un message de commit ».

**Exemple :**

```
/mc
```

```
/mc /d
```

---

## Process

### Commit

**Commande :** `/c`

**Options :** `/a` — tout le working tree, pas seulement l’index. `/p` — push après le commit. `/p /f` — `--force-with-lease` après confirmation **oui** au message suivant.

**Corps :** inutile ; le skill relit le diff via `/mc /d` (bloc 3 = message).

Commit sur la branche courante (HEAD ↔ working tree). Défaut = fichiers déjà stagés. Refuse `main` / `master`. Secrets exclus. Équivalent process : skill `commit`.

**Exemple :**

```
/c
```

```
/c /a /p
```

```
/c /p /f
```

### Ouvrir la version

**Commande :** `Ouvre la version`

**Options :** semver obligatoire `X.Y.Z` (ex. `1.3.0`).

**Corps :** seulement si la version n’est pas déjà dans `docs/suivi-avancement/feuille-de-route-dev.md` — à quoi elle sert (un job).

Grill + spec + branche + tickets + PR, puis propose le premier `/implement`. Skill `ouvrir-la-version`.

**Exemple :**

```
Ouvre la version 1.3.0
```

### Encadrer `/implement`

**Commande :** `/implement #<n>`

**Options :** le numéro d’issue enfant GitHub.

**Corps :** inutile en général (le ticket suffit).

TDD du ticket (plugin Matt). La **fin** (tests verts → commit, push, fermer l’enfant) est le skill `encadrer-implement`. Ne pas l’appeler à la place de `/implement`.

**Exemple :**

```
/implement #42
```

### Finaliser la version

**Commande :** `Finalise la version`

**Options :** aucune.

**Corps :** inutile.

Release GitHub, squash-merge dans `main`, suppression de la branche. Tous les enfants du PR doivent être Closed. Skill `finaliser-la-version`.

**Exemple :**

```
Finalise la version
```
