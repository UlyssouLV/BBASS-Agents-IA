from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import MessageRequest, MessageResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import VmCentraleClient, get_vm_centrale_client

router = APIRouter()

_AUCUNE_SESSION = "Aucune session active"
_RELAIS_INDISPONIBLE = "Le service de chat est indisponible"


@router.post("/chat", response_model=MessageResponse)
def envoyer_message(
    requete: MessageRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> MessageResponse:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    try:
        reponse = client.envoyer_message(requete.message, jeton)
    except Exception as erreur:
        # Couvre aussi bien une VM centrale injoignable qu'une réponse en erreur
        # de sa part : jamais un plantage côté poste, toujours un état d'erreur propre.
        raise HTTPException(status_code=502, detail=_RELAIS_INDISPONIBLE) from erreur

    return MessageResponse(reponse=reponse)
