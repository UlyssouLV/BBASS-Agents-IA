from fastapi import APIRouter, Depends, Header, HTTPException

from poste.schemas import (
    InspecteurCompteResponse,
    InspecteurConversationResponse,
    InspecteurEchangeDetailResponse,
    InspecteurEchangeResumeResponse,
)
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    CleAdminInvalideError,
    EchangeIntrouvableError,
    JetonInvalideError,
    VmCentraleClient,
    get_vm_centrale_client,
)

router = APIRouter(prefix="/inspecteur")

_AUCUNE_SESSION = "Aucune session active"
# Même texte que côté VM (vm_centrale.autorisation._CLE_ADMIN_INVALIDE) : voir
# poste.routers.comptes._CLE_ADMIN_INVALIDE pour le même principe déjà en place.
_CLE_ADMIN_INVALIDE = "Clé d'administration manquante ou invalide"
_ECHANGE_INTROUVABLE = "Échange introuvable"
_VM_CENTRALE_INDISPONIBLE = "Le service de l'inspecteur de la VM centrale est indisponible"

# Base commune aux quatre routes ci-dessous (même principe que
# poste.routers.comptes._RESPONSES_BASE) : jamais de 403 ici, contrairement à
# comptes.py (jeton de n'importe quel compte, pas de droit est_admin requis,
# spec 1.3.0).
_RESPONSES_BASE = {
    401: {"description": f"{_AUCUNE_SESSION} / {_CLE_ADMIN_INVALIDE}"},
    502: {"description": _VM_CENTRALE_INDISPONIBLE},
}


def _jeton_de_session(session: SessionStore) -> str:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    return jeton


def _erreur_vm_vers_http(session: SessionStore, erreur: Exception) -> HTTPException:
    if isinstance(erreur, JetonInvalideError):
        session.fermer()
        return HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    if isinstance(erreur, CleAdminInvalideError):
        # 401, pas 403 : même code que la VM (vm_centrale.autorisation.
        # exiger_cle_admin_vm), et ne ferme pas la session (la clé
        # d'administration VM saisie en trop n'a rien à voir avec elle, voir
        # poste.routers.comptes._erreur_vm_vers_http).
        return HTTPException(status_code=401, detail=_CLE_ADMIN_INVALIDE)
    if isinstance(erreur, EchangeIntrouvableError):
        return HTTPException(status_code=404, detail=_ECHANGE_INTROUVABLE)
    return HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE)


@router.get("/comptes", responses=_RESPONSES_BASE)
def lister_comptes(
    x_admin_key: str = Header(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[InspecteurCompteResponse]:
    jeton = _jeton_de_session(session)
    try:
        comptes = client.lister_comptes_inspecteur(jeton, x_admin_key)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [InspecteurCompteResponse(identifiant_compte=compte.identifiant_compte) for compte in comptes]


@router.get("/comptes/{identifiant_compte}/conversations", responses=_RESPONSES_BASE)
def lister_conversations(
    identifiant_compte: str,
    x_admin_key: str = Header(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[InspecteurConversationResponse]:
    jeton = _jeton_de_session(session)
    try:
        conversations = client.lister_conversations_inspecteur(jeton, identifiant_compte, x_admin_key)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [
        InspecteurConversationResponse(
            id=conversation.id,
            titre=conversation.titre,
            date_creation=conversation.date_creation,
            date_derniere_activite=conversation.date_derniere_activite,
        )
        for conversation in conversations
    ]


@router.get("/conversations/{conversation_id}/echanges", responses=_RESPONSES_BASE)
def lister_echanges(
    conversation_id: int,
    x_admin_key: str = Header(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[InspecteurEchangeResumeResponse]:
    jeton = _jeton_de_session(session)
    try:
        echanges = client.lister_echanges_inspecteur(jeton, conversation_id, x_admin_key)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [
        InspecteurEchangeResumeResponse(
            id=echange.id,
            type_appel=echange.type_appel,
            statut=echange.statut,
            date_creation=echange.date_creation,
        )
        for echange in echanges
    ]


@router.get(
    "/echanges/{echange_id}",
    responses={**_RESPONSES_BASE, 404: {"description": _ECHANGE_INTROUVABLE}},
)
def consulter_echange(
    echange_id: int,
    x_admin_key: str = Header(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> InspecteurEchangeDetailResponse:
    jeton = _jeton_de_session(session)
    try:
        echange = client.consulter_echange_inspecteur(jeton, echange_id, x_admin_key)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return InspecteurEchangeDetailResponse(
        id=echange.id,
        identifiant_compte=echange.identifiant_compte,
        conversation_id=echange.conversation_id,
        piece_jointe_id=echange.piece_jointe_id,
        type_appel=echange.type_appel,
        modele=echange.modele,
        requete_payload=echange.requete_payload,
        reponse_payload=echange.reponse_payload,
        statut=echange.statut,
        erreur=echange.erreur,
        date_creation=echange.date_creation,
    )
