import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vm_centrale.autorisation import get_identifiant_compte_du_jeton
from vm_centrale.concurrence import cache_idempotence, verrous_comptes
from vm_centrale.database import get_db
from vm_centrale.mistral_client import MistralClient, get_mistral_client
from vm_centrale.models import Compte, Conversation, Message, ProfilTravail
from vm_centrale.schemas import (
    ConversationCreeRequest,
    ConversationCreeResponse,
    ConversationDetailResponse,
    ConversationRenommeeRequest,
    ConversationResponse,
    ConversationResume,
    MessageEnvoyeRequest,
    MessageEnvoyeResponse,
    MessageResponse,
)

_TAILLE_FENETRE_HISTORIQUE = 3

router = APIRouter()
logger = logging.getLogger(__name__)

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_CONVERSATION_INTROUVABLE = "Conversation introuvable"

# Sortie structurée stricte (spec V1.1.1) : un seul appel Mistral produit à la
# fois le résumé glissant mis à jour et une éventuelle mise à jour du profil
# de travail, pour ne payer le contexte partagé (résumé courant, profil
# courant, message(s) sortant(s)) qu'une seule fois.
_SCHEMA_RESUME_ET_PROFIL = {
    "type": "json_schema",
    "json_schema": {
        "name": "resume_et_profil",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "resume_contexte": {"type": "string"},
                "profil_travail_delta": {"type": ["string", "null"]},
            },
            "required": ["resume_contexte", "profil_travail_delta"],
            "additionalProperties": False,
        },
    },
}


def _prompt_titrage(message_utilisateur: str, reponse_assistant: str) -> str:
    return (
        "Propose un titre court (moins de 8 mots), sans guillemets, résumant "
        "l'échange suivant :\n"
        f"Utilisateur : {message_utilisateur}\n"
        f"Assistant : {reponse_assistant}"
    )


def _construire_messages_pour_mistral(
    conversation: Conversation,
    derniers_messages: list[Message],
    nouveau_message: str,
    profil_travail: str,
) -> list[dict[str, str]]:
    # Historique borné (résumé glissant + fenêtre courte) plutôt que
    # l'intégralité de la conversation, pour maîtriser le coût en tokens
    # (facturation Mistral au token). Le profil de travail est inclus ici
    # aussi (spec V1.1.1 : résumé + profil + 3 derniers messages + nouveau
    # message) : sans lui, la réponse de chat elle-même ignorerait tout ce
    # que le profil a appris de la façon de travailler du compte, alors que
    # c'est justement sa raison d'être (contexte pour l'IA qui répond).
    messages: list[dict[str, str]] = []
    if conversation.resume_contexte:
        messages.append({"role": "system", "content": conversation.resume_contexte})
    if profil_travail:
        messages.append(
            {"role": "system", "content": f"Profil de travail du compte : {profil_travail}"}
        )
    messages.extend({"role": m.role, "content": m.contenu} for m in derniers_messages)
    messages.append({"role": "user", "content": nouveau_message})
    return messages


def _identite_connue(compte: Compte | None) -> str:
    if compte is None:
        return "(non disponible)"
    poles = ", ".join(pole.pole for pole in compte.poles)
    return f"{compte.prenom} {compte.nom}, pôle(s) : {poles}, agence : {compte.agence}"


def _prompt_resume_et_profil(
    resume_contexte: str,
    profil_travail: str,
    compte: Compte | None,
    messages_sortants: list[Message],
) -> str:
    echange_sortant = "\n".join(f"{m.role} : {m.contenu}" for m in messages_sortants)
    return (
        "Tu maintiens deux mémoires pour ce compte : un résumé glissant de la "
        "conversation en cours, et un profil de travail inter-conversationnel "
        "décrivant sa façon de travailler.\n"
        f"Identité déjà connue du compte, fait acquis — ne cherche jamais à la "
        f"déterminer ni à la modifier : {_identite_connue(compte)}.\n"
        f"Résumé glissant actuel : {resume_contexte or '(vide)'}\n"
        f"Profil de travail actuel : {profil_travail or '(vide)'}\n"
        "Message(s) qui sortent de la fenêtre des derniers messages, à "
        f"absorber dans le résumé :\n{echange_sortant}\n\n"
        "Renvoie un objet JSON avec resume_contexte (résumé glissant mis à "
        "jour, incorporant ces messages sortants) et profil_travail_delta "
        "(un ajout au profil de travail, vide si rien à ajouter). "
        "N'inclus jamais dans profil_travail_delta un fait d'identité "
        "(prénom, nom, pôle, agence) : ceux-ci sont déjà connus et ne "
        "doivent jamais être réinférés ni modifiés depuis une conversation."
    )


