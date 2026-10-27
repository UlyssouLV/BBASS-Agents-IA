from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AccesAdminRequisError,
    JetonInvalideError,
    RefusModuleoError,
    VmCentraleClient,
    get_vm_centrale_client,
)

# Onglet Outils → Moduléo du Panel (spec 1.5.3, #213) : relais des routes
# /moduleo/* de la VM centrale, qui seule valide les droits admin, le
# catalogue des cases (lecture seule, ADR-0019) et les noms Moduléo. Les
# corps passent tels quels : leur forme est celle de vm_centrale.schemas.
router = APIRouter(prefix="/moduleo")

_AUCUNE_SESSION = "Aucune session active"
_ACCES_ADMIN_REQUIS = "Accès réservé aux comptes administrateurs"
_VM_CENTRALE_INDISPONIBLE = "Le service d'administration Moduléo de la VM centrale est indisponible"

_RESPONSES_BASE = {
    401: {"description": _AUCUNE_SESSION},
    403: {"description": _ACCES_ADMIN_REQUIS},
    502: {"description": _VM_CENTRALE_INDISPONIBLE},
}


def _erreur_vm_vers_http(session: SessionStore, erreur: Exception) -> HTTPException:
    if isinstance(erreur, JetonInvalideError):
        session.fermer()
        return HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    if isinstance(erreur, AccesAdminRequisError):
        return HTTPException(status_code=403, detail=_ACCES_ADMIN_REQUIS)
    if isinstance(erreur, RefusModuleoError):
        # Groupe encore rattaché, nom déjà pris, case hors catalogue,
        # utilisateur Moduléo inconnu... : le texte de la VM, tel quel.
        return HTTPException(status_code=erreur.status_code, detail=erreur.detail)
    return HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE)


def _relayer(
    client: VmCentraleClient, session: SessionStore, methode: str, chemin: str, corps: object = None
) -> object:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    try:
        return client.relayer_moduleo(jeton, methode, chemin, corps)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur


@router.get("/catalogue", responses=_RESPONSES_BASE)
def lire_catalogue(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "GET", "catalogue")


@router.get("/groupes", responses=_RESPONSES_BASE)
def lister_groupes(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "GET", "groupes")


@router.post("/groupes", status_code=201, responses=_RESPONSES_BASE)
def creer_groupe(
    corps: dict = Body(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "POST", "groupes", corps)


@router.patch("/groupes/{groupe_id}", responses=_RESPONSES_BASE)
def renommer_groupe(
    groupe_id: int,
    corps: dict = Body(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "PATCH", f"groupes/{groupe_id}", corps)


@router.delete("/groupes/{groupe_id}", status_code=204, responses=_RESPONSES_BASE)
def supprimer_groupe(
    groupe_id: int,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> Response:
    _relayer(client, session, "DELETE", f"groupes/{groupe_id}")
    return Response(status_code=204)


@router.get("/groupes/{groupe_id}/droits", responses=_RESPONSES_BASE)
def lire_droits_du_groupe(
    groupe_id: int,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "GET", f"groupes/{groupe_id}/droits")


@router.put("/groupes/{groupe_id}/droits", responses=_RESPONSES_BASE)
def remplacer_droits_du_groupe(
    groupe_id: int,
    droits: list[dict] = Body(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "PUT", f"groupes/{groupe_id}/droits", droits)


@router.get("/rattachements", responses=_RESPONSES_BASE)
def lister_rattachements(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "GET", "rattachements")


@router.patch("/rattachements/{identifiant}", responses=_RESPONSES_BASE)
def modifier_rattachement(
    identifiant: str,
    corps: dict = Body(...),
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "PATCH", f"rattachements/{quote(identifiant, safe='')}", corps)


@router.get("/journal", responses=_RESPONSES_BASE)
def lire_journal(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> object:
    return _relayer(client, session, "GET", "journal")
