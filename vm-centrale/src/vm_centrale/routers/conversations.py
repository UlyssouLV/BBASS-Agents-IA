import json
import logging
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from vm_centrale.analyse_pieces_jointes import TYPES_SUPPORTES, analyser
from vm_centrale.autorisation import get_identifiant_compte_du_jeton
from vm_centrale.concurrence import cache_idempotence, verrous_comptes
from vm_centrale.config import PIECES_JOINTES_DIR
from vm_centrale.database import get_db
from vm_centrale.mistral_client import AppelOutilDemande, MistralClient, get_mistral_client
from vm_centrale.models import Compte, Conversation, Message, PieceJointe, ProfilTravail
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
    PieceJointeCreeeResponse,
    PieceJointeResume,
)

_TAILLE_FENETRE_HISTORIQUE = 3
# Fixée en dur (comme la fenêtre de 3 messages ci-dessus), indépendante des
# plafonds propres à Mistral (spec 1.1.2).
_TAILLE_MAX_PIECE_JOINTE = 20 * 1024 * 1024
# Extrait (jamais l'intégralité) de contenu_extrait passé à l'appel
# résumé+profil pour un message sortant portant une pièce jointe — juste
# assez pour que le résumé glissant en tire une mention pertinente, façon
# description de skill (spec 1.1.2).
_TAILLE_EXTRAIT_PIECE_JOINTE_RESUME = 200

router = APIRouter()
logger = logging.getLogger(__name__)

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_CONVERSATION_INTROUVABLE = "Conversation introuvable"
_TYPE_NON_SUPPORTE = "Type de fichier non supporté"
_FICHIER_TROP_VOLUMINEUX = "Fichier trop volumineux (max 20 Mo)"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable"
_PIECE_JOINTE_DEJA_LIEE = "Pièce jointe déjà liée à un message"
_PIECE_JOINTE_OUTIL_INTROUVABLE = "Pièce jointe introuvable."
_CHEMIN_PIECE_JOINTE_INVALIDE = "Nom de fichier invalide"

_OUTIL_CONTENU_PIECE_JOINTE = "obtenir_contenu_piece_jointe"

# Déclaré uniquement sur l'appel de réponse de chat principal (jamais
# titrage ni résumé+profil), et seulement si la conversation a une pièce
# jointe déjà liée à un message sorti de la fenêtre des derniers messages
# (spec 1.1.2) : l'IA peut alors le redemander explicitement plutôt que de
# répondre sans son contenu complet.
def _outils_piece_jointe(pieces_jointes_hors_fenetre: list[PieceJointe]) -> list[dict]:
    # La description est générée à chaque appel à partir des pièces jointes
    # réellement éligibles de la conversation courante (jamais une liste
    # statique figée dans le schéma) : sans le nom de fichier en face de
    # chaque id, le modèle doit deviner quel entier correspond à quel
    # document (ticket #50 — cause du mauvais choix de pièce jointe observé
    # dans l'essai du 2026-09-17).
    liste_pieces_jointes = "\n".join(
        f"- id {piece_jointe.id} : {piece_jointe.nom_fichier}"
        for piece_jointe in pieces_jointes_hors_fenetre
    )
    return [
        {
            "type": "function",
            "function": {
                "name": _OUTIL_CONTENU_PIECE_JOINTE,
                "description": (
                    "Récupère le contenu complet d'une pièce jointe de cette "
                    "conversation dont le message n'est plus dans les derniers "
                    "messages. Pièces jointes éligibles (id — nom de fichier) "
                    f":\n{liste_pieces_jointes}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "piece_jointe_id": {
                            "type": "integer",
                            "description": (
                                "Identifiant de la pièce jointe à récupérer, "
                                "parmi ceux listés ci-dessus."
                            ),
                        }
                    },
                    "required": ["piece_jointe_id"],
                },
            },
        }
    ]

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


def _message_systeme_piece_jointe(piece_jointe: PieceJointe) -> dict[str, str]:
    # Même mécanisme que resume_contexte/profil_travail ci-dessous : un
    # message system supplémentaire, propre à cet appel précis (spec 1.1.2).
    # Framing explicite du "ce tour précis" (ticket #50) : dans l'essai du
    # 2026-09-17, le modèle traitait cet extrait comme un exemple ou un
    # rappel d'un tour antérieur plutôt que comme le fichier que le compte
    # vient d'envoyer avec le message de ce tour.
    return {
        "role": "system",
        "content": (
            f"Pièce jointe « {piece_jointe.nom_fichier} » du message que le "
            "compte vient d'envoyer à ce tour précis — ce n'est ni un "
            "exemple, ni un rappel d'un tour antérieur. Contenu extrait :\n"
            f"{piece_jointe.contenu_extrait or ''}"
        ),
    }


