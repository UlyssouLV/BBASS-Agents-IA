import json
from pathlib import Path

from sqlalchemy.orm import Session

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit

# Catalogue des Droits Moduléo et groupes recopiés de Moduléo (spec 1.5.1,
# ADR-0018) : fichier versionné, transcrit des captures de
# moduleo/docs/droits/, chargé en base à chaque démarrage. Règles :
# moduleo/README.md.

FICHIER_CATALOGUE = Path(__file__).parent / "catalogue.json"

COGEO = "cogeo"
PLANNING = "planning"
APPLICATIONS = (COGEO, PLANNING)
# Groupe local, jamais dans Moduléo : tous les droits de son application,
# pour le dev et les tests. Créé seulement à la demande (creer_groupes_dev).
GROUPE_DEV = "Tous droits (dev)"

_SEPARATEUR = " › "


def chemin(*parties: str) -> str:
    # « Devis, factures et avoirs › Consulter les devis › Émettre un devis ».
    return _SEPARATEUR.join(parties)


def charger_catalogue(db: Session, fichier: Path = FICHIER_CATALOGUE) -> None:
    # Idempotent : un droit est retrouvé par son chemin, un groupe par
    # (application, nom) ; les droits d'un groupe du fichier sont remplacés
    # par ceux du fichier. Les groupes de dev existants reçoivent les droits
    # ajoutés au catalogue. Ne valide pas : l'appelant committe.
    donnees = json.loads(fichier.read_text(encoding="utf-8"))
    droits = {droit.chemin: droit for droit in db.query(DroitModuleo)}
    for application in APPLICATIONS:
        ordre = 0
        for categorie in donnees["catalogue"][application]:
            ordre = _inscrire(db, droits, application, categorie["categorie"], categorie["droits"], [], None, ordre)
    for groupe in donnees["groupes"]:
        _accorder(db, _groupe(db, groupe["application"], groupe["nom"]), droits, groupe["droits"])
    for groupe in db.query(GroupeModuleo).filter(GroupeModuleo.nom == GROUPE_DEV):
        _accorder_tout(db, groupe)
    db.flush()


def creer_groupes_dev(db: Session) -> None:
    # Les deux groupes « Tous droits (dev) », Cogeo et Planning, sans
    # condition. Jamais au démarrage : aucun groupe autre qu'Admin en prod.
    for application in APPLICATIONS:
        _accorder_tout(db, _groupe(db, application, GROUPE_DEV))
    db.flush()


def _inscrire(
    db: Session,
    droits: dict[str, DroitModuleo],
    application: str,
    categorie: str,
    entrees: list[dict],
    parents: list[str],
    parent_id: int | None,
    ordre: int,
) -> int:
    for entree in entrees:
        cle = chemin(categorie, *parents, entree["libelle"])
        droit = droits.get(cle)
        if droit is None:
            droit = droits[cle] = DroitModuleo(chemin=cle)
            db.add(droit)
        droit.application = application
        droit.categorie = categorie
        droit.libelle = entree["libelle"]
        droit.parent_id = parent_id
        droit.ordre = ordre
        droit.conditions = entree.get("conditions")
        db.flush()
        ordre = _inscrire(
            db,
            droits,
            application,
            categorie,
            entree.get("sous_droits", []),
            [*parents, entree["libelle"]],
            droit.id,
            ordre + 1,
        )
    return ordre


def _groupe(db: Session, application: str, nom: str) -> GroupeModuleo:
    groupe = db.query(GroupeModuleo).filter_by(application=application, nom=nom).one_or_none()
    if groupe is None:
        groupe = GroupeModuleo(application=application, nom=nom)
        db.add(groupe)
        db.flush()
    return groupe


def _accorder(db: Session, groupe: GroupeModuleo, droits: dict[str, DroitModuleo], entrees: list) -> None:
    # Une entrée : le chemin du droit (liste), ou {"chemin", "conditions"}.
    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    for entree in entrees:
        parties, conditions = (entree["chemin"], entree.get("conditions")) if isinstance(entree, dict) else (entree, None)
        cle = chemin(*parties)
        if cle not in droits or droits[cle].application != groupe.application:
            raise ValueError(f"Groupe {groupe.application} « {groupe.nom} » : droit absent du catalogue : {cle}")
        db.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droits[cle].id, conditions=conditions))


def _accorder_tout(db: Session, groupe: GroupeModuleo) -> None:
    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    for droit in db.query(DroitModuleo).filter_by(application=groupe.application):
        db.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
