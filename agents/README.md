# Agents de développement

C’est depuis ce dossier qu’on génère les skills, hooks et le reste de l’outillage des agents de développement. Le résultat est ensuite dispatché de façon cohérente dans les méthodes de travail des différents modèles d’IA (Cursor, Claude Code).

Les conventions de process (tracker, labels, lecture du domaine) sont ici. Chemins et règle d’arrêt si un rôle est irrésolu : [roles.yml](roles.yml). Comment lancer les skills : [docs/guide-skills.md](docs/guide-skills.md). Hooks : [docs/guide-hooks.md](docs/guide-hooks.md).

Skills : `agents/skills/meta/` (fonctions primaires des agents : créer un skill, message de commit, …) et `agents/skills/process/` (recettes qui s’appellent entre elles, ex. cycle de version, `/c`). Nouveau skill : `creer-skill`, puis `python3 agents/scripts/dispatch.py` (copie à plat vers `.claude/skills/` et `.cursor/skills/`).
