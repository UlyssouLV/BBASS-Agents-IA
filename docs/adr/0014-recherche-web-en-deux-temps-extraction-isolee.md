# La recherche web passe par un appel d'extraction isolé du contexte de la conversation

L'outil `rechercher_web` de la V1.4.0 ([spec 1.4.0](../specs/v1.4.0-recherche-web-dans-le-chat.md)) télécharge les pages trouvées **entières**, nettoyées mais jamais coupées : on ne veut pas perdre une information parce qu'elle est en bas de page. Une page nettoyée peut peser des milliers, voire des dizaines de milliers de tokens.

Chaque appel Mistral renvoie tout ce qu'on lui donne : avec un contexte de conversation C (consigne, résumé, fenêtre, résultats d'outils précédents), envoyer les pages P dans l'appel principal coûte C + P, puis P est renvoyé à chaque tour suivant de la boucle d'outils (jusqu'à 3 tours principaux).

Mais les appels Mistral sont **indépendants** : un appel dédié n'a pas à recevoir C. On fait donc la recherche **en deux temps** :

1. l'appel principal demande `rechercher_web(requete, besoin)` ;
2. la VM interroge le moteur, télécharge et nettoie les pages, puis lance un **appel d'extraction** qui ne reçoit que le `besoin` et les pages, avec une consigne fixe : extraire ce qui répond, avec l'URL de chaque information, sans rien ajouter ;
3. l'appel principal reçoit cet extrait et la liste des résultats (titre, URL), pas les pages.

Les pages sont payées une seule fois, dans l'appel d'extraction. Le contexte principal reste léger, y compris aux tours suivants.

Alternatives écartées :
- **Pages brutes dans l'appel principal** : C + P, et P renvoyé à chaque tour de boucle.
- **Pages coupées à environ 4 000 caractères chacune** : perte d'information.
- **Synthèse avec le contexte de la conversation** : C payé une fois de plus, sans gain.
- **Deux outils dès maintenant** (`rechercher_web` qui ne renvoie que la liste, puis `lire_page(url)`) : un aller-retour principal de plus. La porte reste ouverte (registre d'outils, boucle multi-tours).

## Consequences

- Un appel Mistral de plus par recherche, avec un délai de quelques secondes. Il est compté en Consommation sous le type `extraction_web` et visible dans l'inspecteur.
- **L'extrait n'est jamais une source des garde-fous** : il est produit par un modèle et peut inventer. Les chiffres de la réponse sont vérifiés contre le **texte nettoyé complet** des pages et les extraits du moteur, enregistrés pour la conversation ; les URL, contre toute la liste des résultats.
- Seule limite de taille : la fenêtre de contexte du modèle d'extraction. Au-delà d'environ 80 %, la VM retire la dernière page entière plutôt que de couper.
- Si l'appel d'extraction échoue, l'outil renvoie la liste des résultats avec leurs extraits de moteur et la mention « extraction indisponible » ; le tour continue.
- Un futur mode « Approfondi » (outil `lire_page`, autre modèle, autre consigne d'extraction) se branche sur ce découpage sans le remettre en cause.
