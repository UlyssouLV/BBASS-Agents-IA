# relire_pieces_jointes

Relit le `contenu_extrait` déjà en base d'une ou plusieurs pièces jointes de la conversation, par `piece_jointe_ids`. Pas de ré-analyse (OCR, vision) : l'extraction à l'envoi reste dans `analyse_pieces_jointes/`.

**Éligibilité.** Dès qu'une pièce jointe de la conversation n'est pas celle du tour en cours, que son message soit encore dans la fenêtre des derniers messages ou non (spec 1.4.1). Au tour de l'envoi de la seule pièce jointe, l'outil n'est pas déclaré : son contenu part déjà en message système.

**Description.** Générée à chaque appel, jamais une liste figée : chaque pièce jointe éligible y apparaît avec son id et son nom de fichier (#50).

**Exécution.** Un contenu par pièce jointe, dans l'ordre des ids, chacun précédé de son id et de son nom de fichier (`Pièce jointe id 41 « devis.pdf » :`). Id inconnu ou d'une autre conversation : « Pièce jointe introuvable. » pour cet id seul, jamais une erreur HTTP. L'échange d'inspecteur et l'appel principal suivant référencent la première pièce jointe relue (spec 1.3.0).

**Avec un `besoin`** (facultatif, #141). Un seul appel d'extraction isolé pour toutes les pièces jointes relues (`mistral-small-latest`) : consigne fixe `CONSIGNE_RELECTURE_PIECES_JOINTES`, le besoin et les contenus extraits, chacun précédé de son nom de fichier, jamais le contexte de la conversation (ADR-0014). Sortie JSON stricte : `trouvee`, `reponse`, `source` (nom de fichier). Consigne : « non trouvé » plutôt qu'une estimation. Le modèle reçoit la réponse et sa source, ou « Non trouvé… », au lieu des contenus complets. Ligne `Consommation` `extraction_piece_jointe` (catégorie chat) et échange d'inspecteur du même type (origine `mistral`). Résultat enregistré dans `questions_couvertes` (question = besoin, origine `besoin`, hors des 8 questions initiales, réponse coupée à 300 caractères) : trouvé, sur la pièce jointe que nomme `source` (la seule relue, quelle que soit la source ; une source qui n'est pas une pièce jointe relue n'est pas enregistrée) ; non trouvé, `trouvee = faux` sur chacune des pièces jointes relues, affiché « non présent selon l'extraction » dans la Mémoire de la conversation. Jamais une source des garde-fous. Échec de l'appel ou réponse hors du JSON attendu : « Extraction indisponible… », rien d'enregistré. Aucun id trouvé : pas d'appel.

**Statuts publiés** (statut du tour, ADR-0016). « Relecture de <nom du fichier> » avant chaque pièce jointe trouvée, une fois par pièce jointe, dans l'ordre des ids ; un id introuvable n'en publie pas. Libellés construits par `statut_tour.py` (domaine = hôte sans `www.` ; détail tronqué au-delà de `LONGUEUR_MAX_DETAIL_STATUT` caractères, `config.py`). Outil appelé sans émetteur (hors d'un tour en flux) : aucun statut. Depuis 1.4.4 (#165, spec 1.4.4).

**Depuis.** 1.1.2 sous le nom `obtenir_contenu_piece_jointe` (une pièce jointe sortie de la fenêtre, un id), déplacé dans ce paquet en 1.4.0 (#118), renommé et élargi en 1.4.1 (#135), `besoin` en 1.4.1 (#141).

Code : `outil.py`. D'autres modules de cet outil peuvent vivre à côté sans changer le registre (`OUTIL` reste exporté par ce paquet).
