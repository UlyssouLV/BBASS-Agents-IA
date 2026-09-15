# Un compte peut être rattaché à plusieurs pôles

V1 posait qu'un compte est rattaché à exactement un pôle (`CONTEXT.md`, `Compte.pole` en colonne simple). V1.1 rouvre cette décision : un compte peut désormais appartenir à un ou plusieurs des six pôles du cabinet, portés par une relation (table de jointure compte/pôle) plutôt qu'une colonne unique. La liste des six pôles reste une liste fermée fixée dans le code (pas de table `Pôle` gérable dynamiquement pour cette itération) : ce qui change, c'est la cardinalité côté compte, pas la nature des pôles eux-mêmes. On a choisi cette cardinalité pour refléter des collaborateurs couvrant réellement plusieurs domaines, et pour ne pas rouvrir le schéma une troisième fois quand les droits par agent scopés au pôle (prochaine itération envisagée) auront besoin d'une vraie relation d'appartenance. `Agence` reste inchangée : toujours une seule par compte.

## Consequences

Toute lecture ou tout comportement futur qui supposerait un unique pôle par compte (y compris dans un futur routage par agent) doit être conçu pour une liste de pôles, pas une valeur scalaire.
