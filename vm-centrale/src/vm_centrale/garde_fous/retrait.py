from typing import NamedTuple

# Ce qu'un garde-fou laisse à la place de ce qu'il retire, et la phrase
# ajoutée en fin de réponse dès qu'il a retiré quelque chose (spec 1.6.3,
# #131 : `** €**`, cellules `€` vides, rien ne disait que l'information
# manquait).
MARQUEUR_NON_TROUVE = "[non trouvé]"
PHRASE_NON_TROUVE = "Certaines informations n'ont pas été trouvées dans les sources consultées."


class Retrait(NamedTuple):
    # `retire` : le garde-fou a retiré quelque chose (phrase fixe, puis
    # relecture isolée, ADR-0023).
    texte: str
    retire: bool
