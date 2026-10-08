# sources

`ajouter_sources` ajoute à la fin de la réponse de chat une ligne « Sources : » avec un lien Markdown vers chaque page d'où vient un chiffre gardé, et, depuis la 1.5.0 (#174), la citation sans lien de chaque fiche lue par un outil (`LectureSource`, table `lectures_outils`) : `Sources : [titre](url), Moduléo, affaire 2024-123`. Sans chiffre de ce type, la réponse est inchangée.

**Règles.**

- Un chiffre est celui du garde-fou [`chiffres/`](../chiffres/README.md) (même définition, reprise par `chiffres_controles` et `chiffres_des_sources`) : décimale, pourcentage, entier d'au moins deux chiffres, entier d'un chiffre suivi d'une unité de durée, suite de chiffres groupés ; jamais un nombre écrit dans une URL.
- Seuls comptent les chiffres absents des messages du compte (conversation et message du tour) et des extraits des pièces jointes : un chiffre que le compte a lui-même apporté n'appelle pas de source.
- Une année seule (entier de 1900 à 2100) ne fait citer aucune page : « 2026 » figure dans presque toutes.
- Un chiffre qui figure dans une page déjà en lien dans la réponse (lien Markdown ou URL nue, comparée par `normaliser_url`) n'ajoute rien, et cette page n'est pas citée de nouveau.
- Pour chaque autre chiffre, une seule source : la plus récente de la conversation dont le texte le contient, page (table `resultats_recherche_web`, son **texte nettoyé**) ou fiche lue par un outil (table `lectures_outils`, citée « Moduléo, affaire 2024-123 », sans lien), dans l'ordre de leur date d'enregistrement. Jamais d'après l'extrait du moteur (une page qu'on n'a pas lue n'est pas citée ; l'extrait reste une source du garde-fou chiffres), ni d'après les faits de l'appel d'extraction ou les questions couvertes, écrits par un modèle.
- Le texte du lien est le titre de la page (crochets remplacés par des parenthèses), sinon son URL. Une page présente sur plusieurs lignes (relue, recherchée deux fois) n'est citée qu'une fois, avec le premier titre connu. Les pages suivent l'ordre de la conversation.
- **Un seul bloc.** Si la réponse se termine déjà par un bloc « Source : » ou « Sources : » (gras compris), les pages manquantes y sont ajoutées au même format : à la suite de la ligne (`, [titre](url)`) ou en puces de même marque. « Source » passe au pluriel. Un bloc qui n'est pas à la fin de la réponse ne compte pas.

**Appelant.** `routers/conversations.py`, `_reponse_visible`, après les garde-fous URL et chiffres (seuls les chiffres gardés sont cités, et la ligne ajoutée par le code n'est jamais contrôlée comme un texte du modèle), avant la mention des [pages trop longues](../pages_trop_longues/README.md), sur la réponse finale de chat de `creer_conversation` et `envoyer_message`. L'échange `garde_fous` de l'inspecteur montre la réponse brute sans la ligne et la réponse visible avec.

**Depuis.** 1.4.3 (#160, #162). Origine : test humain 1 de la 1.4.3, conversation 103 (« Durée d'un bornage amiable ») : la réponse donnait « 6 à 12 semaines » sans dire de quelle page venait le chiffre. Test humain 2 (conversations 105 et 106, #162) : deux blocs de sources, et des pages citées pour « 2026 » ou d'après leur seul extrait du moteur.

**Limite.** Le garde-fou vérifie qu'un chiffre de la réponse figure dans une page, pas que la phrase lui attribue le bon fait : un nombre courant présent par coïncidence dans une page (10, 20) la fait citer.

Code : `garde_fou.py`.
