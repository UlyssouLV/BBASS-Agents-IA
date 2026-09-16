# PostgreSQL plutôt que SQLite pour la VM centrale

À partir de la [1.1.1](../specs/v1.1.1-persistance-conversations.md), la VM centrale passe de SQLite (le défaut depuis la V1) à PostgreSQL comme moteur de base de données (`VM_CENTRALE_DATABASE_URL`), pour les comptes, jetons, et désormais les conversations et messages. SQLite sérialise les écritures (un seul rédacteur à la fois) : jusqu'ici sans conséquence avec seulement des tables `Compte`/`Jeton` peu sollicitées en écriture, mais la persistance des conversations introduit une écriture en base à chaque message envoyé par chaque collaborateur connecté, potentiellement en parallèle. Comme la [VM centrale](../../CONTEXT.md) n'est physiquement pas encore créée, ce changement se fait avant qu'il y ait la moindre donnée de production à migrer — le moment le moins coûteux pour ce choix.

## Consequences

Le développement local ne peut plus se contenter d'un fichier SQLite ouvert directement : un PostgreSQL local (conteneur Docker) devient nécessaire pour développer et faire tourner les tests de la VM centrale. La création des tables reste `Base.metadata.create_all` (pas de système de migration introduit par ce changement) : toute base existante doit être recréée, comme à chaque évolution de schéma depuis la V1.
