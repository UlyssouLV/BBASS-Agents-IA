from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vm_centrale.mistral_client import MistralClient, get_mistral_client
from vm_centrale.schemas import RelaisRequest, RelaisResponse
from vm_centrale.jetons import JetonStore, get_jeton_store

router = APIRouter()

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_JETON_INVALIDE = "Jeton d'authentification manquant ou invalide"

_bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/relais", response_model=RelaisResponse)
def relayer(
    requete: RelaisRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    client: MistralClient = Depends(get_mistral_client),
    jetons: JetonStore = Depends(get_jeton_store),
) -> RelaisResponse:
    if credentials is None or not jetons.est_valide(credentials.credentials):
        raise HTTPException(status_code=401, detail=_JETON_INVALIDE)

    try:
        reponse = client.chat(requete.message)
    except Exception as erreur:
        # Le message d'exception n'est jamais renvoyé au client : une erreur
        # Mistral pourrait techniquement porter des détails de la requête
        # (dont la clé API) que l'endpoint ne doit jamais exposer.
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    return RelaisResponse(reponse=reponse)