def _construire_messages_pour_mistral(
    conversation: Conversation,
    derniers_messages: list[Message],
    nouveau_message: str,
    profil_travail: str,
    piece_jointe: PieceJointe | None = None,
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
    if piece_jointe is not None:
        messages.append(_message_systeme_piece_jointe(piece_jointe))
    messages.extend({"role": m.role, "content": m.contenu} for m in derniers_messages)
    messages.append({"role": "user", "content": nouveau_message})
    return messages


def _identite_connue(compte: Compte | None) -> str:
    if compte is None:
        return "(non disponible)"
    poles = ", ".join(pole.pole for pole in compte.poles)
    return f"{compte.prenom} {compte.nom}, pôle(s) : {poles}, agence : {compte.agence}"


def _ligne_message_sortant(message: Message, piece_jointe: PieceJointe | None) -> str:
    ligne = f"{message.role} : {message.contenu}"
    if piece_jointe is None:
        return ligne
    # Extrait court seulement (jamais l'intégralité de contenu_extrait) : le
    # résumé glissant n'en garde qu'une mention, pas le document complet
    # (spec 1.1.2).
    extrait = (piece_jointe.contenu_extrait or "")[:_TAILLE_EXTRAIT_PIECE_JOINTE_RESUME]
    return (
        f"{ligne}\n"
        f"(Pièce jointe « {piece_jointe.nom_fichier} », extrait pour situer le "
        f"sujet : {extrait})"
    )


def _prompt_resume_et_profil(
    resume_contexte: str,
    profil_travail: str,
    compte: Compte | None,
    messages_sortants: list[Message],
    pieces_jointes_sortantes: dict[int, PieceJointe] | None = None,
) -> str:
    pieces_jointes_sortantes = pieces_jointes_sortantes or {}
    echange_sortant = "\n".join(
        _ligne_message_sortant(m, pieces_jointes_sortantes.get(m.id)) for m in messages_sortants
    )
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
        "doivent jamais être réinférés ni modifiés depuis une conversation. "
        "Si un message sortant porte une pièce jointe, n'en garde dans "
        "resume_contexte qu'une mention courte (façon description de skill : "
        "juste assez pour situer le sujet), jamais son contenu intégral. "
        "N'inclus jamais non plus dans profil_travail_delta un trait "
        "décrivant ton propre comportement d'assistant (ton adopté, "
        "réflexes de réponse, suggestions d'outils externes que tu "
        "formules) : seul un trait observé chez le compte lui-même, sa "
        "façon à lui de travailler, y a sa place."
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


def _recuperer_piece_jointe_du_compte(
    db: Session, identifiant_compte: str, piece_jointe_id: int, conversation_id: int
) -> PieceJointe:
    piece_jointe = db.get(PieceJointe, piece_jointe_id)
    if (
        piece_jointe is None
        or piece_jointe.identifiant_compte != identifiant_compte
        # None (pas encore rattachée) accepté ; rattachée à une AUTRE
        # conversation refusé — jamais 403, même confidentialité que
        # _recuperer_conversation_du_compte, y compris pour un jeton admin.
        or (piece_jointe.conversation_id is not None and piece_jointe.conversation_id != conversation_id)
    ):
        raise HTTPException(status_code=404, detail=_PIECE_JOINTE_INTROUVABLE)
    if piece_jointe.message_id is not None:
        raise HTTPException(status_code=400, detail=_PIECE_JOINTE_DEJA_LIEE)
    return piece_jointe


_CARACTERES_DANGEREUX_DANS_NOM_FICHIER = re.compile(r"[\\/\x00-\x1f\x7f]")


def _nom_fichier_sur_disque(nom_fichier: str | None) -> str:
    # Le nom de fichier vient du client (en-tête multipart, jamais de
    # confiance). Seuls deux types de caractères sont réellement dangereux
    # ici et sont retirés : "/" et "\" (permettraient de sortir de
    # PIECES_JOINTES_DIR, Path Traversal CWE-22 — "../../../etc/cron.d/x")
    # et les caractères de contrôle dont l'octet nul (troncature de chaîne
    # côté OS, injection dans les logs). Tout le reste — accents, espaces,
    # parenthèses, etc. — reste lisible tel quel sur le disque.
    nom_filtre = _CARACTERES_DANGEREUX_DANS_NOM_FICHIER.sub("_", nom_fichier or "")
    return nom_filtre or "fichier"


def _chemin_piece_jointe_sur_disque(chemin_relatif: str) -> Path:
    # Défense en profondeur en plus de _nom_fichier_sur_disque ci-dessus :
    # vérifie, au moment de toucher le disque, que le chemin final reste bien
    # sous PIECES_JOINTES_DIR avant toute écriture/suppression/déplacement
    # (CWE-22, Path Traversal) — abspath/join/startswith plutôt que pathlib,
    # motif explicitement reconnu par l'analyse de sécurité de SonarCloud.
    racine = os.path.abspath(str(PIECES_JOINTES_DIR))
    chemin_absolu = os.path.abspath(os.path.join(racine, chemin_relatif))
    if chemin_absolu != racine and not chemin_absolu.startswith(racine + os.sep):
        raise HTTPException(status_code=400, detail=_CHEMIN_PIECE_JOINTE_INVALIDE)
    return Path(chemin_absolu)


def _lier_piece_jointe_a_la_conversation(piece_jointe: PieceJointe, conversation: Conversation) -> None:
    if piece_jointe.conversation_id == conversation.id:
        return

    # Téléversée avant que la conversation n'existe (POST /pieces-jointes) :
    # déplace le fichier vers le chemin canonique de la spec 1.1.2
    # (<identifiant_compte>/<conversation_id>/<piece_jointe_id>-<nom_fichier>),
    # jusqu'ici sous un répertoire de dépôt temporaire.
    chemin_relatif = (
        f"{conversation.identifiant_compte}/{conversation.id}/"
        f"{piece_jointe.id}-{_nom_fichier_sur_disque(piece_jointe.nom_fichier)}"
    )
    chemin_absolu = _chemin_piece_jointe_sur_disque(chemin_relatif)
    chemin_absolu.parent.mkdir(parents=True, exist_ok=True)
    _chemin_piece_jointe_sur_disque(piece_jointe.chemin_fichier).replace(chemin_absolu)

    piece_jointe.chemin_fichier = chemin_relatif
    piece_jointe.conversation_id = conversation.id


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

        maintenant = datetime.now(timezone.utc)
        conversation = Conversation(
            identifiant_compte=identifiant_compte,
            titre="",
            resume_contexte="",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
        )
        db.add(conversation)
        # Flush (jamais commit) pour obtenir conversation.id : une pièce
        # jointe téléversée avant que la conversation n'existe (POST
        # /pieces-jointes) ne peut être rattachée qu'une fois cet id connu
        # (spec 1.1.2, référencement dès le premier message). Un rollback
        # explicite plus bas annule cette écriture si l'appel Mistral échoue
        # — pas de conversation fantôme persistée (même garantie qu'avant).
        db.flush()

        piece_jointe: PieceJointe | None = None
        if requete.piece_jointe_id is not None:
            piece_jointe = _recuperer_piece_jointe_du_compte(
                db, identifiant_compte, requete.piece_jointe_id, conversation.id
            )

        message_pour_mistral: str | list[dict[str, str]] = requete.message
        if piece_jointe is not None:
            message_pour_mistral = [
                _message_systeme_piece_jointe(piece_jointe),
                {"role": "user", "content": requete.message},
            ]

        # Les deux appels Mistral (réponse, puis titrage) sont faits avant
        # toute autre écriture en base : en cas d'échec de l'un ou l'autre,
        # rollback (annule aussi la conversation flushée ci-dessus) — aucune
        # conversation fantôme n'est persistée.
        try:
            reponse = client.chat(message_pour_mistral)
            titre = client.chat(_prompt_titrage(requete.message, reponse))
        except Exception as erreur:
            db.rollback()
            logger.error("Échec de l'appel au relais Mistral : %s", erreur)
            raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

        conversation.titre = titre

        message_utilisateur = Message(
            conversation_id=conversation.id,
            role="user",
            contenu=requete.message,
            date_creation=maintenant,
        )
        db.add_all(
            [
                message_utilisateur,
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    contenu=reponse,
                    date_creation=maintenant,
                ),
            ]
        )
        if piece_jointe is not None:
            db.flush()
            _lier_piece_jointe_a_la_conversation(piece_jointe, conversation)
            piece_jointe.message_id = message_utilisateur.id
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

    # Pièces jointes (base + fichier disque) supprimées avant les messages
    # (spec 1.1.2) : PieceJointe.message_id référence Message, donc l'ordre
    # inverse violerait l'intégrité référentielle. missing_ok=True car un
    # fichier déjà absent ne doit jamais empêcher la suppression de la
    # conversation elle-même.
    pieces_jointes = db.query(PieceJointe).filter(PieceJointe.conversation_id == conversation.id).all()
    for piece_jointe in pieces_jointes:
        (Path(PIECES_JOINTES_DIR) / piece_jointe.chemin_fichier).unlink(missing_ok=True)
    db.query(PieceJointe).filter(PieceJointe.conversation_id == conversation.id).delete()

    # Message n'a pas de cascade ORM déclarée sur Conversation (même
    # convention que Jeton/Compte, voir comptes.py) : la suppression des
    # messages associés doit donc être explicite, avant celle de la
    # conversation elle-même.
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()


