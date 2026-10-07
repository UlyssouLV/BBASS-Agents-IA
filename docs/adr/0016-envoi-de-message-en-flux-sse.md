# L'envoi d'un message répond en flux SSE, le tour s'exécute à part

Jusqu'à la V1.4.3, `POST /conversations` et `POST /conversations/{id}/messages` (VM centrale et Poste) répondent un JSON en fin de tour. Un tour peut enchaîner plusieurs appels principaux, des recherches web, des pages lues et des pièces jointes relues : le Poste n'affiche que « Réflexion… ». La V1.4.4 ([spec 1.4.4](../specs/v1.4.4-statut-attente-dynamique.md)) affiche le Statut du tour en direct :

- les deux routes répondent toujours en `text/event-stream` : des événements `statut`, puis `fin` (le JSON d'avant) ou `erreur` (mêmes code et détail qu'avant) ;
- les refus d'avant le début du tour (401, 404, 400, 422) restent de vrais statuts HTTP ;
- le Poste relaie le flux de la VM tel quel ;
- le tour s'exécute dans un thread de la VM qui publie ses statuts dans une file ; le flux ne fait que lire cette file, et le tour va au bout même si personne ne la lit plus ;
- le texte de la réponse n'est pas streamé : il arrive entier dans `fin`, après les garde-fous.

Alternatives écartées :
- **Polling d'un statut** (`GET` toutes les 500 ms) : état partagé en mémoire par conversation, décalage, requêtes en plus.
- **WebSocket** : canal bidirectionnel pour un flux descendant, plus de plomberie à travers le Poste.
- **SSE seulement sur `Accept: text/event-stream`** : deux contrats à maintenir et à tester.
- **Streaming des tokens de la réponse** : les garde-fous (URL, chiffres, sources, pages trop longues) retirent ou ajoutent du texte sur la réponse complète ; un texte déjà affiché ne peut plus être corrigé.
- **Tour lié à la vie du flux** (générateur qui exécute le tour) : un onglet fermé abandonnerait un tour en partie payé, sans rien enregistrer.

## Consequences

- Tout client des deux routes (Poste, tests) lit un flux et prend l'événement `fin`.
- Un tour commencé s'enregistre même si le navigateur coupe le flux ; il se retrouve en rouvrant la Conversation, pas en direct.
- Un rejeu avec la même `cle_idempotence` reçoit un flux qui ne contient que `fin`.
- Les statuts sont éphémères : ni base, ni inspecteur.
