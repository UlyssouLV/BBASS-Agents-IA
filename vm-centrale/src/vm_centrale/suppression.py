from pathlib import Path

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Session

from vm_centrale.lectures_outils import supprimer_lectures
from vm_centrale.models import (
    Compte,
    Consommation,
    Conversation,
    EchangeInspecteur,
    Message,
    PieceJointe,
    ProfilTravail,
    QuestionCouverte,
    RattachementModuleo,
    ResultatRechercheWeb,
)

# Valeur réservée de Consommation.identifiant_compte pour un compte supprimé
# (spec 1.6.3, #161) : jamais un identifiant de compte (CompteCreeRequest
# exige au moins un caractère), affichée « Compte supprimé » dans le suivi
# des coûts.
IDENTIFIANT_COMPTE_SUPPRIME = ""

# Tables qui portent des données d'un compte, par identifiant_compte. Le
# journal Moduléo n'y est pas : trace d'audit, gardée telle quelle.
_TABLES_DU_COMPTE = (Conversation, PieceJointe, ProfilTravail, EchangeInspecteur, RattachementModuleo)


def supprimer_donnees_conversation(db: Session, conversation: Conversation, dossier_pieces_jointes: str) -> None:
    # echanges_inspecteur disparaît avec sa conversation (FK ON DELETE
    # CASCADE, spec 1.3.0) — contrairement à Consommation ci-dessous.
    # Supprimé ici explicitement, comme Message/PieceJointe plus bas, pour un
    # comportement identique quel que soit le moteur de base (la base de
    # test SQLite n'applique pas les contraintes FK par défaut).
    db.query(EchangeInspecteur).filter(EchangeInspecteur.conversation_id == conversation.id).delete()
    # Même chose pour les questions couvertes (spec 1.4.1), avant les
    # résultats de recherche et les pièces jointes qu'elles référencent, et
    # pour les résultats de recherche (spec 1.4.0).
    db.query(QuestionCouverte).filter(QuestionCouverte.conversation_id == conversation.id).delete()
    db.query(ResultatRechercheWeb).filter(
        ResultatRechercheWeb.conversation_id == conversation.id
    ).delete()
    supprimer_lectures(db, conversation.id)

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
    _supprimer_pieces_jointes(db, PieceJointe.conversation_id == conversation.id, dossier_pieces_jointes)

    # Message n'a pas de cascade ORM déclarée sur Conversation (même
    # convention que Jeton/Compte, voir comptes.py) : la suppression des
    # messages associés doit donc être explicite, avant celle de la
    # conversation elle-même.
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)


def supprimer_donnees_compte(db: Session, identifiant: str, dossier_pieces_jointes: str) -> None:
    # Toutes les données du compte (spec 1.6.3, #161), sans commit : même
    # transaction que l'appelant. Aucune table n'a de ForeignKey vers
    # comptes.identifiant, d'où la suppression explicite table par table.
    for conversation in db.query(Conversation).filter(Conversation.identifiant_compte == identifiant).all():
        supprimer_donnees_conversation(db, conversation, dossier_pieces_jointes)
    # Échanges hors conversation avant les pièces jointes qu'ils référencent.
    db.query(EchangeInspecteur).filter(EchangeInspecteur.identifiant_compte == identifiant).delete()
    _supprimer_pieces_jointes(db, PieceJointe.identifiant_compte == identifiant, dossier_pieces_jointes)
    db.query(ProfilTravail).filter(ProfilTravail.identifiant_compte == identifiant).delete()
    db.query(RattachementModuleo).filter(RattachementModuleo.identifiant_compte == identifiant).delete()
    # La consommation reste dans le suivi des coûts, détachée du compte : un
    # compte recréé avec le même identifiant repart à zéro.
    db.query(Consommation).filter(Consommation.identifiant_compte == identifiant).update(
        {Consommation.identifiant_compte: IDENTIFIANT_COMPTE_SUPPRIME}
    )


def nettoyer_comptes_supprimes(db: Session, dossier_pieces_jointes: str) -> None:
    # Données laissées par les comptes supprimés avant la 1.6.3 : même règle
    # que supprimer_donnees_compte. Idempotent, sans effet sans orphelin.
    comptes = {identifiant for (identifiant,) in db.query(Compte.identifiant)}
    if not comptes:
        # Base sans aucun compte (installation en cours, restauration
        # partielle) : rien ne dit que ces données sont celles de comptes
        # supprimés, on n'y touche pas.
        return
    orphelins = {
        identifiant
        for table in (*_TABLES_DU_COMPTE, Consommation)
        for (identifiant,) in db.query(table.identifiant_compte).distinct()
    } - comptes - {IDENTIFIANT_COMPTE_SUPPRIME}
    for identifiant in orphelins:
        supprimer_donnees_compte(db, identifiant, dossier_pieces_jointes)


def _supprimer_pieces_jointes(db: Session, condition: ColumnElement[bool], dossier_pieces_jointes: str) -> None:
    for piece_jointe in db.query(PieceJointe).filter(condition).all():
        (Path(dossier_pieces_jointes) / piece_jointe.chemin_fichier).unlink(missing_ok=True)
    db.query(PieceJointe).filter(condition).delete()
