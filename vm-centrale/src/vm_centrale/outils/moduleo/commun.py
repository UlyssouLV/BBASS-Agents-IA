import logging
import threading
from collections.abc import Callable
from typing import Any

from vm_centrale.lectures_outils import Fiche, enregistrer_lectures
from vm_centrale.moduleo.client import ErreurModuleo, LecteurModuleo, ModuleoRefuse, RequeteInterdite
from vm_centrale.moduleo.resolution import NomNonResolu
from vm_centrale.outils.base import ContexteTour, ResultatOutil
from vm_centrale.statut_tour import CONSULTATION_MODULEO

# Ce que les outils Moduléo partagent (spec 1.5.0) : plafond des fiches,
# trace des routes, phrases de panne / refus, enregistrement des lectures.
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


class LecteurTrace:
    # Chaque route lue, avec ses paramètres, pour l'inspecteur. Jamais les
    # en-têtes : la clé et le SecurityCode restent dans ClientModuleo. Sûr
    # entre threads : les outils lisent en parallèle (#176).
    def __init__(self, lecteur: LecteurModuleo) -> None:
        self._lecteur = lecteur
        self._verrou = threading.Lock()
        self.routes: list[dict[str, Any]] = []

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        with self._verrou:
            self.routes.append({"route": route, "parametres": parametres or {}})
        return self._lecteur.lire(route, parametres)


def nb_max(valeur: Any) -> int:
    try:
        nombre = int(valeur) if valeur is not None else NB_DEFAUT
    except (TypeError, ValueError):
        nombre = NB_DEFAUT
    return min(max(nombre, 1), NB_PLAFOND)


def lire_argument(arguments: dict, nom: str) -> str:
    return str(arguments.get(nom) or "").strip()


def liste_ids(ids: list[int]) -> str:
    # Séparateur des routes `multi` : la virgule.
    return ",".join(str(i) for i in dict.fromkeys(ids))


def lire_fiches(
    contexte: ContexteTour,
    client: LecteurModuleo,
    lire: Callable[[LecteurModuleo], tuple[list[int], list[Fiche]]],
    aucun: str,
    trouves: str,
) -> ResultatOutil:
    # `client` : celui du contexte, déjà vérifié. `lire` : les ids trouvés
    # et les fiches des premiers. `aucun` : la phrase sans résultat ;
    # `trouves` : « {n} affaires trouvées, {m} affichées », en tête quand il
    # y a plus d'ids que de fiches.
    contexte.publier(CONSULTATION_MODULEO)
    lecteur = LecteurTrace(client)
    try:
        ids, fiches = lire(lecteur)
    except NomNonResolu as erreur:
        return ResultatOutil(str(erreur), trace={"routes": lecteur.routes, "non_resolu": str(erreur)})
    except ModuleoRefuse as erreur:
        logger.warning("Moduléo refuse la lecture : %s", erreur)
        return ResultatOutil(REFUS, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    except (ErreurModuleo, RequeteInterdite, KeyError, TypeError, ValueError, AttributeError) as erreur:
        # Jamais de 500 ni de nouvelle tentative : panne, ou réponse qui n'a
        # pas la forme attendue.
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"routes": lecteur.routes, "erreur": str(erreur)})
    trace = {"routes": lecteur.routes, "trouvees": len(ids), "fiches": [fiche.texte for fiche in fiches]}
    if not fiches:
        return ResultatOutil(aucun, trace=trace)
    enregistrer_lectures(contexte.db, contexte.conversation_id, "moduleo", fiches)
    entete = ""
    if len(ids) > len(fiches):
        plus = "Au moins " if len(ids) >= IDS_MAX else ""
        entete = f"{plus}{trouves.format(n=len(ids), m=len(fiches))}, précise la recherche.\n\n"
    return ResultatOutil(entete + "\n\n".join(fiche.texte for fiche in fiches), trace=trace)
