from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased

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

    def section(self, chemin: str, titre: str) -> str | None:
        # Vérification par champ des fiches (#188) : None si le droit est
        # accordé, sinon la mention qui remplace la section retirée, pour
        # que le modèle ne dise jamais « absent de Moduléo ».
        return None if self.a(chemin) else f"{titre} : non autorisés pour votre compte"


# Compte sans rattachement : aucun outil Moduléo.
AUCUN_DROIT = DroitsModuleo()


def droits_du_compte(db: Session, identifiant_compte: str) -> DroitsModuleo:
    # Une seule requête SQL (#188) : appelée une fois par tour, les droits
    # sont ensuite vérifiés en mémoire par le garde.
    cogeo, planning = aliased(GroupeModuleo), aliased(GroupeModuleo)
    lignes = (
        db.query(RattachementModuleo.id_utilisateur_moduleo, cogeo.nom, planning.nom, DroitModuleo.chemin)
        .outerjoin(cogeo, cogeo.id == RattachementModuleo.groupe_cogeo_id)
        .outerjoin(planning, planning.id == RattachementModuleo.groupe_planning_id)
        .outerjoin(
            GroupeModuleoDroit,
            or_(
                GroupeModuleoDroit.groupe_id == RattachementModuleo.groupe_cogeo_id,
                GroupeModuleoDroit.groupe_id == RattachementModuleo.groupe_planning_id,
            ),
        )
        .outerjoin(DroitModuleo, DroitModuleo.id == GroupeModuleoDroit.droit_id)
        .filter(RattachementModuleo.identifiant_compte == identifiant_compte)
        .all()
    )
    if not lignes:
        return AUCUN_DROIT
    id_utilisateur, groupe_cogeo, groupe_planning, _ = lignes[0]
    return DroitsModuleo(
        groupe_cogeo=groupe_cogeo,
        groupe_planning=groupe_planning,
        id_utilisateur_moduleo=id_utilisateur,
        droits=frozenset(c for *_, c in lignes if c is not None),
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
