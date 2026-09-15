import hmac

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from vm_centrale.config import get_vm_admin_key
from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.models import Compte

_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"
_ACCES_ADMIN_REQUIS = "Accès réservé aux comptes administrateurs"
_CLE_ADMIN_INVALIDE = "Clé d'administration manquante ou invalide"

_bearer_scheme = HTTPBearer(auto_error=False)


def get_compte_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
) -> Compte:
    # Dépendance d'autorisation partagée (jeton valide + est_admin) : toutes
    # les actions d'administration de comptes (créer, lister, et les actions
    # suivantes de la spec V1.1) la réutilisent, plutôt qu'un second système
    # d'autorisation.
    identifiant = jetons.identifiant_pour(credentials.credentials) if credentials is not None else None
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    if compte is None or not compte.est_admin:
        raise HTTPException(status_code=403, detail=_ACCES_ADMIN_REQUIS)

    return compte


def exiger_cle_admin_vm(x_admin_key: str | None = Header(default=None)) -> None:
    # Dépendance partagée avec DELETE /auth/jeton/{identifiant} (ADR-0007) :
    # les actions les plus sensibles (promotion/rétrogradation, et suppression
    # d'un ticket ultérieur) exigent cette même clé, en plus (jamais à la
    # place) du jeton + est_admin vérifié par get_compte_admin.
    cle_attendue = get_vm_admin_key()
    if cle_attendue is None or x_admin_key is None or not hmac.compare_digest(x_admin_key, cle_attendue):
        raise HTTPException(status_code=401, detail=_CLE_ADMIN_INVALIDE)
