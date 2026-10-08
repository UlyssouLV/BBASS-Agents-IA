# contact_non_lu

`remplacer_contact_non_lu` remplace toute la réponse de chat par la phrase fixe « Moduléo n'a pas encore été consulté pour ce contact. Précisez son nom pour que je le cherche. » quand elle affirme qu'une coordonnée est absente de Moduléo sans que `chercher_contacts_moduleo` ait été appelé dans le tour. Sinon, la réponse est inchangée.

**Règles.**

- Une phrase de la réponse (coupée sur `.`, `!`, `?` et les retours à la ligne) qui nomme à la fois Moduléo (`Moduléo` ou `Moduleo`, casse indifférente), une coordonnée (coordonnées, téléphone, portable, email, mail, courriel, joindre) et une absence (`pas`, `aucun(e)`, absent, indisponible, manquant, non renseigné) suffit.
- `chercher_contacts_moduleo` appelé dans le tour (`ContexteTour.outils_appeles`) : rien n'est remplacé, même si la réponse dit le contact sans coordonnées.
- Une adresse n'est pas une coordonnée ici : la fiche d'affaire en porte une, celle de l'affaire.
- S'applique même à une demande explicite d'inventer.

**Appelant.** `routers/conversations.py`, `_appliquer_garde_fous`, avant les garde-fous URL et chiffres (une réponse remplacée n'a plus rien à contrôler), sur la réponse finale de chat de `creer_conversation` et `envoyer_message`. La phrase compte parmi les phrases fixes : au premier échange, le titrage se fait sur le seul message du compte. Au tour suivant, pas de note système : la phrase demande déjà un nom, que le modèle cherche avec l'outil contacts.

**Depuis.** 1.5.0 (#183). Origine : test humain 2 de la 1.5.0, conversation 116, « Affaires en cours depuis octobre » : sur quatre demandes de coordonnées (client de 22_369-152, client d'une affaire citée, intervenants de 25_862-17, « Céline Bourdoncle » puis « non par moduléo »), le modèle n'a jamais appelé `chercher_contacts_moduleo`, pourtant proposé à chaque tour, et a répondu « pas disponibles dans Moduléo » à partir des seules fiches d'affaire. La description de `chercher_affaires_moduleo` et la fiche d'affaire renvoient désormais vers l'outil contacts ; ce garde-fou le garantit.

Limite connue : une phrase qui nie autre chose (« je n'ai pas encore cherché son téléphone dans Moduléo ») est aussi remplacée, ce qui revient au même pour le collaborateur.

Code : `garde_fou.py`.
