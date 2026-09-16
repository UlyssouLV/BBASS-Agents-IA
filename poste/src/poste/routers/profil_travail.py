from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import ProfilTravailResponse
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import JetonInvalideError, VmCentraleClient, get_vm_centrale_client

router = APIRouter()

_AUCUNE_SESSION = "Aucune session active"
_VM_CENTRALE_INDISPONIBLE = "Le service de profil de travail de la VM centrale est indisponible"


@router.get("/profil-travail", response_model=ProfilTravailResponse)
def consulter_profil_travail(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> ProfilTravailResponse:
    identifiant = session.identifiant
    jeton = session.jeton
    if identifiant is None or jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)

    try:
        # Toujours le compte de la session : jamais d'identifiant fourni par
        # l'appelant (l'écran ne montre que le profil du collaborateur
        # connecté, spec V1.1.1 — pas de consultation croisée côté poste).
        profil = client.consulter_profil_travail(jeton, identifiant)
    except JetonInvalideError:
        session.fermer()
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION) from None
    except Exception as erreur:
        raise HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE) from erreur

    return ProfilTravailResponse(contenu=profil.contenu, date_derniere_maj=profil.date_derniere_maj)
