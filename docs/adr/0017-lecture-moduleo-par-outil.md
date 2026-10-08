# Moduléo est lu par des outils du modèle, avec un client GET seul et une clé chiffrée

Les affaires, intervenants et contacts du cabinet vivent dans Moduléo ([ADR-0013](./0013-recherche-web-searxng-auto-heberge.md) : « les données clients du cabinet viendront de Moduléo »). La V1.5.0 ([spec 1.5.0](../specs/v1.5.0-lire-moduleo-depuis-le-chat.md)) les rend lisibles depuis le chat :

- le modèle **décide** de lire Moduléo, par deux Outils (`chercher_affaires_moduleo`, `chercher_contacts_moduleo`), comme il décide de chercher sur le web ; pas de workflow n8n, pas un outil par route de l'API ;
- un client HTTP de la VM centrale (`vm_centrale/moduleo/`) couvre toutes les routes **GET** de l'API du cabinet, générées depuis son WADL, et **refuse toute autre méthode** avant envoi ; la clé d'API BBASS est réglée dans Moduléo **en lecture seule** sur ses catégories (Affaire, Contact…, chacune en lecture ou en lecture et écriture) : deux barrières, la clé côté Moduléo et le client côté VM ;
- **une seule clé d'API** dédiée à BBASS et le SecurityCode d'un **utilisateur de test**, pour tous les comptes ; l'utilisateur Moduléo qui lit est donc le même pour tout le monde ;
- les fiches lues partent vers Mistral dans le message `tool` (`chat/completions`, sans rétention côté modèle) et sont enregistrées dans la Conversation (`lectures_outils`), sources des Garde-fous ; aucune copie hors de la Conversation, aucun cache entre Conversations ;
- la clé et le SecurityCode sont **chiffrés** (Fernet) dans la config de la VM ; la clé maître est un fichier séparé, hors du dépôt, dont le chemin est en config. Ni la clé ni le code ne vont au modèle ou à l'inspecteur.

Alternatives écartées :
- **Workflow n8n par question** : un runtime de plus à opérer pour des lectures simples ; n8n viendra pour des enchaînements multi-étapes (1.8.0), en réutilisant ce client.
- **Un outil par route** (207 routes GET) : un catalogue d'outils illisible pour le modèle et coûteux en tokens à chaque appel.
- **Se fier aux seuls droits de la clé** pour interdire l'écriture : une clé mal cochée, ou réglée par quelqu'un d'autre plus tard, ouvrirait l'écriture sans que le code de BBASS le voie ; le client GET seul reste.
- **Une clé par compte BBASS** dès la 1.5.0 : demande une correspondance comptes BBASS / utilisateurs Moduléo et un écran d'affectation ; reporté (« Clés API Moduléo par utilisateur »).
- **Secrets en clair dans `.env`** (comme `MISTRAL_API_KEY`) : Kipaware recommande un stockage chiffré ; un `.env` qui fuit (capture, ticket, sauvegarde) ne doit pas livrer l'accès à Moduléo.
- **Clé maître dans `.env`** : ne protège rien. **Coffre du système** (`keyring`) : dépend de l'OS de la VM, pas encore figé (1.7.0).

## Consequences

- La lecture seule tient à la clé (lecture seule dans Moduléo) et au client (GET seul) : toute écriture future (POST / PUT / DELETE) passe par une nouvelle décision, et par un serveur Moduléo de test.
- Ce que voit le chat est ce que voit l'utilisateur de test dans Moduléo, quel que soit le compte BBASS qui pose la question.
- Sans config Moduléo complète et déchiffrable, les outils Moduléo ne sont pas proposés au modèle ; la VM démarre quand même.
- Perdre la clé maître oblige à rechiffrer les secrets (nouvelle clé d'API ou nouveau code créés dans Moduléo). Une clé maître sur un support amovible (clé USB) est une piste pour la production (1.7.0), au prix d'une VM qui ne lit plus Moduléo si elle redémarre sans elle.
- `MISTRAL_API_KEY` reste en clair jusqu'à une version dédiée.
