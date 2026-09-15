from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from vm_centrale.database import Base


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifiant: Mapped[str] = mapped_column(String, unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String)
    prenom: Mapped[str] = mapped_column(String)
    nom: Mapped[str] = mapped_column(String)
    agence: Mapped[str] = mapped_column(String)
    pole: Mapped[str] = mapped_column(String)


class Jeton(Base):
    __tablename__ = "jetons"

    jeton: Mapped[str] = mapped_column(String, primary_key=True)
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    date_emission: Mapped[datetime] = mapped_column(DateTime)
