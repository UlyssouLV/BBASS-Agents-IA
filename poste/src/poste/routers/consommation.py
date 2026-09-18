from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import ConsommationResponse, ConversationConsommationResponse, DetailConsommationCategorieResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    Consommation,
    ConversationConsommation,
    DetailConsommationCategorie,
    JetonInvalideError,
    VmCentraleClient,
    get_vm_centrale_client,
)

router = APIRouter()

_AUCUNE_SESSION = "Aucune session active"
_VM_CENTRALE_INDISPONIBLE = "Le service de consommation de la VM centrale est indisponible"


def _vers_detail_reponse(detail: DetailConsommationCategorie) -> DetailConsommationCategorieResponse:
    return DetailConsommationCategorieResponse(
        tokens_total=detail.tokens_total,
        pages_traitees=detail.pages_traitees,
        cout_usd=detail.cout_usd,
        nombre_requetes=detail.nombre_requetes,
    )


def _vers_conversation_reponse(conversation: ConversationConsommation) -> ConversationConsommationResponse:
    return ConversationConsommationResponse(
        id=conversation.id,
        titre=conversation.titre,
        cout_usd=conversation.cout_usd,
        chat=_vers_detail_reponse(conversation.chat),
        piece_jointe=_vers_detail_reponse(conversation.piece_jointe),
    )


@router.get(
    "/consommation",
    responses={
        401: {"description": _AUCUNE_SESSION},
        502: {"description": _VM_CENTRALE_INDISPONIBLE},
    },
)
def consulter_consommation(
    client: Annotated[VmCentraleClient, Depends(get_vm_centrale_client)],
    session: Annotated[SessionStore, Depends(get_session_store)],
) -> ConsommationResponse:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    try:
        # Toujours celle du compte de la session : GET /consommation côté VM
        # centrale n'accepte pas d'identifiant, il extrait le compte du jeton
        # lui-même (voir vm_centrale_client.consulter_consommation).
        consommation: Consommation = client.consulter_consommation(jeton)
    except JetonInvalideError:
        session.fermer()
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION) from None
    except Exception as erreur:
        raise HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE) from erreur

    return ConsommationResponse(
        chat=_vers_detail_reponse(consommation.chat),
        piece_jointe=_vers_detail_reponse(consommation.piece_jointe),
        conversations=[_vers_conversation_reponse(c) for c in consommation.conversations],
    )
