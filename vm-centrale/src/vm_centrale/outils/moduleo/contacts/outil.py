from concurrent.futures import ThreadPoolExecutor
from typing import Any

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo.client import LecteurModuleo, ModuleoIntrouvable
from vm_centrale.moduleo.enumerations import TYPES_CONTACT, nom_api
from vm_centrale.moduleo.fiches import DetailsContact, fiche_contact
from vm_centrale.moduleo.resolution import NomNonResolu, chercher_qualifications, resoudre_communes
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import (
    IDS_MAX,
    NB_DEFAUT,
    NB_PLAFOND,
    SANS_GROUPE_COGEO,
    liste_ids,
    lire_argument,
    lire_fiches,
    nb_max,
    propose_cogeo,
)

_NOM = "chercher_contacts_moduleo"

_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/contact?texte="))
_ROUTE_CONTACTS = "cogeo/contact/multi?ids={ids}"
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"
# Coordonnées d'un contact : route de ses ids, puis route de la fiche de
# chacun et son paramètre de chemin.
_COORDONNEES = {
    "telephones": ("cogeo/contact/{idContact}/telephones", "moduleo/telephone/{idTelephone}", "idTelephone"),
    "emails": ("cogeo/contact/{idContact}/emails", "cogeo/email/{idEmail}", "idEmail"),
    "adresses": ("cogeo/contact/{idContact}/adresses", "moduleo/adresse/{idAdresse}", "idAdresse"),
}
# Affaires où le contact apparaît : client, intervenant.
_AFFAIRES = {
    "affaires_client": "cogeo/contact/{idContact}/affaires",
    "affaires_intervenant": "cogeo/contact/{idContact}/affaireintervenant",
}
# Lectures par contact en parallèle (spec 1.5.0) : au plus 10 contacts × 4.
_LECTURES_PARALLELES = 16

_AUCUN_CONTACT = "Aucun contact Moduléo ne correspond à cette recherche."
_TROUVES = "{n} contacts trouvés, {m} affichés"
# Ajoutée à toute phrase de l'outil qui n'a rien lu (#182).
_SANS_LECTURE = (
    "Aucune lecture faite dans Moduléo : n'invente aucun contact, demande au collaborateur "
    "un nom, un type ou une qualification."
)
_RIEN_A_CHERCHER = f"Donne un texte (nom du contact), un type ou une qualification à chercher. {_SANS_LECTURE}"

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des contacts (clients, notaires, entreprises, collectivités…) dans Moduléo, "
            "le logiciel de gestion du cabinet, par nom ou texte, type de contact, type de donneur "
            "d'ordre ou qualifications, donnés en noms. Renvoie une fiche par contact : type, nom, "
            "téléphones, emails, adresses et numéros des affaires où il est client ou intervenant. "
            "À utiliser pour joindre un contact du cabinet ou retrouver ses affaires : ces données "
            "ne sont pas sur Internet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texte": {
                    "type": "string",
                    "description": "Le nom du contact, ou un mot de son nom (ex. « Dupont »).",
                },
                "type_contact": {
                    "type": "string",
                    "enum": ["personne", "société", "collectivité", "groupe de contacts"],
                    "description": "Type du contact.",
                },
                "type_donneur_ordre": {
                    "type": "string",
                    "description": "Type de donneur d'ordre tel que Moduléo le nomme.",
                },
                "qualifications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Qualifications du contact, en noms (ex. « Notaire », « Syndic »).",
                },
                "nb_max": {
                    "type": "integer",
                    "description": f"Nombre de fiches voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus.",
                },
            },
        },
    },
}


def _declarer(contexte: ContexteTour) -> dict | None:
    # Moduléo configuré, compte rattaché à un groupe Cogeo (spec 1.5.1).
    return _SCHEMA if propose_cogeo(contexte) else None


def _type_contact(valeur: str) -> str:
    # Type dit par le modèle → nom de l'énumération en filtre
    # (moduleo/enumerations.py, relevé #180).
    if (nom := nom_api(TYPES_CONTACT, valeur)) is None:
        raise NomNonResolu(
            f"Type de contact « {valeur} » inconnu : personne, société, collectivité ou groupe de contacts. "
            "Recherche non lancée."
        )
    return nom


def _qualifications(arguments: dict) -> list[str]:
    # Un tableau de noms ; une chaîne seule est tolérée.
    valeur = arguments.get("qualifications") or []
    noms = [valeur] if isinstance(valeur, str) else valeur
    return [nom for nom in (str(n).strip() for n in noms) if nom]