def _contenu_profil_actuel(db: Session, identifiant_compte: str) -> str:
    profil = db.get(ProfilTravail, identifiant_compte)
    return profil.contenu if profil is not None else ""


def _recuperer_ou_creer_profil(db: Session, identifiant_compte: str) -> ProfilTravail:
    # N'ajoute à la session que lorsqu'une mise à jour va effectivement être
    # persistée (jamais depuis _contenu_profil_actuel, une simple lecture
    # utilisée avant l'appel Mistral) : pas de ligne fantôme en cas d'échec.
    profil = db.get(ProfilTravail, identifiant_compte)
    if profil is None:
        profil = ProfilTravail(
            identifiant_compte=identifiant_compte,
            contenu="",
            date_derniere_maj=datetime.now(timezone.utc),
        )
        db.add(profil)
    return profil


def _recuperer_conversation_du_compte(
    db: Session, conversation_id: int, identifiant_compte: str
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.identifiant_compte != identifiant_compte:
        # Jamais 403 : ne révèle pas l'existence de l'id à un compte qui n'en
        # est pas propriétaire, y compris un compte administrateur (spec
        # V1.1.1 — le droit de compte administrateur ne porte jamais sur le
        # contenu des conversations).
        raise HTTPException(status_code=404, detail=_CONVERSATION_INTROUVABLE)
    return conversation


def _vers_resume(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_derniere_activite=conversation.date_derniere_activite,
    )


@router.post("/conversations", response_model=ConversationCreeResponse)
def creer_conversation(
    requete: ConversationCreeRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    db: Session = Depends(get_db),
) -> ConversationCreeResponse:
    with verrous_comptes.pour(identifiant_compte):
        if requete.cle_idempotence is not None:
            reponse_en_cache = cache_idempotence.recuperer(identifiant_compte, requete.cle_idempotence)
            if reponse_en_cache is not None:
                assert isinstance(reponse_en_cache, ConversationCreeResponse)
                return reponse_en_cache

        # Les deux appels Mistral (réponse, puis titrage) sont faits avant toute
        # écriture en base : en cas d'échec de l'un ou l'autre, aucune conversation
        # fantôme n'est persistée (cf. "pas de création d'une conversation vide").
        try:
            reponse = client.chat(requete.message)
            titre = client.chat(_prompt_titrage(requete.message, reponse))
        except Exception as erreur:
            logger.error("Échec de l'appel au relais Mistral : %s", erreur)
            raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

        maintenant = datetime.now(timezone.utc)
        conversation = Conversation(
            identifiant_compte=identifiant_compte,
            titre=titre,
            resume_contexte="",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
        )
        db.add(conversation)
        db.flush()

        db.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    contenu=requete.message,
                    date_creation=maintenant,
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    contenu=reponse,
                    date_creation=maintenant,
                ),
            ]
        )
        db.commit()
        db.refresh(conversation)

        resultat = ConversationCreeResponse(
            conversation=ConversationResume(id=conversation.id, titre=conversation.titre),
            reponse=reponse,
        )
        if requete.cle_idempotence is not None:
            cache_idempotence.enregistrer(identifiant_compte, requete.cle_idempotence, resultat)
        return resultat


