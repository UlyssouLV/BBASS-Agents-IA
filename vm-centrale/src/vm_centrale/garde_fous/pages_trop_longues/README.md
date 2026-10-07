# pages_trop_longues

`mentionner_pages_trop_longues` ajoute à la fin de la réponse de chat une phrase fixe par page que `lire_pages_web` a jugée trop longue pendant le tour : « La page <url> était trop longue pour être lue en entier. » Sans page trop longue, la réponse est inchangée.

**Règles.**

- Une page est trop longue quand `lire_pages_web` l'a comptée avec un `besoin` au-delà de `PLAFOND_TOKENS_PAGES` (voir [`outils/lire_pages_web/`](../../outils/lire_pages_web/README.md)). La liste vient de `ContexteTour.pages_trop_longues`, remplie par l'outil pendant le tour et perdue à la fin du tour.
- Une page citée plusieurs fois dans le tour n'est mentionnée qu'une fois, avec l'URL de sa première relecture.
- La mention est ajoutée quelle que soit la réponse du modèle, même s'il a déjà prévenu le collaborateur, ou si le garde-fou chiffres a remplacé la réponse par sa phrase fixe.

**Appelant.** `routers/conversations.py`, `_reponse_visible`, après les garde-fous URL et chiffres (ajoutée par le code, elle n'est jamais contrôlée comme un texte du modèle), sur la réponse finale de chat de `creer_conversation` et `envoyer_message`, avant titrage, persistance et réponse au poste. L'échange `garde_fous` de l'inspecteur montre la réponse brute sans la mention et la réponse visible avec.

**Depuis.** 1.4.2 (#151). Origine : test humain 1.4.2, conversation 100 : « Résume moi ce livre » sur une page de 745 692 tokens. Après le refus, le modèle a relu la page sans besoin, reçu un aperçu de 8 000 caractères, puis résumé le roman de mémoire en le présentant comme lu à l'URL fournie. La consigne du refus (`lire_pages_web`) demande désormais de le dire ; ce garde-fou le garantit.

Code : `garde_fou.py`.
