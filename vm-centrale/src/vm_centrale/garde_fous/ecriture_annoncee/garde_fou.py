import re
from collections.abc import Iterable

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
# Autres tournures du second passage de #206 (#259) : « prête à être
# confirmée », « validez-la sur la carte qui s'affiche ».
_CARTE_AUTREMENT = re.compile(
    r"\bprêt\w*\s+à\s+être\s+(?:confirm|valid)\w*"
    r"|\bcartes?\s+(?:qui\s+s['’]\s*affiche|ci-dessous|ci-dessus)"
    r"|\b(?:valid|confirm)\w*(?:-(?:la|le|les))?\s+(?:\w+\s+)?sur\s+la\s+carte\b",
    re.IGNORECASE,
)
# Une confirmation demandée en texte (#256, #259) : la carte est la
# confirmation. Pas « Confirmez-vous qu'il s'agit… ? », une clarification.
_QUESTION = re.compile(
    r"\b(?:souhaitez|voulez)[\s-]+vous\s+que\s+je\s+"
    r"(?:procède|procede|crée|cree|ajoute|modifie|supprime|enregistre|saisisse|déplace|deplace"
    r"|mette\s+à\s+jour|écrive|ecrive)\b"
    r"|(?:^|[.!?:\n]\s*)confirmez\s+(?:le|la|les|l['’])\s*"
    r"(?:création|creation|ajout|modification|suppression|enregistrement|saisie|déplacement|deplacement"
    r"|mise\s+à\s+jour|écriture|ecriture)\b",
    re.IGNORECASE,
)
_BOUTON = re.compile(
    r"\b(?:valid|confirm)\w*\s+pour\s+(?:l['’]\s*)?(?:appliquer|enregistrer|écrire|ecrire|envoyer)\b", re.IGNORECASE
)
# Une route d'écriture (« POST moduleo/tacheafaire ») ou un bloc JSON de
# requête (« "route": … », « "corps": … »).
_ROUTE = re.compile(r"\b(?:POST|PUT|DELETE)\s+[a-z]+/\w|\"(?:route|methode|corps)\"\s*:", re.IGNORECASE)
# Une fausse carte en lignes (#259) : « Route : PUT … », « Paramètre :
# idTelephone = 152 », « Corps : … ».
_LIGNE_REQUETE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?\**[ \t]*(?:route|m[ée]thode|param[èe]tres?|corps)[ \t]*\**[ \t]*:",
    re.IGNORECASE | re.MULTILINE,
)
_FAITE = re.compile(
    r"\b(?:cré|écrit|ecrit|ajout|modifi|supprim|enregistr|mis\s+à\s+jour|saisi|déplac|deplac)\w*"
    r"\s+(?:dans|sur)\s+(?:le\s+logiciel\s+)?modul[eé]o\b",
    re.IGNORECASE,
)
# Sans nommer Moduléo (#259) : « La note … est supprimée. », le participe
# en fin de phrase. « La tâche a été créée le 3 mars » est une fiche lue.
_FAITE_SANS_MODULEO = re.compile(
    r"\b(?:est|sont|a|ont)\s+(?:bien\s+)?(?:été\s+)?(?:bien\s+)?"
    r"(?:(?:cré|ajout|modifi|supprim|enregistr|saisi|déplac|deplac)\w*|mis\w*\s+à\s+jour)"
    r"(?:\s+avec\s+succès)?\s*(?:[.!]|$)",
    re.IGNORECASE,
)
# Un élément nommé, et le début du segment de ses routes (« moduleo/
# telephone », « cogeo/note/{idNote} ») : après une confirmation, seul le
# résultat de son élément peut être redit (#259).
_ELEMENTS = tuple(
    (segment, re.compile(rf"\b(?:{motif})\b", re.IGNORECASE))
    for segment, motif in (
        ("telephone", r"t[ée]l[ée]phones?|num[ée]ros?"),
        ("email", r"e-?mails?|courriels?"),
        ("adresse", r"adresses?"),
        ("note", r"notes?"),
        ("tache", r"t[âa]ches?"),
        ("contact", r"contacts?"),
        ("affaire", r"affaires?"),
        ("tempspasse", r"temps\s+pass[ée]s?"),
        ("devis", r"devis"),
        ("frais", r"frais"),
        ("archive", r"archives?"),
        ("dossier", r"dossiers?"),
    )
)
# Une lecture, pas une écriture (#258, second passage de #206) : une
# négation dans la même proposition (« Aucun contact … n'est enregistré
# dans Moduléo »), ou un état lu sur une fiche (« l'affaire est enregistrée
# dans Moduléo »), sans « a été ».
_PROPOSITION = re.compile(r"[^,;:]*$")
_NEGATION = re.compile(r"\b(?:n['’]|ne\b|aucun|aucune|ni\b)", re.IGNORECASE)
_CONSTAT = re.compile(r"\b(?:est|sont)\s+(?:bien\s+|déjà\s+|deja\s+)?$", re.IGNORECASE)
# Sans Moduléo non plus (troisième passage de #206) : « L'affaire SCPT-0010
# est enregistrée. » décrit la fiche lue ; « est supprimée. » reste affirmé.
_ETAT_LU = re.compile(r"(?:est|sont)\s+enregistr", re.IGNORECASE)


