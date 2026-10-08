import logging
from typing import Any

from vm_centrale.lectures_outils import Fiche, enregistrer_lectures
from vm_centrale.moduleo.client import (
    ErreurModuleo,
    LecteurModuleo,
    ModuleoIntrouvable,
    ModuleoRefuse,
    RequeteInterdite,
)
from vm_centrale.moduleo.fiches import fiche_affaire, reference_affaire
from vm_centrale.moduleo.resolution import Noms, resoudre_communes, resoudre_contacts, resoudre_utilisateurs
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.statut_tour import CONSULTATION_MODULEO

_NOM = "chercher_affaires_moduleo"
# Fiches renvoyées au modèle (spec 1.5.0) : 5 par défaut, 10 au plus.
_NB_DEFAUT = 5
_NB_PLAFOND = 10
# Ids demandés à la recherche par texte, pour dire combien d'affaires
# correspondent au-delà des fiches affichées ; limite des routes `multi`.
_IDS_MAX = 200

_ROUTE_NUMERO = "cogeo/affaire/numeroAffaire?numAffaire={numAffaire}"
_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/affaire?texte="))
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"
_ROUTE_INTERVENANTS_AFFAIRE = "cogeo/affaire/{idAffaire}/intervenants"
_ROUTE_INTERVENANTS = "cogeo/intervenant/multi?ids={ids}"

# Phrases fixes au modèle (spec 1.5.0) : le détail technique ne va qu'à
# l'inspecteur.
INDISPONIBLE = "Moduléo est indisponible pour le moment."
REFUS = "Moduléo refuse l'accès à cette donnée."
_AUCUNE_AFFAIRE = "Aucune affaire Moduléo ne correspond à cette recherche."
_RIEN_A_CHERCHER = "Donne un numéro d'affaire ou un texte à chercher dans Moduléo."

logger = logging.getLogger(__name__)

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des affaires dans Moduléo, le logiciel de gestion du cabinet, "
            "par numéro ou par texte. Renvoie une fiche par affaire : numéro, objet, "
            "état, dates, adresse, commune, client, représentant, responsable, "
            "chargé d'affaire et intervenants avec leur qualité. À utiliser pour "
            "toute question sur une affaire du cabinet : ces données ne sont pas "
            "sur Internet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {
                    "type": "string",
                    "description": "Le numéro exact de l'affaire (ex. « 2024-123 »), s'il est connu.",
                },
                "texte": {
                    "type": "string",
                    "description": (
                        "Sans numéro : un mot de l'objet, de l'adresse ou du client de l'affaire."
                    ),
                },
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de fiches voulues, {_NB_DEFAUT} par défaut, {_NB_PLAFOND} au plus."
                    ),
                },
            },
        },
    },
}


def _declarer(contexte: ContexteTour) -> dict | None:
    # Pour tous les comptes, dès que Moduléo est configuré (spec 1.5.0).
    return _SCHEMA if contexte.client_moduleo is not None else None


class _LecteurTrace:
    # Chaque route lue, avec ses paramètres, pour l'inspecteur. Jamais les
    # en-têtes : la clé et le SecurityCode restent dans ClientModuleo.
    def __init__(self, lecteur: LecteurModuleo) -> None:
        self._lecteur = lecteur
        self.routes: list[dict[str, Any]] = []

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        self.routes.append({"route": route, "parametres": parametres or {}})
        return self._lecteur.lire(route, parametres)


def _nb_max(valeur: Any) -> int:
    try:
        nombre = int(valeur) if valeur is not None else _NB_DEFAUT
    except (TypeError, ValueError):
        nombre = _NB_DEFAUT
    return min(max(nombre, 1), _NB_PLAFOND)


