import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from vm_centrale.models import EcritureModuleo, Message
from vm_centrale.moduleo.client import (
    ClientModuleo,
    ModuleoDonneesRefusees,
    ModuleoIndisponible,
    ModuleoIntrouvable,
    ModuleoRefuse,
    RequeteInterdite,
)
from vm_centrale.moduleo.droits import DroitManquant, DroitsModuleo

# Écritures Moduléo proposées et Journal des écritures (spec 1.5.2, #204,
# ADR-0019) : une ligne `ecritures_moduleo` par écriture que le modèle
# propose. La Carte de confirmation la montre tant qu'elle est « proposee » ;
# seul le clic du collaborateur (decider) l'envoie, une fois. Règles :
# moduleo/README.md, section **Carte de confirmation**.

PROPOSEE = "proposee"
CONFIRMEE = "confirmee"
ANNULEE = "annulee"
EXPIREE = "expiree"
REFUSEE = "refusee"
EN_ECHEC = "en_echec"

ECRIT = "Écrit dans Moduléo."
_ANNULEE = "Annulée : rien n'a été écrit."
_EXPIREE = "Expirée : un nouveau message a été envoyé avant la confirmation. Rien n'a été écrit."
# Phrases fixes d'un échec, telles que la carte les affiche.
_BARRIERE = "L'écriture dans Moduléo n'est plus ouverte sur cette VM. Rien n'a été écrit."
_DONNEES_REFUSEES = "Moduléo a refusé les données envoyées : {message}"
_REFUS = "Moduléo refuse cette écriture. Rien n'a été écrit."
_INTROUVABLE = "L'élément visé n'existe pas dans Moduléo. Rien n'a été écrit."
_PANNE = "Moduléo est indisponible : l'écriture n'a pas pu être vérifiée. Vérifiez dans Moduléo avant de recommencer."

logger = logging.getLogger(__name__)


class EcritureIntrouvable(Exception):
    # Aucune écriture de ce compte sous cet id.
    pass


class EcritureDejaDecidee(Exception):
    # L'écriture n'est plus « proposee » : déjà confirmée, annulée,
    # expirée… Rien n'est envoyé.
    def __init__(self, ecriture: EcritureModuleo) -> None:
        super().__init__(ecriture.statut)
        self.ecriture = ecriture


@dataclass(frozen=True)
class Decision:
    # Ce qu'un clic a produit : l'écriture à jour et, pour l'inspecteur,
    # ce que Moduléo a répondu (jamais la clé ni le SecurityCode).
    ecriture: EcritureModuleo
    reponse_moduleo: Any = None
    detail: str | None = None


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def proposer(
    db: Session,
    identifiant_compte: str,
    conversation_id: int,
    methode: str,
    route: str,
    parametres: dict[str, Any],
    corps: Any,
    carte: dict | None,
    statut: str = PROPOSEE,
    erreur: str | None = None,
) -> EcritureModuleo:
    # Flush (jamais commit), comme les lectures : un tour qui échoue
    # l'annule. Une écriture refusée dès la proposition : `statut` REFUSEE,
    # sans carte.
    ecriture = EcritureModuleo(
        identifiant_compte=identifiant_compte,
        conversation_id=conversation_id,
        methode=methode,
        route=route,
        parametres=parametres,
        corps=corps,
        carte=carte,
        statut=statut,
        erreur=erreur,
        date_creation=_maintenant(),
        date_decision=_maintenant() if statut != PROPOSEE else None,
    )
    db.add(ecriture)
    db.flush()
    return ecriture


def carte_de(ecriture: EcritureModuleo) -> dict[str, Any]:
    # Ce que reçoit le poste (événement `carte`, rechargement de la
    # Conversation, réponse au clic) : jamais le corps brut, la carte en noms.
    # PUT (#205) : `avant` de chaque ligne, null hors différence. DELETE :
    # `rubrique` (« Sera supprimé ») et `fiche`, le texte de l'élément quand
    # il en a une.
    carte = ecriture.carte or {}
    return {
        "id": ecriture.id,
        "statut": ecriture.statut,
        "methode": ecriture.methode,
        "route": ecriture.route,
        "titre": carte.get("titre", ""),
        "lignes": [{"avant": None, **ligne} for ligne in carte.get("lignes", [])],
        "rubrique": carte.get("rubrique"),
        "fiche": carte.get("fiche"),
        "message": message_de(ecriture),
    }


def message_de(ecriture: EcritureModuleo) -> str | None:
    if ecriture.statut == CONFIRMEE:
        return ECRIT
    if ecriture.statut == ANNULEE:
        return _ANNULEE
    if ecriture.statut == EXPIREE:
        return _EXPIREE
    return ecriture.erreur


def expirer(db: Session, conversation_id: int) -> None:
    # Un nouveau message dans la Conversation : toute proposition encore
    # ouverte expire. L'appelant commite avant le tour.
    db.query(EcritureModuleo).filter(
        EcritureModuleo.conversation_id == conversation_id, EcritureModuleo.statut == PROPOSEE
    ).update({EcritureModuleo.statut: EXPIREE, EcritureModuleo.date_decision: _maintenant()})


def rattacher_ecritures_au_message(db: Session, message: Message) -> None:
    # Les écritures sans message sont celles de ce tour.
    db.flush()
    db.query(EcritureModuleo).filter(
        EcritureModuleo.conversation_id == message.conversation_id,
        EcritureModuleo.message_id.is_(None),
    ).update({EcritureModuleo.message_id: message.id})


