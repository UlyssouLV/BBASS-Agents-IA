from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from vm_centrale.config import VALIDITE_CACHE_PAGES
from vm_centrale.models import PageWebEnCache

# Tâches planifiées de la VM (spec 1.6.1, ADR-0021, #234) : une tâche = une
# entrée de TACHES, lancée par la sous-commande `tache <nom>`, et une ligne
# `<nom> <OnCalendar>` dans deploiement/taches-planifiees.conf (timer
# bbass-<env>-<nom>, voir vm_centrale.taches_planifiees).


def maintenant() -> datetime:
    return datetime.now(UTC)


def purger_cache_pages(db: Session) -> None:
    # Copies du cache commun des pages web de plus de 24 h (spec 1.4.3,
    # ADR-0015) : déjà ignorées à la lecture, supprimées ici hors des tours.
    # Jamais les copies des conversations (`resultats_recherche_web`).
    limite = maintenant() - VALIDITE_CACHE_PAGES
    nombre = (
        db.query(PageWebEnCache)
        .filter(PageWebEnCache.date_telechargement < limite)
        .delete(synchronize_session=False)
    )
    db.commit()
    print(f"Copies du cache des pages web supprimées : {nombre}")


TACHES: dict[str, Callable[[Session], None]] = {
    "purger-cache-pages": purger_cache_pages,
}


def executer_tache(nom: str) -> None:
    # Import à l'appel : `database` crée l'engine de VM_CENTRALE_DATABASE_URL.
    from vm_centrale import database

    database.init_db()
    with database.SessionLocal() as db:
        TACHES[nom](db)
