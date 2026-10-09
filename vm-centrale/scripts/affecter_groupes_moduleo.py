"""Rattache un compte a son groupe Moduleo Cogeo, son groupe Planning et son utilisateur Moduleo.

Spec 1.5.1, ADR-0018 : sans groupe, aucun outil Moduleo n'est propose au
compte ; etre compte administrateur BBASS n'en donne aucun. Les groupes sont
ceux de `vm_centrale/moduleo/droits/catalogue.json` (en 1.5.1 : Admin),
charges en base au demarrage de la VM. L'utilisateur Moduleo est donne par
son nom (« Martin », « Jean Martin ») et resolu en id par une lecture de
`moduleo/utilisateur` : il faut alors la config Moduleo du `.env`.

Lancement, depuis vm-centrale/ :

    python scripts/affecter_groupes_moduleo.py j.dupont --cogeo Admin --planning Admin --utilisateur "Jean Dupont"
    python scripts/affecter_groupes_moduleo.py j.dupont --planning aucun
    python scripts/affecter_groupes_moduleo.py j.dupont

Une option absente garde sa valeur ; `aucun` la retire ; sans option, le
rattachement actuel est affiche. `--groupe-dev` cree d'abord les groupes
locaux « Tous droits (dev) » (Cogeo et Planning), pour le dev seulement.
Un droit ou un groupe change vaut a partir du tour suivant.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from vm_centrale.database import SessionLocal, init_db
from vm_centrale.models import Compte
from vm_centrale.moduleo.client import ErreurModuleo, LecteurModuleo, get_client_moduleo
from vm_centrale.moduleo.droits import GroupeInconnu, creer_groupes_dev, droits_du_compte, rattacher
from vm_centrale.moduleo.resolution import NomNonResolu, chercher_utilisateur

AUCUN = "aucun"


class AffectationImpossible(Exception):
    pass


def affecter(
    db: Session,
    lecteur: LecteurModuleo | None,
    identifiant: str,
    cogeo: str | None = None,
    planning: str | None = None,
    utilisateur: str | None = None,
    groupe_dev: bool = False,
) -> str:
    # None : inchangé ; AUCUN : retiré. Valide et renvoie le rattachement
    # obtenu, ou lève AffectationImpossible sans rien changer.
    if db.query(Compte).filter(Compte.identifiant == identifiant).first() is None:
        raise AffectationImpossible(f"Aucun compte « {identifiant} ».")
    if groupe_dev:
        creer_groupes_dev(db)
    actuel = droits_du_compte(db, identifiant)
    id_utilisateur = actuel.id_utilisateur_moduleo
    if utilisateur is not None and utilisateur != AUCUN:
        if lecteur is None:
            raise AffectationImpossible("Moduléo n'est pas configuré : utilisateur non résolu.")
        try:
            id_utilisateur = chercher_utilisateur(lecteur, utilisateur)
        except (NomNonResolu, ErreurModuleo) as erreur:
            raise AffectationImpossible(str(erreur)) from erreur
    elif utilisateur == AUCUN:
        id_utilisateur = None
    try:
        rattacher(
            db,
            identifiant,
            _valeur(cogeo, actuel.groupe_cogeo),
            _valeur(planning, actuel.groupe_planning),
            id_utilisateur,
        )
    except GroupeInconnu as erreur:
        db.rollback()
        raise AffectationImpossible(str(erreur)) from erreur
    db.commit()
    return decrire(db, identifiant)


def decrire(db: Session, identifiant: str) -> str:
    droits = droits_du_compte(db, identifiant)
    return (
        f"{identifiant} : groupe Cogeo {droits.groupe_cogeo or AUCUN}, "
        f"groupe Planning {droits.groupe_planning or AUCUN}, "
        f"utilisateur Moduléo {droits.id_utilisateur_moduleo or AUCUN}"
    )


def _valeur(option: str | None, actuelle: str | None) -> str | None:
    if option is None:
        return actuelle
    return None if option == AUCUN else option


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rattache un compte à ses groupes et à son utilisateur Moduléo.")
    parser.add_argument("identifiant", help="identifiant du compte BBASS")
    parser.add_argument("--cogeo", help=f"nom du groupe Cogeo, ou « {AUCUN} »")
    parser.add_argument("--planning", help=f"nom du groupe Planning, ou « {AUCUN} »")
    parser.add_argument("--utilisateur", help=f"nom de l'utilisateur Moduléo, ou « {AUCUN} »")
    parser.add_argument("--groupe-dev", action="store_true", help="crée d'abord les groupes « Tous droits (dev) »")
    arguments = parser.parse_args(argv)
    init_db()
    db = SessionLocal()
    try:
        if not (arguments.cogeo or arguments.planning or arguments.utilisateur or arguments.groupe_dev):
            print(decrire(db, arguments.identifiant))
            return 0
        lecteur = get_client_moduleo() if arguments.utilisateur not in (None, AUCUN) else None
        print(
            affecter(
                db,
                lecteur,
                arguments.identifiant,
                arguments.cogeo,
                arguments.planning,
                arguments.utilisateur,
                arguments.groupe_dev,
            )
        )
        return 0
    except AffectationImpossible as erreur:
        print(erreur, file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
