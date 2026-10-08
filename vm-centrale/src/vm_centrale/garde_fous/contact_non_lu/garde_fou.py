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


def remplacer_contact_non_lu(reponse: str, contacts_lus: bool) -> str:
    # Une phrase qui nomme Moduléo, une coordonnée et une absence.
    if contacts_lus:
        return reponse
    for phrase in _PHRASES.findall(reponse):
        if _MODULEO.search(phrase) and _COORDONNEE.search(phrase) and _ABSENCE.search(phrase):
            return PHRASE_CONTACT_NON_LU
    return reponse
