def test_compte_valide_reussit_et_retourne_agence_et_poles(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["agence"] == "Castries"
    assert corps["poles"] == ["Foncier"]
    assert corps["jeton"]


def test_compte_admin_avec_plusieurs_poles_s_authentifie_et_retourne_ses_champs_tels_quels(
    client, seed_compte
):
    seed_compte(
        "a.martin", "correcthorsebatterystaple", agence="Castries",
        poles=["Foncier", "Urbanisme"], prenom="Alice", nom="Martin",
        email="a.martin@bbass.fr", est_admin=True, doit_changer_mot_de_passe=True,
    )

    reponse = client.post(
        "/auth", json={"identifiant": "a.martin", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["prenom"] == "Alice"
    assert corps["nom"] == "Martin"
    assert corps["agence"] == "Castries"
    assert corps["email"] == "a.martin@bbass.fr"
    assert corps["poles"] == ["Foncier", "Urbanisme"]
    assert corps["est_admin"] is True
    assert corps["doit_changer_mot_de_passe"] is True
    assert corps["jeton"]


def test_compte_sans_email_retourne_email_a_null(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["email"] is None
    assert corps["est_admin"] is False
    assert corps["doit_changer_mot_de_passe"] is False


def test_compte_valide_retourne_prenom_et_nom(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["prenom"] == "Jean"
    assert corps["nom"] == "Dupont"


def test_compte_valide_recoit_un_jeton_different_a_chaque_connexion(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    premiere_reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )
    seconde_reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert premiere_reponse.json()["jeton"] != seconde_reponse.json()["jeton"]


def test_identifiant_inconnu_echoue(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.post(
        "/auth", json={"identifiant": "inconnu", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 401
    assert "agence" not in reponse.text
    assert "poles" not in reponse.text


def test_mot_de_passe_incorrect_echoue(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais-mot-de-passe"}
    )

    assert reponse.status_code == 401
    assert "agence" not in reponse.text
    assert "poles" not in reponse.text


def test_echec_ne_revele_pas_quelle_partie_est_fausse(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )

    reponse_identifiant_inconnu = client.post(
        "/auth", json={"identifiant": "inconnu", "mot_de_passe": "correcthorsebatterystaple"}
    )
    reponse_mot_de_passe_incorrect = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais-mot-de-passe"}
    )

    assert reponse_identifiant_inconnu.status_code == reponse_mot_de_passe_incorrect.status_code
    assert reponse_identifiant_inconnu.json() == reponse_mot_de_passe_incorrect.json()


def test_aucun_endpoint_de_creation_de_compte(client):
    reponse = client.post(
        "/comptes",
        json={
            "identifiant": "nouveau",
            "mot_de_passe": "x",
            "agence": "Castries",
            "pole": "Foncier",
        },
    )

    assert reponse.status_code == 404
