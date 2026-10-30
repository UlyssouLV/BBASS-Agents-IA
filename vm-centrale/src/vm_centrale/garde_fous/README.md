# Garde-fous

Corrections que le code applique à ce que le modèle produit **malgré sa consigne**. Une consigne seule ne garantit rien : chaque garde-fou garantit dans le code un résultat que le prompt demande déjà.

Chaque garde-fou est une fonction pure (texte en entrée, texte en sortie), appelée à un seul endroit. Depuis la 1.6.3, `retirer_urls_inventees` et `retirer_chiffres_hors_source` rendent un `Retrait` (`retrait.py`) : le texte, et s'ils ont retiré quelque chose. Ce qu'ils retirent devient le marqueur « [non trouvé] » (`MARQUEUR_NON_TROUVE`) ; dès que l'un d'eux a retiré quelque chose, `_reponse_visible` ajoute en toute fin de réponse, après la ligne « Sources : » et la mention des pages trop longues, la phrase fixe « Certaines informations n'ont pas été trouvées dans les sources consultées. » (`PHRASE_NON_TROUVE`, spec 1.6.3, #131). Une réponse entièrement remplacée par une phrase fixe (`contact_non_lu/`, réponse chiffrée sans aucune source) ne la reçoit pas. Ajouter, déplacer ou retirer un garde-fou met à jour ce fichier dans le même commit (`agents/domain.md`, « Centralised packages »).

Depuis la 1.6.3 ([ADR-0023](../../../../docs/adr/0023-relecture-isolee-apres-garde-fou.md)), un retrait déclenche une seule **relecture isolée** (`vm_centrale/relecture.py`, échange `mistral` et consommation `relecture`) : un appel Mistral sans outils qui reçoit seulement la question, la réponse marquée, les résultats d'outils du tour et la pièce jointe du message. Les garde-fous repassent sur sa sortie : rendue telle quelle, elle remplace la réponse, sans phrase fixe ; sinon, ou si l'appel échoue, la réponse marquée reste avec la phrase fixe. La ligne d'inspecteur dit `"relecture": "retenue"` ou `"écartée"`.

Depuis la 1.4.0, `routers/conversations._reponse_visible` enregistre à chaque réponse de chat un échange `local` de type `garde_fous` dans l'inspecteur : la réponse brute du modèle et la réponse visible.

Chaque garde-fou est un paquet (`longueur/`, `titre/`, `urls/`, `chiffres/`, `contact_non_lu/`, `sources/`, `pages_trop_longues/`) : `garde_fou.py` porte le comportement, `__init__.py` exporte ses fonctions publiques, et `vm_centrale.garde_fous` les réexporte toutes. Les règles, l'appelant, l'origine et les limites connues sont dans le `README.md` du paquet.

| Garde-fou | Ce qu'il corrige | Depuis |
| --- | --- | --- |
| `plafonner` ([`longueur/`](longueur/README.md)) | Plafonne le résumé glissant et le profil de travail à la dernière fin de phrase sous un maximum. | 1.3.1 |
| `nettoyer_titre` ([`titre/`](titre/README.md)) | Retire la mise en forme Markdown du titre généré, affiché en texte brut côté poste. | 1.2.2 (déplacé ici en 1.3.1) |
| `retirer_urls_inventees` ([`urls/`](urls/README.md)) | Remplace par « [non trouvé] » toute URL ou lien de la réponse de chat ni écrit par le compte, ni ramené par une recherche de la conversation ; une parenthèse qui ne contenait que ces liens part. | 1.3.1 (résultats de recherche : 1.4.0 ; marqueur : 1.6.3) |
| `retirer_chiffres_hors_source` ([`chiffres/`](chiffres/README.md)) | Remplace par « [non trouvé] » un chiffre de la réponse de chat absent des textes source, ou remplace une réponse chiffrée sans aucune source. | 1.3.1 (recherche web : 1.4.0 ; bloc entier : 1.4.3 ; numéros à points : 1.5.0, #180 ; date du jour et phrase fixe Moduléo : 1.5.0, #182 ; marqueur, « 5 € » : 1.6.3) |
| `remplacer_contact_non_lu` ([`contact_non_lu/`](contact_non_lu/README.md)) | Remplace la réponse de chat par une phrase fixe quand elle dit une coordonnée absente de Moduléo sans appel `chercher_contacts_moduleo` dans le tour. | 1.5.0 (#183) |
| `ajouter_sources` ([`sources/`](sources/README.md)) | Ajoute à la fin de la réponse de chat une ligne « Sources : » (ou complète le bloc de sources du modèle) vers la page la plus récente d'où vient chaque chiffre gardé, années ignorées ; une fiche Moduléo est citée sans lien. | 1.4.3 (lectures d'outil : 1.5.0 ; sans doublon : 1.5.0, #180) |
| `mentionner_pages_trop_longues` ([`pages_trop_longues/`](pages_trop_longues/README.md)) | Ajoute à la fin de la réponse de chat une phrase fixe par page jugée trop longue par `lire_pages_web` pendant le tour. | 1.4.2 |
