from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import (
    CompteAdminResponse,
    CompteCreationRequest,
    CompteCreeResponse,
    CompteModificationRequest,
    MotDePasseReinitialiseResponse,
)
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AccesAdminRequisError,
    CompteInexistantError,
    IdentifiantDejaUtiliseError,
    JetonInvalideError,
    VmCentraleClient,
    get_vm_centrale_client,
)

router = APIRouter()

_AUCUNE_SESSION = "Aucune session active"
_ACCES_ADMIN_REQUIS = "Accès réservé aux comptes administrateurs"
_IDENTIFIANT_DEJA_UTILISE = "Cet identifiant est déjà utilisé"
_COMPTE_INTROUVABLE = "Compte introuvable"
_VM_CENTRALE_INDISPONIBLE = "Le service de gestion des comptes de la VM centrale est indisponible"


def _jeton_de_session(session: SessionStore) -> str:
    jeton = session.jeton
    if jeton is None:
        raise HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    return jeton


def _erreur_vm_vers_http(session: SessionStore, erreur: Exception) -> HTTPException:
    # Partagée par les deux endpoints : IdentifiantDejaUtiliseError ne peut
    # survenir qu'à la création, mais la traiter ici aussi évite de dupliquer
    # cette correspondance erreur-VM -> HTTP entre lister_comptes et
    # creer_compte. Couvre aussi bien une VM centrale injoignable qu'une
    # réponse en erreur de sa part (cas générique) : jamais un plantage côté
    # poste, toujours un état d'erreur propre.
    if isinstance(erreur, JetonInvalideError):
        session.fermer()
        return HTTPException(status_code=401, detail=_AUCUNE_SESSION)
    if isinstance(erreur, AccesAdminRequisError):
        return HTTPException(status_code=403, detail=_ACCES_ADMIN_REQUIS)
    if isinstance(erreur, IdentifiantDejaUtiliseError):
        return HTTPException(status_code=409, detail=_IDENTIFIANT_DEJA_UTILISE)
    if isinstance(erreur, CompteInexistantError):
        return HTTPException(status_code=404, detail=_COMPTE_INTROUVABLE)
    return HTTPException(status_code=502, detail=_VM_CENTRALE_INDISPONIBLE)


@router.get("/comptes", response_model=list[CompteAdminResponse])
def lister_comptes(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[CompteAdminResponse]:
    jeton = _jeton_de_session(session)
    try:
        comptes = client.lister_comptes(jeton)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [
        CompteAdminResponse(
            identifiant=compte.identifiant,
            prenom=compte.prenom,
            nom=compte.nom,
            email=compte.email,
            agence=compte.agence,
            poles=compte.poles,
            est_admin=compte.est_admin,
            doit_changer_mot_de_passe=compte.doit_changer_mot_de_passe,
        )
        for compte in comptes
    ]


@router.post("/comptes", response_model=CompteCreeResponse, status_code=201)
def creer_compte(
    requete: CompteCreationRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> CompteCreeResponse:
    jeton = _jeton_de_session(session)
    try:
        compte = client.creer_compte(
            jeton,
            identifiant=requete.identifiant,
            prenom=requete.prenom,
            nom=requete.nom,
            email=requete.email,
            agence=requete.agence,
            poles=requete.poles,
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return CompteCreeResponse(
        identifiant=compte.identifiant,
        prenom=compte.prenom,
        nom=compte.nom,
        email=compte.email,
        agence=compte.agence,
        poles=compte.poles,
        est_admin=compte.est_admin,
        doit_changer_mot_de_passe=compte.doit_changer_mot_de_passe,
        mot_de_passe=compte.mot_de_passe,
    )


@router.patch("/comptes/{identifiant}", response_model=CompteAdminResponse)
def modifier_compte(
    identifiant: str,
    requete: CompteModificationRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> CompteAdminResponse:
    jeton = _jeton_de_session(session)
    try:
        compte = client.modifier_compte(
            jeton,
            identifiant,
            prenom=requete.prenom,
            nom=requete.nom,
            email=requete.email,
            agence=requete.agence,
            poles=requete.poles,
        )
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return CompteAdminResponse(
        identifiant=compte.identifiant,
        prenom=compte.prenom,
        nom=compte.nom,
        email=compte.email,
        agence=compte.agence,
        poles=compte.poles,
        est_admin=compte.est_admin,
        doit_changer_mot_de_passe=compte.doit_changer_mot_de_passe,
    )


@router.post(
    "/comptes/{identifiant}/reinitialiser-mot-de-passe",
    response_model=MotDePasseReinitialiseResponse,
)
def reinitialiser_mot_de_passe(
    identifiant: str,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> MotDePasseReinitialiseResponse:
    jeton = _jeton_de_session(session)
    try:
        mot_de_passe = client.reinitialiser_mot_de_passe(jeton, identifiant)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return MotDePasseReinitialiseResponse(mot_de_passe=mot_de_passe)


@router.post("/comptes/{identifiant}/deconnexion-forcee", status_code=204)
def deconnexion_forcee(
    identifiant: str,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> None:
    jeton = _jeton_de_session(session)
    try:
        client.deconnexion_forcee(jeton, identifiant)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur
