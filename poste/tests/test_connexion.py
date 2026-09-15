import httpx


def test_connexion_valide_reussit_et_ouvre_la_session(client, vm_centrale_client_factice):
    vm_centrale_client_factice.accepter(prenom="Jean", nom="Dupont")

    reponse = client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"identifiant": "j.dupont", "prenom": "Jean", "nom": "Dupont"}
    assert vm_centrale_client_factice.appels == [("j.dupont", "correcthorsebatterystaple")]


def test_connexion_invalide_echoue_avec_un_message_clair(client, vm_centrale_client_factice):
    vm_centrale_client_factice.rejeter()

    reponse = client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais"})

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_connexion_invalide_n_ouvre_pas_de_session(client, vm_centrale_client_factice):
    vm_centrale_client_factice.rejeter()
    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais"})

    reponse = client.get("/compte")

    assert reponse.status_code == 401


def test_vm_centrale_injoignable_retourne_une_erreur_propre_pas_un_plantage(
    client, vm_centrale_client_factice
):
    vm_centrale_client_factice.echouer(httpx.ConnectError("connexion refusée"))

    reponse = client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_vm_centrale_injoignable_n_ouvre_pas_de_session(client, vm_centrale_client_factice):
    vm_centrale_client_factice.echouer(httpx.ConnectError("connexion refusée"))
    client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    reponse = client.get("/compte")

    assert reponse.status_code == 401


def test_reponse_de_connexion_n_expose_ni_agence_ni_pole(client, vm_centrale_client_factice):
    vm_centrale_client_factice.accepter()

    reponse = client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert "agence" not in reponse.text
    assert "pole" not in reponse.text


def test_connexion_normale_n_expose_aucun_avertissement(client, vm_centrale_client_factice):
    vm_centrale_client_factice.accepter()

    reponse = client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert "avertissement" not in reponse.json()


def test_connexion_signale_un_avertissement_si_la_persistance_est_degradee(
    client, vm_centrale_client_factice, monkeypatch
):
    def set_password_en_echec(service_name, username, password):
        raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.set_password", set_password_en_echec)
    vm_centrale_client_factice.accepter()

    reponse = client.post(
        "/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["avertissement"]
