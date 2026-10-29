import re

# Au premier passage des tests humains de la 1.5.2 (#206), le modèle a
# écrit une fausse carte dans sa réponse (bloc JSON avec « POST
# moduleo/tacheafaire », « Valider pour appliquer ») sans appeler
# ecrire_moduleo, et une fois « la tâche … a été créée dans Moduléo » alors
# que rien n'était écrit (#252). Seule une vraie Carte de confirmation, et
# son statut, disent une écriture.

PHRASE_ECRITURE_NON_PROPOSEE = (
    "Aucune carte de confirmation n'a été ouverte : rien n'a été écrit dans Moduléo. "
    "Reformulez la demande d'écriture si besoin."
)
PHRASE_CARTE_OUVERTE = "Confirmez ou annulez sur la carte : rien n'est écrit dans Moduléo avant votre confirmation."

_PHRASES = re.compile(r"[^.!?\n]+[.!?]*\s*")
_CARTE = re.compile(r"\bcartes?\s+de\s+confirmation\b", re.IGNORECASE)
_BOUTON = re.compile(
    r"\b(?:valid|confirm)\w*\s+pour\s+(?:l['’]\s*)?(?:appliquer|enregistrer|écrire|ecrire|envoyer)\b", re.IGNORECASE
)
# Une route d'écriture (« POST moduleo/tacheafaire ») ou un bloc JSON de
# requête (« "route": … », « "corps": … »).
_ROUTE = re.compile(r"\b(?:POST|PUT|DELETE)\s+[a-z]+/\w|\"(?:route|methode|corps)\"\s*:", re.IGNORECASE)
_FAITE = re.compile(
    r"\b(?:cré|écrit|ecrit|ajout|modifi|supprim|enregistr|mis\s+à\s+jour|saisi|déplac|deplac)\w*"
    r"\s+(?:dans|sur)\s+(?:le\s+logiciel\s+)?modul[eé]o\b",
    re.IGNORECASE,
)
# Une lecture, pas une écriture (#258, second passage de #206) : une
# négation dans la même proposition (« Aucun contact … n'est enregistré
# dans Moduléo »), ou un état lu sur une fiche (« l'affaire est enregistrée
# dans Moduléo »), sans « a été ».
_PROPOSITION = re.compile(r"[^,;:]*$")
_NEGATION = re.compile(r"\b(?:n['’]|ne\b|aucun|aucune|ni\b)", re.IGNORECASE)
_CONSTAT = re.compile(r"\b(?:est|sont)\s+(?:bien\s+|déjà\s+|deja\s+)?$", re.IGNORECASE)


def annonce_une_carte(reponse: str) -> bool:
    # Une carte, un bouton ou une requête d'écriture écrits par le modèle.
    return any(motif.search(reponse) for motif in (_CARTE, _BOUTON, _ROUTE))


def affirme_une_ecriture(reponse: str) -> bool:
    # « créé / écrit / modifié / supprimé dans Moduléo », hors lecture.
    return any(_affirme(phrase) for phrase in _PHRASES.findall(reponse))


def _affirme(phrase: str) -> bool:
    for faite in _FAITE.finditer(phrase):
        avant = _PROPOSITION.search(phrase[: faite.start()]).group()
        if not _NEGATION.search(avant) and not _CONSTAT.search(avant):
            return True
    return False


def retirer_ecriture_affirmee(reponse: str) -> str:
    # Avec une carte ouverte, rien n'est encore écrit : chaque phrase qui
    # dit le contraire part. Plus rien : la phrase de la carte.
    sans = "".join(phrase for phrase in _PHRASES.findall(reponse) if not _affirme(phrase)).strip()
    if sans == reponse.strip():
        return reponse
    return sans or PHRASE_CARTE_OUVERTE

