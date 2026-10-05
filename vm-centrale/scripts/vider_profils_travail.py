"""Vide le contenu de tous les profils de travail, une fois au passage en 1.3.1.

Jusqu'en 1.3.0, chaque tour concatenait un delta au profil : tous les profils
existants sont potentiellement contamines (doublons, traits de l'assistant,
inventions figees). La VM n'a pas de framework de migration (init_db ne fait
que create_all) : ce script s'en charge. Les lignes sont gardees, seul
`contenu` est vide ; le prochain resume+profil reecrit le profil en entier.

Lancement : `python scripts/vider_profils_travail.py` depuis vm-centrale/.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.database import SessionLocal, init_db
from vm_centrale.models import ProfilTravail


def vider(db: Session) -> int:
    profils = db.query(ProfilTravail).all()
    maintenant = datetime.now(timezone.utc)
    for profil in profils:
        profil.contenu = ""
        profil.date_derniere_maj = maintenant
    db.commit()
    return len(profils)


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        nombre = vider(db)
    finally:
        db.close()
    print(f"Profils de travail vides : {nombre}")


if __name__ == "__main__":
    main()
