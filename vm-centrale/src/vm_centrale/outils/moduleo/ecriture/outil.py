import json
import logging
from typing import Any

from vm_centrale.moduleo.carte import lignes_en_noms
from vm_centrale.moduleo.client import ErreurModuleo, RequeteInterdite
from vm_centrale.moduleo.droits import DroitManquant, ecriture_possible
from vm_centrale.moduleo.ecritures import REFUSEE, carte_de, proposer
from vm_centrale.moduleo.routes import ROUTES_ECRITURE, RouteEcriture
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import INDISPONIBLE, LecteurTrace
from vm_centrale.statut_tour import consultation_moduleo

# Écriture Moduléo (spec 1.5.2, #204, ADR-0019) : deux outils génériques.
# `decrire_ecriture_moduleo` donne les champs d'une route sans appeler
# Moduléo ; `ecrire_moduleo` propose l'écriture (Carte de confirmation),
# n'envoie rien. Règles : README.md.

_DECRIRE = "decrire_ecriture_moduleo"
_ECRIRE = "ecrire_moduleo"

# Méthodes ouvertes aux outils : les POST d'abord (#204) ; PUT et DELETE
# attendent leur carte détaillée (différences, fiche entière, #205).
_METHODES_OUVERTES = ("POST",)

PROPOSEE = "Écriture proposée au collaborateur, en attente de sa confirmation. Rien n'a été écrit."
_ROUTE_INCONNUE = (
    "Route d'écriture Moduléo inconnue ou fermée : « {route} ». Choisis une route listée dans la "
    "description de ecrire_moduleo, sous la forme « MÉTHODE route ». Rien n'a été écrit."
)
_NON_PROPOSEE = "Écriture non proposée : {erreur} Rien n'a été écrit."
_JSON_ILLISIBLE = "« {nom} » n'est pas un objet JSON valide."
_SANS_MOT = "Ne dis jamais que l'écriture est faite : seul le collaborateur la confirme, sur la carte."

logger = logging.getLogger(__name__)


def _routes_ouvertes(contexte: ContexteTour) -> list[RouteEcriture]:
    # Barrière serveur de test et réglage (client), puis routes que le
    # garde des droits peut ouvrir au compte.
    client = contexte.client_moduleo
    if client is None or not client.ecriture_ouverte():
        return []
    return [
        decrite
        for (methode, route), decrite in sorted(ROUTES_ECRITURE.items())
        if methode in _METHODES_OUVERTES and ecriture_possible(methode, route, contexte.droits_moduleo)
    ]


def _nom_route(decrite: RouteEcriture) -> str:
    return f"{decrite.methode} {decrite.route}"


def _route_connue(nom: Any) -> RouteEcriture | None:
    # « POST moduleo/telephone » → la route du WADL, d'une méthode ouverte.
    methode, _, route = str(nom or "").strip().partition(" ")
    cle = (methode.upper(), route.strip())
    return ROUTES_ECRITURE.get(cle) if cle[0] in _METHODES_OUVERTES else None


def _route_ouverte(contexte: ContexteTour, nom: Any) -> RouteEcriture | None:
    # La route, si elle est aussi ouverte au compte.
    decrite = _route_connue(nom)
    return decrite if decrite is not None and decrite in _routes_ouvertes(contexte) else None


_ARGUMENT_ROUTE = {
    "type": "string",
    "description": "Route d'écriture, « MÉTHODE route » telle que listée par ecrire_moduleo (« POST moduleo/telephone »).",
}


def _declarer_decrire(contexte: ContexteTour) -> dict | None:
    if not _routes_ouvertes(contexte):
        return None
    return {
        "type": "function",
        "function": {
            "name": _DECRIRE,
            "description": (
                "Donne les champs attendus par une route d'écriture Moduléo : paramètres de la route, "
                "exemple de corps JSON et description. N'appelle pas Moduléo. À appeler avant "
                "ecrire_moduleo pour connaître le corps à envoyer."
            ),
            "parameters": {
                "type": "object",
                "properties": {"route": _ARGUMENT_ROUTE},
                "required": ["route"],
            },
        },
    }


