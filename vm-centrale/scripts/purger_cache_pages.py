"""Supprime les copies du cache commun des pages web de plus de 24 h.

Une copie expiree est deja ignoree a la lecture (spec 1.4.3, ADR-0015) :
aucune purge pendant une requete, ce script s'en charge hors des tours. Seule
la table `cache_pages_web` est touchee, jamais les copies des conversations
(`resultats_recherche_web`). Pret pour une crontab ; le branchement releve du
deploiement (1.7.0).

Lancement : `python scripts/purger_cache_pages.py` depuis vm-centrale/.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.config import VALIDITE_CACHE_PAGES
from vm_centrale.database import SessionLocal, init_db
from vm_centrale.models import PageWebEnCache


def purger(db: Session, maintenant: datetime) -> int:
    limite = maintenant - VALIDITE_CACHE_PAGES
    nombre = (
        db.query(PageWebEnCache)
        .filter(PageWebEnCache.date_telechargement < limite)
        .delete(synchronize_session=False)
    )
    db.commit()
    return nombre


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        nombre = purger(db, datetime.now(timezone.utc))
    finally:
        db.close()
    print(f"Copies du cache des pages web supprimées : {nombre}")


if __name__ == "__main__":
    main()
