# chiffres

`retirer_chiffres_hors_source` retire de la réponse un chiffre (décimale, pourcentage, entier d'au moins deux chiffres, ou entier d'un chiffre suivi d'une unité de durée) absent des textes source.

**Textes source.** Messages `user` de la conversation, message du tour, extraits de pièces jointes, extraits du moteur et texte nettoyé des pages de la conversation (table `resultats_recherche_web`, depuis 1.4.0 ; page écrite par le compte et lue par `lire_pages_web`, provenance `utilisateur`, depuis 1.4.1, #140). Jamais l'extrait de l'appel d'extraction ni les réponses des questions couvertes, écrites par un modèle (depuis 1.4.1, #137).

**Règles.**

- `1,7` et `1.7` sont le même chiffre.
- Une suite de chiffres groupés par des espaces (`831 193 453 00022`) est comparée chiffres mis bout à bout, dans la réponse comme dans les sources : un numéro (SIRET, TVA, téléphone) regroupé autrement que la source passe, et une suite dont une partie est retirée part en entier, jamais un fragment (depuis 1.4.1 : essai, conversation 93, un SIRET devenait « 22 »).
- Un entier seul d'un chiffre (« 3 pistes ») n'est pas touché.
- Un nombre écrit dans une URL (partie `url` d'un lien Markdown, URL nue ; motifs repris de [`urls/garde_fou.py`](../urls/README.md)) n'est jamais touché : les URL relèvent du seul garde-fou URL. Le texte d'un lien `[texte](url)` reste contrôlé (depuis 1.4.0, #128).

**Appelant.** `routers/conversations.py`, `_reponse_visible`, après le garde-fou URL, sur la réponse finale de chat de `creer_conversation` et `envoyer_message`, avant titrage, persistance et réponse au poste. Sans pièce jointe, sans texte de recherche non vide et sans chiffre dans le message du tour, la réponse entière est remplacée par la phrase fixe « Je n'ai trouvé ni page ni document pour appuyer une réponse chiffrée. » (reformulée en 1.4.0, sans « pas accès à Internet »). Une demande explicite d'inventer, d'imaginer ou de faire une hypothèse laisse les chiffres.

**Depuis.** 1.3.1 (recherche web : 1.4.0). Origine : conversation 78 : le modèle a rédigé un rapport chiffré après avoir reçu la consigne de ne pas inventer, puis a écrit en bas qu'il ne pouvait pas vérifier. URL épargnées : #128, conversation 87 (« 2025-03/202503-guide… » devenu « 2025-/-guide… »).

## Limites connues (#131, correction prévue en 1.4.5)

Constatées au test humain de la 1.4.0 (conversations 90 et 91). La 1.4.0 est livrée avec.

- Dès qu'un chiffre est retiré, la réduction finale des doubles espaces écrase aussi l'indentation en début de ligne (sous-listes et tableaux aplatis).
- Le chiffre retiré ne laisse aucune trace (`** €**`, « ans pour les B2C »).
- Un entier d'un chiffre sans unité de durée (« 5 € ») n'est pas contrôlé, et un nombre courant présent par coïncidence dans les sources (10, 20) passe : le garde-fou vérifie qu'un nombre existe, pas qu'il est attribué au bon fait.

Code : `garde_fou.py`.
