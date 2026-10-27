from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from vm_centrale.autorisation import get_compte_admin
from vm_centrale.database import get_db
from vm_centrale.models import (
    Compte,
    DroitModuleo,
    EvenementJournalModuleo,
    GroupeModuleo,
    GroupeModuleoDroit,
    RattachementModuleo,
)
from vm_centrale.moduleo.client import ClientModuleo, ErreurModuleo, get_client_moduleo
from vm_centrale.moduleo.droits import APPLICATIONS, AUCUN_DROIT, COGEO, GROUPE_DEV, PLANNING
from vm_centrale.moduleo.resolution import NomNonResolu, chercher_utilisateur
from vm_centrale.schemas import (
    CatalogueModuleoResponse,
    CategorieDroitsModuleoResponse,
    DroitAccordeModuleo,
    DroitModuleoResponse,
    EvenementJournalModuleoResponse,
    GroupeModuleoRenommeRequest,
    GroupeModuleoRequest,
    GroupeModuleoResponse,
    RattachementModuleoRequest,
    RattachementModuleoResponse,
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
_SOUS_DROIT_SANS_PARENT = "Sous-droit accordé sans son droit parent"
_COMPTE_INTROUVABLE = "Compte introuvable"
_GROUPE_HORS_APPLICATION = "Aucun groupe Moduléo de cette application ne porte cet id"
_MODULEO_NON_CONFIGURE = "Moduléo n'est pas configuré : utilisateur non résolu"
_MODULEO_EN_ECHEC = "Moduléo n'a pas répondu : utilisateur non résolu"
# Le journal se consulte sans export (spec 1.5.3) : les plus récents.
_JOURNAL_RECENT = 200
_AUCUN = "aucun"
# Champ de condition « L'activité … des activités suivantes » : un opérateur
# et une liste, comme dans Moduléo ; les autres champs sont des cases.
_OPERATEURS = ("Fait partie", "Ne fait pas partie")


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


def _journaliser(db: Session, admin: Compte, action: str, cible: str) -> None:
    # Avant le commit de l'action : une action refusée n'est pas journalisée.
    db.add(
        EvenementJournalModuleo(
            date=datetime.now(timezone.utc), identifiant_admin=admin.identifiant, action=action, cible=cible
        )
    )


def _decrire(groupe: GroupeModuleo) -> str:
    return f"{groupe.application} « {groupe.nom} »"


def _vers_reponse(groupe: GroupeModuleo) -> GroupeModuleoResponse:
    return GroupeModuleoResponse(id=groupe.id, application=groupe.application, nom=groupe.nom)


def _groupe(db: Session, groupe_id: int) -> GroupeModuleo:
    # « Tous droits (dev) » reste hors Panel (ADR-0019) : ni lu ni modifié.
    groupe = db.get(GroupeModuleo, groupe_id)
    if groupe is None or groupe.nom == GROUPE_DEV:
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
    groupes = (
        db.query(GroupeModuleo)
        .filter(GroupeModuleo.nom != GROUPE_DEV)
        .order_by(GroupeModuleo.application, GroupeModuleo.nom)
        .all()
    )
    return [_vers_reponse(groupe) for groupe in groupes]


@router.post("/groupes", status_code=201, responses={409: {"description": _NOM_DEJA_UTILISE}})
def creer_groupe(
    requete: GroupeModuleoRequest,
    db: Session = Depends(get_db),
    admin: Compte = Depends(get_compte_admin),
) -> GroupeModuleoResponse:
    groupe = GroupeModuleo(application=requete.application, nom=requete.nom)
    db.add(groupe)
    _journaliser(db, admin, "Groupe créé", _decrire(groupe))
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
    admin: Compte = Depends(get_compte_admin),
) -> GroupeModuleoResponse:
    groupe = _groupe(db, groupe_id)
    _journaliser(db, admin, "Groupe renommé", f"{_decrire(groupe)} → « {requete.nom} »")
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
    admin: Compte = Depends(get_compte_admin),
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
    _journaliser(db, admin, "Groupe supprimé", _decrire(groupe))
    db.commit()


