import json
import logging
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from vm_centrale.analyse_pieces_jointes import TYPES_SUPPORTES, analyser, type_appel_mistral
from vm_centrale.autorisation import get_identifiant_compte_du_jeton
from vm_centrale.concurrence import cache_idempotence, verrous_comptes
from vm_centrale.config import MODELE_CHAT, MODELE_OCR, PIECES_JOINTES_DIR
from vm_centrale.consommation import enregistrer_consommation
from vm_centrale.database import get_db
from vm_centrale.garde_fous import (
    nettoyer_titre,
    plafonner,
    retirer_chiffres_hors_source,
    retirer_urls_inventees,
)
from vm_centrale.inspecteur import (
    enregistrer_echange_echec,
    enregistrer_echange_local,
    enregistrer_echange_succes,
    payload_depuis_erreur,
    reponse_depuis_erreur,
)
from vm_centrale.mistral_client import (
    AppelOutilDemande,
    MistralClient,
    ReponseChat,
    get_mistral_client,
)
from vm_centrale.models import (
    Compte,
    Consommation,
    Conversation,
    EchangeInspecteur,
    Message,
    PieceJointe,
    ProfilTravail,
    ResultatRechercheWeb,
)
from vm_centrale.moteur_recherche import MoteurRecherche, get_moteur_recherche
from vm_centrale.outils import ContexteTour, executer_appel, outils_du_tour
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
# Appels de chat principaux par message, le dernier sans `tools` (spec 1.4.0,
# décision n° 7) : évite que le modèle tourne en rond.
_TOURS_MAX_PAR_MESSAGE = 3
# Taille de la fenêtre par défaut de GET /conversations/{id} (issue #103) :
# un détail d'implémentation, pas une décision produit figée (spec
# 1.2.3) — ajustable librement sans changer le contrat de pagination
# (curseur avant_id + limite).
_TAILLE_FENETRE_PAGINATION_PAR_DEFAUT = 20
# Fixée en dur (comme la fenêtre de 3 messages ci-dessus), indépendante des
# plafonds propres à Mistral (spec 1.1.2).
_TAILLE_MAX_PIECE_JOINTE = 20 * 1024 * 1024
# Extrait (jamais l'intégralité) de contenu_extrait passé à l'appel
# résumé+profil pour un message sortant portant une pièce jointe — juste
# assez pour que le résumé glissant en tire une mention pertinente, façon
# description de skill (spec 1.1.2).
_TAILLE_EXTRAIT_PIECE_JOINTE_RESUME = 200
# Plafond du résumé glissant persisté, fixé en dur comme la fenêtre de 3 et
# énoncé aussi dans le prompt résumé+profil (spec 1.3.1).
_TAILLE_MAX_RESUME_CONTEXTE = 1500
# Plafond du profil de travail persisté, même convention (spec 1.3.1).
_TAILLE_MAX_PROFIL_TRAVAIL = 800

router = APIRouter()
logger = logging.getLogger(__name__)

_ECHEC_RELAIS = "Le relais Mistral est indisponible"
_MSG_ECHEC_RELAIS_LOG = "Échec de l'appel au relais Mistral"
_CONVERSATION_INTROUVABLE = "Conversation introuvable"
_TYPE_NON_SUPPORTE = "Type de fichier non supporté"
_FICHIER_TROP_VOLUMINEUX = "Fichier trop volumineux (max 20 Mo)"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable"
_PIECE_JOINTE_DEJA_LIEE = "Pièce jointe déjà liée à un message"
_CHEMIN_PIECE_JOINTE_INVALIDE = "Nom de fichier invalide"

# Sortie structurée stricte (spec V1.1.1) : un seul appel Mistral produit à la
# fois le résumé glissant mis à jour et, si le profil de travail change, ce
# profil réécrit en entier (spec 1.3.1 : plus de delta concaténé), pour ne
# payer le contexte partagé (résumé courant, profil courant, message(s)
# sortant(s)) qu'une seule fois.
_SCHEMA_RESUME_ET_PROFIL = {
    "type": "json_schema",
    "json_schema": {
        "name": "resume_et_profil",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "resume_contexte": {"type": "string"},
                "profil_travail": {"type": ["string", "null"]},
            },
            "required": ["resume_contexte", "profil_travail"],
            "additionalProperties": False,
        },
    },
}


