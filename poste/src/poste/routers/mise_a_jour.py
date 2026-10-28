import json
import logging
import subprocess
from collections.abc import Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from poste import config
from poste.routers.configuration import etat_a_l_adresse, get_client_sante
from poste.schemas import AProposResponse, DerniereVerificationResponse

# Dernière vérification de mise à jour faite par le Lanceur au lancement
# (ADR-0022), lue dans son fichier d'état : le front en tire le bandeau
# « Mise à jour … impossible » et « À propos ». Sans Lanceur (dev) ou sans
# fichier lisible : null, l'application s'affiche sans bandeau.
router = APIRouter()
journal = logging.getLogger("poste.mise_a_jour")

# Même argument que le Lanceur (lanceur/coeur/src/lancement.rs) : l'instance
# unique le transmet au Lanceur en cours, qui redémarre en mode vérification.
ARGUMENT_VERIFICATION = "--verifier-mise-a-jour"


def _demander_au_lanceur() -> None:
    subprocess.Popen([config.LANCEUR or "", ARGUMENT_VERIFICATION], close_fds=True)


def get_demandeur_de_verification() -> Callable[[], None]:
    return _demander_au_lanceur


def _derniere_verification() -> DerniereVerificationResponse | None:
    if not config.EN_MODE_PAQUET:
        return None
    try:
        contenu = json.loads(config.FICHIER_ETAT_MISE_A_JOUR.read_text(encoding="utf-8"))
        return DerniereVerificationResponse.model_validate(contenu)
    except (OSError, ValueError, ValidationError):
        return None


def _verification_possible() -> bool:
    return config.EN_MODE_PAQUET and config.LANCEUR is not None


@router.get("/mise-a-jour")
def derniere_verification() -> DerniereVerificationResponse | None:
    return _derniere_verification()


# Menu « … » (spec 1.6.2, point 9), sans session comme la Configuration.
@router.get("/a-propos")
def a_propos(client: httpx.Client = Depends(get_client_sante)) -> AProposResponse:
    adresse = config.adresse_serveur_bbass()
    version_serveur = etat_a_l_adresse(client, adresse).version if adresse else None
    return AProposResponse(
        version_poste=config.VERSION_POSTE if config.EN_MODE_PAQUET else None,
        version_serveur=version_serveur,
        derniere_verification=_derniere_verification(),
        verification_possible=_verification_possible(),
    )


@router.post("/mise-a-jour/verifier", status_code=202)
def verifier_maintenant(demander: Callable[[], None] = Depends(get_demandeur_de_verification)) -> None:
    # Même parcours qu'au lancement : le Lanceur redémarre (écran de démarrage,
    # mise à jour éventuelle, retour arrière) puis rouvre la fenêtre sur À propos.
    if not _verification_possible():
        raise HTTPException(
            status_code=409,
            detail="En développement, pas de Lanceur : relancez lancer-logiciel pour changer de version.",
        )
    try:
        demander()
    except OSError as erreur:
        journal.warning("Vérification des mises à jour non lancée : %s", erreur)
        raise HTTPException(
            status_code=500, detail="La vérification des mises à jour n'a pas pu être lancée. Relancez BBASS."
        ) from erreur
    journal.info("Vérification des mises à jour demandée au Lanceur")