@router.get("/groupes/{groupe_id}/droits", responses={404: {"description": _GROUPE_INTROUVABLE}})
def lire_droits_du_groupe(
    groupe_id: int,
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[DroitAccordeModuleo]:
    return _droits_accordes(db, _groupe(db, groupe_id))


def _valeur_de_champ(champ: str, valeur: object) -> bool:
    if "…" not in champ:
        return isinstance(valeur, bool)
    if not isinstance(valeur, dict) or valeur.get("operateur") not in _OPERATEURS or len(valeur) != 2:
        return False
    (liste,) = (v for cle, v in valeur.items() if cle != "operateur")
    return isinstance(liste, list) and all(isinstance(element, str) for element in liste)


def _conditions_du_catalogue(droit: DroitModuleo, conditions: dict | None) -> bool:
    # Le catalogue liste, par condition proposée sur l'action, ses champs ;
    # le groupe pose une valeur par champ.
    if conditions is None:
        return True
    possibles = droit.conditions or {}
    return all(
        condition in possibles
        and isinstance(champs, dict)
        and all(champ in possibles[condition] and _valeur_de_champ(champ, valeur) for champ, valeur in champs.items())
        for condition, champs in conditions.items()
    )


@router.put(
    "/groupes/{groupe_id}/droits",
    responses={
        404: {"description": _GROUPE_INTROUVABLE},
        422: {"description": f"{_DROIT_HORS_CATALOGUE}, {_CONDITION_HORS_CATALOGUE} ou {_SOUS_DROIT_SANS_PARENT}"},
    },
)
def remplacer_droits_du_groupe(
    groupe_id: int,
    droits: list[DroitAccordeModuleo],
    db: Session = Depends(get_db),
    admin: Compte = Depends(get_compte_admin),
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
    # Comme dans Moduléo, un sous-droit ne se coche que sous son parent.
    accordes_ids = {droit.id for droit in catalogue.values()}
    for droit in catalogue.values():
        if droit.parent_id is not None and droit.parent_id not in accordes_ids:
            raise HTTPException(status_code=422, detail=f"{_SOUS_DROIT_SANS_PARENT} : {droit.chemin}")

    accordes = {d.chemin: d for d in droits}.values()
    pluriel = "s" if len(accordes) > 1 else ""
    _journaliser(db, admin, "Droits remplacés", f"{_decrire(groupe)} : {len(accordes)} droit{pluriel}")
    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    for accorde in accordes:
        db.add(
            GroupeModuleoDroit(groupe_id=groupe.id, droit_id=catalogue[accorde.chemin].id, conditions=accorde.conditions)
        )
    db.commit()
    return _droits_accordes(db, groupe)


def _rattachement(compte: Compte, rattachement: RattachementModuleo | None) -> RattachementModuleoResponse:
    return RattachementModuleoResponse(
        identifiant=compte.identifiant,
        groupe_cogeo_id=rattachement.groupe_cogeo_id if rattachement else None,
        groupe_planning_id=rattachement.groupe_planning_id if rattachement else None,
        id_utilisateur_moduleo=rattachement.id_utilisateur_moduleo if rattachement else None,
    )


@router.get("/rattachements")
def lister_rattachements(
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[RattachementModuleoResponse]:
    # Chaque compte, rattaché ou non (spec 1.5.3, #212).
    lignes = (
        db.query(Compte, RattachementModuleo)
        .outerjoin(RattachementModuleo, RattachementModuleo.identifiant_compte == Compte.identifiant)
        .order_by(Compte.identifiant)
    )
    return [_rattachement(compte, rattachement) for compte, rattachement in lignes]


def _groupe_de(db: Session, application: str, groupe_id: int | None) -> GroupeModuleo | None:
    if groupe_id is None:
        return None
    groupe = db.get(GroupeModuleo, groupe_id)
    if groupe is None or groupe.application != application or groupe.nom == GROUPE_DEV:
        raise HTTPException(status_code=422, detail=f"{_GROUPE_HORS_APPLICATION} : {application} {groupe_id}")
    return groupe


@router.patch(
    "/rattachements/{identifiant}",
    responses={
        404: {"description": _COMPTE_INTROUVABLE},
        422: {"description": f"{_GROUPE_HORS_APPLICATION}, ou nom d'utilisateur Moduléo inconnu ou ambigu"},
        502: {"description": _MODULEO_EN_ECHEC},
        503: {"description": _MODULEO_NON_CONFIGURE},
    },
)
def modifier_rattachement(
    identifiant: str,
    requete: RattachementModuleoRequest,
    db: Session = Depends(get_db),
    client_moduleo: ClientModuleo | None = Depends(get_client_moduleo),
    admin: Compte = Depends(get_compte_admin),
) -> RattachementModuleoResponse:
    # Tout est validé avant d'écrire : une erreur ne change rien. Effet au
    # tour suivant (droits_du_compte relu à chaque tour).
    compte = db.query(Compte).filter(Compte.identifiant == identifiant).one_or_none()
    if compte is None:
        raise HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)
    # Champ absent : inchangé. Seuls les champs changés vont au journal
    # (« n.durand : groupe Cogeo Admin, utilisateur Moduléo 31 »).
    champs = requete.model_fields_set
    rattachement = db.get(RattachementModuleo, identifiant)
    if not champs:
        return _rattachement(compte, rattachement)
    valeurs: dict[str, int | None] = {}
    changes: list[str] = []
    for champ, application, libelle in (
        ("groupe_cogeo_id", COGEO, "groupe Cogeo"),
        ("groupe_planning_id", PLANNING, "groupe Planning"),
    ):
        if champ in champs:
            groupe = _groupe_de(db, application, getattr(requete, champ))
            valeurs[champ] = groupe.id if groupe else None
            changes.append(f"{libelle} {groupe.nom if groupe else _AUCUN}")
    if "utilisateur_moduleo" in champs:
        id_utilisateur = _id_utilisateur(client_moduleo, requete.utilisateur_moduleo)
        valeurs["id_utilisateur_moduleo"] = id_utilisateur
        changes.append(f"utilisateur Moduléo {_AUCUN if id_utilisateur is None else id_utilisateur}")

    rattachement = rattachement or RattachementModuleo(identifiant_compte=identifiant)
    for champ, valeur in valeurs.items():
        setattr(rattachement, champ, valeur)
    db.add(rattachement)
    _journaliser(db, admin, "Rattachement modifié", f"{identifiant} : {', '.join(changes)}")
    db.commit()
    return _rattachement(compte, rattachement)


def _id_utilisateur(client_moduleo: ClientModuleo | None, nom: str | None) -> int | None:
    if nom is None:
        return None
    if client_moduleo is None:
        raise HTTPException(status_code=503, detail=_MODULEO_NON_CONFIGURE)
    # moduleo/utilisateur est une route libre du garde des droits (#188).
    try:
        return chercher_utilisateur(client_moduleo.pour(AUCUN_DROIT), nom)
    except NomNonResolu as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from None
    except ErreurModuleo as erreur:
        raise HTTPException(status_code=502, detail=f"{_MODULEO_EN_ECHEC} : {erreur}") from None


@router.get("/journal")
def lire_journal(
    db: Session = Depends(get_db),
    _admin: Compte = Depends(get_compte_admin),
) -> list[EvenementJournalModuleoResponse]:
    evenements = db.query(EvenementJournalModuleo).order_by(EvenementJournalModuleo.id.desc()).limit(_JOURNAL_RECENT)
    return [
        EvenementJournalModuleoResponse(
            # SQLite rend la date sans fuseau, enregistrée en UTC.
            date=evenement.date.replace(tzinfo=timezone.utc), admin=evenement.identifiant_admin, action=evenement.action, cible=evenement.cible
        )
        for evenement in evenements
    ]
