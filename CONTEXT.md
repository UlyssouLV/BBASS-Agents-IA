# BBASS Agents IA

Logiciel donnant aux collaborateurs du cabinet BBASS un point d'entrée unique (chat) vers des agents IA métiers, construit sur Mistral AI. La V1 pose le socle (comptes, connexion, appel Mistral) avant que les agents métiers eux-mêmes n'existent.

## Language

**Pôle**:
Un des six domaines métiers du cabinet auxquels le logiciel est destiné (Administration, Appels d'offres, Foncier, DAO, Urbanisme, Détection de réseaux). Un compte peut être rattaché à un ou plusieurs pôles ([[0006-compte-rattache-plusieurs-poles]]). Le pôle « Administration » est une valeur de pôle ordinaire, sans lien avec le droit de compte administrateur.
_Avoid_: métier, domaine, agent (l'agent est l'implémentation logicielle qui servira un pôle, pas le pôle lui-même)

**Agent**:
Le système IA destiné à traiter les demandes d'un pôle donné. Non construit en V1 : seule une réponse Mistral générique existe, sans distinction de pôle.
_Avoid_: assistant, bot

**Compte**:
L'identité de connexion d'un collaborateur : un login, un prénom et un nom (obligatoires, affichés dans l'interface), rattaché à exactement une agence et à un ou plusieurs pôles ([[0006-compte-rattache-plusieurs-poles]]). Un email est optionnel. Créé et modifié par un compte administrateur ; le tout premier compte administrateur reste créé manuellement en base, comme tous les comptes en V1. Jamais par auto-inscription.
_Avoid_: utilisateur, profil

**Compte administrateur**:
Un compte portant, en plus de son identité de connexion normale, le droit de créer, modifier, supprimer n'importe quel compte, promouvoir ou rétrograder un autre compte administrateur, et forcer la déconnexion d'un compte. Un droit global, jamais limité à un pôle ou une agence ([[0005-compte-administrateur-droit-global]]). Distinct de la Clé d'administration VM, que ce compte doit en plus fournir pour supprimer un compte ou promouvoir/rétrograder un autre compte administrateur.
_Avoid_: admin (seul, ambigu avec la Clé d'administration VM), rôle

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

**Clé d'administration VM**:
Un secret partagé, distinct du mot de passe de tout compte, qui autorise les actions les plus sensibles de la VM centrale : la révocation forcée de tous les jetons d'un compte, et la suppression d'un compte ou la promotion/rétrogradation d'un compte administrateur, saisie depuis le poste au moment de l'action ([[0007-cle-admin-vm-reutilisee-poste]]). Connue des comptes administrateurs, pas seulement de l'équipe technique.
_Avoid_: clé admin (seul, ambigu avec compte administrateur)

**Session**:
L'état de connexion d'un compte sur un poste. Persiste au-delà de la fermeture/relance de l'appli et d'un redémarrage complet du poste : l'identifiant et le jeton sont conservés via le gestionnaire d'identifiants Windows (chiffré, lié au compte Windows courant) côté poste, et le jeton est lui-même persisté côté VM centrale (survit à un redémarrage de la VM). Se termine par une déconnexion explicite depuis le poste (qui invalide aussi le jeton côté VM) ou par une déconnexion forcée déclenchée côté VM (invalide tous les jetons actifs du compte) ; jamais par expiration automatique en V1. Si le gestionnaire d'identifiants Windows est indisponible, le poste dégrade silencieusement vers une session en mémoire pour la durée du processus.
_Avoid_: session applicative limitée au process (ancien comportement, remplacé)

**Conversation**:
Un fil d'échanges avec l'IA rattaché à un compte, nommé automatiquement à partir de son premier message. Un compte peut avoir plusieurs conversations. Persistée par la VM centrale ([ADR-0008](docs/adr/0008-postgresql-vm-centrale.md)), jamais par le stockage propre de Mistral — voir la Solution de [la spec 1.1.1](docs/specs/v1.1.1-persistance-conversations.md) pour les raisons (confidentialité, isolation entre comptes). Strictement privée à son compte : ni un autre compte ni un compte administrateur n'y accède, sauf via le [Mode développeur](#language) ([ADR-0012](docs/adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)).
_Avoid_: fil, thread, session de chat (Session ci-dessus a déjà un sens différent)

**Profil de travail**:
Un résumé synthétique par compte de sa façon de travailler, construit au fil de ses conversations pour donner à l'IA un contexte sur qui lui parle. Distinct de l'historique d'une conversation donnée. Ne porte jamais de fait d'identité (prénom, nom, pôle, agence) : ceux-ci restent uniquement portés par Compte, jamais réinférés depuis une conversation. Fondé sur les seuls messages du compte, jamais sur les réponses de l'assistant ni sur un trait décrivant l'assistant ; réécrit en entier à chaque mise à jour (jamais empilé), sous un plafond de longueur ([spec 1.3.1](docs/specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md)). Consultable en lecture seule par le compte concerné ; pas par un compte administrateur.
_Avoid_: mémoire (ambigu avec le résumé propre à chaque conversation, voir la spec 1.1.1), profil utilisateur

**Pièce jointe**:
Un fichier (PDF, Word, Excel ou image) joint par un collaborateur à un message d'une [Conversation](#language) ([ADR-0009](docs/adr/0009-pieces-jointes-jamais-mistral-files-api.md), [spec 1.1.2](docs/specs/v1.1.2-pieces-jointes.md)). Le fichier original est stocké sur la VM centrale (jamais chez Mistral, jamais via sa Files API) ; son contenu est extrait avant tout envoi à Mistral (OCR pour un PDF, extraction locale pour Word/Excel, appel vision Mistral pour une image, seul cas sans Zero Data Retention par défaut). Strictement privée à la conversation qui la porte, au même titre que le reste de son contenu : ni un autre compte ni un compte administrateur n'y accède, sauf via le [Mode développeur](#language) ([ADR-0012](docs/adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)). Une seule par message pour cette version.
_Avoid_: document, fichier (seul, ambigu avec le fichier physique sur disque), attachment

**Consommation**:
Un enregistrement d'un appel Mistral effectué pour le compte d'un collaborateur — tokens ou pages traitées selon le type d'appel, modèle utilisé, coût figé au tarif du jour de l'appel, date ([spec 1.1.3](docs/specs/v1.1.3-consommation.md)). Rattachée à une [Conversation](#language) quand applicable, mais conservée même si celle-ci est supprimée (seul le rattachement disparaît, pas la ligne). Consultable par le compte concerné (son propre détail par conversation) et, de façon agrégée par compte seulement (jamais par conversation), par un compte administrateur.
_Avoid_: usage (trop vague, déjà le nom du champ brut renvoyé par Mistral), coût (un attribut de la Consommation, pas le concept lui-même)

**Mode développeur**:
Un mode d'accès technique du poste, déclenché par un raccourci clavier depuis n'importe quel compte connecté, débloqué par la Clé d'administration VM plutôt que par un droit de compte ([spec 1.3.0](docs/specs/v1.3.0-inspecteur-echanges-modele.md), [ADR-0012](docs/adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)). Donne accès à l'inspecteur des échanges, lui-même outil de débogage, pas un écran métier destiné à l'usage quotidien d'un collaborateur ou d'un compte administrateur.
_Avoid_: mode admin, mode debug (le terme retenu dans le produit est « Mode développeur »)

**Échange**:
Une étape d'un tour capturée pour le Mode développeur ([spec 1.3.0](docs/specs/v1.3.0-inspecteur-echanges-modele.md)). D'origine **Mistral** : un appel Mistral réel, avec le payload exact envoyé et la réponse brute reçue (ou le statut d'échec), pour un type d'appel donné (chat, titrage, résumé+profil, OCR, vision, extraction web). D'origine **locale** depuis la [spec 1.4.0](docs/specs/v1.4.0-recherche-web-dans-le-chat.md) : l'exécution d'un Outil par la VM (entrée, résultats, texte renvoyé au modèle) ou le passage des garde-fous (réponse brute du modèle et réponse visible). Les échanges d'un tour se lisent dans l'ordre chronologique. Distinct d'un Message (le contenu visible dans le chat) et d'une ligne de Consommation (ses métadonnées de facturation) : les trois coexistent pour un même tour sans se dupliquer entre eux.
_Avoid_: appel (seul, trop vague), tour (un tour de chat peut produire plusieurs échanges, ex. tool calling)

**Garde-fou**:
Une correction appliquée par la VM centrale à ce que le modèle produit malgré sa consigne (ex. retirer une URL ni écrite par le compte ni renvoyée par une Recherche web, ou un chiffre absent des messages du compte, des pièces jointes et des pages lues, remplacer par une phrase fixe une réponse chiffrée sans document, plafonner le résumé glissant ou le profil de travail, nettoyer le Markdown d'un titre) ([spec 1.3.1](docs/specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md)). Tous regroupés dans `vm-centrale/src/vm_centrale/garde_fous/`, listés dans son `README.md`. Ne remplace pas la consigne : il garantit ce qu'elle seule ne garantit pas.
_Avoid_: filtre, sanitizer

**Outil**:
Une capacité que le modèle de chat **décide lui-même** d'appeler (tool calling), et que la VM centrale exécute pour lui avant de lui renvoyer le résultat (ex. relire une Pièce jointe sortie de la fenêtre, lancer une Recherche web) ([spec 1.4.0](docs/specs/v1.4.0-recherche-web-dans-le-chat.md)). Tous regroupés dans `vm-centrale/src/vm_centrale/outils/`, listés dans son `README.md`. Proposés seulement sur l'appel de chat principal.
_Avoid_: calling tool, fonction (ambigu avec le code), outil pour une Étape de traitement

**Étape de traitement**:
Un traitement que la VM centrale impose à chaque tour, sans que le modèle le demande (ex. extraction du contenu d'une Pièce jointe à l'envoi, Garde-fou sur la réponse). Ce n'est pas un Outil.
_Avoid_: outil, tool

**Recherche web**:
L'Outil `rechercher_web` : la VM interroge un moteur de recherche auto-hébergé (SearXNG, [ADR-0013](docs/adr/0013-recherche-web-searxng-auto-heberge.md)), télécharge et nettoie les pages trouvées, puis les fait passer par un Appel d'extraction avant de renvoyer le résultat au modèle ([spec 1.4.0](docs/specs/v1.4.0-recherche-web-dans-le-chat.md)). Seule la requête sort vers les moteurs ; les résultats (URL, titre, extrait du moteur, texte nettoyé) sont enregistrés pour la Conversation et supprimés avec elle. Ils servent de source aux Garde-fous.
_Avoid_: web search (outil intégré de l'API Conversations Mistral, écartée), scraping

**Appel d'extraction**:
L'appel Mistral interne à une Recherche web qui reçoit seulement le besoin exprimé par le modèle et les pages nettoyées, jamais le contexte de la Conversation, et en extrait ce qui répond, avec l'URL de chaque information ([ADR-0014](docs/adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)). Compté en Consommation (`extraction_web`). Son texte n'est jamais une source des Garde-fous : il peut lui-même inventer.
_Avoid_: résumé (ambigu avec le résumé glissant), synthèse