# Déclaré uniquement sur l'appel de réponse de chat principal (jamais
# titrage ni résumé+profil, qui gardent leurs consignes dédiées), en tête de
# la liste de messages — avant résumé glissant / profil de travail / pièce
# jointe (consigne de comportement générale avant le contexte propre à ce
# tour), cf. spec 1.2.2. Renforcé après validation manuelle de la 1.2.2
# (réponses à une question ouverte type « que peux-tu me dire sur... ? ») :
# la question de relance finale et les faux titres en gras revenaient de
# façon systématique malgré la première version de cette consigne.
# Tableaux, blocs de code et liens passés de déconseillés à autorisés le
# même jour, une fois le rendu Markdown du poste (#93) étendu pour les
# afficher proprement (table HTML, police mono, pastille de source cliquable)
# plutôt que les neutraliser. Capacité réelle placée en tête en 1.3.1
# (#110, conversation 76) : sans accès à Internet, la « certitude » qu'exigeait
# l'ancienne ligne des liens n'existe pas — le modèle inventait des liens
# puis affirmait les avoir vérifiés. Garanti en plus dans le code par
# garde_fous.retirer_urls_inventees.
_PROMPT_STYLE = (
    "Capacité réelle, avant toute autre consigne : tu n'as aucun accès à "
    "Internet, donc tu ne proposes jamais de lien, de PDF ou d'image à "
    "télécharger, et tu n'affirmes jamais qu'un lien a été vérifié ; si le "
    "utilisateur te demande un lien ou un fichier à télécharger, dis-lui d'emblée "
    "que tu n'as pas accès à Internet. Tu n'inventes jamais un fait, un "
    "rapport, une source ou un chiffre, sauf si l'utilisateur te demande "
    "explicitement d'inventer, d'imaginer ou de faire une hypothèse. Si tu "
    "n'es pas sûr qu'il faille inventer, pose la question de confirmation "
    "en tout début de réponse, et n'invente rien tant qu'il n'a pas "
    "confirmé.\n"
    "Consigne de style pour ta réponse, à respecter systématiquement :\n"
    "- Ton : vouvoiement, professionnel, cohérent avec un outil de travail "
    "de cabinet.\n"
    "- Longueur : pas de remplissage par réflexe (pas de préambule inutile, "
    "pas de plan en sections pour une question simple, pas de conclusion "
    "qui ne sert à rien) ; la longueur réelle de ta réponse suit la "
    "complexité de la question, pas une limite fixe.\n"
    "- Emojis : rares, seulement quand ils portent un vrai signal que le "
    "texte seul ne porterait pas aussi bien (ex. ⚠️ pour un avertissement) ; "
    "jamais décoratifs ni systématiques, jamais en guise de puces pour "
    "énumérer plusieurs éléments dans un même paragraphe.\n"
    "- Relance finale : ne termine jamais ta réponse par une question, y "
    "compris une proposition du type « Souhaitez-vous que je... ? » ou "
    "« Besoin de précisions sur... ? ». Si une clarification est "
    "réellement nécessaire à la tâche, pose-la en tout début de réponse, "
    "jamais en conclusion.\n"
    "- Titres : n'utilise jamais un texte en gras isolé sur sa propre "
    "ligne en guise de titre de section (ex. « **1. Missions "
    "principales** ») ; le gras reste réservé à des mots ou expressions "
    "au sein d'une phrase ou d'un élément de liste.\n"
    "- Listes : un seul niveau d'imbrication au maximum ; au-delà, "
    "reformule en phrases plutôt qu'en sous-listes empilées. Si tu "
    "énumères plusieurs éléments, utilise toujours une vraie liste à "
    "puces ou numérotée, jamais des éléments mis bout à bout dans un même "
    "paragraphe.\n"
    "- Markdown autorisé dans ta réponse : gras, italique, listes à puces "
    "ou numérotées, paragraphes, tableaux (uniquement quand l'information "
    "s'y prête vraiment, jamais par réflexe), blocs de code pour du code "
    "ou une formule, et liens uniquement vers une URL que l'utilisateur a "
    "lui-même écrite dans cette conversation (jamais une autre URL, même "
    "une que tu crois connaître). "
    "Déconseillés : titres, séparateurs `---`, citations, images."
)


def _message_systeme_style() -> dict[str, str]:
    return {"role": "system", "content": _PROMPT_STYLE}


