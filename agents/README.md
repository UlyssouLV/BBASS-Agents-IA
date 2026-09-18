# agents/

Bac à sable pour **entraîner** le workflow d’agents (relais de session, pont Cursor → Claude Code, hooks partagés). Branche `pipeline-workflow-agents` : pas une version produit.

## Skills = modes opératoires, pas modèles

On configure **un skill par intention** (`encadrer-implement`, `prochaine-etape`). N’importe quel agent du dépôt doit pouvoir le suivre : Cursor, Claude Code, un autre CLI.

Le skill décrit des **actes observables** : `gh`, git, pytest, fichiers. Il ne dit pas « appelle le tool Shell de Cursor » ni « tu es Sonnet ». Le harnais traduit tout seul.

| Où | Quoi |
|---|---|
| `.claude/skills/` | Pack **partagé** (les deux agents le chargent ici) |
| `.cursor/skills/` | **Pont Cursor uniquement** (`lancer-claude` : ouvrir un terminal `claude`) |
| Plugins Claude Code | Runtime (`/implement`), pas à dupliquer dans Cursor |

`lancer-claude` n’est pas un skill métier : c’est un pont harnais, donc il reste sous `.cursor/skills/`.