def _creer_piece_jointe(
    db: Session,
    client: MistralClient,
    identifiant_compte: str,
    conversation_id: int | None,
    fichier: UploadFile,
) -> PieceJointeCreeeResponse:
    # Type vérifié avant lecture du contenu (évite de lire en mémoire un
    # fichier volumineux d'un type de toute façon refusé).
    if fichier.content_type not in TYPES_SUPPORTES:
        raise HTTPException(status_code=400, detail=_TYPE_NON_SUPPORTE)

    contenu = fichier.file.read()
    if len(contenu) > _TAILLE_MAX_PIECE_JOINTE:
        raise HTTPException(status_code=400, detail=_FICHIER_TROP_VOLUMINEUX)

    maintenant = datetime.now(timezone.utc)
    piece_jointe = PieceJointe(
        identifiant_compte=identifiant_compte,
        conversation_id=conversation_id,
        message_id=None,
        nom_fichier=fichier.filename,
        type_mime=fichier.content_type,
        taille_octets=len(contenu),
        chemin_fichier="",
        contenu_extrait=None,
        echec_analyse=False,
        date_creation=maintenant,
    )
    db.add(piece_jointe)
    db.flush()

    # <identifiant_compte>/<conversation_id>/<piece_jointe_id>-<nom_fichier>
    # (spec 1.1.2) quand la conversation est déjà connue à l'upload ; sinon
    # (POST /pieces-jointes, conversation_id=None) un répertoire de dépôt
    # temporaire, déplacé au chemin canonique lors du rattachement — voir
    # _lier_piece_jointe_a_la_conversation.
    segment_conversation = str(conversation_id) if conversation_id is not None else "_sans_conversation"
    chemin_relatif = (
        f"{identifiant_compte}/{segment_conversation}/"
        f"{piece_jointe.id}-{_nom_fichier_sur_disque(fichier.filename)}"
    )
    chemin_absolu = _chemin_piece_jointe_sur_disque(chemin_relatif)
    chemin_absolu.parent.mkdir(parents=True, exist_ok=True)
    chemin_absolu.write_bytes(contenu)
    piece_jointe.chemin_fichier = chemin_relatif

    try:
        resultat = analyser(contenu, fichier.content_type, client)
    except Exception as erreur:
        # Rollback + suppression du fichier déjà écrit : comme pour
        # creer_conversation, aucune pièce jointe ni fichier fantôme ne doit
        # survivre à un échec de l'appel Mistral.
        db.rollback()
        chemin_absolu.unlink(missing_ok=True)
        logger.error("Échec de l'appel au relais Mistral (OCR) : %s", erreur)
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    piece_jointe.contenu_extrait = resultat.contenu_extrait
    piece_jointe.echec_analyse = resultat.echec_analyse
    db.commit()
    db.refresh(piece_jointe)

    return PieceJointeCreeeResponse(
        piece_jointe=PieceJointeResume(
            id=piece_jointe.id,
            nom_fichier=piece_jointe.nom_fichier,
            type_mime=piece_jointe.type_mime,
        ),
        echec_analyse=piece_jointe.echec_analyse,
    )


