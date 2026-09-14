from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vm_centrale.database import get_db
from vm_centrale.models import Compte
from vm_centrale.schemas import AuthRequest, AuthResponse
from vm_centrale.security import hash_password, verify_password
from vm_centrale.jetons import JetonStore, get_jeton_store

router = APIRouter()

_ECHEC_AUTHENTIFICATION = "Identifiant ou mot de passe incorrect"

# Hash bidon de coût identique à un vrai hash, utilisé quand l'identifiant est
# inconnu : sans lui, vérifier un mot de passe contre un compte inexistant
# serait quasi instantané (pas de PBKDF2 exécuté) alors que le rejeter pour un
# mauvais mot de passe prend le temps du hash — un écart de timing qui
# révélerait quelle partie était fausse, ce que l'endpoint doit justement
# éviter.
_HASH_BIDON = hash_password("mot-de-passe-bidon-pour-le-timing")


@router.post("/auth", response_model=AuthResponse)
def authentifier(
    requete: AuthRequest,
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
) -> AuthResponse:
    compte = db.query(Compte).filter(Compte.identifiant == requete.identifiant).first()
    hash_a_verifier = compte.mot_de_passe_hash if compte is not None else _HASH_BIDON
    mot_de_passe_valide = verify_password(requete.mot_de_passe, hash_a_verifier)

    if compte is None or not mot_de_passe_valide:
        raise HTTPException(status_code=401, detail=_ECHEC_AUTHENTIFICATION)

    return AuthResponse(agence=compte.agence, pole=compte.pole, jeton=jetons.emettre())
