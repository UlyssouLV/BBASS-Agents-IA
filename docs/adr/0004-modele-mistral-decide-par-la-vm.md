# Modèle Mistral décidé par la VM centrale, jamais paramétrable depuis le poste

Le message envoyé par le poste au [relais](./0002-relais-central-mistral.md) ne porte aucun paramètre de modèle : l'endpoint `/relais` de la VM centrale n'accepte qu'un message, jamais un nom de modèle Mistral. Le modèle appelé (`mistral-small-latest` pour la V1, figé à `mistral-small-2603` dans une fiche de modèle depuis la [1.4.2](../specs/v1.4.2-contexte-en-vrais-tokens.md)) est fixé dans le code de la VM centrale. On a écarté un paramètre de modèle transmis par le poste pour ne pas laisser un poste choisir librement un modèle plus coûteux : la VM centrale est déjà seule dépositaire de la clé API ([ADR-0002](./0002-relais-central-mistral.md)) précisément pour garder la maîtrise des coûts et de l'usage Mistral à un seul endroit ; un paramètre de modèle libre côté poste romprait cette maîtrise de la même façon qu'exposer la clé le ferait.

## Consequences

Une évolution future vers un choix de modèle depuis le poste devra rester un choix contraint, jamais un nom de modèle Mistral libre : le poste sélectionnerait un profil parmi une liste fermée (par ex. « rapide » / « efficace »), et la VM centrale resterait seule responsable de faire correspondre chaque profil à un modèle Mistral réel. Voir [#6](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/6) pour cette évolution.
