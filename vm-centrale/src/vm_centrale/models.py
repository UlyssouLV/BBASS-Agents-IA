from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from vm_centrale.database import Base


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifiant: Mapped[str] = mapped_column(String, unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String)
    agence: Mapped[str] = mapped_column(String)
    pole: Mapped[str] = mapped_column(String)
