import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.mistral_client import MistralClient, get_mistral_client
from vm_centrale.models import Conversation, Message
from vm_centrale.schemas import (
    ConversationCreeRequest,
    ConversationCreeResponse,
    ConversationResume,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"

_bearer_scheme = HTTPBearer(auto_error=False)


def _prompt_titrage(message_utilisateur: str, reponse_assistant: str) -> str:
    return (
        "Propose un titre court (moins de 8 mots), sans guillemets, résumant "
        "l'échange suivant :\n"
        f"Utilisateur : {message_utilisateur}\n"
        f"Assistant : {reponse_assistant}"
    )


@router.post("/conversations", response_model=ConversationCreeResponse)
def creer_conversation(
    requete: ConversationCreeRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    client: MistralClient = Depends(get_mistral_client),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> ConversationCreeResponse:
    identifiant_compte = (
        jetons.identifiant_pour(credentials.credentials) if credentials is not None else None
    )
    if identifiant_compte is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    # Les deux appels Mistral (réponse, puis titrage) sont faits avant toute
    # écriture en base : en cas d'échec de l'un ou l'autre, aucune conversation
    # fantôme n'est persistée (cf. "pas de création d'une conversation vide").
    try:
        reponse = client.chat(requete.message)
        titre = client.chat(_prompt_titrage(requete.message, reponse))
    except Exception as erreur:
        logger.error("Échec de l'appel au relais Mistral : %s", erreur)
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    maintenant = datetime.now(timezone.utc)
    conversation = Conversation(
        identifiant_compte=identifiant_compte,
        titre=titre,
        resume_contexte="",
        date_creation=maintenant,
        date_derniere_activite=maintenant,
    )
    db.add(conversation)
    db.flush()

    db.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role="user",
                contenu=requete.message,
                date_creation=maintenant,
            ),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                contenu=reponse,
                date_creation=maintenant,
            ),
        ]
    )
    db.commit()
    db.refresh(conversation)

    return ConversationCreeResponse(
        conversation=ConversationResume(id=conversation.id, titre=conversation.titre),
        reponse=reponse,
    )
