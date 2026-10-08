from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.models import LectureOutil, Message

# Lectures d'outil (spec 1.5.0, #174) : chaque fiche qu'un outil d'un
# logiciel du cabinet renvoie au modèle, enregistrée dans la conversation
# (table `lectures_outils`), source des garde-fous chiffres et sources.

# Nom du logiciel dans la ligne « Sources : », par valeur de `outil`.
_LOGICIELS = {"moduleo": "Moduléo"}


@dataclass(frozen=True)
class Fiche:
    # `reference` : ce que la ligne « Sources : » cite après le logiciel
    # (« affaire 2024-123 ») ; `texte` : la fiche envoyée au modèle.
    reference: str
    texte: str


@dataclass(frozen=True)
class LectureDeLaConversation:
    # `citation` : « Moduléo, affaire 2024-123 », sans lien.
    citation: str
    texte: str
    date_creation: datetime


def enregistrer_lectures(db: Session, conversation_id: int, outil: str, fiches: list[Fiche]) -> None:
    # Flush (jamais commit), comme les résultats de recherche : les
    # garde-fous du même tour les relisent, un tour qui échoue les annule.
    maintenant = datetime.now(timezone.utc)
    db.add_all(
        LectureOutil(
            conversation_id=conversation_id,
            outil=outil,
            reference=fiche.reference,
            texte=fiche.texte,
            date_creation=maintenant,
        )
        for fiche in fiches
    )
    db.flush()


def lectures_de_la_conversation(db: Session, conversation_id: int) -> list[LectureDeLaConversation]:
    # Dans l'ordre de la conversation, la plus récente en dernier.
    lignes = (
        db.query(LectureOutil.outil, LectureOutil.reference, LectureOutil.texte, LectureOutil.date_creation)
        .filter(LectureOutil.conversation_id == conversation_id)
        .order_by(LectureOutil.id)
        .all()
    )
    return [
        LectureDeLaConversation(f"{_LOGICIELS.get(outil, outil)}, {reference}", texte, date_creation)
        for outil, reference, texte, date_creation in lignes
    ]


def rattacher_lectures_au_message(db: Session, message: Message) -> None:
    # Les lectures sans message sont celles de ce tour.
    db.flush()
    db.query(LectureOutil).filter(
        LectureOutil.conversation_id == message.conversation_id,
        LectureOutil.message_id.is_(None),
    ).update({LectureOutil.message_id: message.id})


def supprimer_lectures(db: Session, conversation_id: int) -> None:
    db.query(LectureOutil).filter(LectureOutil.conversation_id == conversation_id).delete()