@router.post(
    "/conversations/{conversation_id}/pieces-jointes",
    response_model=PieceJointeCreeeResponse,
    status_code=201,
)
def televerser_piece_jointe(
    conversation_id: int,
    fichier: UploadFile = File(...),
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    db: Session = Depends(get_db),
) -> PieceJointeCreeeResponse:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)
    return _creer_piece_jointe(db, client, identifiant_compte, conversation.id, fichier)


@router.post("/pieces-jointes", response_model=PieceJointeCreeeResponse, status_code=201)
def televerser_piece_jointe_sans_conversation(
    fichier: UploadFile = File(...),
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    db: Session = Depends(get_db),
) -> PieceJointeCreeeResponse:
    # Pas de conversation à posséder ici : c'est la seule façon de joindre un
    # fichier dès le tout premier message d'une conversation, qui n'existe
    # pas encore au moment de l'upload (spec 1.1.2, référencement — voir
    # ConversationCreeRequest.piece_jointe_id).
    return _creer_piece_jointe(db, client, identifiant_compte, None, fichier)


def _appeler_reponse_chat(
    client: MistralClient,
    messages_pour_mistral: list[dict[str, str]],
    tools: list[dict] | None = None,
) -> str:
    return client.chat(messages_pour_mistral, tools=tools)


