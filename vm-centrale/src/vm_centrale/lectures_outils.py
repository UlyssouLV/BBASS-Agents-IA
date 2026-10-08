from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.models import LectureOutil, Message, QuestionCouverte
from vm_centrale.questions_couvertes import REPONSE_MAX

# Lectures d'outil (spec 1.5.0, #174) : chaque fiche qu'un outil d'un
# logiciel du cabinet renvoie au modèle, enregistrée dans la conversation
# (table `lectures_outils`), source des garde-fous chiffres et sources,
# listée dans la Mémoire de la conversation avec ses questions couvertes
# (#177).

# Nom du logiciel dans la ligne « Sources : », par valeur de `outil`.
_LOGICIELS = {"moduleo": "Moduléo"}


@dataclass(frozen=True)
class Fiche:
    # `reference` : ce que la ligne « Sources : » cite après le logiciel
    # (« affaire 2024-123 ») ; `texte` : la fiche envoyée au modèle ;
    # `questions` : ses questions couvertes (question, réponse), écrites par
    # script.
    reference: str
    texte: str
    questions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LectureDeLaConversation:
    # `citation` : « Moduléo, affaire 2024-123 », sans lien. `message_id` :
    # None pour une lecture du tour en cours.
    id: int
    message_id: int | None
    citation: str
    texte: str
    date_creation: datetime


def enregistrer_lectures(db: Session, conversation_id: int, outil: str, fiches: list[Fiche]) -> None:
    # Flush (jamais commit), comme les résultats de recherche : les
    # garde-fous du même tour les relisent, un tour qui échoue les annule.
    # Questions couvertes d'origine `initiale`, jamais une source des
    # garde-fous (règle 1.4.1).
    maintenant = datetime.now(timezone.utc)
    lectures = [
        LectureOutil(
            conversation_id=conversation_id,
            outil=outil,
            reference=fiche.reference,
            texte=fiche.texte,
            date_creation=maintenant,
        )
        for fiche in fiches
    ]
    db.add_all(lectures)
    db.flush()
    db.add_all(
        QuestionCouverte(
            conversation_id=conversation_id,
            lecture_outil_id=lecture.id,
            question=question,
            reponse=reponse[:REPONSE_MAX],
            source=_citation(outil, fiche.reference),
            trouvee=True,
            origine="initiale",
            date_creation=maintenant,
        )
        for lecture, fiche in zip(lectures, fiches)
        for question, reponse in fiche.questions
    )
    db.flush()


def lectures_de_la_conversation(db: Session, conversation_id: int) -> list[LectureDeLaConversation]:
    # Dans l'ordre de la conversation, la plus récente en dernier.
    lignes = (
        db.query(
            LectureOutil.id,
            LectureOutil.message_id,
            LectureOutil.outil,
            LectureOutil.reference,
            LectureOutil.texte,
            LectureOutil.date_creation,
        )
        .filter(LectureOutil.conversation_id == conversation_id)
        .order_by(LectureOutil.id)
        .all()
    )
    return [
        LectureDeLaConversation(lecture_id, message_id, _citation(outil, reference), texte, date_creation)
        for lecture_id, message_id, outil, reference, texte, date_creation in lignes
    ]


def _citation(outil: str, reference: str) -> str:
    return f"{_LOGICIELS.get(outil, outil)}, {reference}"


def rattacher_lectures_au_message(db: Session, message: Message) -> None:
    # Les lectures sans message sont celles de ce tour.
    db.flush()
    db.query(LectureOutil).filter(
        LectureOutil.conversation_id == message.conversation_id,
        LectureOutil.message_id.is_(None),
    ).update({LectureOutil.message_id: message.id})


def supprimer_lectures(db: Session, conversation_id: int) -> None:
    db.query(LectureOutil).filter(LectureOutil.conversation_id == conversation_id).delete()
