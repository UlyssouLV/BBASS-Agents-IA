import json
import logging
import queue
import threading
from collections.abc import Callable, Iterator
from urllib.parse import urlsplit

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vm_centrale.config import LONGUEUR_MAX_DETAIL_STATUT

# Statut du tour (spec 1.4.4, ADR-0016) : le tour d'un envoi de message
# s'exécute dans son propre thread et publie ses étapes dans une file ; la
# réponse HTTP n'est qu'un flux `text/event-stream` qui lit cette file. Le
# tour va au bout même si personne ne lit plus le flux (onglet fermé).

REFLEXION = "Réflexion…"
VERIFICATION = "Vérification de la réponse…"
TITRAGE = "Titre de la conversation…"
ATTENTE = "En attente de la réponse en cours dans une autre conversation…"

Publier = Callable[[str], None]

logger = logging.getLogger(__name__)


def ne_rien_publier(libelle: str) -> None:
    # Émetteur d'un outil appelé hors d'un tour en flux (tests, scripts).
    pass


def _tronquer(detail: str) -> str:
    detail = detail.strip()
    return detail if len(detail) <= LONGUEUR_MAX_DETAIL_STATUT else f"{detail[:LONGUEUR_MAX_DETAIL_STATUT]}…"


# Libellés des outils (#165), construits ici seulement : le poste affiche le
# texte reçu.
def recherche_web(requete: str) -> str:
    return f"Recherche sur le web : “{_tronquer(requete)}”"


def lecture_de(url: str) -> str:
    # Domaine = hôte sans `www.` ; une URL écrite par le compte peut venir
    # sans schéma (« www.bbass.fr »).
    hote = urlsplit(url if "://" in url else f"https://{url}").hostname or url
    return f"Lecture de {hote.removeprefix('www.')}"


def relecture_de(nom_fichier: str) -> str:
    return f"Relecture de {_tronquer(nom_fichier)}"


def consultation_moduleo(domaine: str) -> str:
    # Avant toute lecture d'un outil Moduléo (spec 1.5.0, #174), avec son
    # domaine depuis 1.5.1 (#188) : « Consultation Moduléo : affaires ».
    return f"Consultation Moduléo : {domaine}"


def _evenement(nom: str, donnees: dict) -> str:
    return f"event: {nom}\ndata: {json.dumps(donnees, ensure_ascii=False)}\n\n"


def _fin(resultat: BaseModel) -> str:
    # Exactement le JSON que la route renvoyait avant le flux.
    return _evenement("fin", resultat.model_dump(mode="json"))


def _reponse_en_flux(evenements: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(evenements, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def flux_de_la_fin(resultat: BaseModel) -> StreamingResponse:
    # Rejeu d'une clé d'idempotence : la fin mise en cache, sans statut.
    return _reponse_en_flux(iter([_fin(resultat)]))


def lancer_tour(executer: Callable[[Publier], BaseModel]) -> StreamingResponse:
    # Une HTTPException levée pendant le tour devient un événement `erreur`
    # avec le même code et le même détail qu'avant le flux.
    file: queue.SimpleQueue[str | None] = queue.SimpleQueue()

    def publier(libelle: str) -> None:
        file.put(_evenement("statut", {"libelle": libelle}))

    def tour() -> None:
        try:
            file.put(_fin(executer(publier)))
        except HTTPException as erreur:
            file.put(_evenement("erreur", {"status": erreur.status_code, "detail": erreur.detail}))
        except Exception:
            logger.exception("Échec inattendu d'un tour de chat")
            file.put(_evenement("erreur", {"status": 500, "detail": "Internal Server Error"}))
        finally:
            file.put(None)

    def lire() -> Iterator[str]:
        while (evenement := file.get()) is not None:
            yield evenement

    # Pas un thread démon : un arrêt de la VM attend la fin des tours en cours.
    threading.Thread(target=tour, name="tour-de-chat").start()
    return _reponse_en_flux(lire())
