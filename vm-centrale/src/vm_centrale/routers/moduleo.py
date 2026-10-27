from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from vm_centrale.autorisation import get_compte_admin
from vm_centrale.database import get_db
from vm_centrale.models import Compte, DroitModuleo, GroupeModuleo, GroupeModuleoDroit, RattachementModuleo
from vm_centrale.moduleo.droits import APPLICATIONS
from vm_centrale.schemas import (
    CatalogueModuleoResponse,
    CategorieDroitsModuleoResponse,
    DroitAccordeModuleo,
    DroitModuleoResponse,
    GroupeModuleoRenommeRequest,
    GroupeModuleoRequest,
    GroupeModuleoResponse,
)

# Administration Moduléo du Panel (spec 1.5.3, ADR-0019) : jeton d'un
# Compte administrateur, comme /comptes. Le catalogue des cases est en
# lecture seule : aucune route ne le crée, ne le renomme ni ne le supprime.
router = APIRouter(prefix="/moduleo")

_GROUPE_INTROUVABLE = "Groupe Moduléo introuvable"
_NOM_DEJA_UTILISE = "Un groupe de cette application porte déjà ce nom"
_GROUPE_RATTACHE = "Ce groupe est encore rattaché à des comptes"
_DROIT_HORS_CATALOGUE = "Droit absent du catalogue Moduléo de cette application"
_CONDITION_HORS_CATALOGUE = "Condition que Moduléo ne propose pas sur ce droit"


