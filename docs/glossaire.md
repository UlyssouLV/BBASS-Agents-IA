# Glossaire

Vocabulaire du projet. Une seule source pour les agents, le code-review et le site de documentation. Les termes soulignés en pointillés dans les fiches renvoient ici.

## Pôle {#pole}

Un des six domaines métiers du cabinet auxquels le logiciel est destiné (Administration, Appels d'offres, Foncier, DAO, Urbanisme, Détection de réseaux). Un compte peut être rattaché à un ou plusieurs pôles ([ADR-0006](./adr/0006-compte-rattache-plusieurs-poles.md)). Le pôle « Administration » est une valeur de pôle ordinaire, sans lien avec le droit de compte administrateur.

À éviter : métier, domaine, agent (l'agent est l'implémentation logicielle qui servira un pôle, pas le pôle lui-même).

## Agent {#agent}

Le système IA destiné à traiter les demandes d'un pôle donné. Non construit en V1 : seule une réponse générique du modèle existe, sans distinction de pôle.

À éviter : assistant, bot.

## Compte {#compte}

L'identité de connexion d'un collaborateur : un login, un prénom et un nom (obligatoires, affichés dans l'interface), rattaché à exactement une agence et à un ou plusieurs pôles ([ADR-0006](./adr/0006-compte-rattache-plusieurs-poles.md)). Un email est optionnel. Créé et modifié par un compte administrateur ; le tout premier compte administrateur reste créé manuellement en base, comme tous les comptes en V1. Jamais par auto-inscription.

À éviter : utilisateur, profil.

## Compte administrateur {#compte-administrateur}

Un compte portant, en plus de son identité de connexion normale, le droit de créer, modifier, supprimer n'importe quel compte, promouvoir ou rétrograder un autre compte administrateur, et forcer la déconnexion d'un compte. Un droit global, jamais limité à un pôle ou une agence ([ADR-0005](./adr/0005-compte-administrateur-droit-global.md)). Distinct de la Clé d'administration VM, que ce compte doit en plus fournir pour supprimer un compte ou promouvoir/rétrograder un autre compte administrateur.

À éviter : admin (seul, ambigu avec la Clé d'administration VM), rôle.

## Poste {#poste}

La machine d'un collaborateur, sur laquelle le backend Python et l'interface web sont installés et exécutés localement.

À éviter : machine, client, ordinateur.

## Agence {#agence}

Un site physique du cabinet BBASS. Castries est la maison mère ; les autres agences sont des satellites.

À éviter : site, filiale.

## Satellite {#satellite}

Une agence autre que Castries. Un satellite ne voit que Castries sur le réseau interne ; Castries voit tous les satellites. Hors périmètre de déploiement de la V1.

## VM centrale {#vm-centrale}

La machine hébergée à Castries qui porte la base de comptes et l'API exposant l'authentification et le relais vers le fournisseur de modèle. Accessible en LAN interne uniquement pour la V1.

À éviter : serveur, backend central (le backend s'exécute sur le poste, pas sur la VM).

## Relais Mistral {#relais-mistral}

Le service de la VM centrale qui détient seul la clé API du fournisseur (aujourd'hui Mistral) et transmet les appels des postes. Un poste n'appelle jamais le fournisseur directement.

À éviter : proxy, passerelle.

## Clé d'administration VM {#cle-d-administration-vm}

Un secret partagé, distinct du mot de passe de tout compte, qui autorise les actions les plus sensibles de la VM centrale : la révocation forcée de tous les jetons d'un compte, la suppression d'un compte ou la promotion/rétrogradation d'un compte administrateur, et le Mode développeur. Saisie depuis le poste au moment de l'action ([ADR-0007](./adr/0007-cle-admin-vm-reutilisee-poste.md)). Connue des comptes administrateurs, pas seulement de l'équipe technique.

À éviter : clé admin (seul, ambigu avec compte administrateur).

## Session {#session}

L'état de connexion d'un compte sur un poste. Persiste au-delà de la fermeture/relance de l'appli et d'un redémarrage complet du poste : l'identifiant et le jeton sont conservés via le gestionnaire d'identifiants Windows (chiffré, lié au compte Windows courant) côté poste, et le jeton est lui-même persisté côté VM centrale. Se termine par une déconnexion explicite depuis le poste ou par une déconnexion forcée déclenchée côté VM ; jamais par expiration automatique en V1. Si le gestionnaire d'identifiants Windows est indisponible, le poste dégrade silencieusement vers une session en mémoire pour la durée du processus.

À éviter : session applicative limitée au process (ancien comportement, remplacé).

## Conversation {#conversation}

Un fil d'échanges avec l'IA rattaché à un compte, nommé automatiquement à partir de son premier message. Un compte peut avoir plusieurs conversations. Persistée par la VM centrale ([ADR-0008](./adr/0008-postgresql-vm-centrale.md)). Strictement privée à son compte : ni un autre compte ni un compte administrateur n'y accède, sauf via le Mode développeur ([ADR-0012](./adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)).

À éviter : fil, thread, session de chat (Session a déjà un sens différent).

## Profil de travail {#profil-de-travail}

Un résumé synthétique par compte de sa façon de travailler, construit au fil de ses conversations pour donner à l'IA un contexte sur qui lui parle. Distinct de l'historique d'une conversation donnée. Ne porte jamais de fait d'identité (prénom, nom, pôle, agence). Fondé sur les seuls messages du compte ; réécrit en entier à chaque mise à jour. Consultable en lecture seule par le compte concerné.

À éviter : mémoire (ambigu avec le résumé propre à chaque conversation), profil utilisateur.

## Pièce jointe {#piece-jointe}

Un fichier (PDF, Word, Excel ou image) joint par un collaborateur à un message d'une Conversation ([ADR-0009](./adr/0009-pieces-jointes-jamais-mistral-files-api.md)). Le fichier original est stocké sur la VM centrale (jamais chez le fournisseur) ; son contenu est extrait avant tout envoi au modèle. Strictement privée à la conversation qui la porte. Une seule par message pour cette version.

À éviter : document, fichier (seul), attachment.

## Consommation {#consommation}

Un enregistrement d'un appel au modèle effectué pour le compte d'un collaborateur — tokens ou pages traitées, modèle utilisé, coût figé au tarif du jour, date. Rattachée à une Conversation quand applicable, mais conservée même si celle-ci est supprimée. Consultable par le compte concerné et, de façon agrégée par compte seulement, par un compte administrateur.

À éviter : usage, coût (un attribut de la Consommation, pas le concept lui-même).

## Mode développeur {#mode-developpeur}

Un mode d'accès technique du poste, déclenché par un raccourci clavier depuis n'importe quel compte connecté, débloqué par la Clé d'administration VM plutôt que par un droit de compte ([ADR-0012](./adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)). Donne accès à l'inspecteur des échanges, outil de débogage, pas un écran métier.

À éviter : mode admin, mode debug.

## Échange {#echange}

Une étape d'un tour capturée pour le Mode développeur. D'origine **fournisseur** : un appel réel au modèle, avec le payload exact envoyé et la réponse brute reçue (ou le statut d'échec). D'origine **locale** : l'exécution d'un Outil par la VM ou le passage des garde-fous. Distinct d'un message visible dans le chat et d'une ligne de Consommation.

À éviter : appel (seul, trop vague), tour (un tour de chat peut produire plusieurs échanges).

## Garde-fou {#garde-fou}

Une correction appliquée par la VM centrale à ce que le modèle produit malgré sa consigne (ex. retirer une URL non autorisée, ou un chiffre absent des sources). Tous regroupés dans `vm-centrale/src/vm_centrale/garde_fous/`. Ne remplace pas la consigne : il garantit ce qu'elle seule ne garantit pas.

À éviter : filtre, sanitizer.

## Outil {#outil}

Une capacité que le modèle de chat **décide lui-même** d'appeler (tool calling), et que la VM centrale exécute pour lui avant de lui renvoyer le résultat. Tous regroupés dans `vm-centrale/src/vm_centrale/outils/`. Proposés seulement sur l'appel de chat principal.

À éviter : calling tool, fonction (ambigu avec le code), outil pour une Étape de traitement.

## Étape de traitement {#etape-de-traitement}

Un traitement que la VM centrale impose à chaque tour, sans que le modèle le demande (ex. extraction du contenu d'une Pièce jointe à l'envoi, Garde-fou sur la réponse). Ce n'est pas un Outil.

À éviter : outil, tool.

## Recherche web {#recherche-web}

L'Outil `rechercher_web` : la VM interroge un moteur de recherche auto-hébergé (SearXNG, [ADR-0013](./adr/0013-recherche-web-searxng-auto-heberge.md)), télécharge et nettoie les pages trouvées, puis les fait passer par un Appel d'extraction avant de renvoyer le résultat au modèle. Seule la requête sort vers les moteurs amont.

À éviter : web search (outil intégré écarté), scraping.

## Appel d'extraction {#appel-d-extraction}

L'appel au modèle interne à une Recherche web qui reçoit seulement le besoin exprimé par le modèle et les pages nettoyées, jamais le contexte de la Conversation, et en extrait ce qui répond ([ADR-0014](./adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)). Compté en Consommation (`extraction_web`). Son texte n'est jamais une source des Garde-fous.

À éviter : résumé (ambigu avec le résumé glissant), synthèse.

## Mémoire de la conversation {#memoire-de-la-conversation}

La liste, recalculée par la VM centrale et envoyée au modèle à chaque appel de chat principal, de tout ce qui a été partagé dans une Conversation : Pièces jointes, Recherches web, URL écrites par le compte, Lectures d'outil (avec leur date), chacune avec ses Questions couvertes. Distincte du résumé glissant : jamais réécrite par un modèle. Propre à sa Conversation et supprimée avec elle.

À éviter : mémoire (seul), historique.

## Question couverte {#question-couverte}

Une question à laquelle une Pièce jointe, une page lue ou une Lecture d'outil répond, enregistrée avec sa réponse courte et sa source (nom de fichier, URL ou référence de la fiche). Écrite par un modèle, ou par script à partir des champs d'une Fiche Moduléo : jamais une source des Garde-fous.

À éviter : FAQ, index, résumé.

## Fiche de modèle {#fiche-de-modele}

Tout ce qui dépend d'un modèle, regroupé à un seul endroit de la VM centrale : sa fenêtre de contexte en tokens, son fichier tokenizer, ses tarifs. Le modèle est désigné par un nom figé (jamais un alias mobile `-latest` pour le chat) : en changer, c'est changer sa fiche en entier, dans un commit.

À éviter : configuration du modèle (le `.env` ne la porte pas), alias.

## Jauge de contexte {#jauge-de-contexte}

Le cercle, sous le champ de saisie du Poste, qui montre ce que pesait le dernier envoi au modèle principal d'une Conversation : tokens envoyés sur la fenêtre de contexte du modèle. Orange à partir de 80 %.

À éviter : usage, consommation (le coût, pas le remplissage), mémoire.

## Cache des pages web {#cache-des-pages-web}

Le texte nettoyé et le titre des pages web lues avec succès, gardés 24 h par la VM centrale et partagés entre tous les comptes ([ADR-0015](./adr/0015-cache-commun-des-pages-web.md)). Clé : l'URL exacte. Sert au premier téléchargement d'une URL dans une Conversation ; jamais un échec, jamais un extrait ni une Question couverte.

À éviter : mémoire (c'est la Mémoire de la conversation), historique, copie (la copie est celle de la Conversation).

## Relecture forcée {#relecture-forcee}

Le nouveau téléchargement d'une page déjà lue dans une Conversation, demandé par le collaborateur parce qu'elle a changé (`lire_pages_web` avec `retelecharger`). Contourne le Cache des pages web, remplace la copie de la Conversation et revérifie ses Questions couvertes.

À éviter : rafraîchissement, actualisation.

## Statut du tour {#statut-du-tour}

L'étape en cours d'un tour de chat, publiée en direct par la VM centrale et affichée dans le fil à la place de « Réflexion… » (« Recherche sur le web : “…” », « Lecture de &lt;domaine&gt; », « Relecture de &lt;fichier&gt; »…). Une étape à la fois, jamais persistée ni visible dans l'inspecteur ([ADR-0016](./adr/0016-envoi-de-message-en-flux-sse.md)).

À éviter : progression, log, raisonnement (le modèle ne montre pas sa réflexion).

## Moduléo {#moduleo}

Le logiciel métier du cabinet (affaires, contacts, planning, GED…), édité par Kipaware. La VM centrale le lit par son API, en lecture seule, avec une seule clé dédiée à BBASS ([ADR-0017](./adr/0017-lecture-moduleo-par-outil.md)).

À éviter : Agent Moduléo (Moduléo est lu par des Outils communs, pas par un Agent), Cogeo (un module de Moduléo).

## Fiche Moduléo {#fiche-moduleo}

Le texte dense qu'un Outil Moduléo renvoie au modèle pour une affaire ou un contact : champs utiles, ids résolus en noms (client, responsable, intervenants, commune). Jamais la réponse brute de l'API.

À éviter : résultat, JSON, enregistrement.

## Lecture d'outil {#lecture-d-outil}

Ce qu'un Outil a lu dans un logiciel pour une Conversation (en 1.5.0 : une Fiche Moduléo), enregistré avec l'outil, une référence (« affaire 2024-123 ») et sa date. Source des Garde-fous sur toute la Conversation, citée dans la ligne « Sources : ». Jamais partagée entre Conversations. Les pages web gardent leur propre enregistrement (Recherche web).

À éviter : cache, appel, échange (l'Échange est celui de l'inspecteur).