def _chercher(lecteur: LecteurModuleo, numero: str, texte: str) -> list[int]:
    # Ids des affaires trouvées, dans l'ordre de Moduléo.
    if numero:
        try:
            id_affaire = lecteur.lire(_ROUTE_NUMERO, {"numAffaire": numero})
        except ModuleoIntrouvable:
            return []
        return [int(id_affaire)] if id_affaire else []
    return [int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, {"texte": texte, "nbMaxResultats": _IDS_MAX})]


def _fiches(lecteur: LecteurModuleo, ids: list[int]) -> list[Fiche]:
    affaires = {affaire["IdAffaire"]: affaire for affaire in lecteur.lire(_ROUTE_AFFAIRES, {"ids": _liste(ids)})}
    ids_intervenants = [
        id_intervenant
        for id_affaire in ids
        if id_affaire in affaires
        for id_intervenant in lecteur.lire(_ROUTE_INTERVENANTS_AFFAIRE, {"idAffaire": id_affaire})
    ]
    intervenants = lecteur.lire(_ROUTE_INTERVENANTS, {"ids": _liste(ids_intervenants)}) if ids_intervenants else []
    # Tous les noms de l'appel d'un coup, dédoublonnés.
    noms = Noms(
        utilisateurs=resoudre_utilisateurs(
            lecteur, [a.get(champ) for a in affaires.values() for champ in ("IdResponsable", "IdActeurEnCharge")]
        ),
        contacts=resoudre_contacts(
            lecteur,
            [a.get(champ) for a in affaires.values() for champ in ("IdClient", "IdRepresentant")]
            + [i.get(champ) for i in intervenants for champ in ("IdContact", "IdRepresentant")],
        ),
        communes=resoudre_communes(lecteur, [a.get("IdCommune") for a in affaires.values()]),
    )
    return [
        Fiche(
            reference_affaire(affaires[id_affaire]),
            fiche_affaire(
                affaires[id_affaire],
                [intervenant for intervenant in intervenants if intervenant.get("IdAffaire") == id_affaire],
                noms,
            ),
        )
        for id_affaire in ids
        if id_affaire in affaires
    ]


def _liste(ids: list[int]) -> str:
    # Séparateur des routes `multi` : la virgule.
    return ",".join(str(i) for i in dict.fromkeys(ids))


def _contenu(fiches: list[Fiche], trouvees: int) -> str:
    entete = ""
    if trouvees > len(fiches):
        plus = "Au moins " if trouvees >= _IDS_MAX else ""
        entete = f"{plus}{trouvees} affaires trouvées, {len(fiches)} affichées, précise la recherche.\n\n"
    return entete + "\n\n".join(fiche.texte for fiche in fiches)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    numero = str(arguments.get("numero") or "").strip()
    texte = str(arguments.get("texte") or "").strip()
    if contexte.client_moduleo is None or not (numero or texte):
        return ResultatOutil(_RIEN_A_CHERCHER)
    contexte.publier(CONSULTATION_MODULEO)
    lecteur = _LecteurTrace(contexte.client_moduleo)
    try:
        ids = _chercher(lecteur, numero, texte)
        fiches = _fiches(lecteur, ids[: _nb_max(arguments.get("nb_max"))]) if ids else []
    except ModuleoRefuse as erreur:
        logger.warning("Moduléo refuse la lecture : %s", erreur)
        return ResultatOutil(REFUS, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    except (ErreurModuleo, RequeteInterdite, KeyError, TypeError, ValueError, AttributeError) as erreur:
        # Jamais de 500 ni de nouvelle tentative (spec 1.5.0) : panne, ou
        # réponse qui n'a pas la forme attendue.
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    trace = {"routes": lecteur.routes, "trouvees": len(ids), "fiches": [fiche.texte for fiche in fiches]}
    if not fiches:
        return ResultatOutil(_AUCUNE_AFFAIRE, trace=trace)
    enregistrer_lectures(contexte.db, contexte.conversation_id, "moduleo", fiches)
    return ResultatOutil(_contenu(fiches, len(ids)), trace=trace)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