@router.get("/conversations", response_model=list[ConversationResponse])
def lister_conversations(
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.identifiant_compte == identifiant_compte)
        .order_by(Conversation.date_derniere_activite.desc())
        .all()
    )
    return [_vers_resume(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def consulter_conversation(
    conversation_id: int,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )
    return ConversationDetailResponse(
        id=conversation.id,
        titre=conversation.titre,
        date_creation=conversation.date_creation,
        date_derniere_activite=conversation.date_derniere_activite,
        messages=[
            MessageResponse(
                id=message.id,
                role=message.role,
                contenu=message.contenu,
                date_creation=message.date_creation,
            )
            for message in messages
        ],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def renommer_conversation(
    conversation_id: int,
    requete: ConversationRenommeeRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    conversation.titre = requete.titre
    db.commit()
    db.refresh(conversation)

    return _vers_resume(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
def supprimer_conversation(
    conversation_id: int,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> None:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    # Message n'a pas de cascade ORM déclarée sur Conversation (même
    # convention que Jeton/Compte, voir comptes.py) : la suppression des
    # messages associés doit donc être explicite, avant celle de la
    # conversation elle-même.
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()


def _appeler_reponse_chat(client: MistralClient, messages_pour_mistral: list[dict[str, str]]) -> str:
    return client.chat(messages_pour_mistral)


def _appeler_resume_et_profil(
    client: MistralClient,
    resume_contexte: str,
    profil_actuel: str,
    compte: Compte | None,
    messages_sortants: list[Message],
) -> str:
    return client.chat(
        _prompt_resume_et_profil(resume_contexte, profil_actuel, compte, messages_sortants),
        response_format=_SCHEMA_RESUME_ET_PROFIL,
    )


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageEnvoyeResponse
)
def envoyer_message(
    conversation_id: int,
    requete: MessageEnvoyeRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    db: Session = Depends(get_db),
) -> MessageEnvoyeResponse:
    with verrous_comptes.pour(identifiant_compte):
        if requete.cle_idempotence is not None:
            reponse_en_cache = cache_idempotence.recuperer(identifiant_compte, requete.cle_idempotence)
            if reponse_en_cache is not None:
                assert isinstance(reponse_en_cache, MessageEnvoyeResponse)
                return reponse_en_cache

        conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

        derniers_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(_TAILLE_FENETRE_HISTORIQUE)
            .all()
        )
        derniers_messages.reverse()

        # Lus une seule fois, avant les appels Mistral : sous le verrou par
        # compte ci-dessus, aucune autre requête concurrente sur ce compte ne
        # peut modifier resume_contexte/ProfilTravail entre cette lecture et
        # l'écriture plus bas (auparavant une "lost update" possible : deux
        # requêtes concurrentes pouvaient toutes deux lire l'ancienne valeur
        # puis écraser l'une des deux mises à jour au commit).
        profil_actuel = _contenu_profil_actuel(db, identifiant_compte)
        messages_pour_mistral = _construire_messages_pour_mistral(
            conversation, derniers_messages, requete.message, profil_actuel
        )

        # Un message sort de la fenêtre des 3 derniers dès que ce tour (2 nouveaux
        # messages) ne laisse plus la place à tous les messages qui y étaient
        # jusque-là : tous sauf le plus récent (qui reste dans la fenêtre aux
        # côtés des 2 nouveaux, cf. spec V1.1.1).
        messages_sortants = derniers_messages[:-1]

        compte = db.query(Compte).filter(Compte.identifiant == identifiant_compte).first()

        resume_maj: str | None = None
        profil_travail_delta: str | None = None

        # Comme pour la création (cf. creer_conversation) : les appels Mistral
        # sont faits avant toute écriture, pour ne jamais persister un message
        # utilisateur sans sa réponse en cas d'échec. Contrairement à
        # creer_conversation (où le titrage a besoin de la réponse de chat),
        # les deux appels ici sont indépendants l'un de l'autre : lancés en
        # parallèle plutôt qu'en séquence pour ne pas doubler la latence de
        # ce tour.
        if messages_sortants:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futur_reponse = executor.submit(_appeler_reponse_chat, client, messages_pour_mistral)
                futur_resume = executor.submit(
                    _appeler_resume_et_profil,
                    client,
                    conversation.resume_contexte,
                    profil_actuel,
                    compte,
                    messages_sortants,
                )
                try:
                    reponse = futur_reponse.result()
                except Exception as erreur:
                    logger.error("Échec de l'appel au relais Mistral : %s", erreur)
                    raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur
                try:
                    contenu_json = futur_resume.result()
                except Exception as erreur:
                    logger.error("Échec de l'appel au relais Mistral : %s", erreur)
                    raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

            try:
                donnees = json.loads(contenu_json)
                resume_maj = donnees["resume_contexte"]
                profil_travail_delta = donnees.get("profil_travail_delta")
            except (json.JSONDecodeError, KeyError, TypeError) as erreur:
                # Distinct du bloc ci-dessus : une réponse reçue mais mal
                # formée n'est pas une panne du relais Mistral, ne doit jamais
                # être journalisée comme telle (les deux étaient auparavant
                # confondues dans un seul except Exception large).
                logger.error("Réponse résumé+profil de Mistral invalide : %s", erreur)
                raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur
        else:
            try:
                reponse = _appeler_reponse_chat(client, messages_pour_mistral)
            except Exception as erreur:
                logger.error("Échec de l'appel au relais Mistral : %s", erreur)
                raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

        maintenant = datetime.now(timezone.utc)
        if resume_maj is not None:
            conversation.resume_contexte = resume_maj
        if profil_travail_delta:
            profil = _recuperer_ou_creer_profil(db, identifiant_compte)
            profil.contenu = f"{profil.contenu}\n{profil_travail_delta}".strip()
            profil.date_derniere_maj = maintenant

        db.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    contenu=requete.message,
                    date_creation=maintenant,
                ),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    contenu=reponse,
                    date_creation=maintenant,
                ),
            ]
        )
        conversation.date_derniere_activite = maintenant
        db.commit()

        resultat = MessageEnvoyeResponse(reponse=reponse)
        if requete.cle_idempotence is not None:
            cache_idempotence.enregistrer(identifiant_compte, requete.cle_idempotence, resultat)
        return resultat
