# V1 — Socle interface, comptes et connexion Mistral (Castries)

## Problem Statement

Les collaborateurs du cabinet BBASS n'ont aujourd'hui aucun moyen d'accéder à un assistant IA. Le cabinet veut leur donner un point d'entrée simple et sûr — un chat — vers les futurs agents métiers, en s'appuyant sur Mistral (choix déjà fait pour des raisons de souveraineté), sans exposer la clé API payante sur chaque poste, et sans construire dès maintenant les agents métiers qui n'existent pas encore.

## Solution

Un logiciel installé et exécuté localement sur chaque poste de l'agence de Castries : un collaborateur se connecte avec son compte, arrive directement sur une fenêtre de chat sobre, et peut envoyer un message qui déclenche un vrai appel à Mistral. Le poste ne détient jamais la clé API : il passe par un relais porté par une VM centrale à Castries, qui détient seule la clé et valide aussi les comptes. Cette itération pose et valide ce socle (comptes, connexion, chat, appel Mistral réel) sans construire les agents métiers eux-mêmes, sans déployer sur les autres agences, et sans mécanisme de mise à jour automatique.

## User Stories

1. En tant que collaborateur de Castries, je veux me connecter avec mon compte, afin que seuls les collaborateurs autorisés puissent utiliser le logiciel.
2. En tant que collaborateur de Castries, je veux que ma connexion soit vérifiée auprès de la base de comptes centrale, afin que l'accès soit contrôlé depuis un seul endroit plutôt que poste par poste.
3. En tant que collaborateur de Castries, je veux rester connecté pendant toute la durée de ma session Windows, afin de ne pas ressaisir mes identifiants à chaque relance de l'appli.
4. En tant que collaborateur de Castries partageant un poste avec des collègues, je veux une option de déconnexion explicite, afin de pouvoir changer de compte sans laisser ma session ouverte pour la personne suivante.
5. En tant que collaborateur de Castries, je veux voir mon nom/mes informations de compte quelque part dans l'interface, afin de savoir quel compte est actif.
6. En tant que collaborateur de Castries, je veux arriver directement sur une fenêtre de chat après connexion, afin de ne pas naviguer dans des menus pour commencer à travailler.
7. En tant que collaborateur de Castries, je veux une fenêtre de chat sobre et professionnelle, afin qu'elle corresponde au ton d'un cabinet de géomètres-experts.
8. En tant que collaborateur de Castries, je veux envoyer un message et voir un état de chargement clair pendant l'attente, afin de savoir que l'appli fonctionne et n'est pas figée.
9. En tant que collaborateur de Castries, je veux que mon message déclenche un vrai appel à Mistral, afin d'obtenir une réponse réellement générée plutôt qu'un texte statique.
10. En tant que collaborateur de Castries, je veux recevoir la réponse de Mistral même si elle est générique/pas encore adaptée à mon métier, afin que la mécanique sous-jacente puisse être validée avant que le comportement spécifique aux agents ne soit construit.
11. En tant que collaborateur de Castries, je veux que l'interface n'affiche aucun sélecteur de pôle ni mention de mon métier, afin que l'écran reste aussi simple qu'une seule fenêtre de chat pour cette itération.
12. En tant que collaborateur de Castries, je veux un message d'erreur clair (pas un plantage) si la VM centrale est injoignable, afin de comprendre pourquoi le chat ne répond pas.
13. En tant que responsable du projet, je veux que le backend local du poste ne détienne jamais la clé API Mistral, afin qu'un poste compromis ou inspecté ne puisse pas divulguer une clé payante partagée.
14. En tant que responsable du projet, je veux que chaque appel à Mistral passe par le relais central de la VM à Castries, afin que la clé API reste à un seul endroit.
15. En tant que responsable du projet, je veux que l'URL du relais soit un paramètre de configuration sur le poste plutôt qu'une valeur en dur, afin qu'une évolution future (ex. clé par agence) n'exige pas de réécrire le backend du poste.
16. En tant que responsable du projet, je veux insérer les comptes directement dans la base centrale, afin que les collaborateurs puissent se connecter sans qu'un écran de gestion des comptes soit nécessaire pour cette itération.
17. En tant que responsable du projet, je veux que chaque compte stocke un champ agence et un champ pôle, afin que le schéma n'ait pas à changer quand un comportement dépendant de l'agence ou du pôle sera construit plus tard.
18. En tant que responsable du projet, je veux que les champs agence et pôle n'aient aucun effet sur le comportement ni sur l'affichage pour cette itération, afin de ne pas construire de logique de routage avant que de vrais agents n'existent.
19. En tant que responsable du projet, je veux que les conversations soient éphémères (non persistées) pour cette itération, afin de ne pas prendre en charge les questions de rétention/confidentialité avant que le socle ne soit validé.
20. En tant que responsable du projet, je veux que la base de comptes et le relais de la VM centrale ne soient joignables qu'en LAN interne (pas d'exposition Internet), afin que le périmètre de cette itération reste limité à Castries.
21. En tant que responsable du projet, je veux redéployer le code mis à jour sur les postes manuellement, afin de ne pas construire de launcher de mise à jour automatique avant que le socle applicatif ne soit éprouvé.
22. En tant que responsable du projet, je veux que le backend local du poste et l'API de la VM centrale soient chacun testables à leur propre frontière HTTP, afin que les tests portent sur un comportement observable réel plutôt que sur des détails internes.
23. En tant que futur mainteneur de ce code, je veux que les ADR existants (backend local par poste, relais central Mistral, périmètre V1 limité à Castries) soient respectés par l'implémentation, afin que l'architecture ne dérive pas silencieusement des décisions documentées.

