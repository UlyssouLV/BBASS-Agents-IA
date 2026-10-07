# sources

`ajouter_sources` ajoute à la fin de la réponse de chat une ligne « Sources : » avec un lien Markdown vers chaque page d'où vient un chiffre gardé : `Sources : [titre](url), [titre](url)`. Sans chiffre de ce type, la réponse est inchangée.

**Règles.**

- Un chiffre est celui du garde-fou [`chiffres/`](../chiffres/README.md) (même définition, reprise par `chiffres_controles` et `chiffres_des_sources`) : décimale, pourcentage, entier d'au moins deux chiffres, entier d'un chiffre suivi d'une unité de durée, suite de chiffres groupés ; jamais un nombre écrit dans une URL.
- Seuls comptent les chiffres absents des messages du compte (conversation et message du tour) et des extraits des pièces jointes : un chiffre que le compte a lui-même apporté n'appelle pas de source.
- Une page est citée quand un de ces chiffres figure dans son texte nettoyé ou dans son extrait du moteur (table `resultats_recherche_web`, toute la conversation, page de recherche ou URL écrite par le compte). Jamais d'après les faits de l'appel d'extraction ni les questions couvertes, écrits par un modèle.
- Le texte du lien est le titre de la page (crochets remplacés par des parenthèses), sinon son URL. Une page présente sur plusieurs lignes (relue, recherchée deux fois) n'est citée qu'une fois, avec le premier titre connu.
- Une page dont l'URL est déjà écrite dans la réponse (lien Markdown ou URL nue, comparée par `normaliser_url`) n'est pas citée de nouveau.

**Appelant.** `routers/conversations.py`, `_reponse_visible`, après les garde-fous URL et chiffres (seuls les chiffres gardés sont cités, et la ligne ajoutée par le code n'est jamais contrôlée comme un texte du modèle), avant la mention des [pages trop longues](../pages_trop_longues/README.md), sur la réponse finale de chat de `creer_conversation` et `envoyer_message`. L'échange `garde_fous` de l'inspecteur montre la réponse brute sans la ligne et la réponse visible avec.

**Depuis.** 1.4.3 (#160). Origine : test humain 1 de la 1.4.3, conversation 103 (« Durée d'un bornage amiable ») : la réponse donnait « 6 à 12 semaines » sans dire de quelle page venait le chiffre.

**Limite.** Le garde-fou vérifie qu'un chiffre de la réponse figure dans une page, pas que la phrase lui attribue le bon fait : un nombre courant présent par coïncidence dans une page (10, 20) la fait citer.

Code : `garde_fou.py`.
