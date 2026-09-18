from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from poste.schemas import (
    ConversationCreationRequest,
    ConversationCreeResponse,
    ConversationDetailResponse,
    ConversationRenommeeRequest,
    ConversationResponse,
    ConversationResume,
    MessageEnvoyeRequest,
    MessageEnvoyeResponse,
    MessageResponse,
    PieceJointeCreeeResponse,
    PieceJointeResumeResponse,
)
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    ConversationIntrouvableError,
    JetonInvalideError,
    PieceJointeCreee,
    PieceJointeIntrouvableError,
    PieceJointeRefuseeError,
    VmCentraleClient,
    get_vm_centrale_client,
)

router = APIRouter()

_AUCUNE_SESSION = "Aucune session active"
_CONVERSATION_INTROUVABLE = "Conversation introuvable"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable"
_PIECE_JOINTE_REFUSEE = "Pièce jointe refusée"
_VM_CENTRALE_INDISPONIBLE = "Le service de conversations de la VM centrale est indisponible"


def _jeton_de_session(session: SessionStore) -> str:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    return jeton


def _erreur_vm_vers_http(session: SessionStore, erreur: Exception) -> HTTPException:
    # Même principe que poste.routers.comptes._erreur_vm_vers_http : couvre
    # aussi bien une VM centrale injoignable qu'une réponse en erreur de sa
    # part, jamais un plantage côté poste.
    if isinstance(erreur, JetonInvalideError):
        session.fermer()
        return HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    if isinstance(erreur, ConversationIntrouvableError):
        return HTTPException(status_code=404, detail=_CONVERSATION_INTROUVABLE)
    if isinstance(erreur, PieceJointeIntrouvableError):
        return HTTPException(status_code=404, detail=str(erreur) or _PIECE_JOINTE_INTROUVABLE)
    if isinstance(erreur, PieceJointeRefuseeError):
        # Relaie le texte de la VM (type non supporté, fichier trop
        # volumineux, ou déjà liée à un autre message — voir
        # PieceJointeRefuseeError), même principe que DernierAdministrateurError
        # côté comptes.py.
        return HTTPException(status_code=400, detail=str(erreur) or _PIECE_JOINTE_REFUSEE)
    return HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE)


# Base commune à toutes les routes ci-dessous : _jeton_de_session et
# _erreur_vm_vers_http sont partagées par tous les appelants (401/502 donc
# toujours atteignables). Chaque route étend ce socle avec les codes propres
# à son opération (404 conversation, 404/400 pièce jointe).
_RESPONSES_BASE = {
    401: {"description": _AUCUNE_SESSION},
    502: {"description": _VM_CENTRALE_INDISPONIBLE},
}
_RESPONSES_PIECE_JOINTE = {
    404: {"description": _PIECE_JOINTE_INTROUVABLE},
    400: {"description": _PIECE_JOINTE_REFUSEE},
}


