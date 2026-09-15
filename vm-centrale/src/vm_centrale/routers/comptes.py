from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from vm_centrale.autorisation import get_compte_admin
from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.models import Compte, ComptePole
from vm_centrale.schemas import (
    CompteCreeRequest,
    CompteCreeResponse,
    CompteModifieRequest,
    CompteResponse,
    MotDePasseReinitialiseResponse,
)
from vm_centrale.security import generer_mot_de_passe_aleatoire, hash_password

router = APIRouter(prefix="/comptes")

_IDENTIFIANT_DEJA_UTILISE = "Cet identifiant est déjà utilisé"
_COMPTE_INTROUVABLE = "Compte introuvable"


def _vers_reponse(compte: Compte) -> CompteResponse:
    return CompteResponse(
        identifiant=compte.identifiant,
        prenom=compte.prenom,
        nom=compte.nom,
        email=compte.email,
        agence=compte.agence,
        poles=[compte_pole.pole for compte_pole in compte.poles],
        est_admin=compte.est_admin,
        doit_changer_mot_de_passe=compte.doit_changer_mot_de_passe,
    )


@router.get("", response_model=list[CompteResponse])
def lister_comptes(
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[CompteResponse]:
    comptes = (
        db.query(Compte)
        .options(selectinload(Compte.poles))
        .order_by(Compte.identifiant)
        .all()
    )
    return [_vers_reponse(compte) for compte in comptes]


@router.post("", response_model=CompteCreeResponse, status_code=201)
def creer_compte(
    requete: CompteCreeRequest,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> CompteCreeResponse:
    if db.query(Compte).filter(Compte.identifiant == requete.identifiant).first() is not None:
        raise HTTPException(status_code=409, detail=_IDENTIFIANT_DEJA_UTILISE)

    mot_de_passe = generer_mot_de_passe_aleatoire()
    compte = Compte(
        identifiant=requete.identifiant,
        mot_de_passe_hash=hash_password(mot_de_passe),
        prenom=requete.prenom,
        nom=requete.nom,
        email=requete.email,
        agence=requete.agence,
        # doit_changer_mot_de_passe posé à vrai à la création (spec V1.1) ;
        # est_admin ne se pose jamais à la création, seulement via la
        # promotion/rétrogradation dédiée d'un ticket ultérieur.
        est_admin=False,
        doit_changer_mot_de_passe=True,
        poles=[ComptePole(pole=pole) for pole in requete.poles],
    )
    db.add(compte)
    try:
        db.commit()
    except IntegrityError:
        # Filet de sécurité contre une course entre deux créations concurrentes
        # pour le même identifiant : la vérification ci-dessus ne suffit pas
        # seule à l'empêcher (fenêtre entre le SELECT et le COMMIT).
        db.rollback()
        raise HTTPException(status_code=409, detail=_IDENTIFIANT_DEJA_UTILISE) from None
    db.refresh(compte)

    return CompteCreeResponse(**_vers_reponse(compte).model_dump(), mot_de_passe=mot_de_passe)


@router.patch("/{identifiant}", response_model=CompteResponse)
def modifier_compte(
    identifiant: str,
    requete: CompteModifieRequest,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> CompteResponse:
    compte = (
        db.query(Compte)
        .options(selectinload(Compte.poles))
        .filter(Compte.identifiant == identifiant)
        .first()
    )
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)

    compte.prenom = requete.prenom
    compte.nom = requete.nom
    compte.email = requete.email
    compte.agence = requete.agence
    compte.poles = [ComptePole(pole=pole) for pole in requete.poles]
    db.commit()
    db.refresh(compte)

    return _vers_reponse(compte)


@router.post(
    "/{identifiant}/reinitialiser-mot-de-passe",
    response_model=MotDePasseReinitialiseResponse,
)
def reinitialiser_mot_de_passe(
    identifiant: str,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> MotDePasseReinitialiseResponse:
    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)

    mot_de_passe = generer_mot_de_passe_aleatoire()
    compte.mot_de_passe_hash = hash_password(mot_de_passe)
    compte.doit_changer_mot_de_passe = True
    # Ne touche pas à la table Jeton : les jetons actifs du compte restent
    # valides, à la différence de la déconnexion forcée (ticket #12), qui est
    # une action distincte et explicite (spec V1.1, user story 16).
    db.commit()

    return MotDePasseReinitialiseResponse(mot_de_passe=mot_de_passe)


@router.post("/{identifiant}/deconnexion-forcee", status_code=204)
def deconnexion_forcee(
    identifiant: str,
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
    _admin: Compte = Depends(get_compte_admin),
) -> None:
    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)

    # Réutilise le même mécanisme de révocation que DELETE /auth/jeton/{identifiant}
    # (protégé par X-Admin-Key) plutôt que d'en construire un second.
    jetons.revoquer_tous(identifiant)