## Implementation Decisions

- **Poste — backend local (Python)** : s'exécute sur le poste de chaque collaborateur. Sert le front-end (HTML/CSS/JS) et expose trois comportements : connexion (transmet les identifiants à l'endpoint d'authentification de la VM centrale et maintient une session locale pour la durée du processus/de la session Windows), envoi de message (transmet le message du collaborateur à l'endpoint du relais Mistral de la VM centrale et retourne la réponse telle quelle), et déconnexion (efface la session locale). Ne détient ni la clé Mistral, ni les données de comptes.
- **VM centrale — API (Python)** : pas encore provisionnée ; le contrat de l'API doit pouvoir être développé et testé sur un environnement local avant que la VM réelle à Castries n'existe. Expose deux comportements : authentification (vérifie les identifiants d'un compte auprès de la base de comptes et retourne succès/échec ainsi que l'agence et le pôle du compte) et relais Mistral (reçoit un message de chat, appelle l'API de complétion de chat de Mistral avec la seule clé API qu'elle détient, retourne la réponse de Mistral sans modification — aucune logique par pôle).
- **Base de comptes (DB centrale)** : un enregistrement compte par collaborateur, portant au minimum des identifiants, une agence et un pôle. Les comptes sont insérés manuellement (aucun écran de gestion des comptes pour cette itération). Un seul rôle plat pour tous les comptes.
- **Configuration** : le backend local du poste lit l'URL de base de la VM centrale depuis un paramètre de configuration, jamais une valeur en dur (ADR-0002).
- **Accessibilité réseau** : les endpoints d'authentification et de relais de la VM centrale sont exposés en LAN interne uniquement, pas sur Internet (ADR-0003).
- **Session** : l'état de session ne vit que dans le processus du backend local en cours d'exécution ; il n'expire jamais automatiquement — seule une déconnexion explicite l'efface.
- **Front-end** : un seul écran de chat après connexion, avec indicateur de chargement et affichage de l'identité du compte connecté ; aucun sélecteur de pôle/agent nulle part dans l'interface.
- **Gestion des erreurs** : quand le backend local du poste ne peut pas joindre la VM centrale, le front-end doit afficher un état d'erreur clair, sans plantage.
- **Aucune persistance de conversation** pour cette itération.

## Testing Decisions

Les tests portent sur la frontière HTTP propre à chaque service et vérifient des réponses observables, jamais des appels de fonctions internes — le repo est vierge de code, il n'y a donc pas de précédent à suivre ; ces tests fixent la convention pour la suite.

- **API de la VM centrale** : authentification contre une base de comptes de test préremplie (un compte valide réussit et retourne son agence/pôle ; un compte invalide ou inconnu échoue sans révéler quelle partie était fausse) ; relais avec le client Mistral mocké (le message est transmis, la réponse mockée est retournée telle quelle, la clé API n'apparaît jamais dans une réponse ni un message d'erreur).
- **Backend local du poste** (client de la VM centrale mocké) : chemins de succès/échec de la connexion ; le chat est accessible après connexion sans ré-authentification ; la déconnexion révoque l'accès au chat ; la route de chat transmet le message et retourne la réponse mockée du relais ; une erreur de connexion mockée vers la VM centrale se traduit par un état d'erreur propre, jamais un plantage ; le front-end servi ne contient aucun balisage de sélecteur de pôle/agent.

## Out of Scope

- Déploiement sur les agences satellites ; exposition Internet du relais/authentification.
- Agents métiers réels et toute réponse différenciée par pôle.
- Historique de conversation persistant.
- Écran d'administration des comptes.
- Launcher / mise à jour automatique au lancement.
- Répartition multi-clés ou multi-workspace Mistral pour absorber la charge.
- Mode hors-ligne, modèle local, entraînement de modèle.

## Further Notes

- La VM centrale à Castries n'est pas encore créée : l'API centrale doit être développable et testable sur un environnement local avant provisionnement.
- Vocabulaire et décisions d'architecture sous-jacentes : voir `CONTEXT.md` (Poste, Agence, Compte, Pôle, Agent, VM centrale, Relais Mistral, Session) et `docs/adr/0001` à `0003`.
