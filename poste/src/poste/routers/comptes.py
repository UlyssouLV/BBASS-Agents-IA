from fastapi import APIRouter, Depends, HTTPException

from poste.schemas import (
    CompteAdminResponse,
    CompteConsommationResponse,
    CompteCreationRequest,
    CompteCreeResponse,
    CompteModificationRequest,
    DetailConsommationCategorieResponse,
    MotDePasseReinitialiseResponse,
    StatutAdminRequest,
    SuppressionCompteRequest,
)
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AccesAdminRequisError,
    CleAdminInvalideError,
    CompteInexistantError,
    DernierAdministrateurError,
    DetailConsommationCategorie,
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
# Mêmes textes que côté VM (vm_centrale.routers.comptes/autorisation) : voir
# _COMPTE_INTROUVABLE ci-dessus pour le même principe déjà en place.
_CLE_ADMIN_INVALIDE = "Clé d'administration manquante ou invalide"
_DERNIER_ADMINISTRATEUR = "Impossible de retirer le dernier compte administrateur restant"


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
    if isinstance(erreur, CleAdminInvalideError):
        # 403, jamais 401 : contrairement à un jeton invalide, la clé
        # d'administration VM saisie en trop n'a rien à voir avec la session
        # de l'administrateur, qui doit rester ouverte (voir
        # CleAdminInvalideError et ADR-0007).
        return HTTPException(status_code=403, detail=_CLE_ADMIN_INVALIDE)
    if isinstance(erreur, DernierAdministrateurError):
        # La VM distingue rétrogradation ("retirer") et suppression
        # ("supprimer") par un texte différent (voir DernierAdministrateurError) :
        # on le relaie tel quel plutôt que d'afficher toujours le même verbe.
        # Le message factice sans argument des tests de router retombe sur
        # _DERNIER_ADMINISTRATEUR.
        detail = str(erreur) or _DERNIER_ADMINISTRATEUR
        return HTTPException(status_code=409, detail=detail)
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


def _vers_detail_consommation_reponse(detail: DetailConsommationCategorie) -> DetailConsommationCategorieResponse:
    return DetailConsommationCategorieResponse(
        tokens_total=detail.tokens_total,
        pages_traitees=detail.pages_traitees,
        cout_usd=detail.cout_usd,
        nombre_requetes=detail.nombre_requetes,
    )


@router.get("/comptes/consommation", response_model=list[CompteConsommationResponse])
def lister_consommation_comptes(
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> list[CompteConsommationResponse]:
    jeton = _jeton_de_session(session)
    try:
        comptes = client.lister_consommation_comptes(jeton)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur

    return [
        CompteConsommationResponse(
            identifiant=compte.identifiant,
            prenom=compte.prenom,
            nom=compte.nom,
            cout_usd=compte.cout_usd,
            chat=_vers_detail_consommation_reponse(compte.chat),
            piece_jointe=_vers_detail_consommation_reponse(compte.piece_jointe),
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


@router.delete("/comptes/{identifiant}", status_code=204)
def supprimer_compte(
    identifiant: str,
    requete: SuppressionCompteRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> None:
    jeton = _jeton_de_session(session)
    try:
        client.supprimer_compte(jeton, identifiant, cle_admin_vm=requete.cle_admin_vm)
    except Exception as erreur:
        raise _erreur_vm_vers_http(session, erreur) from erreur


@router.patch("/comptes/{identifiant}/est-admin", response_model=CompteAdminResponse)
def modifier_statut_admin(
    identifiant: str,
    requete: StatutAdminRequest,
    client: VmCentraleClient = Depends(get_vm_centrale_client),
    session: SessionStore = Depends(get_session_store),
) -> CompteAdminResponse:
    jeton = _jeton_de_session(session)
    try:
        compte = client.modifier_statut_admin(
            jeton, identifiant, est_admin=requete.est_admin, cle_admin_vm=requete.cle_admin_vm
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
