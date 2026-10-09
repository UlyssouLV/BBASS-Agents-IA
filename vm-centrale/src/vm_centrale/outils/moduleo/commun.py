import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vm_centrale.lectures_outils import Fiche, enregistrer_lectures
from vm_centrale.moduleo.client import (
    ClientModuleo,
    ErreurModuleo,
    LecteurModuleo,
    ModuleoIntrouvable,
    ModuleoRefuse,
    RequeteInterdite,
)
from vm_centrale.moduleo.droits import DroitManquant, DroitsModuleo, autorise, verifier
from vm_centrale.moduleo.resolution import NomNonResolu
from vm_centrale.outils.base import ContexteTour, ResultatOutil
from vm_centrale.statut_tour import consultation_moduleo

# Ce que les outils Moduléo partagent (spec 1.5.0) : plafond des fiches,
# trace des routes, phrases de panne / refus, garde des droits (1.5.1),
# enregistrement des lectures.
# Règles : README.md.

# Fiches renvoyées au modèle : 5 par défaut, 10 au plus.
NB_DEFAUT = 5
NB_PLAFOND = 10
# Ids demandés à une recherche, pour dire combien d'éléments correspondent
# au-delà des fiches affichées ; limite des routes `multi`.
IDS_MAX = 200

# Phrases fixes au modèle : le détail technique ne va qu'à l'inspecteur.
INDISPONIBLE = "Moduléo est indisponible pour le moment."
REFUS = "Moduléo refuse l'accès à cette donnée."

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lecture:
    # Ce que lit un outil : les ids trouvés, les fiches des premiers et,
    # pour les outils à totaux (#189), la synthèse calculée par la VM sur
    # l'ensemble trouvé. Elle remplace l'en-tête « N trouvés » et elle est
    # enregistrée comme une fiche, avant elles.
    ids: list[int]
    fiches: list[Fiche]
    synthese: Fiche | None = None


class LecteurTrace:
    # Chaque route lue, avec ses paramètres, pour l'inspecteur. Jamais les
    # en-têtes : la clé et le SecurityCode restent dans TransportHttp. Une
    # route refusée par le garde des droits n'est pas tracée : elle n'est
    # pas partie. Sûr entre threads : les outils lisent en parallèle (#176).
    def __init__(self, client: ClientModuleo, droits: DroitsModuleo) -> None:
        self._client = client
        self._droits = droits
        self._verrou = threading.Lock()
        self.routes: list[dict[str, Any]] = []

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        verifier(route, self._droits)
        with self._verrou:
            self.routes.append({"route": route, "parametres": parametres or {}})
        return self._client.lire(route, parametres, self._droits)


def propose(contexte: ContexteTour, route: str) -> bool:
    # Outil proposé au modèle (spec 1.5.1) : Moduléo configuré et `route`,
    # la recherche de l'outil, autorisée par le garde des droits pour ce
    # compte. Sans groupe, aucun outil Moduléo, même pour un compte
    # administrateur.
    return contexte.client_moduleo is not None and autorise(route, contexte.droits_moduleo)


def refus_du_garde(contexte: ContexteTour, route: str) -> ResultatOutil | None:
    # Revérifié à l'exécution, avant toute lecture (même libre) : un outil
    # non proposé peut être appelé.
    try:
        verifier(route, contexte.droits_moduleo)
    except DroitManquant as refus:
        return _refuse(refus, [])
    return None


def _refuse(refus: DroitManquant, routes: list[dict[str, Any]]) -> ResultatOutil:
    logger.info("Garde des droits Moduléo : %s", refus.refus)
    return ResultatOutil(refus.phrase, trace={"routes": routes, "garde_des_droits": refus.refus})


def nb_max(valeur: Any) -> int:
    try:
        nombre = int(valeur) if valeur is not None else NB_DEFAUT
    except (TypeError, ValueError):
        nombre = NB_DEFAUT
    return min(max(nombre, 1), NB_PLAFOND)


def lire_argument(arguments: dict, nom: str) -> str:
    return str(arguments.get(nom) or "").strip()


# Formats de date acceptés du modèle ; l'API reçoit AAAA-MM-JJ.
_FORMATS_DATE = ("%Y-%m-%d", "%d/%m/%Y")


def date_api(valeur: str) -> str:
    # Une date illisible lève NomNonResolu : jamais une recherche sans le
    # filtre demandé.
    for format_date in _FORMATS_DATE:
        try:
            return datetime.strptime(valeur, format_date).date().isoformat()
        except ValueError:
            continue
    raise NomNonResolu(f"Date « {valeur} » illisible : donne-la au format AAAA-MM-JJ. Recherche non lancée.")


