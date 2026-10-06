from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vm_centrale.autorisation import exiger_cle_admin_vm, get_identifiant_compte_du_jeton
from vm_centrale.database import get_db
from vm_centrale.models import Conversation, EchangeInspecteur
from vm_centrale.schemas import (
    InspecteurCompteResponse,
    InspecteurConversationResponse,
    InspecteurEchangeDetailResponse,
    InspecteurEchangeResumeResponse,
)

# Mode développeur (spec 1.3.0) : chaque endpoint exige à la fois un jeton
# valide de n'importe quel compte (pas de droit est_admin requis, contrairement
# à routers/comptes.py) et la Clé d'administration VM — même combinaison que
# les endpoints les plus sensibles de routers/comptes.py, voir ADR-0012.
router = APIRouter(
    prefix="/inspecteur",
    dependencies=[Depends(get_identifiant_compte_du_jeton), Depends(exiger_cle_admin_vm)],
)

_ECHANGE_INTROUVABLE = "Échange introuvable"


def _vers_conversation(conversation: Conversation) -> InspecteurConversationResponse:
    return InspecteurConversationResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_creation=conversation.date_creation,
        date_derniere_activite=conversation.date_derniere_activite,
    )


def _vers_echange_resume(echange: EchangeInspecteur) -> InspecteurEchangeResumeResponse:
    return InspecteurEchangeResumeResponse(
        id=echange.id,
        origine=echange.origine,
        type_appel=echange.type_appel,
        statut=echange.statut,
        date_creation=echange.date_creation,
    )


@router.get("/comptes")
def lister_comptes(db: Session = Depends(get_db)) -> list[InspecteurCompteResponse]:
    # Jamais de jointure vers Compte (Conversation n'a pas de ForeignKey vers
    # comptes.identifiant) : juste les identifiants distincts portés par au
    # moins une conversation, pour la navigation du mode développeur.
    identifiants = (
        db.query(Conversation.identifiant_compte)
        .distinct()
        .order_by(Conversation.identifiant_compte)
        .all()
    )
    return [InspecteurCompteResponse(identifiant_compte=ligne[0]) for ligne in identifiants]


@router.get("/comptes/{identifiant_compte}/conversations")
def lister_conversations(
    identifiant_compte: str, db: Session = Depends(get_db)
) -> list[InspecteurConversationResponse]:
    # Portée volontairement sans restriction (spec 1.3.0, ADR-0012) : pas de
    # vérification que identifiant_compte correspond au compte du jeton — une
    # liste vide pour un identifiant inconnu ou sans conversation, jamais un
    # 404 (pas de notion d'existence de compte à protéger ici).
    conversations = (
        db.query(Conversation)
        .filter(Conversation.identifiant_compte == identifiant_compte)
        .order_by(Conversation.date_creation)
        .all()
    )
    return [_vers_conversation(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}/echanges")
def lister_echanges(
    conversation_id: int, db: Session = Depends(get_db)
) -> list[InspecteurEchangeResumeResponse]:
    # Ordre chronologique réel des appels Mistral et des échanges locaux
    # (spec 1.3.0, 1.4.0) : par id
    # d'insertion, jamais par date_creation seule (plusieurs échanges d'un
    # même tour peuvent partager le même instant applicatif, cf.
    # ThreadPoolExecutor de routers/conversations._generer_reponse_et_resume).
    echanges = (
        db.query(EchangeInspecteur)
        .filter(EchangeInspecteur.conversation_id == conversation_id)
        .order_by(EchangeInspecteur.id)
        .all()
    )
    return [_vers_echange_resume(echange) for echange in echanges]


@router.get(
    "/echanges/{echange_id}",
    responses={404: {"description": _ECHANGE_INTROUVABLE}},
)
def consulter_echange(echange_id: int, db: Session = Depends(get_db)) -> InspecteurEchangeDetailResponse:
    echange = db.get(EchangeInspecteur, echange_id)
    if echange is None:
        raise HTTPException(status_code=404, detail=_ECHANGE_INTROUVABLE)

    return InspecteurEchangeDetailResponse(
        id=echange.id,
        identifiant_compte=echange.identifiant_compte,
        conversation_id=echange.conversation_id,
        piece_jointe_id=echange.piece_jointe_id,
        origine=echange.origine,
        type_appel=echange.type_appel,
        modele=echange.modele,
        requete_payload=echange.requete_payload,
        reponse_payload=echange.reponse_payload,
        statut=echange.statut,
        erreur=echange.erreur,
        date_creation=echange.date_creation,
    )
