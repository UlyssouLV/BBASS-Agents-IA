# Garde-fous

Corrections que le code applique à ce que le modèle produit **malgré sa consigne**. Une consigne seule ne garantit rien : chaque garde-fou garantit dans le code un résultat que le prompt demande déjà.

Chaque garde-fou est une fonction pure (texte en entrée, texte en sortie), appelée à un seul endroit. Ajouter, déplacer ou retirer un garde-fou met à jour ce fichier dans le même commit (`agents/domain.md`, « Centralised packages »).

Depuis la 1.4.0, `routers/conversations._reponse_visible` enregistre à chaque réponse de chat un échange `local` de type `garde_fous` dans l'inspecteur : la réponse brute du modèle et la réponse visible.

Chaque garde-fou est un paquet (`longueur/`, `titre/`, `urls/`, `chiffres/`, `sources/`, `pages_trop_longues/`) : `garde_fou.py` porte le comportement, `__init__.py` exporte ses fonctions publiques, et `vm_centrale.garde_fous` les réexporte toutes. Les règles, l'appelant, l'origine et les limites connues sont dans le `README.md` du paquet.

| Garde-fou | Ce qu'il corrige | Depuis |
| --- | --- | --- |
| `plafonner` ([`longueur/`](longueur/README.md)) | Plafonne le résumé glissant et le profil de travail à la dernière fin de phrase sous un maximum. | 1.3.1 |
| `nettoyer_titre` ([`titre/`](titre/README.md)) | Retire la mise en forme Markdown du titre généré, affiché en texte brut côté poste. | 1.2.2 (déplacé ici en 1.3.1) |
| `retirer_urls_inventees` ([`urls/`](urls/README.md)) | Retire de la réponse de chat toute URL ni écrite par le compte, ni ramenée par une recherche de la conversation. | 1.3.1 (résultats de recherche : 1.4.0) |
| `retirer_chiffres_hors_source` ([`chiffres/`](chiffres/README.md)) | Retire de la réponse de chat un chiffre absent des textes source, avec sa parenthèse ou sa phrase, ou remplace une réponse chiffrée sans aucune source. | 1.3.1 (recherche web : 1.4.0 ; bloc entier : 1.4.3 ; numéros à points : 1.5.0, #180) |
| `ajouter_sources` ([`sources/`](sources/README.md)) | Ajoute à la fin de la réponse de chat une ligne « Sources : » (ou complète le bloc de sources du modèle) vers la page la plus récente d'où vient chaque chiffre gardé, années ignorées ; une fiche Moduléo est citée sans lien. | 1.4.3 (lectures d'outil : 1.5.0 ; sans doublon : 1.5.0, #180) |
| `mentionner_pages_trop_longues` ([`pages_trop_longues/`](pages_trop_longues/README.md)) | Ajoute à la fin de la réponse de chat une phrase fixe par page jugée trop longue par `lire_pages_web` pendant le tour. | 1.4.2 |
