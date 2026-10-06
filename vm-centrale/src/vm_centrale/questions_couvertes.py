import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.config import MODELE_CHAT
from vm_centrale.consommation import enregistrer_consommation
from vm_centrale.inspecteur import (
    enregistrer_echange_echec,
    enregistrer_echange_succes,
    payload_depuis_erreur,
    reponse_depuis_erreur,
)
from vm_centrale.mistral_client import MistralClient, ReponseChat
from vm_centrale.models import QuestionCouverte

# Questions couvertes (spec 1.4.1) : constantes du code, comme la fenêtre de
# 3 messages. Partagées avec l'appel d'extraction de rechercher_web.
QUESTIONS_MAX = 8
REPONSE_MAX = 300

_TYPE_APPEL = "questions_piece_jointe"
# Consigne fixe de l'appel de questions d'une pièce jointe (spec 1.4.1) :
# il ne reçoit que le contenu extrait et le message du tour comme indice,
# jamais le reste de la conversation.
CONSIGNE_QUESTIONS_PIECE_JOINTE = (
    "Voici le contenu extrait d'une pièce jointe et le message envoyé avec "
    f"elle. Donne jusqu'à {QUESTIONS_MAX} questions auxquelles ce contenu "
    "répond, dont une pour le besoin du message si le contenu y répond, "
    f"chacune avec sa réponse ({REPONSE_MAX} caractères au plus). Le message "
    "n'est qu'un indice : jamais une question sur le message lui-même ou sur "
    "ce qu'il demande, seulement sur le contenu de la pièce jointe. N'écris rien "
    "qui ne soit pas dans le contenu : une information absente est « non "
    "trouvé », jamais une estimation.\n\n"
    "Réponds en JSON : `questions_couvertes`, la liste des questions "
    "(`question`, `reponse`)."
)
_SCHEMA_QUESTIONS_PIECE_JOINTE = {
    "type": "json_schema",
    "json_schema": {
        "name": _TYPE_APPEL,
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "questions_couvertes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "reponse": {"type": "string"},
                        },
                        "required": ["question", "reponse"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["questions_couvertes"],
            "additionalProperties": False,
        },
    },
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppelQuestionsPieceJointe:
    # Issue de l'appel, sans écriture en base : il tourne dans un thread, en
    # parallèle de la réponse de chat, hors de la session du tour.
    reponse: ReponseChat | None
    erreur: Exception | None = None


def appeler_questions_piece_jointe(
    client: MistralClient, nom_fichier: str, contenu_extrait: str, message: str
) -> AppelQuestionsPieceJointe:
    # Jamais d'exception : un échec est rendu à l'appelant, qui le journalise
    # sans erreur HTTP (la pièce jointe reste utilisable, sans questions).
    messages = [
        {"role": "system", "content": CONSIGNE_QUESTIONS_PIECE_JOINTE},
        {
            "role": "user",
            "content": (
                f"Message envoyé avec la pièce jointe : {message}\n\n"
                f"Pièce jointe « {nom_fichier} » :\n{contenu_extrait}"
            ),
        },
    ]
    try:
        return AppelQuestionsPieceJointe(client.chat(messages, response_format=_SCHEMA_QUESTIONS_PIECE_JOINTE))
    except Exception as erreur:
        return AppelQuestionsPieceJointe(None, erreur)


def _lire_questions(contenu: str) -> list[tuple[str, str]]:
    # Lève ValueError, KeyError ou TypeError si le JSON n'a pas la forme
    # demandée. Seules les QUESTIONS_MAX premières questions comptent.
    questions = json.loads(contenu)["questions_couvertes"]
    if not isinstance(questions, list):
        raise TypeError("questions_couvertes mal formé")
    lues = []
    for question in questions[:QUESTIONS_MAX]:
        champs = (question["question"], question["reponse"])
        if not all(isinstance(champ, str) for champ in champs):
            raise TypeError("question couverte mal formée")
        lues.append((champs[0].strip(), champs[1].strip()[:REPONSE_MAX]))
    return lues


def enregistrer_questions_piece_jointe(
    db: Session,
    appel: AppelQuestionsPieceJointe,
    *,
    identifiant_compte: str,
    conversation_id: int,
    piece_jointe_id: int,
    nom_fichier: str,
) -> None:
    # Sans commit, comme Consommation et l'inspecteur : le tour commite, ou
    # annule tout s'il échoue.
    if appel.reponse is None:
        logger.warning("Appel de questions de pièce jointe en échec : %s", appel.erreur)
        enregistrer_echange_echec(
            db,
            identifiant_compte=identifiant_compte,
            conversation_id=conversation_id,
            piece_jointe_id=piece_jointe_id,
            type_appel=_TYPE_APPEL,
            modele=MODELE_CHAT,
            requete_payload=payload_depuis_erreur(appel.erreur),
            reponse_payload=reponse_depuis_erreur(appel.erreur),
            erreur=str(appel.erreur),
            commit=False,
        )
        return
    reponse = appel.reponse
    enregistrer_consommation(db, identifiant_compte, conversation_id, _TYPE_APPEL, MODELE_CHAT, usage=reponse.usage)
    enregistrer_echange_succes(
        db,
        identifiant_compte=identifiant_compte,
        conversation_id=conversation_id,
        piece_jointe_id=piece_jointe_id,
        type_appel=_TYPE_APPEL,
        modele=MODELE_CHAT,
        requete_payload=reponse.payload_envoye,
        reponse_payload=reponse.reponse_brute,
    )
    try:
        questions = _lire_questions(reponse.contenu)
    except (ValueError, KeyError, TypeError) as erreur:
        # Appel payé et tracé tel quel : seule sa sortie est inutilisable.
        logger.warning("Appel de questions de pièce jointe hors du JSON attendu : %s", erreur)
        return
    maintenant = datetime.now(timezone.utc)
    db.add_all(
        QuestionCouverte(
            conversation_id=conversation_id,
            piece_jointe_id=piece_jointe_id,
            question=question,
            reponse=reponse_question,
            source=nom_fichier,
            trouvee=True,
            origine="initiale",
            date_creation=maintenant,
        )
        for question, reponse_question in questions
        if question
    )
