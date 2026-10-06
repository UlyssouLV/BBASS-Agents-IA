# Outils

Ce que le modèle peut **décider** d'appeler (tool calling). Une étape de traitement imposée par la VM n'est pas un outil, même si elle appelle Mistral : l'extraction d'une pièce jointe à l'envoi (OCR, vision) reste dans `analyse_pieces_jointes/`, les corrections de la réponse dans `garde_fous/` (spec 1.4.0, décision n° 8).

Chaque outil est un `Outil` (`base.py`) inscrit dans `registre.py` : son nom, `declarer` (le schéma `tools` pour ce tour, ou `None` s'il n'est pas éligible) et `executer` (arguments du modèle → contenu du message `tool`). `routers/conversations.py` ne connaît que `outils_du_tour` et `executer_appel`, appelés sur l'appel de chat principal ; jamais sur le titrage ni sur le résumé et profil. Un nom d'outil inconnu donne « Outil inconnu. », jamais une erreur.

Boucle (`_resoudre_reponse_chat`, spec 1.4.0) : la VM exécute **tous** les appels d'une réponse, un message `tool` par appel, puis relance l'appel principal ; au plus 3 appels principaux par message, le 3e sans `tools`. Chaque exécution est un échange d'inspecteur d'origine `local`, de type `outil:<nom>` (arguments, contenu renvoyé au modèle). Un appel Mistral fait par l'outil lui-même revient dans `ResultatOutil.appels_mistral` : la boucle l'enregistre (Consommation, échange d'origine `mistral`) juste après.

Chaque outil est un paquet (`rechercher_web/`, `piece_jointe/`) : `outil.py` porte le comportement, `__init__.py` exporte `OUTIL` (et `CONSIGNE_EXTRACTION` pour la recherche). D'autres modules du même outil peuvent s'ajouter dans le paquet sans changer `registre.py`. Le détail du fonctionnement est dans le `README.md` du paquet. Ajouter, déplacer ou retirer un outil met à jour ce fichier dans le même commit (`agents/domain.md`, « Centralised packages »).

| Outil | Ce qu'il fait | Éligibilité | Depuis | Origine |
| --- | --- | --- | --- | --- |
| `rechercher_web` ([`recherche_web/`](recherche_web/README.md)) | Cherche via SearXNG, lit les pages, extrait ce qui répond au besoin, renvoie titre, URL et extrait. | Toujours, sur chaque appel de chat principal. | 1.4.0 | Spec 1.4.0, ADR-0013 : pas d'outil `web_search` Mistral ; le modèle décide de chercher (décision n° 3). |
| `obtenir_contenu_piece_jointe` ([`piece_jointe/`](piece_jointe/README.md)) | Renvoie le contenu déjà extrait d'une pièce jointe, par id. | Seulement si une pièce jointe est sortie de la fenêtre des derniers messages. | 1.1.2 (déplacé ici en 1.4.0) | Spec 1.1.2. Description avec noms de fichiers : #50. |
