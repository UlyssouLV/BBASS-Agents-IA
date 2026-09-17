from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vm_centrale.autorisation import get_identifiant_compte_du_jeton
from vm_centrale.database import get_db
from vm_centrale.models import Consommation, Conversation
from vm_centrale.schemas import (
    ConsommationResponse,
    ConversationConsommationResponse,
    DetailConsommationCategorie,
)

router = APIRouter()

# Catégorisation à l'affichage (spec 1.1.3), calculée côté lecture — jamais
# stockée comme colonne dérivée sur Consommation.
_TYPES_CHAT = frozenset({"chat", "titrage", "resume_et_profil"})


def _detail_vide() -> DetailConsommationCategorie:
    return DetailConsommationCategorie(
        tokens_total=0, pages_traitees=0, cout_usd=Decimal(0), nombre_requetes=0
    )


def _accumuler(
    detail: DetailConsommationCategorie, ligne: Consommation
) -> DetailConsommationCategorie:
    return DetailConsommationCategorie(
        tokens_total=detail.tokens_total + (ligne.tokens_total or 0),
        pages_traitees=detail.pages_traitees + (ligne.pages_traitees or 0),
        cout_usd=detail.cout_usd + ligne.cout_usd,
        nombre_requetes=detail.nombre_requetes + 1,
    )


@router.get("/consommation", response_model=ConsommationResponse)
def consulter_consommation(
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
) -> ConsommationResponse:
    lignes = (
        db.query(Consommation).filter(Consommation.identifiant_compte == identifiant_compte).all()
    )

    chat_global = _detail_vide()
    piece_jointe_global = _detail_vide()
    # Détail par conversation, accumulé en mémoire (pas de GROUP BY SQL) :
    # même style que le reste du routeur conversations.py, à un volume de
    # lignes qui reste modeste (usage interne d'un cabinet).
    par_conversation: dict[int, dict[str, DetailConsommationCategorie]] = {}

    for ligne in lignes:
        categorie = "chat" if ligne.type_appel in _TYPES_CHAT else "piece_jointe"
        if categorie == "chat":
            chat_global = _accumuler(chat_global, ligne)
        else:
            piece_jointe_global = _accumuler(piece_jointe_global, ligne)

        if ligne.conversation_id is not None:
            details = par_conversation.setdefault(
                ligne.conversation_id, {"chat": _detail_vide(), "piece_jointe": _detail_vide()}
            )
            details[categorie] = _accumuler(details[categorie], ligne)

    conversations: list[ConversationConsommationResponse] = []
    if par_conversation:
        lignes_titres = (
            db.query(Conversation.id, Conversation.titre)
            .filter(Conversation.id.in_(par_conversation.keys()))
            .all()
        )
        titres = {conversation_id: titre for conversation_id, titre in lignes_titres}
        for conversation_id, details in par_conversation.items():
            titre = titres.get(conversation_id)
            if titre is None:
                # Conversation supprimée entretemps : le rattachement est
                # perdu, cette conversation n'apparaît plus au classement
                # (spec 1.1.3), même si ses lignes comptent toujours dans le
                # total global ci-dessus.
                continue
            conversations.append(
                ConversationConsommationResponse(
                    id=conversation_id,
                    titre=titre,
                    cout_usd=details["chat"].cout_usd + details["piece_jointe"].cout_usd,
                    chat=details["chat"],
                    piece_jointe=details["piece_jointe"],
                )
            )
    conversations.sort(key=lambda conversation: conversation.cout_usd, reverse=True)

    return ConsommationResponse(
        chat=chat_global, piece_jointe=piece_jointe_global, conversations=conversations
    )
