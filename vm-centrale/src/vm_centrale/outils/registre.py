from vm_centrale.mistral_client import AppelOutil
from vm_centrale.outils import lire_pages_web, piece_jointe, recherche_web
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo import affaires as moduleo_affaires
from vm_centrale.outils.moduleo import contacts as moduleo_contacts
from vm_centrale.outils.moduleo import devis as moduleo_devis
from vm_centrale.outils.moduleo import factures as moduleo_factures
from vm_centrale.outils.moduleo import planning as moduleo_planning
from vm_centrale.outils.moduleo import temps_passes as moduleo_temps_passes

_OUTIL_INCONNU = "Outil inconnu."

_OUTILS: dict[str, Outil] = {
    outil.nom: outil
    for outil in (
        piece_jointe.OUTIL,
        recherche_web.OUTIL,
        lire_pages_web.OUTIL,
        moduleo_affaires.OUTIL,
        moduleo_contacts.OUTIL,
        moduleo_devis.OUTIL,
        moduleo_factures.OUTIL,
        moduleo_temps_passes.OUTIL,
        moduleo_planning.OUTIL,
    )
}


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
