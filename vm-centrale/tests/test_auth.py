def test_compte_valide_reussit_et_retourne_agence_et_pole(client, seed_compte):
    seed_compte("j.dupont", "correcthorsebatterystaple", agence="Castries", pole="Foncier")

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"agence": "Castries", "pole": "Foncier"}


def test_identifiant_inconnu_echoue(client, seed_compte):
    seed_compte("j.dupont", "correcthorsebatterystaple", agence="Castries", pole="Foncier")

    reponse = client.post(
        "/auth", json={"identifiant": "inconnu", "mot_de_passe": "correcthorsebatterystaple"}
    )

    assert reponse.status_code == 401
    assert "agence" not in reponse.text
    assert "pole" not in reponse.text


def test_mot_de_passe_incorrect_echoue(client, seed_compte):
    seed_compte("j.dupont", "correcthorsebatterystaple", agence="Castries", pole="Foncier")

    reponse = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais-mot-de-passe"}
    )

    assert reponse.status_code == 401
    assert "agence" not in reponse.text
    assert "pole" not in reponse.text


def test_echec_ne_revele_pas_quelle_partie_est_fausse(client, seed_compte):
    seed_compte("j.dupont", "correcthorsebatterystaple", agence="Castries", pole="Foncier")

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
