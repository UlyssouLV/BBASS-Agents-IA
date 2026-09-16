from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vm_centrale.database import Base


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifiant: Mapped[str] = mapped_column(String, unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String)
    prenom: Mapped[str] = mapped_column(String)
    nom: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    agence: Mapped[str] = mapped_column(String)
    est_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    doit_changer_mot_de_passe: Mapped[bool] = mapped_column(Boolean, default=False)
    poles: Mapped[list["ComptePole"]] = relationship(
        back_populates="compte", cascade="all, delete-orphan", order_by="ComptePole.pole"
    )


class ComptePole(Base):
    # Table de jointure compte/pôle ([[0006-compte-rattache-plusieurs-poles]]) :
    # la liste des six pôles reste une liste fermée fixée dans le code, pas une
    # table `Pôle` gérable dynamiquement pour cette itération.
    __tablename__ = "comptes_poles"

    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    pole: Mapped[str] = mapped_column(String, primary_key=True)

    compte: Mapped["Compte"] = relationship(back_populates="poles")


class Jeton(Base):
    __tablename__ = "jetons"

    jeton: Mapped[str] = mapped_column(String, primary_key=True)
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    date_emission: Mapped[datetime] = mapped_column(DateTime)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Pas de ForeignKey vers comptes.identifiant : même convention que Jeton
    # ci-dessus (le compte du jeton est résolu via JetonStore, jamais rejoint
    # en base).
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    titre: Mapped[str] = mapped_column(String)
    resume_contexte: Mapped[str] = mapped_column(String, default="")
    date_creation: Mapped[datetime] = mapped_column(DateTime)
    date_derniere_activite: Mapped[datetime] = mapped_column(DateTime)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String)
    contenu: Mapped[str] = mapped_column(String)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class ProfilTravail(Base):
    __tablename__ = "profils_travail"

    # Un-à-un avec Compte (une ligne par compte, identifiant_compte en PK).
    # Pas de ForeignKey vers comptes.identifiant : même convention que
    # Conversation/Jeton ci-dessus (le compte du jeton est résolu via
    # JetonStore, jamais rejoint en base).
    identifiant_compte: Mapped[str] = mapped_column(String, primary_key=True)
    contenu: Mapped[str] = mapped_column(String, default="")
    date_derniere_maj: Mapped[datetime] = mapped_column(DateTime)