def _prompt_titrage(message_utilisateur: str, reponse_assistant: str) -> str:
    return (
        "Propose un titre court (moins de 8 mots), sans guillemets et sans "
        "aucune mise en forme Markdown (pas de **, #, etc.), résumant "
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
    # Règles de la spec 1.3.1 (issue #110) : le modèle demandait d'envoyer
    # une image déjà jointe (message au futur), puis la décrivait d'après
    # le profil de travail au lieu de l'extrait.
    return {
        "role": "system",
        "content": (
            f"Pièce jointe « {piece_jointe.nom_fichier} » du message que "
            "l'utilisateur vient d'envoyer à ce tour précis — ce n'est ni un "
            "exemple, ni un rappel d'un tour antérieur. Règles :\n"
            "- Le fichier est déjà joint à ce tour : ne demande pas de "
            "l'envoyer, même si le message de l'utilisateur est au futur.\n"
            "- Le contenu extrait ci-dessous est la seule description "
            "autorisée de ce fichier : n'affirme rien qui en soit absent "
            "(pas de schéma, de carte, de nœud ni de texte inventé).\n"
            "- Le profil de travail ne remplace jamais cet extrait.\n"
            "Contenu extrait :\n"
            f"{piece_jointe.contenu_extrait or ''}"
        ),
    }


def _construire_messages_pour_mistral(
    resume_contexte: str,
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
    # Reçoit resume_contexte/derniers_messages déjà extraits (plutôt qu'une
    # Conversation) : le tout premier message d'une conversation
    # (creer_conversation) n'a ni résumé ni historique, et réutilise ainsi
    # ce même builder avec une liste vide et une chaîne vide plutôt que de
    # dupliquer l'assemblage [style, pièce jointe ?, user].
    messages: list[dict[str, str]] = [_message_systeme_style()]
    if resume_contexte:
        messages.append({"role": "system", "content": resume_contexte})
    if profil_travail:
        messages.append(
            {"role": "system", "content": f"Profil de travail de l'utilisateur : {profil_travail}"}
        )
    if piece_jointe is not None:
        messages.append(_message_systeme_piece_jointe(piece_jointe))
    messages.extend({"role": m.role, "content": m.contenu} for m in derniers_messages)
    messages.append({"role": "user", "content": nouveau_message})
    return messages


# Phrase écrite par la VM, pas par le modèle (conversation 78 : la consigne
# était dans l'appel, le modèle a quand même rédigé le rapport, puis s'est
# couvert en bas). Affichée quand la réponse avance une donnée chiffrée que
# ni le message du tour, ni une pièce jointe, ne contiennent — sauf demande
# explicite d'inventer, d'imaginer ou de faire une hypothèse.
_REPONSE_SANS_DONNEES = (
    "Je n'ai pas accès à Internet et je n'ai pas de document pour appuyer une réponse."
)
_MOTIF_INVENTION = re.compile(
    r"\b(inventer|invente|inventes|inventé|inventée|invention|imaginer|imagine|imagines|"
    r"imaginé|imaginée|hypothèse|hypothese|hypothèses|hypotheses)\b",
    re.IGNORECASE,
)
_MOTIF_NEGATION = re.compile(r"(?:n['’]|ne\s+)$", re.IGNORECASE)


def _demande_invention(message: str) -> bool:
    for correspondance in _MOTIF_INVENTION.finditer(message):
        if _MOTIF_NEGATION.search(message[: correspondance.start()]):
            continue
        return True
    return False


def _reponse_sans_url_inventee(
    db: Session, conversation_id: int, nouveau_message: str, reponse: str
) -> str:
    # Textes du compte lus en base, pas seulement dans la fenêtre des
    # derniers messages (spec 1.3.1) : une URL que le compte a donnée il y a
    # longtemps reste légitime à redonner. De même pour les URL des résultats
    # de recherche de la conversation (spec 1.4.0), ce tour compris. Point
    # d'appel unique du garde-fou, pour le premier message comme pour les
    # suivants (voir garde_fous/README.md).
    messages_du_compte = (
        db.query(Message.contenu)
        .filter(Message.conversation_id == conversation_id, Message.role == "user")
        .all()
    )
    textes_du_compte = [contenu for (contenu,) in messages_du_compte] + [nouveau_message]
    urls_trouvees = (
        db.query(ResultatRechercheWeb.url)
        .filter(ResultatRechercheWeb.conversation_id == conversation_id)
        .all()
    )
    return retirer_urls_inventees(reponse, textes_du_compte, [url for (url,) in urls_trouvees])


def _extraits_pieces_jointes(
    db: Session, conversation_id: int, piece_jointe: PieceJointe | None
) -> list[str]:
    lignes = (
        db.query(PieceJointe.contenu_extrait)
        .filter(PieceJointe.conversation_id == conversation_id)
        .all()
    )
    extraits = [extrait for (extrait,) in lignes if extrait and extrait.strip()]
    extrait_du_tour = piece_jointe.contenu_extrait if piece_jointe is not None else None
    if extrait_du_tour and extrait_du_tour.strip() and extrait_du_tour not in extraits:
        extraits.append(extrait_du_tour)
    return extraits


def _reponse_visible(
    db: Session,
    conversation_id: int,
    nouveau_message: str,
    reponse: str,
    piece_jointe: PieceJointe | None,
) -> str:
    # URL d'abord : un chiffre qui ne vivait que dans une URL inventée
    # disparaît avec elle, et n'est pas relu comme une donnée.
    reponse = _reponse_sans_url_inventee(db, conversation_id, nouveau_message, reponse)
    if _demande_invention(nouveau_message):
        return reponse
    messages_du_compte = (
        db.query(Message.contenu)
        .filter(Message.conversation_id == conversation_id, Message.role == "user")
        .all()
    )
    extraits = _extraits_pieces_jointes(db, conversation_id, piece_jointe)
    textes_source = [contenu for (contenu,) in messages_du_compte] + [nouveau_message, *extraits]
    sans_chiffre_invente = retirer_chiffres_hors_source(reponse, textes_source)
    if sans_chiffre_invente == reponse:
        return reponse
    # Un document, ou un chiffre déjà écrit dans le message du tour : on
    # retire seulement le chiffre absent. Sans rien de tout ça, la réponse
    # entière devient la phrase fixe — un rapport troué n'est pas une réponse.
    message_apporte_une_donnee = (
        retirer_chiffres_hors_source(nouveau_message, []) != nouveau_message
    )
    if extraits or message_apporte_une_donnee:
        return sans_chiffre_invente
    return _REPONSE_SANS_DONNEES


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
        "Tu maintiens deux mémoires pour cet utilisateur : un résumé glissant de la "
        "conversation en cours, et un profil de travail inter-conversationnel "
        "décrivant sa façon de travailler.\n"
        f"Identité déjà connue de l'utilisateur, fait acquis — ne cherche jamais à la "
        f"déterminer ni à la modifier : {_identite_connue(compte)}.\n"
        f"Résumé glissant actuel : {resume_contexte or '(vide)'}\n"
        f"Profil de travail actuel : {profil_travail or '(vide)'}\n"
        "Message(s) qui sortent de la fenêtre des derniers messages, à "
        f"absorber dans le résumé :\n{echange_sortant}\n\n"
        "Renvoie un objet JSON avec resume_contexte (résumé glissant mis à "
        "jour, incorporant ces messages sortants) et profil_travail (le "
        "profil de travail complet, réécrit en entier : il remplace le "
        "profil actuel, doublons fusionnés, sans aucun doublon ; null si "
        "rien n'y change). "
        "N'inclus jamais dans profil_travail un fait d'identité "
        "(prénom, nom, pôle, agence) : ceux-ci sont déjà connus et ne "
        "doivent jamais être réinférés ni modifiés depuis une conversation. "
        "Si un message sortant porte une pièce jointe, n'en garde dans "
        "resume_contexte qu'une mention courte (façon description de skill : "
        "juste assez pour situer le sujet), jamais son contenu intégral. "
        "Dans resume_contexte, une affirmation de l'assistant (rapport, "
        "chiffre, URL) est notée « proposé, non vérifié » : jamais comme un "
        "fait, jamais comme quelque chose que l'utilisateur a fourni. Un sujet "
        "que l'utilisateur abandonne (« oublie », « laisse tomber ») sort du "
        "résumé. Une URL écrite par l'utilisateur est recopiée à l'identique ; "
        "une URL écrite par l'assistant n'est jamais gardée. "
        f"resume_contexte tient en {_TAILLE_MAX_RESUME_CONTEXTE} caractères au plus. "
        "profil_travail se fonde sur les seules lignes « user » (les "
        "messages de l'utilisateur), jamais sur une réponse de l'assistant. "
        "N'inclus jamais non plus dans profil_travail un trait "
        "décrivant ton propre comportement d'assistant (liens fournis, "
        "PDF proposés, vérification annoncée, ton adopté, suggestions "
        "d'outils externes que tu formules) : seul un trait observé chez "
        "l'utilisateur lui-même, sa façon à lui de travailler, y a sa place. "
        f"profil_travail tient en {_TAILLE_MAX_PROFIL_TRAVAIL} caractères au plus."
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


@router.post(
    "/conversations",
    responses={
        404: {"description": _PIECE_JOINTE_INTROUVABLE},
        400: {"description": _PIECE_JOINTE_DEJA_LIEE},
        502: {"description": _ECHEC_RELAIS},
    },
)
def creer_conversation(
    requete: ConversationCreeRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    moteur_recherche: MoteurRecherche = Depends(get_moteur_recherche),
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
        piece_jointe_id = piece_jointe.id if piece_jointe is not None else None

        # Même builder qu'envoyer_message ci-dessous : ce chemin couvre le
        # tout premier message d'une conversation (jamais de résumé glissant
        # ni d'historique à ce stade), l'autre chemin menant au même appel de
        # chat principal (spec 1.2.2).
        message_pour_mistral = _construire_messages_pour_mistral(
            "", [], requete.message, "", piece_jointe
        )

        # Les deux appels Mistral (réponse, puis titrage) sont faits avant
        # toute autre écriture en base : en cas d'échec de l'un ou l'autre,
        # rollback (annule aussi la conversation flushée ci-dessus) — aucune
        # conversation fantôme n'est persistée. Essayés séparément (plutôt
        # qu'un seul try englobant les deux, comme avant la spec 1.3.0) pour
        # savoir lequel des deux a échoué et l'enregistrer comme tel dans
        # l'inspecteur ; conversation_id=None pour ces deux échecs (la
        # conversation flushée plus haut n'existe plus en base une fois le
        # rollback fait, aucune ligne ne peut la référencer par FK).
        # piece_jointe_id=None aussi : la pièce jointe peut être rattachée
        # plus tard à une autre conversation puis supprimée avec elle
        # (supprimer_conversation), ce qui laisserait cette ligne sans
        # conversation pointer vers une pièce jointe disparue.
        # Outils sur l'appel principal dès le premier message (spec 1.4.0) :
        # aucune fenêtre ni pièce jointe hors fenêtre ici, seul
        # rechercher_web est éligible.
        contexte_outils = ContexteTour(
            db=db,
            conversation_id=conversation.id,
            ids_fenetre=frozenset(),
            moteur_recherche=moteur_recherche,
        )
        tools = outils_du_tour(contexte_outils)
        reponse_chat = _resoudre_reponse_chat(
            lambda: _appeler_reponse_chat(client, message_pour_mistral, tools),
            client,
            message_pour_mistral,
            tools,
            contexte_outils,
            identifiant_compte,
            piece_jointe_id,
            conversation_persistee=False,
        )

        reponse = _reponse_visible(
            db, conversation.id, requete.message, reponse_chat.contenu, piece_jointe
        )

        try:
            reponse_titrage = client.chat(_prompt_titrage(requete.message, reponse))
        except Exception as erreur:
            db.rollback()
            enregistrer_echange_echec(
                db,
                identifiant_compte=identifiant_compte,
                conversation_id=None,
                piece_jointe_id=None,
                type_appel="titrage",
                modele=MODELE_CHAT,
                requete_payload=payload_depuis_erreur(erreur),
                erreur=str(erreur),
            )
            logger.exception(_MSG_ECHEC_RELAIS_LOG)
            raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

        titre = nettoyer_titre(reponse_titrage.contenu)

        conversation.titre = titre
        enregistrer_consommation(
            db, identifiant_compte, conversation.id, "titrage", MODELE_CHAT, usage=reponse_titrage.usage
        )
        enregistrer_echange_succes(
            db,
            identifiant_compte=identifiant_compte,
            conversation_id=conversation.id,
            piece_jointe_id=None,
            type_appel="titrage",
            modele=MODELE_CHAT,
            requete_payload=reponse_titrage.payload_envoye,
            reponse_payload=reponse_titrage.reponse_brute,
        )

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


@router.get("/conversations")
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


@router.get(
    "/conversations/{conversation_id}",
    responses={404: {"description": _CONVERSATION_INTROUVABLE}},
)
def consulter_conversation(
    conversation_id: int,
    # Curseur par identifiant de message (jamais un numéro de page ni un
    # décalage global, spec 1.2.3) : sans lui, la fenêtre la plus récente de
    # la conversation ; avec lui, les messages strictement plus anciens que
    # ce message de référence.
    avant_id: int | None = None,
    limite: int = Query(default=_TAILLE_FENETRE_PAGINATION_PAR_DEFAUT, gt=0),
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    requete_messages = db.query(Message).filter(Message.conversation_id == conversation.id)
    if avant_id is not None:
        requete_messages = requete_messages.filter(Message.id < avant_id)

    # Un message de plus que la limite demandée, trié du plus récent au plus
    # ancien : sa seule présence indique qu'il reste des messages plus
    # anciens que cette fenêtre, sans nécessiter de second COUNT(*) (spec
    # 1.2.3 — indication de présence, jamais un total ni un numéro de page).
    messages_page_desc = requete_messages.order_by(Message.id.desc()).limit(limite + 1).all()
    a_des_messages_plus_anciens = len(messages_page_desc) > limite
    messages = list(reversed(messages_page_desc[:limite]))

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
        a_des_messages_plus_anciens=a_des_messages_plus_anciens,
    )


@router.patch(
    "/conversations/{conversation_id}",
    responses={404: {"description": _CONVERSATION_INTROUVABLE}},
)
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


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    responses={404: {"description": _CONVERSATION_INTROUVABLE}},
)
def supprimer_conversation(
    conversation_id: int,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> None:
    conversation = _recuperer_conversation_du_compte(db, conversation_id, identifiant_compte)

    # echanges_inspecteur disparaît avec sa conversation (FK ON DELETE
    # CASCADE, spec 1.3.0) — contrairement à Consommation ci-dessous.
    # Supprimé ici explicitement, comme Message/PieceJointe plus bas, pour un
    # comportement identique quel que soit le moteur de base (la base de
    # test SQLite n'applique pas les contraintes FK par défaut).
    db.query(EchangeInspecteur).filter(EchangeInspecteur.conversation_id == conversation.id).delete()
    # Même chose pour les résultats de recherche (spec 1.4.0).
    db.query(ResultatRechercheWeb).filter(
        ResultatRechercheWeb.conversation_id == conversation.id
    ).delete()

    # Consommation n'a pas de cascade ORM déclarée sur Conversation (spec
    # 1.1.3) : la ligne survit à la conversation qui l'a produite, seul le
    # rattachement disparaît — jamais de suppression en cascade comme pour
    # les messages/pièces jointes ci-dessous. Même transaction que le reste
    # de la suppression.
    db.query(Consommation).filter(Consommation.conversation_id == conversation.id).update(
        {Consommation.conversation_id: None}
    )

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
        type_appel = type_appel_mistral(fichier.content_type)
        if type_appel is not None and conversation_id is not None:
            # conversation_id=None (upload via POST /pieces-jointes, sans
            # conversation encore) n'a sa place nulle part dans l'inspecteur
            # (spec 1.3.0, navigation uniquement par conversation) : aucune
            # ligne dans ce cas. piece_jointe_id=None : la ligne PieceJointe
            # flushée ci-dessus a été annulée par le rollback, aucune ligne
            # ne peut plus la référencer par FK.
            enregistrer_echange_echec(
                db,
                identifiant_compte=identifiant_compte,
                conversation_id=conversation_id,
                piece_jointe_id=None,
                type_appel=type_appel,
                modele=MODELE_OCR if type_appel == "ocr" else MODELE_CHAT,
                requete_payload=payload_depuis_erreur(erreur),
                reponse_payload=reponse_depuis_erreur(erreur),
                erreur=str(erreur),
            )
        logger.exception("Échec de l'appel au relais Mistral (OCR)")
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    piece_jointe.contenu_extrait = resultat.contenu_extrait
    piece_jointe.echec_analyse = resultat.echec_analyse
    if resultat.consommation is not None:
        enregistrer_consommation(
            db,
            identifiant_compte,
            conversation_id,
            resultat.consommation.type_appel,
            resultat.consommation.modele,
            usage=resultat.consommation.usage,
            pages_traitees=resultat.consommation.pages_traitees,
        )
        if conversation_id is not None:
            enregistrer_echange_succes(
                db,
                identifiant_compte=identifiant_compte,
                conversation_id=conversation_id,
                piece_jointe_id=piece_jointe.id,
                type_appel=resultat.consommation.type_appel,
                modele=resultat.consommation.modele,
                requete_payload=resultat.consommation.payload_envoye,
                reponse_payload=resultat.consommation.reponse_brute,
            )
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
    status_code=201,
    responses={
        404: {"description": _CONVERSATION_INTROUVABLE},
        400: {"description": f"{_TYPE_NON_SUPPORTE} / {_FICHIER_TROP_VOLUMINEUX}"},
        502: {"description": _ECHEC_RELAIS},
    },
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


@router.post(
    "/pieces-jointes",
    status_code=201,
    responses={
        400: {"description": f"{_TYPE_NON_SUPPORTE} / {_FICHIER_TROP_VOLUMINEUX}"},
        502: {"description": _ECHEC_RELAIS},
    },
)
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
) -> ReponseChat:
    return client.chat(messages_pour_mistral, tools=tools)


def _executer_appels_outils(
    demande: AppelOutilDemande,
    contexte_outils: ContexteTour,
    identifiant_compte: str,
) -> tuple[list[dict], int | None]:
    # Tous les appels de la réponse (spec 1.4.0), dans l'ordre : un message
    # `tool` et un échange local d'inspecteur par appel. piece_jointe_id
    # renvoyé à part (spec 1.3.0) : celui de la pièce jointe relue par un
    # outil, pour l'échange de l'appel principal suivant.
    messages_outils: list[dict] = []
    piece_jointe_relue: int | None = None
    for appel in demande.appels:
        resultat = executer_appel(appel, contexte_outils)
        enregistrer_echange_local(
            contexte_outils.db,
            identifiant_compte=identifiant_compte,
            conversation_id=contexte_outils.conversation_id,
            piece_jointe_id=resultat.piece_jointe_id,
            type_appel=f"outil:{appel.nom}",
            requete_payload={"arguments": appel.arguments},
            reponse_payload={"contenu": resultat.contenu, **resultat.trace},
        )
        messages_outils.append(
            {"role": "tool", "tool_call_id": appel.id, "name": appel.nom, "content": resultat.contenu}
        )
        piece_jointe_relue = piece_jointe_relue or resultat.piece_jointe_id
    return messages_outils, piece_jointe_relue


def _enregistrer_appel_principal(
    contexte_outils: ContexteTour,
    identifiant_compte: str,
    piece_jointe_id: int | None,
    reponse: ReponseChat | AppelOutilDemande,
) -> None:
    # Chaque appel principal, même s'il ne fait que demander des outils :
    # une ligne Consommation "chat" (spec 1.1.3) et un échange succès
    # (spec 1.3.0).
    db = contexte_outils.db
    enregistrer_consommation(
        db, identifiant_compte, contexte_outils.conversation_id, "chat", MODELE_CHAT, usage=reponse.usage
    )
    enregistrer_echange_succes(
        db,
        identifiant_compte=identifiant_compte,
        conversation_id=contexte_outils.conversation_id,
        piece_jointe_id=piece_jointe_id,
        type_appel="chat",
        modele=MODELE_CHAT,
        requete_payload=reponse.payload_envoye,
        reponse_payload=reponse.reponse_brute,
    )


def _resoudre_reponse_chat(
    obtenir_reponse: Callable[[], ReponseChat],
    client: MistralClient,
    messages_pour_mistral: list[dict[str, str]],
    tools: list[dict] | None,
    contexte_outils: ContexteTour,
    identifiant_compte: str,
    piece_jointe_id: int | None,
    conversation_persistee: bool = True,
) -> ReponseChat:
    # Boucle de tool calling (spec 1.4.0). Un tour = un appel de chat
    # principal : au plus _TOURS_MAX_PAR_MESSAGE, le dernier sans `tools`
    # pour forcer une réponse. Le premier est obtenu par `obtenir_reponse`
    # (`futur_reponse.result` ou appel direct à _appeler_reponse_chat, voir
    # _generer_reponse_et_resume). `piece_jointe_id` : celle éventuellement
    # jointe au nouveau message (spec 1.3.0) ; les appels suivants portent
    # celle relue par un outil, s'il y en a une. `conversation_persistee` à
    # False (creer_conversation) : le rollback d'un échec annule aussi la
    # conversation flushée, l'échange d'échec ne peut ni la référencer ni
    # référencer la pièce jointe (voir creer_conversation).
    db = contexte_outils.db
    messages = list(messages_pour_mistral)
    try:
        for tour in range(1, _TOURS_MAX_PAR_MESSAGE + 1):
            try:
                if tour == 1:
                    reponse = obtenir_reponse()
                else:
                    dernier_tour = tour == _TOURS_MAX_PAR_MESSAGE
                    reponse = client.chat(messages, tools=None if dernier_tour else tools)
            except AppelOutilDemande as demande:
                _enregistrer_appel_principal(contexte_outils, identifiant_compte, piece_jointe_id, demande)
                messages_outils, piece_jointe_id = _executer_appels_outils(
                    demande, contexte_outils, identifiant_compte
                )
                messages = [*messages, demande.message_assistant, *messages_outils]
                continue
            _enregistrer_appel_principal(contexte_outils, identifiant_compte, piece_jointe_id, reponse)
            return reponse
        # Ne devrait pas arriver : le dernier tour part sans `tools`.
        raise RuntimeError("Demande d'outil sur le dernier tour, parti sans outils")
    except Exception as erreur:
        # Rollback d'abord : enregistrer_echange_echec commite, et les
        # Consommation + échanges succès des appels déjà faits pour ce
        # message ne doivent pas survivre à un tour qui échoue (jamais de
        # coût compté deux fois si l'utilisateur relance).
        db.rollback()
        enregistrer_echange_echec(
            db,
            identifiant_compte=identifiant_compte,
            conversation_id=contexte_outils.conversation_id if conversation_persistee else None,
            piece_jointe_id=piece_jointe_id if conversation_persistee else None,
            type_appel="chat",
            modele=MODELE_CHAT,
            requete_payload=payload_depuis_erreur(erreur),
            erreur=str(erreur),
        )
        logger.exception(_MSG_ECHEC_RELAIS_LOG)
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur


def _appeler_resume_et_profil(
    client: MistralClient,
    resume_contexte: str,
    profil_actuel: str,
    compte: Compte | None,
    messages_sortants: list[Message],
    pieces_jointes_sortantes: dict[int, PieceJointe],
) -> ReponseChat:
    return client.chat(
        _prompt_resume_et_profil(
            resume_contexte, profil_actuel, compte, messages_sortants, pieces_jointes_sortantes
        ),
        response_format=_SCHEMA_RESUME_ET_PROFIL,
    )


def _generer_reponse_et_resume(
    client: MistralClient,
    messages_pour_mistral: list[dict[str, str]],
    tools: list[dict] | None,
    contexte_outils: ContexteTour,
    conversation: Conversation,
    identifiant_compte: str,
    messages_sortants: list[Message],
    profil_actuel: str,
    compte: Compte | None,
    pieces_jointes_sortantes: dict[int, PieceJointe],
    piece_jointe_id: int | None,
) -> tuple[ReponseChat, str | None, str | None]:
    # Comme pour la création (cf. creer_conversation) : les appels Mistral
    # sont faits avant toute écriture, pour ne jamais persister un message
    # utilisateur sans sa réponse en cas d'échec. Contrairement à
    # creer_conversation (où le titrage a besoin de la réponse de chat), les
    # deux appels ici sont indépendants l'un de l'autre : lancés en parallèle
    # plutôt qu'en séquence pour ne pas doubler la latence de ce tour — mais
    # seulement s'il y a effectivement un résumé à mettre à jour.
    db = contexte_outils.db
    if not messages_sortants:
        reponse_chat = _resoudre_reponse_chat(
            lambda: _appeler_reponse_chat(client, messages_pour_mistral, tools),
            client,
            messages_pour_mistral,
            tools,
            contexte_outils,
            identifiant_compte,
            piece_jointe_id,
        )
        return reponse_chat, None, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futur_reponse = executor.submit(_appeler_reponse_chat, client, messages_pour_mistral, tools)
        futur_resume = executor.submit(
            _appeler_resume_et_profil,
            client,
            conversation.resume_contexte,
            profil_actuel,
            compte,
            messages_sortants,
            pieces_jointes_sortantes,
        )
        reponse_chat = _resoudre_reponse_chat(
            futur_reponse.result,
            client,
            messages_pour_mistral,
            tools,
            contexte_outils,
            identifiant_compte,
            piece_jointe_id,
        )
        try:
            reponse_resume = futur_resume.result()
        except Exception as erreur:
            # Pas de piece_jointe_id unique ici (spec 1.3.0) : un appel
            # résumé+profil peut absorber plusieurs messages sortants, donc
            # plusieurs pièces jointes potentiellement différentes — jamais
            # une seule référence à privilégier arbitrairement. Rollback
            # d'abord (enregistrer_echange_echec commite) : la Consommation et
            # l'échange succès du chat déjà résolu ci-dessus ne doivent pas
            # survivre à ce tour, dont aucun message n'est persisté.
            conversation_id = conversation.id
            db.rollback()
            enregistrer_echange_echec(
                db,
                identifiant_compte=identifiant_compte,
                conversation_id=conversation_id,
                piece_jointe_id=None,
                type_appel="resume_et_profil",
                modele=MODELE_CHAT,
                requete_payload=payload_depuis_erreur(erreur),
                erreur=str(erreur),
            )
            logger.exception(_MSG_ECHEC_RELAIS_LOG)
            raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    enregistrer_consommation(
        db,
        identifiant_compte,
        conversation.id,
        "resume_et_profil",
        MODELE_CHAT,
        usage=reponse_resume.usage,
    )
    enregistrer_echange_succes(
        db,
        identifiant_compte=identifiant_compte,
        conversation_id=conversation.id,
        piece_jointe_id=None,
        type_appel="resume_et_profil",
        modele=MODELE_CHAT,
        requete_payload=reponse_resume.payload_envoye,
        reponse_payload=reponse_resume.reponse_brute,
    )
    try:
        donnees = json.loads(reponse_resume.contenu)
        resume_maj = donnees["resume_contexte"]
        profil_travail = donnees.get("profil_travail")
    except (json.JSONDecodeError, KeyError, TypeError) as erreur:
        # Distinct du bloc ci-dessus : une réponse reçue mais mal formée n'est
        # pas une panne du relais Mistral, ne doit jamais être journalisée
        # comme telle (les deux étaient auparavant confondues dans un seul
        # except Exception large).
        logger.exception("Réponse résumé+profil de Mistral invalide")
        raise HTTPException(status_code=502, detail=_ECHEC_RELAIS) from erreur

    return reponse_chat, resume_maj, profil_travail


@router.post(
    "/conversations/{conversation_id}/messages",
    responses={
        404: {"description": _CONVERSATION_INTROUVABLE},
        400: {"description": _PIECE_JOINTE_INTROUVABLE},
        502: {"description": _ECHEC_RELAIS},
    },
)
def envoyer_message(
    conversation_id: int,
    requete: MessageEnvoyeRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    client: MistralClient = Depends(get_mistral_client),
    moteur_recherche: MoteurRecherche = Depends(get_moteur_recherche),
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
        piece_jointe_id = piece_jointe.id if piece_jointe is not None else None

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
            conversation.resume_contexte, derniers_messages, requete.message, profil_actuel, piece_jointe
        )

        # Un message sort de la fenêtre des 3 derniers dès que ce tour (2 nouveaux
        # messages) ne laisse plus la place à tous les messages qui y étaient
        # jusque-là : tous sauf le plus récent (qui reste dans la fenêtre aux
        # côtés des 2 nouveaux, cf. spec V1.1.1).
        messages_sortants = derniers_messages[:-1]

        # Outils déclarés uniquement sur l'appel de réponse de chat principal
        # ci-dessous, jamais sur celui de résumé+profil (spec 1.1.2) : la
        # fenêtre ici est celle des messages déjà en base avant ce tour
        # (`derniers_messages`), pas `messages_sortants` (qui n'en retire que
        # le plus ancien, propre à l'absorption de CE tour dans le résumé).
        contexte_outils = ContexteTour(
            db=db,
            conversation_id=conversation.id,
            ids_fenetre=frozenset(m.id for m in derniers_messages),
            moteur_recherche=moteur_recherche,
        )
        tools = outils_du_tour(contexte_outils)

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

        reponse_chat, resume_maj, profil_travail = _generer_reponse_et_resume(
            client,
            messages_pour_mistral,
            tools,
            contexte_outils,
            conversation,
            identifiant_compte,
            messages_sortants,
            profil_actuel,
            compte,
            pieces_jointes_sortantes,
            piece_jointe_id,
        )

        reponse = _reponse_visible(
            db, conversation.id, requete.message, reponse_chat.contenu, piece_jointe
        )

        maintenant = datetime.now(timezone.utc)
        if resume_maj is not None:
            conversation.resume_contexte = plafonner(resume_maj, _TAILLE_MAX_RESUME_CONTEXTE)
        if profil_travail and profil_travail.strip():
            # Remplacé, jamais concaténé (spec 1.3.1) : null ou vide le
            # laisse intact.
            profil = _recuperer_ou_creer_profil(db, identifiant_compte)
            profil.contenu = plafonner(profil_travail.strip(), _TAILLE_MAX_PROFIL_TRAVAIL)
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
