def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def test_verifier_avec_jeton_valide_retourne_l_identifiant(client, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse = client.get("/auth/verifier", headers=_autorisation(jeton))

    assert reponse.status_code == 200
    assert reponse.json() == {"identifiant": "j.dupont", "est_admin": False}


def test_verifier_retourne_est_admin_a_jour_meme_change_apres_l_emission_du_jeton(
    client, seed_compte, db_session
):
    compte = seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", est_admin=False,
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )
    jeton = reponse_auth.json()["jeton"]

    compte.est_admin = True
    db_session.commit()

    reponse = client.get("/auth/verifier", headers=_autorisation(jeton))

    assert reponse.status_code == 200
    assert reponse.json() == {"identifiant": "j.dupont", "est_admin": True}


def test_verifier_avec_jeton_pour_un_compte_introuvable_retourne_est_admin_false(
    client, jeton_valide
):
    reponse = client.get("/auth/verifier", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    assert reponse.json() == {"identifiant": "j.dupont", "est_admin": False}


def test_verifier_sans_jeton_echoue(client):
    reponse = client.get("/auth/verifier")

    assert reponse.status_code == 401


def test_verifier_avec_jeton_invalide_echoue(client):
    reponse = client.get("/auth/verifier", headers=_autorisation("jeton-inconnu"))

    assert reponse.status_code == 401


def test_deconnexion_du_jeton_courant_l_invalide(client, jeton_valide):
    reponse_deconnexion = client.delete("/auth/jeton", headers=_autorisation(jeton_valide))
    reponse_verifier = client.get("/auth/verifier", headers=_autorisation(jeton_valide))

    assert reponse_deconnexion.status_code == 204
    assert reponse_verifier.status_code == 401


def test_deconnexion_ne_revoque_pas_les_jetons_des_autres_comptes(client, jeton_store):
    jeton_a_deconnecter = jeton_store.emettre("j.dupont")
    jeton_autre_compte = jeton_store.emettre("a.martin")

    client.delete("/auth/jeton", headers=_autorisation(jeton_a_deconnecter))

    reponse = client.get("/auth/verifier", headers=_autorisation(jeton_autre_compte))
    assert reponse.status_code == 200


def test_deconnexion_sans_jeton_ne_plante_pas(client):
    reponse = client.delete("/auth/jeton")

    assert reponse.status_code == 204


def test_jeton_revoque_est_rejete(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")
    client.delete("/auth/jeton", headers=_autorisation(jeton_valide))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []


def test_revocation_forcee_invalide_tous_les_jetons_du_compte_vise(
    client, monkeypatch, jeton_store
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    jeton_1 = jeton_store.emettre("j.dupont")
    jeton_2 = jeton_store.emettre("j.dupont")
    jeton_autre_compte = jeton_store.emettre("a.martin")

    reponse = client.delete(
        "/auth/jeton/j.dupont", headers={"X-Admin-Key": "cle-admin-de-test"}
    )

    assert reponse.status_code == 204
    assert client.get("/auth/verifier", headers=_autorisation(jeton_1)).status_code == 401
    assert client.get("/auth/verifier", headers=_autorisation(jeton_2)).status_code == 401
    assert (
        client.get("/auth/verifier", headers=_autorisation(jeton_autre_compte)).status_code
        == 200
    )


def test_revocation_forcee_sans_cle_admin_echoue(client, monkeypatch, jeton_valide):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.delete("/auth/jeton/j.dupont")

    assert reponse.status_code == 401
    assert client.get("/auth/verifier", headers=_autorisation(jeton_valide)).status_code == 200


def test_revocation_forcee_avec_une_mauvaise_cle_echoue(client, monkeypatch, jeton_valide):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.delete(
        "/auth/jeton/j.dupont", headers={"X-Admin-Key": "mauvaise-cle"}
    )

    assert reponse.status_code == 401
    assert client.get("/auth/verifier", headers=_autorisation(jeton_valide)).status_code == 200


def test_revocation_forcee_sans_cle_admin_configuree_echoue(client, monkeypatch, jeton_valide):
    monkeypatch.delenv("VM_ADMIN_KEY", raising=False)

    reponse = client.delete(
        "/auth/jeton/j.dupont", headers={"X-Admin-Key": "peu-importe"}
    )

    assert reponse.status_code == 401


def test_revocation_forcee_avec_une_cle_admin_vide_configuree_echoue_meme_avec_cle_vide_fournie(
    client, monkeypatch, jeton_valide
):
    # VM_ADMIN_KEY="" (valeur laissée vide dans .env) doit être traité comme
    # non configuré, sinon un appelant envoyant une clé vide serait accepté.
    monkeypatch.setenv("VM_ADMIN_KEY", "")

    reponse = client.delete(
        "/auth/jeton/j.dupont", headers={"X-Admin-Key": ""}
    )

    assert reponse.status_code == 401
    assert client.get("/auth/verifier", headers=_autorisation(jeton_valide)).status_code == 200
