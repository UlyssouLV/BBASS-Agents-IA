import logging
from datetime import datetime, timezone
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
    MigrationUnique,
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

_NETTOYAGE_COMPTES_SUPPRIMES = "nettoyage-comptes-supprimes-1.6.3"

logger = logging.getLogger(__name__)


# Les fonctions de suppression ne valident pas et rendent les fichiers de
# pièces jointes à effacer : l'appelant passe ces chemins à
# supprimer_fichiers après son commit, pour qu'un rollback ne perde aucun
# fichier.
def supprimer_donnees_conversation(db: Session, conversation: Conversation) -> list[str]:
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

    # Pièces jointes supprimées avant les messages (spec 1.1.2) :
    # PieceJointe.message_id référence Message, donc l'ordre inverse violerait
    # l'intégrité référentielle.
    fichiers = _supprimer_pieces_jointes(db, PieceJointe.conversation_id == conversation.id)

    # Message n'a pas de cascade ORM déclarée sur Conversation (même
    # convention que Jeton/Compte, voir comptes.py) : la suppression des
    # messages associés doit donc être explicite, avant celle de la
    # conversation elle-même.
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)
    return fichiers


def supprimer_donnees_compte(db: Session, identifiant: str) -> list[str]:
    # Toutes les données du compte (spec 1.6.3, #161), sans commit : même
    # transaction que l'appelant. Aucune table n'a de ForeignKey vers
    # comptes.identifiant, d'où la suppression explicite table par table.
    fichiers = [
        fichier
        for conversation in db.query(Conversation).filter(Conversation.identifiant_compte == identifiant).all()
        for fichier in supprimer_donnees_conversation(db, conversation)
    ]
    # Échanges hors conversation avant les pièces jointes qu'ils référencent.
    db.query(EchangeInspecteur).filter(EchangeInspecteur.identifiant_compte == identifiant).delete()
    fichiers += _supprimer_pieces_jointes(db, PieceJointe.identifiant_compte == identifiant)
    db.query(ProfilTravail).filter(ProfilTravail.identifiant_compte == identifiant).delete()
    db.query(RattachementModuleo).filter(RattachementModuleo.identifiant_compte == identifiant).delete()
    # La consommation reste dans le suivi des coûts, détachée du compte : un
    # compte recréé avec le même identifiant repart à zéro.
    db.query(Consommation).filter(Consommation.identifiant_compte == identifiant).update(
        {Consommation.identifiant_compte: IDENTIFIANT_COMPTE_SUPPRIME}
    )
    return fichiers


def nettoyer_comptes_supprimes(db: Session) -> list[str]:
    # Données laissées par les comptes supprimés avant la 1.6.3 : même règle
    # que supprimer_donnees_compte. Migration unique, tentée une seule fois
    # par base : une suppression irréversible ne doit pas tourner à chaque
    # init_db, où un compte créé après une restauration partielle rendrait
    # orphelin tout le reste.
    if db.get(MigrationUnique, _NETTOYAGE_COMPTES_SUPPRIMES) is not None:
        return []
    db.add(MigrationUnique(nom=_NETTOYAGE_COMPTES_SUPPRIMES, date_application=datetime.now(timezone.utc)))
    comptes = {identifiant for (identifiant,) in db.query(Compte.identifiant)}
    if not comptes:
        # Base sans aucun compte (installation en cours, restauration
        # partielle) : rien ne dit que ces données sont celles de comptes
        # supprimés, on n'y touche pas.
        return []
    orphelins = {
        identifiant
        for table in (*_TABLES_DU_COMPTE, Consommation)
        for (identifiant,) in db.query(table.identifiant_compte).distinct()
    } - comptes - {IDENTIFIANT_COMPTE_SUPPRIME}
    return [fichier for identifiant in orphelins for fichier in supprimer_donnees_compte(db, identifiant)]


def supprimer_fichiers(fichiers: list[str], dossier_pieces_jointes: str) -> None:
    # Après le commit : la base est déjà à jour, un fichier verrouillé ne
    # doit ni faire échouer la requête ni empêcher la VM de démarrer. Un
    # fichier déjà absent n'est pas une erreur.
    for fichier in fichiers:
        try:
            (Path(dossier_pieces_jointes) / fichier).unlink(missing_ok=True)
        except OSError as erreur:
            logger.warning("Fichier de pièce jointe non supprimé %s : %s", fichier, erreur)


def _supprimer_pieces_jointes(db: Session, condition: ColumnElement[bool]) -> list[str]:
    fichiers = [chemin for (chemin,) in db.query(PieceJointe.chemin_fichier).filter(condition)]
    db.query(PieceJointe).filter(condition).delete()
    return fichiers
