import json

from fastapi import APIRouter
from pydantic import ValidationError

from poste import config
from poste.schemas import DerniereVerificationResponse

# Dernière vérification de mise à jour faite par le Lanceur au lancement
# (ADR-0022), lue dans son fichier d'état : le front en tire le bandeau
# « Mise à jour … impossible ». Sans Lanceur (dev) ou sans fichier lisible :
# null, l'application s'affiche sans bandeau.
router = APIRouter()


@router.get("/mise-a-jour")
def derniere_verification() -> DerniereVerificationResponse | None:
    if not config.EN_MODE_PAQUET:
        return None
    try:
        contenu = json.loads(config.FICHIER_ETAT_MISE_A_JOUR.read_text(encoding="utf-8"))
        return DerniereVerificationResponse.model_validate(contenu)
    except (OSError, ValueError, ValidationError):
        return None
