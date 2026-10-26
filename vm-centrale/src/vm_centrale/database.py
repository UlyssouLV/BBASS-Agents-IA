from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from vm_centrale.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# Colonnes ajoutées à une table existante, que `create_all` ne crée pas
# (pas de framework de migration) : (table, colonne, définition SQL).
_COLONNES_AJOUTEES = (
    # Spec 1.4.1 (#140) : les lignes existantes sont des résultats de
    # recherche.
    ("resultats_recherche_web", "provenance", "VARCHAR NOT NULL DEFAULT 'recherche'"),
    # Spec 1.4.2 : les messages existants restent à NULL.
    ("messages", "tokens_contexte", "INTEGER"),
    # Spec 1.5.0 (#177) : les questions existantes restent à NULL.
    ("questions_couvertes", "lecture_outil_id", "INTEGER REFERENCES lectures_outils(id)"),
)


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
    with bind.begin() as connexion:
        inspecteur = inspect(connexion)
        for table, colonne, definition in _COLONNES_AJOUTEES:
            if colonne not in {existante["name"] for existante in inspecteur.get_columns(table)}:
                connexion.execute(text(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}"))
    # Catalogue des Droits Moduléo et groupe Admin, rechargés à chaque
    # démarrage sans doublon (spec 1.5.1). Import ici : models importe Base.
    from vm_centrale.moduleo.droits import charger_catalogue

    with Session(bind=bind) as db:
        charger_catalogue(db)
        db.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


FabriqueSession = Callable[[], AbstractContextManager[Session]]


@contextmanager
def _session_du_tour() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_fabrique_session() -> FabriqueSession:
    # Le tour d'un envoi de message (ADR-0016) survit à la requête : il ouvre
    # et ferme sa propre session, jamais celle de get_db.
    return _session_du_tour