@router.post(
    "/conversations",
    responses={**_RESPONSES_BASE, **_RESPONSES_PIECE_JOINTE},
)
def creer_conversation(
    requete: ConversationCreationRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ConversationCreeResponse:
    jeton = _jeton_de_session(session)
    try:
        cree = client.creer_conversation(
            jeton, requete.message, requete.cle_idempotence, requete.piece_jointe_id
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return ConversationCreeResponse(
        conversation=ConversationResume(id=cree.conversation.id, titre=cree.conversation.titre),
        reponse=cree.reponse,
    )


@router.get("/conversations", responses=_RESPONSES_BASE)
def lister_conversations(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[ConversationResponse]:
    jeton = _jeton_de_session(session)
    try:
        conversations = client.lister_conversations(jeton)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [
        ConversationResponse(
            id=conversation.id,
            titre=conversation.titre,
            date_derniere_activite=conversation.date_derniere_activite,
        )
        for conversation in conversations
    ]


@router.get(
    "/conversations/{conversation_id}",
    responses={**_RESPONSES_BASE, 404: {"description": _CONVERSATION_INTROUVABLE}},
)
def consulter_conversation(
    conversation_id: int,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ConversationDetailResponse:
    jeton = _jeton_de_session(session)
    try:
        detail = client.consulter_conversation(jeton, conversation_id)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return ConversationDetailResponse(
        id=detail.id,
        titre=detail.titre,
        date_creation=detail.date_creation,
        date_derniere_activite=detail.date_derniere_activite,
        messages=[
            MessageResponse(
                id=message.id,
                role=message.role,
                contenu=message.contenu,
                date_creation=message.date_creation,
            )
            for message in detail.messages
        ],
    )


@router.patch(
    "/conversations/{conversation_id}",
    responses={**_RESPONSES_BASE, 404: {"description": _CONVERSATION_INTROUVABLE}},
)
def renommer_conversation(
    conversation_id: int,
    requete: ConversationRenommeeRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ConversationResponse:
    jeton = _jeton_de_session(session)
    try:
        conversation = client.renommer_conversation(jeton, conversation_id, requete.titre)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return ConversationResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_derniere_activite=conversation.date_derniere_activite,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    responses={**_RESPONSES_BASE, 404: {"description": _CONVERSATION_INTROUVABLE}},
)
def supprimer_conversation(
    conversation_id: int,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> None:
    jeton = _jeton_de_session(session)
    try:
        client.supprimer_conversation(jeton, conversation_id)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur


@router.post(
    "/conversations/{conversation_id}/messages",
    responses={
        **_RESPONSES_BASE,
        **_RESPONSES_PIECE_JOINTE,
        404: {"description": f"{_CONVERSATION_INTROUVABLE} / {_PIECE_JOINTE_INTROUVABLE}"},
    },
)
def envoyer_message(
    conversation_id: int,
    requete: MessageEnvoyeRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> MessageEnvoyeResponse:
    jeton = _jeton_de_session(session)
    try:
        reponse = client.envoyer_message(
            jeton, conversation_id, requete.message, requete.cle_idempotence, requete.piece_jointe_id
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return MessageEnvoyeResponse(reponse=reponse)


def _piece_jointe_creee_response(cree: PieceJointeCreee) -> PieceJointeCreeeResponse:
    return PieceJointeCreeeResponse(
        piece_jointe=PieceJointeResumeResponse(
            id=cree.piece_jointe.id,
            nom_fichier=cree.piece_jointe.nom_fichier,
            type_mime=cree.piece_jointe.type_mime,
        ),
        echec_analyse=cree.echec_analyse,
    )


def _nom_et_type_du_fichier(fichier: UploadFile) -> tuple[str, str]:
    # Un fichier multipart sans nom ni type ne peut de toute façon
    # correspondre à aucun des types supportés par la VM (spec 1.1.2) : rejet
    # immédiat côté poste plutôt qu'un relais d'un None que la VM refuserait
    # de la même façon.
    if fichier.filename is None or fichier.content_type is None:
        raise HTTPException(status_code=400, detail=_PIECE_JOINTE_REFUSEE)
    return fichier.filename, fichier.content_type


@router.post(
    "/conversations/{conversation_id}/pieces-jointes",
    status_code=201,
    responses={
        **_RESPONSES_BASE,
        404: {"description": _CONVERSATION_INTROUVABLE},
        400: {"description": _PIECE_JOINTE_REFUSEE},
    },
)
def televerser_piece_jointe(
    conversation_id: int,
    fichier: UploadFile = File(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> PieceJointeCreeeResponse:
    jeton = _jeton_de_session(session)
    nom_fichier, type_mime = _nom_et_type_du_fichier(fichier)
    try:
        cree = client.televerser_piece_jointe(
            jeton, conversation_id, nom_fichier, fichier.file.read(), type_mime
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return _piece_jointe_creee_response(cree)


@router.post(
    "/pieces-jointes",
    status_code=201,
    responses={**_RESPONSES_BASE, 400: {"description": _PIECE_JOINTE_REFUSEE}},
)
def televerser_piece_jointe_sans_conversation(
    fichier: UploadFile = File(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> PieceJointeCreeeResponse:
    # Pas de conversation dans l'URL : seule façon de joindre un fichier dès
    # le tout premier message d'une conversation, qui n'existe pas encore au
    # moment de l'upload (spec 1.1.2 — voir ConversationCreationRequest.piece_jointe_id).
    jeton = _jeton_de_session(session)
    nom_fichier, type_mime = _nom_et_type_du_fichier(fichier)
    try:
        cree = client.televerser_piece_jointe_sans_conversation(
            jeton, nom_fichier, fichier.file.read(), type_mime
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return _piece_jointe_creee_response(cree)
