from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from vm_centrale.autorisation import exiger_cle_admin_vm, get_compte_admin
from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.models import Compte, ComptePole, ProfilTravail
from vm_centrale.schemas import (
    CompteCreeRequest,
    CompteCreeResponse,
    CompteModifieRequest,
    CompteResponse,
    MotDePasseReinitialiseResponse,
    ProfilTravailResponse,
    StatutAdminRequest,
)
from vm_centrale.security import generer_mot_de_passe_aleatoire, hash_password

router = APIRouter(prefix="/comptes")

_IDENTIFIANT_DEJA_UTILISE = "Cet identifiant est déjà utilisé"
_COMPTE_INTROUVABLE = "Compte introuvable"
_DERNIER_ADMINISTRATEUR = "Impossible de retirer le dernier compte administrateur restant"
_DERNIER_ADMINISTRATEUR_SUPPRESSION = (
    "Impossible de supprimer le dernier compte administrateur restant"
)
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"
_ACCES_PROFIL_TRAVAIL_REFUSE = "Le profil de travail n'est consultable que par son propre compte"

_bearer_scheme = HTTPBearer(auto_error=False)


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


@router.delete("/{identifiant}", status_code=204)
def supprimer_compte(
    identifiant: str,
    db: Session = Depends(get_db),
    jetons: JetonStore = Depends(get_jeton_store),
    _admin: Compte = Depends(get_compte_admin),
    _cle_admin: None = Depends(exiger_cle_admin_vm),
) -> None:
    compte = db.query(Compte).filter(Compte.identifiant == identifiant).first()
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)

    if compte.est_admin:
        # Même garde-fou que PATCH .../est-admin (spec V1.1) : la suppression
        # d'un administrateur est traitée comme une rétrogradation à ce titre.
        nombre_administrateurs = db.query(Compte).filter(Compte.est_admin.is_(True)).count()
        if nombre_administrateurs <= 1:
            raise HTTPException(status_code=409, detail=_DERNIER_ADMINISTRATEUR_SUPPRESSION)

    # Jeton n'a pas de clé étrangère vers Compte (voir jetons.py) : la cascade
    # sur les jetons associés doit donc être explicite, avant la suppression
    # du compte lui-même. Aucune trace ni archive conservée (spec du ticket).
    jetons.revoquer_tous(identifiant)
    db.delete(compte)
    db.commit()


@router.patch("/{identifiant}/est-admin", response_model=CompteResponse)
def modifier_statut_admin(
    identifiant: str,
    requete: StatutAdminRequest,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
    _cle_admin: None = Depends(exiger_cle_admin_vm),
) -> CompteResponse:
    compte = (
        db.query(Compte)
        .options(selectinload(Compte.poles))
        .filter(Compte.identifiant == identifiant)
        .first()
    )
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)

    if compte.est_admin and not requete.est_admin:
        # Garde-fou dernier administrateur (spec V1.1) : un administrateur
        # peut se rétrograder lui-même tant qu'un autre subsiste, seul le
        # compte total à zéro est refusé.
        nombre_administrateurs = db.query(Compte).filter(Compte.est_admin.is_(True)).count()
        if nombre_administrateurs <= 1:
            raise HTTPException(status_code=409, detail=_DERNIER_ADMINISTRATEUR)

    compte.est_admin = requete.est_admin
    db.commit()
    db.refresh(compte)

    return _vers_reponse(compte)


@router.get("/{identifiant}/profil-travail", response_model=ProfilTravailResponse)
def consulter_profil_travail(
    identifiant: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> ProfilTravailResponse:
    identifiant_du_jeton = (
        jetons.identifiant_pour(credentials.credentials) if credentials is not None else None
    )
    if identifiant_du_jeton is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    # Lecture seule, strictement réservée au compte propriétaire : le droit de
    # compte administrateur porte sur la gestion des comptes, jamais sur le
    # contenu des conversations/profils (spec V1.1.1) — 403 même pour un
    # jeton est_admin=true, y compris celui du compte propriétaire s'il ne
    # correspond pas à `identifiant`.
    if identifiant_du_jeton != identifiant:
        raise HTTPException(status_code=403, detail=_ACCES_PROFIL_TRAVAIL_REFUSE)

    profil = db.get(ProfilTravail, identifiant)
    if profil is None:
        return ProfilTravailResponse(contenu="", date_derniere_maj=None)

    return ProfilTravailResponse(contenu=profil.contenu, date_derniere_maj=profil.date_derniere_maj)
