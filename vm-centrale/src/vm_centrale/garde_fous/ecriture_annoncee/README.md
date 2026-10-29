# ecriture_annoncee

Seule une vraie Carte de confirmation, ouverte par `ecrire_moduleo`, et son statut (« Écrit dans Moduléo », « Annulée… », « Expirée… », refus) disent une écriture Moduléo. Le texte du modèle ne peut ni montrer une carte, ni dire une écriture faite.

- `annonce_une_carte` : la réponse parle d'une carte de confirmation, d'un bouton (« Valider pour appliquer », « confirmez pour enregistrer »), ou écrit une requête d'écriture (« POST moduleo/tacheafaire », bloc JSON avec `"route"`, `"methode"` ou `"corps"`).
- `affirme_une_ecriture` : la réponse dit un élément « créé / écrit / ajouté / modifié / supprimé / enregistré / mis à jour / saisi / déplacé dans (ou sur) Moduléo », hors lecture : pas de négation dans la même proposition (« Aucun contact … n'est enregistré dans Moduléo », « n'a pas été créé », « aucun téléphone enregistré »), ni un état lu sur une fiche, « est / sont (bien, déjà) enregistré dans Moduléo » sans « a été » (#258).
- `retirer_ecriture_affirmee` : retire chaque phrase qui affirme une écriture ; si plus rien ne reste, `PHRASE_CARTE_OUVERTE`.

**Règles** (`routers/conversations.py`).

1. **Relance forcée** (`_resoudre_reponse_chat`, `_a_relancer`) : une réponse finale du modèle qui annonce une carte, ou affirme une écriture alors qu'aucune écriture de la Conversation n'est `confirmee`, sans aucune carte ouverte dans le tour (`ContexteTour.cartes_du_tour`), n'est jamais montrée. Si `ecrire_moduleo` est proposé au tour, la VM refait l'appel avec le même historique et l'outil imposé (`tool_choice` Mistral `{"type": "function", "function": {"name": "ecrire_moduleo"}}`) : soit une carte s'ouvre, soit l'outil refuse et le modèle répond d'après ce refus. Une seule relance par message ; elle s'ajoute aux tours ordinaires si besoin, le dernier appel partant toujours sans `tools`. L'appel imposé est borné (`config.py`) : `MISTRAL_RELANCE_MAX_TOKENS` (1 024 tokens générés, `max_tokens` Mistral) et `MISTRAL_RELANCE_TIMEOUT` (20 s, à la place de `MISTRAL_HTTP_TIMEOUT`). S'il échoue ou expire, l'échec est journalisé à l'inspecteur sans faire tomber le tour, et la réponse annoncée devient la phrase fixe (règle 2) (#258).
2. **Phrase fixe** (`_appliquer_garde_fous`, en tête) : sans carte dans le tour, une réponse qui annonce encore une écriture (après la relance, ou sans outil d'écriture proposé) devient `PHRASE_ECRITURE_NON_PROPOSEE`. Elle compte parmi les phrases fixes (titrage sur le seul message).
3. **Carte ouverte** : `retirer_ecriture_affirmee` sur la réponse, rien n'est encore écrit avant le clic.

Après une écriture `confirmee` dans la Conversation, le modèle peut redire son résultat (« le téléphone a été ajouté dans Moduléo ») : ce n'est pas relancé.

**Depuis.** 1.5.2 (#252). Faux positifs de lecture et relance bornée : #258 (second passage de #206 : « Aucun contact Client Exemple 10 n'est enregistré dans Moduléo. » relancé, puis 8 868 tokens en 76 s et « service indisponible »). Origine : premier passage des tests humains de la 1.5.2 (#206) : fausse carte en texte (bloc JSON `POST moduleo/tacheafaire`, « Voici la carte de confirmation… Valider pour appliquer ») sans appel de l'outil, et « la tâche … a été créée dans Moduléo » alors que rien n'était écrit.

Limites connues : une écriture inventée dite comme un état (« la tâche est enregistrée dans Moduléo ») n'est pas reconnue. Une affirmation tournée autrement (« c'est fait », « j'ai enregistré la tâche » sans nommer Moduléo) n'est pas reconnue. Après une confirmation dans la Conversation, une affirmation sur une autre écriture, jamais proposée, passe aussi.

Code : `garde_fou.py`.