def booleen(valeur: Any) -> bool | None:
    # Booléen du schéma ; le modèle écrit parfois « true » en texte.
    if isinstance(valeur, bool):
        return valeur
    return {"true": True, "false": False}.get(str(valeur).strip().casefold()) if valeur is not None else None


def liste_ids(ids: list[int]) -> str:
    # Séparateur des routes `multi` : la virgule.
    return ",".join(str(i) for i in dict.fromkeys(ids))


def lire_par_lots(lecteur: LecteurModuleo, route: str, ids: list[int]) -> list[dict]:
    # Tous les éléments de `ids` par une route `multi`, par lots de
    # IDS_MAX (limite de la route) : les totaux portent sur tout l'ensemble
    # trouvé (#189).
    uniques = list(dict.fromkeys(ids))
    return [
        element
        for debut in range(0, len(uniques), IDS_MAX)
        for element in lecteur.lire(route, {"ids": liste_ids(uniques[debut : debut + IDS_MAX])})
    ]


_ROUTE_NUMERO_AFFAIRE = "cogeo/affaire/numeroAffaire?numAffaire={numAffaire}"


def id_affaire(lecteur: LecteurModuleo, numero: str) -> int:
    # Numéro d'affaire → id ; inconnu : NomNonResolu, recherche non lancée.
    try:
        id_trouve = lecteur.lire(_ROUTE_NUMERO_AFFAIRE, {"numAffaire": numero})
    except ModuleoIntrouvable:
        id_trouve = None
    if not id_trouve:
        raise NomNonResolu(f"Aucune affaire Moduléo ne porte le numéro « {numero} » : recherche non lancée.")
    return int(id_trouve)


def lire_fiches(
    contexte: ContexteTour,
    client: ClientModuleo,
    domaine: str,
    lire: Callable[[LecteurModuleo], tuple[list[int], list[Fiche]] | Lecture],
    aucun: str,
    trouves: str,
    sans_lecture: str,
    entete_toujours: bool = False,
) -> ResultatOutil:
    # `client` : celui du contexte, déjà vérifié ; `domaine` : celui du
    # statut (« affaires »). `lire` : les ids trouvés
    # et les fiches des premiers. `aucun` : la phrase sans résultat ;
    # `trouves` : « {n} affaires trouvées, {m} affichées », en tête quand il
    # y a plus d'ids que de fiches, ou toujours avec `entete_toujours`.
    # `sans_lecture` : ajoutée à la phrase d'un nom non résolu (#182).
    # `lire` peut aussi renvoyer une `Lecture` avec sa synthèse.
    contexte.publier(consultation_moduleo(domaine))
    lecteur = LecteurTrace(client, contexte.droits_moduleo)
    try:
        lu = lire(lecteur)
    except DroitManquant as refus:
        return _refuse(refus, lecteur.routes)
    except NomNonResolu as erreur:
        return ResultatOutil(
            f"{erreur} {sans_lecture}", trace={"routes": lecteur.routes, "non_resolu": str(erreur)}
        )
    except ModuleoRefuse as erreur:
        logger.warning("Moduléo refuse la lecture : %s", erreur)
        return ResultatOutil(REFUS, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    except (ErreurModuleo, RequeteInterdite, KeyError, TypeError, ValueError, AttributeError) as erreur:
        # Jamais de 500 ni de nouvelle tentative : panne, ou réponse qui n'a
        # pas la forme attendue.
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    lecture = lu if isinstance(lu, Lecture) else Lecture(*lu)
    ids, fiches = lecture.ids, lecture.fiches
    trace = {"routes": lecteur.routes, "trouvees": len(ids), "fiches": [fiche.texte for fiche in fiches]}
    if not fiches:
        return ResultatOutil(aucun, trace=trace)
    if lecture.synthese is not None:
        trace["synthese"] = lecture.synthese.texte
        enregistrer_lectures(contexte.db, contexte.conversation_id, "moduleo", [lecture.synthese, *fiches])
        return ResultatOutil(
            "\n\n".join(fiche.texte for fiche in (lecture.synthese, *fiches)), trace=trace
        )
    enregistrer_lectures(contexte.db, contexte.conversation_id, "moduleo", fiches)
    entete = ""
    if len(ids) > len(fiches) or entete_toujours:
        plus = "Au moins " if len(ids) >= IDS_MAX else ""
        precise = ", précise la recherche" if len(ids) > len(fiches) else ""
        entete = f"{plus}{trouves.format(n=len(ids), m=len(fiches))}{precise}.\n\n"
    return ResultatOutil(entete + "\n\n".join(fiche.texte for fiche in fiches), trace=trace)
