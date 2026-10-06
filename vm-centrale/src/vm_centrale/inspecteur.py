from datetime import datetime, timezone

from sqlalchemy.orm import Session

from vm_centrale.models import EchangeInspecteur


def payload_depuis_erreur(erreur: Exception) -> dict:
    # ErreurAppelMistral (vm_centrale.mistral_client) porte le payload exact
    # qui allait être envoyé au moment où l'appel a échoué. Toute autre
    # exception (ex. un double de test qui ne la lève pas) n'en porte pas :
    # jamais reconstruit depuis ce que l'appelant avait l'intention
    # d'envoyer, qui ne reflète pas forcément le payload réel construit par
    # MistralClient (ex. document_url en base64 pour l'OCR).
    return getattr(erreur, "payload_envoye", None) or {}


def reponse_depuis_erreur(erreur: Exception) -> dict | None:
    # Même principe que payload_depuis_erreur : la réponse brute n'existe que
    # si Mistral a répondu avant l'échec (voir ErreurAppelMistral).
    return getattr(erreur, "reponse_brute", None)


def enregistrer_echange_succes(
    db: Session,
    *,
    identifiant_compte: str,
    conversation_id: int | None,
    piece_jointe_id: int | None,
    type_appel: str,
    modele: str,
    requete_payload: dict,
    reponse_payload: dict | None,
) -> None:
    # Ajouté à la session sans commit (spec 1.3.0), comme
    # vm_centrale.consommation.enregistrer_consommation : le commit reste
    # celui de l'appelant, dans la même transaction que le reste de son
    # écriture — un rollback plus loin dans le même tour annule aussi cette
    # ligne.
    db.add(
        EchangeInspecteur(
            identifiant_compte=identifiant_compte,
            conversation_id=conversation_id,
            piece_jointe_id=piece_jointe_id,
            origine="mistral",
            type_appel=type_appel,
            modele=modele,
            requete_payload=requete_payload,
            reponse_payload=reponse_payload,
            statut="succes",
            erreur=None,
            date_creation=datetime.now(timezone.utc),
        )
    )


def enregistrer_echange_echec(
    db: Session,
    *,
    identifiant_compte: str,
    conversation_id: int | None,
    piece_jointe_id: int | None,
    type_appel: str,
    modele: str,
    requete_payload: dict,
    erreur: str,
    reponse_payload: dict | None = None,
    commit: bool = True,
) -> None:
    # Commité indépendamment (spec 1.3.0), contrairement à un échange réussi
    # ci-dessus : l'appelant a déjà fait (ou n'a rien à faire) son propre
    # db.rollback() juste avant, et cette ligne doit malgré tout survivre —
    # sinon l'échange qu'on veut le plus pouvoir déboguer disparaîtrait avec
    # le reste du tour applicatif annulé. `commit=False` : un échec qui
    # n'interrompt pas le tour (ex. l'appel d'extraction de rechercher_web,
    # spec 1.4.0) suit le tour, sans commiter ce qui est en cours.
    db.add(
        EchangeInspecteur(
            identifiant_compte=identifiant_compte,
            conversation_id=conversation_id,
            piece_jointe_id=piece_jointe_id,
            origine="mistral",
            type_appel=type_appel,
            modele=modele,
            requete_payload=requete_payload,
            reponse_payload=reponse_payload,
            statut="echec",
            erreur=erreur,
            date_creation=datetime.now(timezone.utc),
        )
    )
    if commit:
        db.commit()


def enregistrer_echange_local(
    db: Session,
    *,
    identifiant_compte: str,
    conversation_id: int,
    piece_jointe_id: int | None,
    type_appel: str,
    requete_payload: dict,
    reponse_payload: dict,
) -> None:
    # Travail de la VM elle-même (spec 1.4.0), ex. l'exécution d'un outil :
    # sans commit, comme enregistrer_echange_succes, pour disparaître avec le
    # reste d'un tour qui échoue.
    db.add(
        EchangeInspecteur(
            identifiant_compte=identifiant_compte,
            conversation_id=conversation_id,
            piece_jointe_id=piece_jointe_id,
            origine="local",
            type_appel=type_appel,
            modele="",
            requete_payload=requete_payload,
            reponse_payload=reponse_payload,
            statut="succes",
            erreur=None,
            date_creation=datetime.now(timezone.utc),
        )
    )
