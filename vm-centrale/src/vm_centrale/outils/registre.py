from vm_centrale.mistral_client import AppelOutil
from vm_centrale.outils import piece_jointe, recherche_web
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil

_OUTIL_INCONNU = "Outil inconnu."

_OUTILS: dict[str, Outil] = {outil.nom: outil for outil in (piece_jointe.OUTIL, recherche_web.OUTIL)}


def outils_du_tour(contexte: ContexteTour) -> list[dict] | None:
    # None plutôt qu'une liste vide : l'appel de chat part alors sans `tools`.
    schemas = [
        schema for outil in _OUTILS.values() if (schema := outil.declarer(contexte)) is not None
    ]
    return schemas or None


def executer_appel(appel: AppelOutil, contexte: ContexteTour) -> ResultatOutil:
    outil = _OUTILS.get(appel.nom)
    if outil is None:
        # Le modèle ne voit que les outils déclarés, mais jamais de 500 sur
        # un nom qui ne correspond à rien : il le lit dans le message `tool`.
        return ResultatOutil(_OUTIL_INCONNU)
    return outil.executer(appel.arguments, contexte)