def _chercher(lecteur: LecteurModuleo, parametres: dict[str, Any], qualifications: list[str]) -> list[int]:
    if qualifications:
        parametres = {**parametres, "idsQualifications": chercher_qualifications(lecteur, qualifications)}
    ids = [int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, {**parametres, "nbMaxResultat": IDS_MAX})]
    return list(dict.fromkeys(ids))


def _coordonnees(lecteur: LecteurModuleo, id_contact: int, genre: str) -> list[dict]:
    route_ids, route_fiche, parametre = _COORDONNEES[genre]
    fiches = []
    for id_coordonnee in lecteur.lire(route_ids, {"idContact": id_contact}):
        try:
            fiches.append(lecteur.lire(route_fiche, {parametre: id_coordonnee}))
        except ModuleoIntrouvable:
            continue
    return fiches


def _numeros_affaires(lecteur: LecteurModuleo, id_contact: int) -> dict[str, list[str]]:
    # Numéros seulement, des deux rôles en une lecture `multi` : les fiches
    # d'affaires sont celles de l'autre outil. Au plus 200 ids, la limite
    # des routes `multi`.
    ids = {role: [int(i) for i in lecteur.lire(route, {"idContact": id_contact})] for role, route in _AFFAIRES.items()}
    tous = list(dict.fromkeys(i for ids_role in ids.values() for i in ids_role))[:IDS_MAX]
    lues = lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(tous)}) if tous else []
    numeros = {affaire["IdAffaire"]: affaire.get("Numero") for affaire in lues}
    return {role: [numeros[i] for i in ids_role if i in numeros] for role, ids_role in ids.items()}


def _lire(lecteur: LecteurModuleo, id_contact: int, genre: str) -> Any:
    # Un contact supprimé entre la recherche et ses lectures (404) n'a ni
    # coordonnées ni affaires : jamais une panne pour toute la recherche.
    try:
        if genre in _COORDONNEES:
            return _coordonnees(lecteur, id_contact, genre)
        return _numeros_affaires(lecteur, id_contact)
    except ModuleoIntrouvable:
        return [] if genre in _COORDONNEES else {role: [] for role in _AFFAIRES}


def _fiches(lecteur: LecteurModuleo, ids: list[int]) -> list[Fiche]:
    contacts = {contact["IdContact"]: contact for contact in lecteur.lire(_ROUTE_CONTACTS, {"ids": liste_ids(ids)})}
    trouves = [id_contact for id_contact in ids if id_contact in contacts]
    taches = [(id_contact, genre) for id_contact in trouves for genre in (*_COORDONNEES, "affaires")]
    # Une panne dans un thread remonte ici, à la lecture de son résultat.
    with ThreadPoolExecutor(max_workers=min(len(taches), _LECTURES_PARALLELES) or 1) as executeur:
        lu = dict(zip(taches, executeur.map(lambda tache: _lire(lecteur, *tache), taches)))
    details = {
        id_contact: DetailsContact(
            **{genre: lu[(id_contact, genre)] for genre in _COORDONNEES}, **lu[(id_contact, "affaires")]
        )
        for id_contact in trouves
    }
    communes = resoudre_communes(
        lecteur, [adresse.get("IdCommune") for d in details.values() for adresse in d.adresses]
    )
    return [fiche_contact(contacts[i], details[i], communes) for i in trouves]


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    if contexte.droits_moduleo.groupe_cogeo is None:
        # Revérifié à l'exécution : un outil non proposé peut être appelé.
        return ResultatOutil(SANS_GROUPE_COGEO)
    texte = lire_argument(arguments, "texte")
    donneur = lire_argument(arguments, "type_donneur_ordre")
    qualifications = _qualifications(arguments)
    try:
        type_contact = _type_contact(valeur) if (valeur := lire_argument(arguments, "type_contact")) else ""
    except NomNonResolu as erreur:
        return ResultatOutil(f"{erreur} {_SANS_LECTURE}", trace={"routes": [], "non_resolu": str(erreur)})
    if contexte.client_moduleo is None or not (texte or type_contact or donneur or qualifications):
        return ResultatOutil(_RIEN_A_CHERCHER)
    parametres = {
        nom: valeur
        for nom, valeur in (("texte", texte), ("typeContact", type_contact), ("typeDonneurOrdreGE", donneur))
        if valeur
    }

    def lire(lecteur: LecteurModuleo) -> tuple[list[int], list[Fiche]]:
        ids = _chercher(lecteur, parametres, qualifications)
        return ids, _fiches(lecteur, ids[: nb_max(arguments.get("nb_max"))]) if ids else []

    return lire_fiches(contexte, contexte.client_moduleo, lire, _AUCUN_CONTACT, _TROUVES, _SANS_LECTURE)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
