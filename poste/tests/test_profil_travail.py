from datetime import datetime, timezone

import httpx

from poste.vm_centrale_client import JetonInvalideError, ProfilTravail


def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def test_consulter_le_profil_de_travail_avec_session_active(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, identifiant="j.dupont")
    date_maj = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.profil_travail_retourne(
        ProfilTravail(contenu="Aime les tableaux de suivi", date_derniere_maj=date_maj)
    )

    reponse = client.get("/profil-travail")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "contenu": "Aime les tableaux de suivi",
        "date_derniere_maj": "2026-09-10T12:00:00Z",
    }


def test_consulter_le_profil_de_travail_interroge_toujours_le_compte_de_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice, identifiant="j.dupont")
    vm_centrale_client_factice.profil_travail_retourne(ProfilTravail(contenu="", date_derniere_maj=None))

    client.get("/profil-travail")

    assert vm_centrale_client_factice._identifiants_profil_travail == ["j.dupont"]
    assert vm_centrale_client_factice._jetons_profil_travail == ["jeton-factice"]


def test_consulter_le_profil_de_travail_jamais_calcule_renvoie_un_contenu_vide(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.profil_travail_retourne(ProfilTravail(contenu="", date_derniere_maj=None))

    reponse = client.get("/profil-travail")

    assert reponse.status_code == 200
    assert reponse.json() == {"contenu": "", "date_derniere_maj": None}


def test_consulter_le_profil_de_travail_sans_session_active_est_refuse(client):
    reponse = client.get("/profil-travail")

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_consulter_le_profil_de_travail_vm_indisponible_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.profil_travail_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.get("/profil-travail")

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_consulter_le_profil_de_travail_jeton_invalide_ferme_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.profil_travail_echoue(JetonInvalideError())

    reponse_profil = client.get("/profil-travail")
    reponse_compte = client.get("/compte")

    assert reponse_profil.status_code == 401
    assert reponse_compte.status_code == 401


def test_le_profil_de_travail_ne_propose_aucune_action_de_modification(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse_patch = client.patch("/profil-travail", json={"contenu": "x"})
    reponse_delete = client.delete("/profil-travail")

    assert reponse_patch.status_code == 405
    assert reponse_delete.status_code == 405
