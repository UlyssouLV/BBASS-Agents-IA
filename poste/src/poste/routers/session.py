from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import CompteResponse, ConnexionRequest, ConnexionResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import VmCentraleClient, get_vm_centrale_client

router = APIRouter()

_ECHEC_CONNEXION = "Identifiant ou mot de passe incorrect"
_VM_CENTRALE_INDISPONIBLE = "Le service de connexion de la VM centrale est indisponible"
_AUCUNE_SESSION = "Aucune session active"


@router.post("/connexion", response_model=ConnexionResponse)
def connexion(
    requete: ConnexionRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ConnexionResponse:
    try:
        authentifie = client.authentifier(requete.identifiant, requete.mot_de_passe)
    except Exception as erreur:
        # Couvre aussi bien une VM centrale injoignable qu'une réponse en erreur
        # de sa part : jamais un plantage côté poste, toujours un état d'erreur
        # propre distinct d'un échec d'authentification (qui reste un 401).
        raise HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE) from erreur

    if not authentifie:
        raise HTTPException(status_code=401, detail=_ECHEC_CONNEXION)

    session.ouvrir(requete.identifiant)
    return ConnexionResponse(identifiant=requete.identifiant)


@router.post("/deconnexion", status_code=204)
def deconnexion(session: SessionStore = Depends(get_session_store)) -> None:
    session.fermer()


@router.get("/compte", response_model=CompteResponse)
def compte_connecte(session: SessionStore = Depends(get_session_store)) -> CompteResponse:
    identifiant = session.identifiant
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    return CompteResponse(identifiant=identifiant)
