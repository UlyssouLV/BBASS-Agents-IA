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
    ConversationDetailResponse,
    ConversationRenommeeRequest,
    ConversationResponse,
    ConversationResume,
    MessageEnvoyeRequest,
    MessageEnvoyeResponse,
    MessageResponse,
)

_TAILLE_FENETRE_HISTORIQUE = 3

router = APIRouter()
logger = logging.getLogger(__name__)

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"
_CONVERSATION_INTROUVABLE = "Conversation introuvable"

_bearer_scheme = HTTPBearer(auto_error=False)


def _prompt_titrage(message_utilisateur: str, reponse_assistant: str) -> str:
    return (
        "Propose un titre court (moins de 8 mots), sans guillemets, résumant "
        "l'échange suivant :\n"
        f"Utilisateur : {message_utilisateur}\n"
        f"Assistant : {reponse_assistant}"
    )


def _construire_messages_pour_mistral(
    conversation: Conversation, derniers_messages: list[Message], nouveau_message: str
) -> list[dict[str, str]]:
    # Historique borné (résumé glissant + fenêtre courte) plutôt que
    # l'intégralité de la conversation, pour maîtriser le coût en tokens
    # (facturation Mistral au token). Le profil de travail sera ajouté par
    # le ticket suivant (#37).
    messages: list[dict[str, str]] = []
    if conversation.resume_contexte:
        messages.append({"role": "system", "content": conversation.resume_contexte})
    messages.extend({"role": m.role, "content": m.contenu} for m in derniers_messages)
    messages.append({"role": "user", "content": nouveau_message})
    return messages


def _identifiant_compte_du_jeton(
    credentials: HTTPAuthorizationCredentials | None, jetons: JetonStore
) -> str:
    identifiant_compte = (
        jetons.identifiant_pour(credentials.credentials) if credentials is not None else None
    )
    if identifiant_compte is None:
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)
    return identifiant_compte


def _recuperer_conversation_du_compte(
    db: Session, conversation_id: int, identifiant_compte: str
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.identifiant_compte != identifiant_compte:
        # Jamais 403 : ne révèle pas l'existence de l'id à un compte qui n'en
        # est pas propriétaire, y compris un compte administrateur (spec
        # V1.1.1 — le droit de compte administrateur ne porte jamais sur le
        # contenu des conversations).
        raise HTTPException(status_code=404, detail=_CONVERSATION_INTROUVABLE)
    return conversation


def _vers_resume(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_derniere_activite=conversation.date_derniere_activite,
    )


@router.post("/conversations", response_model=ConversationCreeResponse)
def creer_conversation(
    requete: ConversationCreeRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    client: MistralClient = Depends(get_mistral_client),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> ConversationCreeResponse:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)

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


@router.get("/conversations", response_model=list[ConversationResponse])
def lister_conversations(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)

    conversations = (
        db.query(Conversation)
        .filter(Conversation.identifiant_compte == identifiant_compte)
        .order_by(Conversation.date_derniere_activite.desc())
        .all()
    )
    return [_vers_resume(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def consulter_conversation(
    conversation_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )
    return ConversationDetailResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_creation=conversation.date_creation,
        date_derniere_activite=conversation.date_derniere_activite,
        messages=[
            MessageResponse(
                id=message.id,
                role=message.role,
                contenu=message.contenu,
                date_creation=message.date_creation,
            )
            for message in messages
        ],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def renommer_conversation(
    conversation_id: int,
    requete: ConversationRenommeeRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    conversation.titre = requete.titre
    db.commit()
    db.refresh(conversation)

    return _vers_resume(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
def supprimer_conversation(
    conversation_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> None:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    # Message n'a pas de cascade ORM déclarée sur Conversation (même
    # convention que Jeton/Compte, voir comptes.py) : la suppression des
    # messages associés doit donc être explicite, avant celle de la
    # conversation elle-même.
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageEnvoyeResponse
)
def envoyer_message(
    conversation_id: int,
    requete: MessageEnvoyeRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    client: MistralClient = Depends(get_mistral_client),
    jetons: JetonStore = Depends(get_jeton_store),
    db: Session = Depends(get_db),
) -> MessageEnvoyeResponse:
    identifiant_compte = _identifiant_compte_du_jeton(credentials, jetons)
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    derniers_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(_TAILLE_FENETRE_HISTORIQUE)
        .all()
    )
    derniers_messages.reverse()

    messages_pour_mistral = _construire_messages_pour_mistral(
        conversation, derniers_messages, requete.message
    )

    # Comme pour la création (cf. creer_conversation) : l'appel Mistral est
    # fait avant toute écriture, pour ne jamais persister un message
    # utilisateur sans sa réponse en cas d'échec.
    try:
        reponse = client.chat(messages_pour_mistral)
    except Exception as erreur:
        logger.error("Échec de l'appel au relais Mistral : %s", erreur)
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    maintenant = datetime.now(timezone.utc)
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
    conversation.date_derniere_activite = maintenant
    db.commit()

    return MessageEnvoyeResponse(reponse=reponse)
