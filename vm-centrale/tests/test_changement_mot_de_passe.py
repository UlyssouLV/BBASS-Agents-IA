def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def test_changement_reussi_met_a_jour_le_hash_et_leve_le_flag(client, seed_compte, db_session):
    compte = seed_compte(
        "j.dupont", "mot-de-passe-aleatoire", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", doit_changer_mot_de_passe=True,
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse = client.post(
        "/auth/mot-de-passe",
        json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"},
        headers=_autorisation(jeton),
    )

    assert reponse.status_code == 204
    db_session.refresh(compte)
    assert compte.doit_changer_mot_de_passe is False

    reponse_ancien_mot_de_passe = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    assert reponse_ancien_mot_de_passe.status_code == 401

    reponse_nouveau_mot_de_passe = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "un-nouveau-mot-de-passe-choisi"}
    )
    assert reponse_nouveau_mot_de_passe.status_code == 200


def test_changement_sans_jeton_echoue(client):
    reponse = client.post(
        "/auth/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"}
    )

    assert reponse.status_code == 401


def test_changement_avec_jeton_invalide_echoue(client):
    reponse = client.post(
        "/auth/mot-de-passe",
        json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"},
        headers=_autorisation("jeton-inconnu"),
    )

    assert reponse.status_code == 401


def test_changement_avec_jeton_revoque_echoue(client, jeton_valide):
    client.delete("/auth/jeton", headers=_autorisation(jeton_valide))

    reponse = client.post(
        "/auth/mot-de-passe",
        json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 401


def test_nouveau_mot_de_passe_vide_est_rejete(client, seed_compte):
    seed_compte(
        "j.dupont", "mot-de-passe-aleatoire", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", doit_changer_mot_de_passe=True,
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse = client.post(
        "/auth/mot-de-passe", json={"nouveau_mot_de_passe": ""}, headers=_autorisation(jeton)
    )

    assert reponse.status_code == 422


def test_changement_ne_revoque_pas_le_jeton_utilise(client, seed_compte):
    seed_compte(
        "j.dupont", "mot-de-passe-aleatoire", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", doit_changer_mot_de_passe=True,
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse_changement = client.post(
        "/auth/mot-de-passe",
        json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"},
        headers=_autorisation(jeton),
    )
    assert reponse_changement.status_code == 204

    reponse_verifier = client.get("/auth/verifier", headers=_autorisation(jeton))
    assert reponse_verifier.status_code == 200


def test_changement_hors_du_flux_impose_est_refuse(client, seed_compte, db_session):
    compte = seed_compte(
        "j.dupont", "mot-de-passe-aleatoire", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", doit_changer_mot_de_passe=False,
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse = client.post(
        "/auth/mot-de-passe",
        json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe-choisi"},
        headers=_autorisation(jeton),
    )

    assert reponse.status_code == 403
    db_session.refresh(compte)
    assert compte.doit_changer_mot_de_passe is False

    reponse_ancien_mot_de_passe = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "mot-de-passe-aleatoire"}
    )
    assert reponse_ancien_mot_de_passe.status_code == 200