def annonce_une_carte(reponse: str) -> bool:
    # Une carte, un bouton, une requête d'écriture ou une confirmation
    # demandée, écrits par le modèle.
    motifs = (_CARTE, _CARTE_AUTREMENT, _QUESTION, _BOUTON, _ROUTE, _LIGNE_REQUETE)
    return any(motif.search(reponse) for motif in motifs)


def affirme_une_ecriture(reponse: str, routes_confirmees: Iterable[str] = ()) -> bool:
    # « créé / écrit / modifié / supprimé dans Moduléo », ou « est
    # supprimée. », hors lecture. `routes_confirmees` : celles des écritures
    # confirmées de la Conversation, dont le résultat peut être redit.
    routes = list(routes_confirmees)
    return any(
        _affirme(phrase) and not (routes and _redit_un_resultat(phrase, routes))
        for phrase in _PHRASES.findall(reponse)
    )


def _affirme(phrase: str) -> bool:
    for faite in _FAITE.finditer(phrase):
        avant = _PROPOSITION.search(phrase[: faite.start()]).group()
        if not _NEGATION.search(avant) and not _CONSTAT.search(avant):
            return True
    for faite in _FAITE_SANS_MODULEO.finditer(phrase):
        if _ETAT_LU.match(faite.group()):
            continue
        if not _NEGATION.search(_PROPOSITION.search(phrase[: faite.start()]).group()):
            return True
    return False


def _redit_un_resultat(phrase: str, routes_confirmees: list[str]) -> bool:
    # Sans élément nommé (« Écrit dans Moduléo. »), ou l'élément d'une
    # écriture confirmée (« le numéro est enregistré » après un téléphone).
    nommes = [segment for segment, motif in _ELEMENTS if motif.search(phrase)]
    segments = [route.split("/")[1] if "/" in route else route for route in routes_confirmees]
    return not nommes or any(segment.startswith(nomme) for nomme in nommes for segment in segments)


def _decrit_une_requete(phrase: str) -> bool:
    return bool(_ROUTE.search(phrase) or _LIGNE_REQUETE.search(phrase))


def retirer_ecriture_affirmee(reponse: str) -> str:
    # Avec une carte ouverte, rien n'est encore écrit : chaque phrase qui
    # dit le contraire part, et chaque route, paramètre ou corps décrit en
    # texte (#259), qui ferait une fausse carte à côté de la vraie. Plus
    # rien : la phrase de la carte.
    phrases = _PHRASES.findall(reponse)
    sans = "".join(phrase for phrase in phrases if not _affirme(phrase) and not _decrit_une_requete(phrase)).strip()
    if sans == reponse.strip():
        return reponse
    return sans or PHRASE_CARTE_OUVERTE
