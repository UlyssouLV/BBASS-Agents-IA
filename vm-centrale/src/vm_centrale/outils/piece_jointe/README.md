# obtenir_contenu_piece_jointe

Relit le `contenu_extrait` déjà en base d'une pièce jointe de la conversation, par `piece_jointe_id`. Pas de ré-analyse (OCR, vision) : l'extraction à l'envoi reste dans `analyse_pieces_jointes/`.

**Éligibilité.** Seulement s'il existe une pièce jointe liée à un message sorti de la fenêtre des derniers messages. Sinon l'outil n'est pas déclaré pour ce tour.

**Description.** Générée à chaque appel, jamais une liste figée : chaque pièce jointe éligible y apparaît avec son id et son nom de fichier (#50).

**Exécution.** Id absent ou d'une autre conversation : « Pièce jointe introuvable. », jamais une erreur HTTP. Sinon le contenu extrait (vide si rien n'a été stocké).

**Depuis.** 1.1.2, déplacé dans ce paquet en 1.4.0 (#118). Spec 1.1.2 : relire une pièce jointe ancienne sans renvoyer son contenu à chaque tour.

Code : `outil.py`. D'autres modules de cet outil peuvent vivre à côté sans changer le registre (`OUTIL` reste exporté par ce paquet).
