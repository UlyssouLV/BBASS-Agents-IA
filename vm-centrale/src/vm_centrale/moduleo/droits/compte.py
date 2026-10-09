from dataclasses import dataclass

from sqlalchemy.orm import Session

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit, RattachementModuleo
from vm_centrale.moduleo.droits.catalogue import COGEO, PLANNING

# Les Droits Moduléo d'un compte (spec 1.5.1, ADR-0018) : ceux de son
# groupe Cogeo et de son groupe Planning, rattachés explicitement. Être
# compte administrateur BBASS n'en donne aucun.


class GroupeInconnu(ValueError):
    pass


@dataclass(frozen=True)
class DroitsModuleo:
    groupe_cogeo: str | None = None
    groupe_planning: str | None = None
    id_utilisateur_moduleo: int | None = None
    # Chemins des droits accordés (catalogue.chemin).
    droits: frozenset[str] = frozenset()

    def a(self, chemin: str) -> bool:
        return chemin in self.droits


# Compte sans rattachement : aucun outil Moduléo.
AUCUN_DROIT = DroitsModuleo()


def droits_du_compte(db: Session, identifiant_compte: str) -> DroitsModuleo:
    rattachement = db.get(RattachementModuleo, identifiant_compte)
    if rattachement is None:
        return AUCUN_DROIT
    ids_groupes = [i for i in (rattachement.groupe_cogeo_id, rattachement.groupe_planning_id) if i is not None]
    groupes = {g.id: g.nom for g in db.query(GroupeModuleo).filter(GroupeModuleo.id.in_(ids_groupes))}
    chemins = (
        db.query(DroitModuleo.chemin)
        .join(GroupeModuleoDroit, GroupeModuleoDroit.droit_id == DroitModuleo.id)
        .filter(GroupeModuleoDroit.groupe_id.in_(ids_groupes))
    )
    return DroitsModuleo(
        groupe_cogeo=groupes.get(rattachement.groupe_cogeo_id) if rattachement.groupe_cogeo_id else None,
        groupe_planning=groupes.get(rattachement.groupe_planning_id) if rattachement.groupe_planning_id else None,
        id_utilisateur_moduleo=rattachement.id_utilisateur_moduleo,
        droits=frozenset(c for (c,) in chemins),
    )


def rattacher(
    db: Session,
    identifiant_compte: str,
    groupe_cogeo: str | None,
    groupe_planning: str | None,
    id_utilisateur_moduleo: int | None,
) -> RattachementModuleo:
    # Remplace tout le rattachement ; None : pas de groupe, pas
    # d'utilisateur. Un nom de groupe inconnu de son application :
    # GroupeInconnu, rien n'est changé. Ne valide pas.
    ids = (_id_groupe(db, COGEO, groupe_cogeo), _id_groupe(db, PLANNING, groupe_planning))
    rattachement = db.get(RattachementModuleo, identifiant_compte)
    if rattachement is None:
        rattachement = RattachementModuleo(identifiant_compte=identifiant_compte)
        db.add(rattachement)
    rattachement.groupe_cogeo_id, rattachement.groupe_planning_id = ids
    rattachement.id_utilisateur_moduleo = id_utilisateur_moduleo
    db.flush()
    return rattachement


def _id_groupe(db: Session, application: str, nom: str | None) -> int | None:
    if nom is None:
        return None
    groupe = db.query(GroupeModuleo).filter_by(application=application, nom=nom).one_or_none()
    if groupe is None:
        connus = ", ".join(sorted(g.nom for g in db.query(GroupeModuleo).filter_by(application=application)))
        raise GroupeInconnu(f"Aucun groupe {application} « {nom} ». Groupes connus : {connus or 'aucun'}.")
    return groupe.id
