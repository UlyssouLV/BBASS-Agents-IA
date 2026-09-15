import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from vm_centrale.config import get_vm_admin_key
from vm_centrale.database import get_db
from vm_centrale.models import Compte
from vm_centrale.schemas import AuthRequest, AuthResponse, VerifierResponse
from vm_centrale.security import hash_password, verify_password
from vm_centrale.jetons import JetonStore, get_jeton_store

router = APIRouter()

_ECHEC_AUTHENTIFICATION = "Identifiant ou mot de passe incorrect"
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"
_CLE_ADMIN_INVALIDE = "Clé d'administration manquante ou invalide"

# Hash bidon de coût identique à un vrai hash, utilisé quand l'identifiant est
# inconnu : sans lui, vérifier un mot de passe contre un compte inexistant
# serait quasi instantané (pas de PBKDF2 exécuté) alors que le rejeter pour un
# mauvais mot de passe prend le temps du hash — un écart de timing qui
# révélerait quelle partie était fausse, ce que l'endpoint doit justement
# éviter.
_HASH_BIDON = hash_password("mot-de-passe-bidon-pour-le-timing")

_bearer_scheme = HTTPBearer(auto_error=False)


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

    return AuthResponse(
        prenom=compte.prenom,
        nom=compte.nom,
        agence=compte.agence,
        pole=compte.pole,
        jeton=jetons.emettre(compte.identifiant),
    )


@router.get("/auth/verifier", response_model=VerifierResponse)
def verifier(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
) -> VerifierResponse:
    identifiant = jetons.identifiant_pour(credentials.credentials) if credentials is not None else None
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)
    return VerifierResponse(identifiant=identifiant)


@router.delete("/auth/jeton", status_code=204)
def revoquer_jeton_courant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
) -> None:
    # Idempotent : un jeton absent ou déjà révoqué ne provoque pas d'erreur,
    # une déconnexion doit toujours pouvoir aboutir côté poste.
    if credentials is not None:
        jetons.revoquer(credentials.credentials)


@router.delete("/auth/jeton/{identifiant}", status_code=204)
def revoquer_tous_les_jetons(
    identifiant: str,
    x_admin_key: str | None = Header(default=None),
    jetons: JetonStore = Depends(get_jeton_store),
) -> None:
    if not _cle_admin_valide(x_admin_key):
        raise HTTPException(status_code=401, detail=_CLE_ADMIN_INVALIDE)
    jetons.revoquer_tous(identifiant)


def _cle_admin_valide(cle_fournie: str | None) -> bool:
    cle_attendue = get_vm_admin_key()
    if cle_attendue is None or cle_fournie is None:
        return False
    return hmac.compare_digest(cle_fournie, cle_attendue)
