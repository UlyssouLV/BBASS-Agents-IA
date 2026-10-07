from collections.abc import Generator

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
)


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
    with bind.begin() as connexion:
        inspecteur = inspect(connexion)
        for table, colonne, definition in _COLONNES_AJOUTEES:
            if colonne not in {existante["name"] for existante in inspecteur.get_columns(table)}:
                connexion.execute(text(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
