# Outils

Ce que le modèle peut **décider** d'appeler (tool calling). Une étape de traitement imposée par la VM n'est pas un outil, même si elle appelle Mistral : l'extraction d'une pièce jointe à l'envoi (OCR, vision) reste dans `analyse_pieces_jointes/`, les corrections de la réponse dans `garde_fous/` (spec 1.4.0, décision n° 8).

Chaque outil est un `Outil` (`base.py`) inscrit dans `registre.py` : son nom, `declarer` (le schéma `tools` pour ce tour, ou `None` s'il n'est pas éligible) et `executer` (arguments du modèle → contenu du message `tool`). `routers/conversations.py` ne connaît que `outils_du_tour` et `executer_appel`, appelés sur l'appel de chat principal ; jamais sur le titrage ni sur le résumé et profil. Un nom d'outil inconnu donne « Outil inconnu. », jamais une erreur.

Boucle (`_resoudre_reponse_chat`, spec 1.4.0) : la VM exécute **tous** les appels d'une réponse, un message `tool` par appel, puis relance l'appel principal ; au plus 3 appels principaux par message, le 3e sans `tools`. Chaque exécution est un échange d'inspecteur d'origine `local`, de type `outil:<nom>` (arguments, contenu renvoyé au modèle).

Ajouter, déplacer ou retirer un outil met à jour ce fichier dans le même commit (`agents/domain.md`, « Centralised packages »).

| Outil | Ce qu'il fait | Éligibilité | Depuis | Origine |
| --- | --- | --- | --- | --- |
| `obtenir_contenu_piece_jointe` (`piece_jointe.py`) | Renvoie le `contenu_extrait` complet d'une pièce jointe de la conversation, par `piece_jointe_id`. Id absent ou d'une autre conversation : « Pièce jointe introuvable. ». | Seulement s'il existe une pièce jointe liée à un message sorti de la fenêtre des derniers messages. La description liste chaque pièce jointe éligible (id et nom de fichier). | 1.1.2 (déplacé ici en 1.4.0) | Spec 1.1.2 : relire une pièce jointe ancienne sans renvoyer son contenu à chaque tour. Description avec noms de fichiers : #50. |
