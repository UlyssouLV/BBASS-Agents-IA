from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import CompteResponse, ConnexionRequest, ConnexionResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import VmCentraleClient, get_vm_centrale_client

router = APIRouter()

_ECHEC_CONNEXION = "Identifiant ou mot de passe incorrect"
_VM_CENTRALE_INDISPONIBLE = "Le service de connexion de la VM centrale est indisponible"
_AUCUNE_SESSION = "Aucune session active"
_PERSISTANCE_DEGRADEE = (
    "Impossible d'enregistrer votre session de façon durable : "
    "une reconnexion sera nécessaire au prochain lancement du poste."
)


@router.post("/connexion", response_model=ConnexionResponse, response_model_exclude_none=True)
def connexion(
    requete: ConnexionRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ConnexionResponse:
    try:
        authentification = client.authentifier(requete.identifiant, requete.mot_de_passe)
    except Exception as erreur:
        # Couvre aussi bien une VM centrale injoignable qu'une réponse en erreur
        # de sa part : jamais un plantage côté poste, toujours un état d'erreur
        # propre distinct d'un échec d'authentification (qui reste un 401).
        raise HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE) from erreur

    if authentification is None:
        raise HTTPException(status_code=401, detail=_ECHEC_CONNEXION)

    session.ouvrir(
        requete.identifiant, authentification.prenom, authentification.nom, authentification.jeton
    )
    return ConnexionResponse(
        identifiant=requete.identifiant,
        prenom=authentification.prenom,
        nom=authentification.nom,
        avertissement=_PERSISTANCE_DEGRADEE if session.persistance_degradee else None,
    )


@router.post("/deconnexion", status_code=204)
def deconnexion(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> None:
    jeton = session.jeton
    session.fermer()
    if jeton is not None:
        try:
            client.revoquer(jeton)
        except Exception:
            # La session locale doit toujours pouvoir se fermer même si la VM
            # centrale est injoignable ; le jeton reste alors valide côté VM
            # jusqu'à son prochain redémarrage ou une révocation forcée.
            pass


@router.get("/compte", response_model=CompteResponse)
def compte_connecte(session: SessionStore = Depends(get_session_store)) -> CompteResponse:
    identifiant = session.identifiant
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    # SessionStore.ouvrir()/fermer() posent toujours identifiant, prenom et nom
    # ensemble : identifiant non-None garantit prenom/nom non-None.
    assert session.prenom is not None and session.nom is not None
    return CompteResponse(identifiant=identifiant, prenom=session.prenom, nom=session.nom)
