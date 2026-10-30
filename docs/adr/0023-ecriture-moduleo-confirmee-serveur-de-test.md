# Moduléo s'écrit par deux outils génériques, après confirmation du collaborateur, sur un serveur de test seulement

En 1.5.0 et 1.5.1, la VM ne fait que lire Moduléo : client GET seul, clé de lecture ([ADR-0017](./0017-lecture-moduleo-par-outil.md)), droits recopiés et garde fermé par défaut ([ADR-0018](./0018-droits-moduleo-appliques-par-bbass.md)). La V1.5.2 ([spec 1.5.2](../specs/v1.5.2-ecrire-dans-moduleo-depuis-le-chat.md)) ouvre l'écriture, sur le serveur de test que Kipaware dédie à l'API :

- **toutes les routes d'écriture** du WADL (POST, PUT, DELETE), sauf webhook, envoi de fichier binaire et paramétrage des procédures, classées `fermee` ;
- **deux outils génériques** : `decrire_ecriture_moduleo(route)` donne au modèle les champs et l'exemple de corps de la route (WADL versionné), `ecrire_moduleo(route, paramètres, corps)` **propose** l'écriture sans rien envoyer ;
- une **Carte de confirmation** dans le poste (en noms, différences pour un PUT, fiche entière pour un DELETE), confirmée ou annulée par un bouton traité par la VM, hors du modèle ; elle expire au message suivant ; le client n'envoie qu'après ce clic, une seule fois ;
- un client `ecrire()` distinct de `lire()` (qui reste GET seul), qui n'envoie que si `MODULEO_ECRITURE` est actif **et** si `MODULEO_URL` figure dans une **liste versionnée de serveurs de test** ; une seule config Moduléo par VM ;
- le **garde des droits** s'étend aux routes d'écriture, chacune classée à la main, fermé par défaut ;
- le modèle voit les ids Moduléo dans les fiches (`[id Moduléo <n>]`), pour pouvoir les écrire ; la VM retire ce motif de la réponse affichée et enregistrée ;
- un **Journal des écritures** en base, lu dans l'inspecteur.

Alternatives écartées :
- **Un outil par route ou par domaine** : 86 routes, un catalogue illisible et coûteux en tokens (même raison qu'ADR-0017) ; un serveur MCP Moduléo pourra venir plus tard.
- **Des noms résolus par l'outil d'écriture** (le modèle ne voit jamais d'id) : un résolveur par champ et par route, intenable pour 86 routes.
- **Une confirmation en texte libre** (« oui » dans le chat) : une instruction cachée dans une page web ou une pièce jointe pourrait la produire.
- **Deux configs Moduléo côte à côte** sur une VM (lecture prod, écriture test) : deux clients, des données mêlées dans une même Conversation.
- **Se fier au réglage seul** pour interdire l'écriture en production : un `.env` mal copié suffirait ; la liste des serveurs de test est une seconde barrière, versionnée.

## Consequences

- Aucune écriture ne peut partir vers le serveur du cabinet : il n'est pas dans la liste, et sa clé reste en lecture seule (deux barrières, comme en 1.5.0). Écrire en production demandera une nouvelle décision.
- Amende ADR-0017 : le client n'est plus « GET seul » partout, seulement `lire()` ; les fiches portent un id, lu par le modèle et jamais affiché.
- Amende ADR-0018 : le classement couvre aussi les routes d'écriture ; un droit retiré entre la proposition et le clic fait refuser l'écriture.
- Un id reformulé par le modèle (« n° 1234 ») n'est pas filtré : risque accepté sur un serveur de test.
- Les groupes et droits du serveur de test ne sont pas connus à l'ouverture : le rattachement du compte de dev s'y adapte aux tests humains.
