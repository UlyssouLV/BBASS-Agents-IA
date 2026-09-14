from fastapi import APIRouter, Depends, HTTPException

from vm_centrale.mistral_client import MistralClient, get_mistral_client
from vm_centrale.schemas import RelaisRequest, RelaisResponse

router = APIRouter()

_ECHEC_RELAIS = "Le relais Mistral est indisponible"


@router.post("/relais", response_model=RelaisResponse)
def relayer(
    requete: RelaisRequest, client: MistralClient = Depends(get_mistral_client)
) -> RelaisResponse:
    try:
        reponse = client.chat(requete.message)
    except Exception as erreur:
        # Le message d'exception n'est jamais renvoyé au client : une erreur
        # Mistral pourrait techniquement porter des détails de la requête
        # (dont la clé API) que l'endpoint ne doit jamais exposer.
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    return RelaisResponse(reponse=reponse)
