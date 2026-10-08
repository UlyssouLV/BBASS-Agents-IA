import re

# Sur quatre demandes de coordonnées, le modèle a répondu « pas disponibles
# dans Moduléo » à partir des seules fiches d'affaire, sans jamais appeler
# chercher_contacts_moduleo (#183, conversation 116) : une absence affirmée
# sans lecture du contact devient une phrase fixe de la VM.

PHRASE_CONTACT_NON_LU = (
    "Moduléo n'a pas encore été consulté pour ce contact. Précisez son nom pour que je le cherche."
)

_PHRASES = re.compile(r"[^.!?\n]+")
_MODULEO = re.compile(r"\bmodul[eé]o\b", re.IGNORECASE)
_COORDONNEE = re.compile(
    r"\b(?:coordonnées?|t[ée]l[ée]phones?|portables?|e-?mails?|mails?|courriels?|joindre)\b", re.IGNORECASE
)
_ABSENCE = re.compile(
    r"\b(?:pas|aucune?|absente?s?|indisponibles?|manquante?s?)\b|\bnon\s+renseign", re.IGNORECASE
)
# Négations qui ne disent pas une absence : « N'hésitez pas à me demander
# ses coordonnées dans Moduléo » effaçait toute une réponse sur des affaires.
_TOURNURES = re.compile(r"\bh[ée]sit\w*\s+pas\b|\bne\s+manquez\s+pas\b", re.IGNORECASE)


def remplacer_contact_non_lu(reponse: str, contacts_lus: bool) -> str:
    # Une phrase qui nomme Moduléo, une coordonnée et une absence.
    # `contacts_lus` : aussi vrai sans Moduléo, où la phrase fixe
    # promettrait une recherche impossible.
    if contacts_lus:
        return reponse
    for phrase in _PHRASES.findall(reponse):
        sans_tournure = _TOURNURES.sub("", phrase)
        if _MODULEO.search(phrase) and _COORDONNEE.search(phrase) and _ABSENCE.search(sans_tournure):
            return PHRASE_CONTACT_NON_LU
    return reponse
