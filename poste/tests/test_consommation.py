from decimal import Decimal

import httpx

from poste.vm_centrale_client import (
    Consommation,
    ConversationConsommation,
    DetailConsommationCategorie,
    JetonInvalideError,
)


def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def _detail(tokens_total=0, pages_traitees=0, cout_usd="0", nombre_requetes=0):
    return DetailConsommationCategorie(
        tokens_total=tokens_total,
        pages_traitees=pages_traitees,
        cout_usd=Decimal(cout_usd),
        nombre_requetes=nombre_requetes,
    )


def test_consulter_la_consommation_avec_session_active(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.consommation_retournee(
        Consommation(
            chat=_detail(tokens_total=1500, cout_usd="0.0023", nombre_requetes=3),
            piece_jointe=_detail(pages_traitees=2, cout_usd="0.008", nombre_requetes=1),
            conversations=[
                ConversationConsommation(
                    id=1,
                    titre="Premier dossier",
                    cout_usd=Decimal("0.0103"),
                    chat=_detail(tokens_total=1500, cout_usd="0.0023", nombre_requetes=3),
                    piece_jointe=_detail(pages_traitees=2, cout_usd="0.008", nombre_requetes=1),
                )
            ],
        )
    )

    reponse = client.get("/consommation")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "chat": {"tokens_total": 1500, "pages_traitees": 0, "cout_usd": "0.0023", "nombre_requetes": 3},
        "piece_jointe": {"tokens_total": 0, "pages_traitees": 2, "cout_usd": "0.008", "nombre_requetes": 1},
        "conversations": [
            {
                "id": 1,
                "titre": "Premier dossier",
                "cout_usd": "0.0103",
                "chat": {"tokens_total": 1500, "pages_traitees": 0, "cout_usd": "0.0023", "nombre_requetes": 3},
                "piece_jointe": {
                    "tokens_total": 0,
                    "pages_traitees": 2,
                    "cout_usd": "0.008",
                    "nombre_requetes": 1,
                },
            }
        ],
    }


def test_consulter_la_consommation_sans_conversation_renvoie_une_liste_vide(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.consommation_retournee(
        Consommation(chat=_detail(), piece_jointe=_detail(), conversations=[])
    )

    reponse = client.get("/consommation")

    assert reponse.status_code == 200
    assert reponse.json()["conversations"] == []


def test_consulter_la_consommation_sans_session_active_est_refuse(client):
    reponse = client.get("/consommation")

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_consulter_la_consommation_vm_indisponible_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.consommation_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.get("/consommation")

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_consulter_la_consommation_jeton_invalide_ferme_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.consommation_echoue(JetonInvalideError())

    reponse_consommation = client.get("/consommation")
    reponse_compte = client.get("/compte")

    assert reponse_consommation.status_code == 401
    assert reponse_compte.status_code == 401


def test_la_consommation_ne_propose_aucune_action_de_modification(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse_patch = client.patch("/consommation", json={})
    reponse_delete = client.delete("/consommation")

    assert reponse_patch.status_code == 405
    assert reponse_delete.status_code == 405
