from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from vm_centrale.config import calculer_cout
from vm_centrale.mistral_client import Usage
from vm_centrale.models import Consommation
from vm_centrale.schemas import DetailConsommationCategorie

# Catégorisation à l'affichage (spec 1.1.3), calculée côté lecture — jamais
# stockée comme colonne dérivée sur Consommation. Partagée par les deux
# endpoints de lecture (vue collaborateur et vue administrateur).
TYPES_CHAT = frozenset(
    {"chat", "titrage", "resume_et_profil", "extraction_web", "questions_piece_jointe", "extraction_piece_jointe"}
)


def detail_vide() -> DetailConsommationCategorie:
    return DetailConsommationCategorie(
        tokens_total=0, pages_traitees=0, cout_usd=Decimal(0), nombre_requetes=0
    )


def accumuler(
    detail: DetailConsommationCategorie, ligne: Consommation
) -> DetailConsommationCategorie:
    return DetailConsommationCategorie(
        tokens_total=detail.tokens_total + (ligne.tokens_total or 0),
        pages_traitees=detail.pages_traitees + (ligne.pages_traitees or 0),
        cout_usd=detail.cout_usd + ligne.cout_usd,
        nombre_requetes=detail.nombre_requetes + 1,
    )


def enregistrer_consommation(
    db: Session,
    identifiant_compte: str,
    conversation_id: int | None,
    type_appel: str,
    modele: str,
    usage: Usage | None = None,
    pages_traitees: int | None = None,
) -> None:
    # Ajoutée à la session sans commit (spec V1.1.3) : le commit reste celui
    # de l'appelant, dans la même transaction que le reste de son écriture —
    # un rollback (appel Mistral suivant en échec, réponse malformée) annule
    # aussi cette ligne, comme pour un message ou une pièce jointe.
    tokens_entree = usage.tokens_entree if usage is not None else None
    tokens_sortie = usage.tokens_sortie if usage is not None else None
    tokens_total = usage.tokens_total if usage is not None else None
    db.add(
        Consommation(
            identifiant_compte=identifiant_compte,
            conversation_id=conversation_id,
            type_appel=type_appel,
            modele=modele,
            tokens_entree=tokens_entree,
            tokens_sortie=tokens_sortie,
            tokens_total=tokens_total,
            pages_traitees=pages_traitees,
            cout_usd=calculer_cout(type_appel, modele, tokens_entree, tokens_sortie, pages_traitees),
            date_creation=datetime.now(timezone.utc),
        )
    )
