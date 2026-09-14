# BBASS Agents IA

Logiciel donnant aux collaborateurs du cabinet BBASS un point d'entrée unique (chat) vers des agents IA métiers, construit sur Mistral AI. La V1 pose le socle (comptes, connexion, appel Mistral) avant que les agents métiers eux-mêmes n'existent.

## Language

**Pôle**:
Un des six domaines métiers du cabinet auxquels le logiciel est destiné (Administration, Appels d'offres, Foncier, DAO, Urbanisme, Détection de réseaux). Chaque compte est rattaché à un seul pôle.
_Avoid_: métier, domaine, agent (l'agent est l'implémentation logicielle qui servira un pôle, pas le pôle lui-même)

**Agent**:
Le système IA destiné à traiter les demandes d'un pôle donné. Non construit en V1 : seule une réponse Mistral générique existe, sans distinction de pôle.
_Avoid_: assistant, bot

**Compte**:
L'identité de connexion d'un collaborateur : un login, rattaché à exactement une agence et un pôle. Créé manuellement en base pour la V1, jamais par auto-inscription.
_Avoid_: utilisateur, profil

**Poste**:
La machine d'un collaborateur, sur laquelle le backend Python et l'interface web sont installés et exécutés localement.
_Avoid_: machine, client, ordinateur

**Agence**:
Un site physique du cabinet BBASS. Castries est la maison mère ; les autres agences sont des satellites.
_Avoid_: site, filiale

**Satellite**:
Une agence autre que Castries. Un satellite ne voit que Castries sur le réseau interne ; Castries voit tous les satellites. Hors périmètre de déploiement de la V1.

**VM centrale**:
La machine hébergée à Castries (pas encore créée) qui porte la base de comptes et l'API exposant l'authentification et le relais Mistral. Accessible en LAN interne uniquement pour la V1.
_Avoid_: serveur, backend central (le backend s'exécute sur le poste, pas sur la VM)

**Relais Mistral**:
Le service de la VM centrale qui détient seul la clé API Mistral et transmet les appels des postes vers Mistral. Un poste n'appelle jamais Mistral directement.
_Avoid_: proxy, passerelle

**Session**:
L'état de connexion d'un compte sur un poste. Persiste tant que la session Windows du collaborateur reste ouverte ; se termine par une déconnexion explicite, jamais par expiration automatique en V1.
