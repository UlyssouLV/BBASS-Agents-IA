import secrets
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.orm import Session

from vm_centrale.database import get_db
from vm_centrale.models import Jeton


class JetonStore:
    # Persisté dans la table `jetons` de la base centrale (voir Session dans
    # CONTEXT.md) : un jeton reste valide après un redémarrage du processus
    # de la VM centrale, jusqu'à une déconnexion explicite ou une révocation
    # forcée.
    def __init__(self, db: Session) -> None:
        self._db = db

    def emettre(self, identifiant_compte: str) -> str:
        jeton = secrets.token_urlsafe(32)
        self._db.add(
            Jeton(
                jeton=jeton,
                identifiant_compte=identifiant_compte,
                date_emission=datetime.now(timezone.utc),
            )
        )
        self._db.commit()
        return jeton

    def est_valide(self, jeton: str) -> bool:
        # Exprimé via identifiant_pour (plutôt qu'un second lookup indépendant)
        # pour qu'un jeton ne puisse jamais être valide pour l'un et invalide
        # pour l'autre.
        return self.identifiant_pour(jeton) is not None

    def identifiant_pour(self, jeton: str) -> str | None:
        ligne = self._db.get(Jeton, jeton)
        return ligne.identifiant_compte if ligne is not None else None

    def revoquer(self, jeton: str) -> None:
        ligne = self._db.get(Jeton, jeton)
        if ligne is not None:
            self._db.delete(ligne)
            self._db.commit()

    def revoquer_tous(self, identifiant_compte: str) -> None:
        self._db.query(Jeton).filter(Jeton.identifiant_compte == identifiant_compte).delete()
        self._db.commit()


def get_jeton_store(db: Session = Depends(get_db)) -> JetonStore:
    return JetonStore(db)