def detacher_de_la_conversation(db: Session, conversation_id: int) -> None:
    # Le journal survit à la conversation supprimée.
    db.query(EcritureModuleo).filter(EcritureModuleo.conversation_id == conversation_id).update(
        {EcritureModuleo.conversation_id: None, EcritureModuleo.message_id: None}
    )


def cartes_par_message(db: Session, message_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    # Cartes rechargées avec la Conversation, dans l'ordre de proposition ;
    # une écriture refusée dès la proposition n'a pas de carte.
    if not message_ids:
        return {}
    ecritures = (
        db.query(EcritureModuleo)
        .filter(EcritureModuleo.message_id.in_(message_ids), EcritureModuleo.carte.is_not(None))
        .order_by(EcritureModuleo.id)
        .all()
    )
    cartes: dict[int, list[dict[str, Any]]] = {}
    for ecriture in ecritures:
        assert ecriture.message_id is not None
        cartes.setdefault(ecriture.message_id, []).append(carte_de(ecriture))
    return cartes


def resultats_par_message(db: Session, message_ids: list[int]) -> dict[int, list[str]]:
    # Résultat de chaque carte décidée, vu par le modèle au tour suivant
    # comme le résultat de son appel à ecrire_moduleo.
    if not message_ids:
        return {}
    ecritures = (
        db.query(EcritureModuleo)
        .filter(
            EcritureModuleo.message_id.in_(message_ids),
            EcritureModuleo.carte.is_not(None),
            EcritureModuleo.statut != PROPOSEE,
        )
        .order_by(EcritureModuleo.id)
        .all()
    )
    resultats: dict[int, list[str]] = {}
    for ecriture in ecritures:
        assert ecriture.message_id is not None
        resultats.setdefault(ecriture.message_id, []).append(_resultat_pour_le_modele(ecriture))
    return resultats


def _resultat_pour_le_modele(ecriture: EcritureModuleo) -> str:
    decision = message_de(ecriture) or ""
    if ecriture.statut == CONFIRMEE and ecriture.id_renvoye:
        decision = f"{decision} Id renvoyé : [id Moduléo {ecriture.id_renvoye}]."
    return (
        f"Résultat de l'outil ecrire_moduleo ({ecriture.methode} {ecriture.route}), après la décision du "
        f"collaborateur sur la Carte de confirmation : {decision}"
    )


def decider(
    db: Session,
    client: ClientModuleo | None,
    identifiant_compte: str,
    ecriture_id: int,
    confirmer: bool,
    droits: DroitsModuleo,
) -> Decision:
    # Appelé sous le verrou du compte : aucun tour ni autre clic du compte
    # en même temps. `droits` : relus au clic, un droit retiré depuis la
    # proposition fait refuser l'écriture. Une seule requête à Moduléo.
    ecriture = db.get(EcritureModuleo, ecriture_id)
    # Une conversation supprimée emporte ses cartes : plus rien à confirmer.
    if (
        ecriture is None
        or ecriture.identifiant_compte != identifiant_compte
        or ecriture.carte is None
        or ecriture.conversation_id is None
    ):
        raise EcritureIntrouvable()
    if ecriture.statut != PROPOSEE:
        raise EcritureDejaDecidee(ecriture)
    ecriture.date_decision = _maintenant()
    if not confirmer:
        ecriture.statut = ANNULEE
        return Decision(ecriture)
    if client is None:
        return _echec(ecriture, REFUSEE, _BARRIERE, "Moduléo n'est pas configuré")
    try:
        reponse = client.ecrire(ecriture.methode, ecriture.route, ecriture.parametres, ecriture.corps, droits)
    except DroitManquant as refus:
        return _echec(ecriture, REFUSEE, refus.phrase, refus.refus)
    except RequeteInterdite as erreur:
        return _echec(ecriture, REFUSEE, _BARRIERE, str(erreur))
    except ModuleoDonneesRefusees as erreur:
        return _echec(ecriture, EN_ECHEC, _DONNEES_REFUSEES.format(message=erreur.message), str(erreur))
    except ModuleoRefuse as erreur:
        return _echec(ecriture, EN_ECHEC, _REFUS, str(erreur))
    except ModuleoIntrouvable as erreur:
        return _echec(ecriture, EN_ECHEC, _INTROUVABLE, str(erreur))
    except ModuleoIndisponible as erreur:
        return _echec(ecriture, EN_ECHEC, _PANNE, str(erreur))
    ecriture.statut = CONFIRMEE
    ecriture.id_renvoye = _id_renvoye(reponse)
    return Decision(ecriture, reponse)


def _echec(ecriture: EcritureModuleo, statut: str, phrase: str, detail: str) -> Decision:
    logger.warning("Écriture Moduléo %s %s : %s", statut, ecriture.id, detail)
    ecriture.statut = statut
    ecriture.erreur = phrase
    return Decision(ecriture, detail=detail)


def _id_renvoye(reponse: Any) -> str | None:
    # Moduléo renvoie l'id créé, seul ou dans l'élément (« Id… »).
    if isinstance(reponse, bool) or reponse is None:
        return None
    if isinstance(reponse, (int, str)):
        return str(reponse).strip() or None
    if isinstance(reponse, dict):
        for cle, valeur in reponse.items():
            if cle.startswith("Id") and isinstance(valeur, int) and not isinstance(valeur, bool):
                return str(valeur)
    return None