def _executer_decrire(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    nom = arguments.get("route")
    decrite = _route_ouverte(contexte, nom)
    if decrite is None:
        return ResultatOutil(_ROUTE_INCONNUE.format(route=nom or ""))
    parametres = ", ".join(f"{p} ({t})" for p, t in decrite.parametres.items()) or "aucun"
    corps = (
        f"Exemple de corps JSON (valeurs d'exemple à remplacer, champs inutiles à omettre) :\n{decrite.exemple}"
        if decrite.exemple is not None
        else "Pas de corps."
    )
    return ResultatOutil(f"{_nom_route(decrite)} : {decrite.description}\nParamètres : {parametres}\n{corps}")


def _declarer_ecrire(contexte: ContexteTour) -> dict | None:
    routes = _routes_ouvertes(contexte)
    if not routes:
        return None
    liste = "\n".join(f"{_nom_route(decrite)} — {decrite.description}" for decrite in routes)
    return {
        "type": "function",
        "function": {
            "name": _ECRIRE,
            "description": (
                "Propose une écriture dans Moduléo (serveur de test) quand le collaborateur la demande. "
                "N'envoie rien : le collaborateur voit une carte de confirmation et décide lui-même. "
                "Désigne chaque élément par son id lu dans une fiche ([id Moduléo <n>]) ; demande "
                "d'abord les champs avec decrire_ecriture_moduleo. Une écriture par appel. "
                f"Routes ouvertes :\n{liste}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "route": _ARGUMENT_ROUTE,
                    "parametres": {
                        "type": "object",
                        "description": "Paramètres de la route par nom ({\"idAffaire\": 12}) ; {} si elle n'en a pas.",
                    },
                    "corps": {
                        "type": "object",
                        "description": "Corps JSON de la requête, champs de decrire_ecriture_moduleo.",
                    },
                },
                "required": ["route"],
            },
        },
    }


def _objet(arguments: dict, nom: str, defaut: Any) -> Any:
    # Le modèle envoie parfois un objet en texte JSON.
    valeur = arguments.get(nom, defaut)
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except ValueError:
            raise RequeteInterdite(_JSON_ILLISIBLE.format(nom=nom)) from None
    return valeur


def _executer_ecrire(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    # Une route connue mais fermée au compte va au garde des droits : sa
    # phrase dit quel droit manque.
    client = contexte.client_moduleo
    nom = arguments.get("route")
    decrite = _route_connue(nom)
    if client is None or decrite is None or not _routes_ouvertes(contexte):
        return ResultatOutil(_ROUTE_INCONNUE.format(route=nom or ""))
    methode, route = decrite.methode, decrite.route
    contexte.publier(consultation_moduleo("préparation de l'écriture"))
    lecteur = LecteurTrace(client, contexte.droits_moduleo)
    parametres: dict[str, Any] = {}
    corps: Any = None
    try:
        lus = _objet(arguments, "parametres", {}) or {}
        if not isinstance(lus, dict):
            raise RequeteInterdite(_JSON_ILLISIBLE.format(nom="parametres"))
        parametres, corps = lus, _objet(arguments, "corps", None)
        client.verifier_ecriture(methode, route, parametres, corps, contexte.droits_moduleo)
    except RequeteInterdite as erreur:
        return ResultatOutil(_NON_PROPOSEE.format(erreur=erreur), trace={"route": f"{methode} {route}"})
    except DroitManquant as refus:
        logger.info("Garde des droits Moduléo : %s", refus.refus)
        ecriture = proposer(
            contexte.db,
            contexte.identifiant_compte,
            contexte.conversation_id,
            methode,
            route,
            parametres,
            corps,
            None,
            statut=REFUSEE,
            erreur=refus.phrase,
        )
        return ResultatOutil(
            refus.phrase,
            trace={"route": f"{methode} {route}", "ecriture_id": ecriture.id, "garde_des_droits": refus.refus},
        )
    except ErreurModuleo as erreur:
        # La relecture d'un élément `siens` (garde des droits) a échoué.
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"route": f"{methode} {route}", "erreur": str(erreur)})
    carte = {"titre": decrite.description, "lignes": lignes_en_noms(lecteur, parametres, corps)}
    ecriture = proposer(
        contexte.db,
        contexte.identifiant_compte,
        contexte.conversation_id,
        methode,
        route,
        parametres,
        corps,
        carte,
    )
    carte_envoyee = carte_de(ecriture)
    contexte.publier_carte(carte_envoyee)
    return ResultatOutil(
        f"{PROPOSEE} {_SANS_MOT}",
        trace={
            "route": f"{methode} {route}",
            "parametres": parametres,
            "corps": corps,
            "carte": carte_envoyee,
            "routes": lecteur.routes,
        },
    )


OUTIL_DECRIRE = Outil(nom=_DECRIRE, declarer=_declarer_decrire, executer=_executer_decrire)
OUTIL_ECRIRE = Outil(nom=_ECRIRE, declarer=_declarer_ecrire, executer=_executer_ecrire)
