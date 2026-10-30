import json
from pathlib import Path

from sqlalchemy.orm import Session

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit

# Catalogue des Droits Moduléo et groupes recopiés de Moduléo (spec 1.5.1,
# ADR-0018) : fichier versionné, transcrit des captures de
# moduleo/docs/droits/. Depuis la 1.5.3 (ADR-0019), source d'une migration
# unique : cases et groupes vivent ensuite en base. Règles :
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
    # Migration unique (spec 1.5.3, #210) : les cases du fichier seulement
    # si la base n'en a aucune, le groupe Admin seulement si la base n'a
    # aucun groupe. Sinon rien : ni les cases ni les droits des groupes ne
    # sont réécrits. Ne valide pas : l'appelant committe.
    sans_cases = db.query(DroitModuleo).first() is None
    sans_groupe = db.query(GroupeModuleo).first() is None
    if not (sans_cases or sans_groupe):
        return
    donnees = json.loads(fichier.read_text(encoding="utf-8"))
    droits = {droit.chemin: droit for droit in db.query(DroitModuleo)}
    if sans_cases:
        for application in APPLICATIONS:
            ordre = 0
            for categorie in donnees["catalogue"][application]:
                ordre = _inscrire(db, droits, application, categorie["categorie"], categorie["droits"], [], None, ordre)
    if sans_groupe:
        for groupe in donnees["groupes"]:
            _accorder(db, _groupe(db, groupe["application"], groupe["nom"]), droits, groupe["droits"])
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
    # Seules les cases en base sont accordées : une case retirée par une
    # migration ne fait pas échouer le démarrage.
    for entree in entrees:
        parties, conditions = (entree["chemin"], entree.get("conditions")) if isinstance(entree, dict) else (entree, None)
        droit = droits.get(chemin(*parties))
        if droit is not None and droit.application == groupe.application:
            db.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id, conditions=conditions))


def _accorder_tout(db: Session, groupe: GroupeModuleo) -> None:
    db.query(GroupeModuleoDroit).filter_by(groupe_id=groupe.id).delete()
    for droit in db.query(DroitModuleo).filter_by(application=groupe.application):
        db.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
