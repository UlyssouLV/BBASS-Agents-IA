# relire_pieces_jointes

Relit le `contenu_extrait` déjà en base d'une ou plusieurs pièces jointes de la conversation, par `piece_jointe_ids`. Pas de ré-analyse (OCR, vision) : l'extraction à l'envoi reste dans `analyse_pieces_jointes/`.

**Éligibilité.** Dès qu'une pièce jointe de la conversation n'est pas celle du tour en cours, que son message soit encore dans la fenêtre des derniers messages ou non (spec 1.4.1). Au tour de l'envoi de la seule pièce jointe, l'outil n'est pas déclaré : son contenu part déjà en message système.

**Description.** Générée à chaque appel, jamais une liste figée : chaque pièce jointe éligible y apparaît avec son id et son nom de fichier (#50).

**Exécution.** Un contenu par pièce jointe, dans l'ordre des ids, chacun précédé de son id et de son nom de fichier (`Pièce jointe id 41 « devis.pdf » :`). Id inconnu ou d'une autre conversation : « Pièce jointe introuvable. » pour cet id seul, jamais une erreur HTTP. L'échange d'inspecteur et l'appel principal suivant référencent la première pièce jointe relue (spec 1.3.0).

**Depuis.** 1.1.2 sous le nom `obtenir_contenu_piece_jointe` (une pièce jointe sortie de la fenêtre, un id), déplacé dans ce paquet en 1.4.0 (#118), renommé et élargi en 1.4.1 (#135).

Code : `outil.py`. D'autres modules de cet outil peuvent vivre à côté sans changer le registre (`OUTIL` reste exporté par ce paquet).
