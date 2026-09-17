from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.config import calculer_cout
from vm_centrale.mistral_client import Usage
from vm_centrale.models import Consommation


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
