from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vm_centrale.autorisation import get_identifiant_compte_du_jeton
from vm_centrale.concurrence import verrous_comptes
from vm_centrale.database import get_db
from vm_centrale.inspecteur import enregistrer_echange_local
from vm_centrale.moduleo.client import ClientModuleo, get_client_moduleo
from vm_centrale.moduleo.droits import droits_du_compte
from vm_centrale.moduleo.ecritures import EcritureDejaDecidee, EcritureIntrouvable, carte_de, decider
from vm_centrale.schemas import CarteEcriture, DecisionEcritureRequest

# Confirmation d'une écriture Moduléo (spec 1.5.2, #204, ADR-0023) : le
# clic du collaborateur sur la Carte de confirmation, hors du modèle. Seul
# chemin par lequel une écriture part vers Moduléo. Règles :
# moduleo/README.md, section **Carte de confirmation**.

router = APIRouter()

_ECRITURE_INTROUVABLE = "Écriture Moduléo introuvable"
_DEJA_DECIDEE = "Écriture Moduléo déjà décidée (voir son statut)"
_TOUR_EN_COURS = "Un message est en cours de traitement : réessayez une fois la réponse affichée"
# Le clic attend la fin d'un tour du même compte (verrou par compte) : une
# carte proposée pendant le tour n'est en base qu'à sa fin.
_ATTENTE_DU_TOUR_SECONDES = 120


@router.post(
    "/ecritures-moduleo/{ecriture_id}",
    responses={
        404: {"description": _ECRITURE_INTROUVABLE},
        409: {"description": f"{_DEJA_DECIDEE} / {_TOUR_EN_COURS}"},
    },
)
def decider_ecriture(
    ecriture_id: int,
    requete: DecisionEcritureRequest,
    identifiant_compte: str = Depends(get_identifiant_compte_du_jeton),
    db: Session = Depends(get_db),
    client_moduleo: ClientModuleo | None = Depends(get_client_moduleo),
) -> CarteEcriture:
    # Sous le verrou du compte : ni tour (qui ferait expirer la carte) ni
    # autre clic en même temps, donc un double clic n'écrit qu'une fois.
    verrou = verrous_comptes.pour(identifiant_compte)
    if not verrou.acquire(timeout=_ATTENTE_DU_TOUR_SECONDES):
        raise HTTPException(status_code=409, detail=_TOUR_EN_COURS)
    try:
        try:
            decision = decider(
                db,
                client_moduleo,
                identifiant_compte,
                ecriture_id,
                requete.decision == "confirmer",
                droits_du_compte(db, identifiant_compte),
            )
        except EcritureIntrouvable:
            raise HTTPException(status_code=404, detail=_ECRITURE_INTROUVABLE) from None
        except EcritureDejaDecidee as deja:
            raise HTTPException(status_code=409, detail=carte_de(deja.ecriture)) from None
        ecriture = decision.ecriture
        assert ecriture.conversation_id is not None
        carte = carte_de(ecriture)
        # Requête et réponse Moduléo ; jamais la clé ni le SecurityCode,
        # qui restent dans les en-têtes de TransportHttp.
        enregistrer_echange_local(
            db,
            identifiant_compte=identifiant_compte,
            conversation_id=ecriture.conversation_id,
            piece_jointe_id=None,
            type_appel="confirmation:ecrire_moduleo",
            requete_payload={
                "ecriture_id": ecriture.id,
                "decision": requete.decision,
                "methode": ecriture.methode,
                "route": ecriture.route,
                "parametres": ecriture.parametres,
                "corps": ecriture.corps,
            },
            reponse_payload={
                "statut": ecriture.statut,
                "reponse_moduleo": decision.reponse_moduleo,
                "erreur": decision.detail,
                "message": carte["message"],
            },
        )
        db.commit()
        return CarteEcriture.model_validate(carte)
    finally:
        verrou.release()