@router.get("/catalogue")
def lire_catalogue(
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> CatalogueModuleoResponse:
    droits = db.query(DroitModuleo).order_by(DroitModuleo.application, DroitModuleo.ordre).all()
    sous_droits: dict[int | None, list[DroitModuleo]] = {}
    for droit in droits:
        sous_droits.setdefault(droit.parent_id, []).append(droit)

    def noeud(droit: DroitModuleo) -> DroitModuleoResponse:
        return DroitModuleoResponse(
            chemin=droit.chemin,
            libelle=droit.libelle,
            conditions=droit.conditions,
            sous_droits=[noeud(enfant) for enfant in sous_droits.get(droit.id, [])],
        )

    arbres: dict[str, dict[str, list[DroitModuleoResponse]]] = {application: {} for application in APPLICATIONS}
    for droit in sous_droits.get(None, []):
        arbres[droit.application].setdefault(droit.categorie, []).append(noeud(droit))
    return CatalogueModuleoResponse(
        **{
            application: [
                CategorieDroitsModuleoResponse(categorie=categorie, droits=racines)
                for categorie, racines in categories.items()
            ]
            for application, categories in arbres.items()
        }
    )


def _vers_reponse(groupe: GroupeModuleo) -> GroupeModuleoResponse:
    return GroupeModuleoResponse(id=groupe.id, application=groupe.application, nom=groupe.nom)


def _groupe(db: Session, groupe_id: int) -> GroupeModuleo:
    groupe = db.get(GroupeModuleo, groupe_id)
    if groupe is None:
        raise HTTPException(status_code=404, detail=_GROUPE_INTROUVABLE)
    return groupe


def _droits_accordes(db: Session, groupe: GroupeModuleo) -> list[DroitAccordeModuleo]:
    accords = (
        db.query(GroupeModuleoDroit, DroitModuleo)
        .join(DroitModuleo, GroupeModuleoDroit.droit_id == DroitModuleo.id)
        .filter(GroupeModuleoDroit.groupe_id == groupe.id)
        .order_by(DroitModuleo.ordre)
    )
    return [DroitAccordeModuleo(chemin=droit.chemin, conditions=accord.conditions) for accord, droit in accords]


def _valider_nom(db: Session) -> None:
    # Unique (application, nom) en base : filet contre deux écritures
    # concurrentes comme contre un doublon simple.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=_NOM_DEJA_UTILISE) from None


@router.get("/groupes")
def lister_groupes(
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[GroupeModuleoResponse]:
    groupes = db.query(GroupeModuleo).order_by(GroupeModuleo.application, GroupeModuleo.nom).all()
    return [_vers_reponse(groupe) for groupe in groupes]


@router.post("/groupes", status_code=201, responses={409: {"description": _NOM_DEJA_UTILISE}})
def creer_groupe(
    requete: GroupeModuleoRequest,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> GroupeModuleoResponse:
    groupe = GroupeModuleo(application=requete.application, nom=requete.nom)
    db.add(groupe)
    _valider_nom(db)
    db.refresh(groupe)
    return _vers_reponse(groupe)


@router.patch(
    "/groupes/{groupe_id}",
    responses={404: {"description": _GROUPE_INTROUVABLE}, 409: {"description": _NOM_DEJA_UTILISE}},
)
def renommer_groupe(
    groupe_id: int,
    requete: GroupeModuleoRenommeRequest,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> GroupeModuleoResponse:
    groupe = _groupe(db, groupe_id)
    groupe.nom = requete.nom
    _valider_nom(db)
    db.refresh(groupe)
    return _vers_reponse(groupe)


@router.delete(
    "/groupes/{groupe_id}",
    status_code=204,
    responses={404: {"description": _GROUPE_INTROUVABLE}, 409: {"description": _GROUPE_RATTACHE}},
)
def supprimer_groupe(
    groupe_id: int,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> None:
    groupe = _groupe(db, groupe_id)
    # Jamais un compte orphelin en silence : l'admin le rattache d'abord
    # ailleurs (spec 1.5.3, user story 7).
    rattaches = [
        identifiant
        for (identifiant,) in db.query(RattachementModuleo.identifiant_compte)
        .filter(
            or_(
                RattachementModuleo.groupe_cogeo_id == groupe.id,
                RattachementModuleo.groupe_planning_id == groupe.id,
            )
        )
        .order_by(RattachementModuleo.identifiant_compte)
    ]
    if rattaches:
        raise HTTPException(status_code=409, detail=f"{_GROUPE_RATTACHE} : {', '.join(rattaches)}")

    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    db.delete(groupe)
    db.commit()


@router.get("/groupes/{groupe_id}/droits", responses={404: {"description": _GROUPE_INTROUVABLE}})
def lire_droits_du_groupe(
    groupe_id: int,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[DroitAccordeModuleo]:
    return _droits_accordes(db, _groupe(db, groupe_id))


def _conditions_du_catalogue(droit: DroitModuleo, conditions: dict | None) -> bool:
    # Le catalogue liste, par condition proposée sur l'action, ses champs ;
    # le groupe pose une valeur par champ.
    if conditions is None:
        return True
    possibles = droit.conditions or {}
    return all(
        condition in possibles and (not isinstance(champs, dict) or set(champs) <= set(possibles[condition]))
        for condition, champs in conditions.items()
    )


@router.put(
    "/groupes/{groupe_id}/droits",
    responses={404: {"description": _GROUPE_INTROUVABLE}, 422: {"description": _DROIT_HORS_CATALOGUE}},
)
def remplacer_droits_du_groupe(
    groupe_id: int,
    droits: list[DroitAccordeModuleo],
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[DroitAccordeModuleo]:
    # Remplace tout : une case absente de la liste n'est plus accordée.
    # Seules les cases déjà en base, de l'application du groupe (ADR-0019).
    groupe = _groupe(db, groupe_id)
    catalogue = {
        droit.chemin: droit
        for droit in db.query(DroitModuleo).filter(DroitModuleo.chemin.in_([d.chemin for d in droits]))
    }
    for accorde in droits:
        droit = catalogue.get(accorde.chemin)
        if droit is None or droit.application != groupe.application:
            raise HTTPException(status_code=422, detail=f"{_DROIT_HORS_CATALOGUE} : {accorde.chemin}")
        if not _conditions_du_catalogue(droit, accorde.conditions):
            raise HTTPException(status_code=422, detail=f"{_CONDITION_HORS_CATALOGUE} : {accorde.chemin}")

    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    for accorde in {d.chemin: d for d in droits}.values():
        db.add(
            GroupeModuleoDroit(groupe_id=groupe.id, droit_id=catalogue[accorde.chemin].id, conditions=accorde.conditions)
        )
    db.commit()
    return _droits_accordes(db, groupe)