def _pieces_jointes_hors_fenetre(
    db: Session, conversation_id: int, ids_fenetre: set[int]
) -> list[PieceJointe]:
    requete = db.query(PieceJointe).filter(
        PieceJointe.conversation_id == conversation_id,
        PieceJointe.message_id.isnot(None),
    )
    if ids_fenetre:
        requete = requete.filter(~PieceJointe.message_id.in_(ids_fenetre))
    return requete.all()


def _traiter_appel_outil(
    client: MistralClient,
    messages_pour_mistral: list[dict[str, str]],
    demande: AppelOutilDemande,
    db: Session,
    conversation_id: int,
) -> str:
    # Un seul outil déclaré pour cette version (spec 1.1.2) : seul le premier
    # appel demandé est traité.
    appel = demande.appels[0]
    piece_jointe = db.get(PieceJointe, appel.arguments.get("piece_jointe_id"))
    if piece_jointe is None or piece_jointe.conversation_id != conversation_id:
        # Ne devrait pas arriver (l'IA ne voit que des piece_jointe_id réels
        # dans son propre contexte), mais jamais de 500 sur une divergence :
        # un contenu explicatif pour l'outil plutôt qu'une pièce jointe
        # rattachée à une autre conversation, même confidentialité que
        # _recuperer_piece_jointe_du_compte.
        contenu_outil = _PIECE_JOINTE_OUTIL_INTROUVABLE
    else:
        contenu_outil = piece_jointe.contenu_extrait or ""

    messages_second_appel = [
        *messages_pour_mistral,
        demande.message_assistant,
        {"role": "tool", "tool_call_id": appel.id, "name": appel.nom, "content": contenu_outil},
    ]
    return client.chat(messages_second_appel)


def _resoudre_reponse_chat(
    obtenir_reponse: Callable[[], str],
    client: MistralClient,
    messages_pour_mistral: list[dict[str, str]],
    db: Session,
    conversation_id: int,
) -> str:
    # Centralise la gestion de AppelOutilDemande (et son propre échec
    # éventuel) pour les deux façons d'obtenir la réponse de chat principale
    # ci-dessous (directe, ou via un ThreadPoolExecutor) : `obtenir_reponse`
    # est soit `futur_reponse.result`, soit un appel direct à
    # _appeler_reponse_chat.
    try:
        return obtenir_reponse()
    except AppelOutilDemande as demande:
        try:
            return _traiter_appel_outil(client, messages_pour_mistral, demande, db, conversation_id)
        except Exception as erreur:
            logger.error("Échec de l'appel au relais Mistral : %s", erreur)
            raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur
    except Exception as erreur:
        logger.error("Échec de l'appel au relais Mistral : %s", erreur)
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur


