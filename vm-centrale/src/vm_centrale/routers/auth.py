from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from vm_centrale.autorisation import exiger_cle_admin_vm
from vm_centrale.database import get_db
from vm_centrale.models import Compte
from vm_centrale.schemas import AuthRequest, AuthResponse, ChangerMotDePasseRequest, VerifierResponse
from vm_centrale.security import hash_password, verify_password
from vm_centrale.jetons import JetonStore, get_jeton_store

router = APIRouter()

_ECHEC_AUTHENTIFICATION = "Identifiant ou mot de passe incorrect"
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"
_CHANGEMENT_NON_AUTORISE = (
    "Le changement de mot de passe n'est autorisé que dans le flux imposé après "
    "création ou réinitialisation"
)

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
        email=compte.email,
        agence=compte.agence,
        poles=[compte_pole.pole for compte_pole in compte.poles],
        est_admin=compte.est_admin,
        doit_changer_mot_de_passe=compte.doit_changer_mot_de_passe,
        jeton=jetons.emettre(compte.identifiant),
    )


def _identifiant_depuis_le_jeton(
    credentials: HTTPAuthorizationCredentials | None, jetons: JetonStore
) -> str | None:
    return jetons.identifiant_pour(credentials.credentials) if credentials is not None else None


@router.get("/auth/verifier", response_model=VerifierResponse)
def verifier(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
) -> VerifierResponse:
    identifiant = _identifiant_depuis_le_jeton(credentials, jetons)
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    # est_admin est toujours relu en base ici, jamais mis en cache dans le
    # jeton : un compte rétrogradé perd le droit admin dès la prochaine
    # vérification, sans attendre une nouvelle connexion. Un compte introuvable
    # (ex. supprimé après l'émission du jeton) est traité comme non-admin
    # plutôt que rejeté : le jeton reste seul juge de la validité de la
    # session, indépendamment de l'existence du compte.
    return VerifierResponse(
        identifiant=identifiant,
        est_admin=compte.est_admin if compte is not None else False,
    )


@router.post("/auth/mot-de-passe", status_code=204)
def changer_mot_de_passe(
    requete: ChangerMotDePasseRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
) -> None:
    identifiant = _identifiant_depuis_le_jeton(credentials, jetons)
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    # Contrairement à verifier(), un compte introuvable est ici rejeté plutôt
    # que toléré : il n'y a pas de ligne sur laquelle poser le nouveau hash.
    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    if compte is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    # Réservé au flux de changement imposé après création/réinitialisation
    # (spec V1.1, user story 15 + Out of Scope) : un compte qui n'a pas ce
    # flag ne peut pas changer volontairement son mot de passe via cet
    # endpoint à un autre moment.
    if not compte.doit_changer_mot_de_passe:
        raise HTTPException(status_code=403, detail=_CHANGEMENT_NON_AUTORISE)

    compte.mot_de_passe_hash = hash_password(requete.nouveau_mot_de_passe)
    compte.doit_changer_mot_de_passe = False
    db.commit()


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
    jetons: JetonStore = Depends(get_jeton_store),
    _cle_admin: None = Depends(exiger_cle_admin_vm),
) -> None:
    jetons.revoquer_tous(identifiant)
