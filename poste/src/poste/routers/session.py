from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import ChangerMotDePasseRequest, CompteResponse, ConnexionRequest, ConnexionResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import JetonInvalideError, VmCentraleClient, get_vm_centrale_client

router = APIRouter()

_ECHEC_CONNEXION = "Identifiant ou mot de passe incorrect"
_VM_CENTRALE_INDISPONIBLE = "Le service de connexion de la VM centrale est indisponible"
_AUCUNE_SESSION = "Aucune session active"
_PERSISTANCE_DEGRADEE = (
    "Impossible d'enregistrer votre session de façon durable : "
    "une reconnexion sera nécessaire au prochain lancement du poste."
)


@router.post(
    "/connexion",
    response_model_exclude_none=True,
    responses={
        401: {"description": _ECHEC_CONNEXION},
        502: {"description": _VM_CENTRALE_INDISPONIBLE},
    },
)
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
        requete.identifiant,
        authentification.prenom,
        authentification.nom,
        authentification.jeton,
        authentification.agence,
        authentification.poles,
        authentification.est_admin,
        authentification.doit_changer_mot_de_passe,
    )
    return ConnexionResponse(
        identifiant=requete.identifiant,
        prenom=authentification.prenom,
        nom=authentification.nom,
        agence=authentification.agence,
        poles=authentification.poles,
        est_admin=authentification.est_admin,
        doit_changer_mot_de_passe=authentification.doit_changer_mot_de_passe,
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


@router.post(
    "/mot-de-passe",
    responses={
        401: {"description": _AUCUNE_SESSION},
        502: {"description": _VM_CENTRALE_INDISPONIBLE},
    },
)
def changer_mot_de_passe(
    requete: ChangerMotDePasseRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> CompteResponse:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    try:
        client.changer_mot_de_passe(jeton, requete.nouveau_mot_de_passe)
    except JetonInvalideError:
        session.fermer()
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION) from None
    except Exception as erreur:
        # Couvre aussi bien une VM centrale injoignable qu'une réponse en erreur
        # de sa part : jamais un plantage côté poste, toujours un état d'erreur
        # propre distinct d'un échec métier (qui reste un 401).
        raise HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE) from erreur

    session.marquer_mot_de_passe_change()

    # SessionStore garantit ces champs non-None dès qu'une session est ouverte
    # (voir compte_connecte ci-dessous), et le jeton ci-dessus le confirme.
    assert (
        session.identifiant is not None
        and session.prenom is not None
        and session.nom is not None
        and session.agence is not None
        and session.poles is not None
        and session.est_admin is not None
    )
    return CompteResponse(
        identifiant=session.identifiant,
        prenom=session.prenom,
        nom=session.nom,
        agence=session.agence,
        poles=session.poles,
        est_admin=session.est_admin,
        doit_changer_mot_de_passe=False,
    )


@router.get(
    "/compte",
    responses={401: {"description": _AUCUNE_SESSION}},
)
def compte_connecte(session: SessionStore = Depends(get_session_store)) -> CompteResponse:
    identifiant = session.identifiant
    if identifiant is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    # SessionStore.ouvrir()/fermer() posent toujours ces champs ensemble :
    # identifiant non-None garantit que les autres le sont aussi.
    assert (
        session.prenom is not None
        and session.nom is not None
        and session.agence is not None
        and session.poles is not None
        and session.est_admin is not None
        and session.doit_changer_mot_de_passe is not None
    )
    return CompteResponse(
        identifiant=identifiant,
        prenom=session.prenom,
        nom=session.nom,
        agence=session.agence,
        poles=session.poles,
        est_admin=session.est_admin,
        doit_changer_mot_de_passe=session.doit_changer_mot_de_passe,
    )