def _appeler_resume_et_profil(
    client: MistralClient,
    resume_contexte: str,
    profil_actuel: str,
    compte: Compte | None,
    messages_sortants: list[Message],
    pieces_jointes_sortantes: dict[int, PieceJointe],
) -> str:
    return client.chat(
        _prompt_resume_et_profil(
            resume_contexte, profil_actuel, compte, messages_sortants, pieces_jointes_sortantes
        ),
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

        piece_jointe: PieceJointe | None = None
        if requete.piece_jointe_id is not None:
            piece_jointe = _recuperer_piece_jointe_du_compte(
                db, identifiant_compte, requete.piece_jointe_id, conversation.id
            )

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
            conversation, derniers_messages, requete.message, profil_actuel, piece_jointe
        )

        # Un message sort de la fenêtre des 3 derniers dès que ce tour (2 nouveaux
        # messages) ne laisse plus la place à tous les messages qui y étaient
        # jusque-là : tous sauf le plus récent (qui reste dans la fenêtre aux
        # côtés des 2 nouveaux, cf. spec V1.1.1).
        messages_sortants = derniers_messages[:-1]

        # Outil déclaré uniquement sur l'appel de réponse de chat principal
        # ci-dessous, jamais sur celui de résumé+profil (spec 1.1.2) : la
        # fenêtre ici est celle des messages déjà en base avant ce tour
        # (`derniers_messages`), pas `messages_sortants` (qui n'en retire que
        # le plus ancien, propre à l'absorption de CE tour dans le résumé).
        ids_fenetre = {m.id for m in derniers_messages}
        pieces_jointes_hors_fenetre = _pieces_jointes_hors_fenetre(db, conversation.id, ids_fenetre)
        tools = _outils_piece_jointe(pieces_jointes_hors_fenetre) if pieces_jointes_hors_fenetre else None

        # Résolues une seule fois, avant l'appel résumé+profil (jamais dans le
        # thread de l'executor ci-dessous, la session SQLAlchemy n'étant pas
        # thread-safe) : la pièce jointe déjà liée à un message sortant, si
        # elle existe, pour n'en glisser qu'un extrait court dans le prompt
        # (spec 1.1.2, jamais le contenu intégral de contenu_extrait).
        pieces_jointes_sortantes: dict[int, PieceJointe] = {}
        if messages_sortants:
            pieces_jointes_sortantes = {
                piece_jointe.message_id: piece_jointe
                for piece_jointe in db.query(PieceJointe)
                .filter(PieceJointe.message_id.in_([m.id for m in messages_sortants]))
                .all()
                if piece_jointe.message_id is not None
            }

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
                futur_reponse = executor.submit(
                    _appeler_reponse_chat, client, messages_pour_mistral, tools
                )
                futur_resume = executor.submit(
                    _appeler_resume_et_profil,
                    client,
                    conversation.resume_contexte,
                    profil_actuel,
                    compte,
                    messages_sortants,
                    pieces_jointes_sortantes,
                )
                reponse = _resoudre_reponse_chat(
                    futur_reponse.result, client, messages_pour_mistral, db, conversation.id
                )
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
            reponse = _resoudre_reponse_chat(
                lambda: _appeler_reponse_chat(client, messages_pour_mistral, tools),
                client,
                messages_pour_mistral,
                db,
                conversation.id,
            )

        maintenant = datetime.now(timezone.utc)
        if resume_maj is not None:
            conversation.resume_contexte = resume_maj
        if profil_travail_delta:
            profil = _recuperer_ou_creer_profil(db, identifiant_compte)
            profil.contenu = f"{profil.contenu}\n{profil_travail_delta}".strip()
            profil.date_derniere_maj = maintenant

        message_utilisateur = Message(
            conversation_id=conversation.id,
            role="user",
            contenu=requete.message,
            date_creation=maintenant,
        )
        db.add_all(
            [
                message_utilisateur,
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    contenu=reponse,
                    date_creation=maintenant,
                ),
            ]
        )
        if piece_jointe is not None:
            db.flush()
            _lier_piece_jointe_a_la_conversation(piece_jointe, conversation)
            piece_jointe.message_id = message_utilisateur.id
        conversation.date_derniere_activite = maintenant
        db.commit()

        resultat = MessageEnvoyeResponse(reponse=reponse)
        if requete.cle_idempotence is not None:
            cache_idempotence.enregistrer(identifiant_compte, requete.cle_idempotence, resultat)
        return resultat
