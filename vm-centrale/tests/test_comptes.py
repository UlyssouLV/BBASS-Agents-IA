def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _jeton_admin(client, seed_compte, identifiant: str = "a.martin") -> str:
    seed_compte(
        identifiant, "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Alice", nom="Martin", est_admin=True,
    )
    reponse = client.post(
        "/auth", json={"identifiant": identifiant, "mot_de_passe": "correcthorsebatterystaple"}
    )
    return reponse.json()["jeton"]


def _jeton_non_admin(client, seed_compte, identifiant: str = "j.dupont") -> str:
    seed_compte(
        identifiant, "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont", est_admin=False,
    )
    reponse = client.post(
        "/auth", json={"identifiant": identifiant, "mot_de_passe": "correcthorsebatterystaple"}
    )
    return reponse.json()["jeton"]


def _requete_creation(**overrides) -> dict:
    base = {
        "identifiant": "n.durand",
        "prenom": "Nadia",
        "nom": "Durand",
        "agence": "Castries",
        "poles": ["Foncier"],
    }
    base.update(overrides)
    return base


def _requete_modification(**overrides) -> dict:
    base = {
        "prenom": "Nadia",
        "nom": "Durand",
        "email": "n.durand@bbass.fr",
        "agence": "Castries",
        "poles": ["Foncier"],
    }
    base.update(overrides)
    return base


# --- POST /comptes ---------------------------------------------------------


def test_creation_reussit_avec_jeton_admin_et_retourne_le_compte_cree(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(poles=["Foncier", "Urbanisme"]), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["identifiant"] == "n.durand"
    assert corps["prenom"] == "Nadia"
    assert corps["nom"] == "Durand"
    assert corps["agence"] == "Castries"
    assert corps["poles"] == ["Foncier", "Urbanisme"]
    assert corps["email"] is None
    assert corps["est_admin"] is False
    assert corps["doit_changer_mot_de_passe"] is True


def test_creation_genere_un_mot_de_passe_aleatoire_qui_permet_de_se_connecter(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse_creation = client.post(
        "/comptes", json=_requete_creation(), headers=_autorisation(jeton)
    )
    mot_de_passe_genere = reponse_creation.json()["mot_de_passe"]
    assert mot_de_passe_genere

    reponse_auth = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": mot_de_passe_genere}
    )
    assert reponse_auth.status_code == 200
    assert reponse_auth.json()["doit_changer_mot_de_passe"] is True


def test_creation_genere_un_mot_de_passe_different_a_chaque_compte(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    premiere = client.post(
        "/comptes", json=_requete_creation(identifiant="n.durand"), headers=_autorisation(jeton)
    )
    seconde = client.post(
        "/comptes", json=_requete_creation(identifiant="p.leroy"), headers=_autorisation(jeton)
    )

    assert premiere.json()["mot_de_passe"] != seconde.json()["mot_de_passe"]


def test_creation_accepte_un_email_optionnel(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(email="n.durand@bbass.fr"), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 201
    assert reponse.json()["email"] == "n.durand@bbass.fr"


def test_creation_echoue_avec_un_pole_inconnu(client, seed_compte, db_session):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(poles=["Comptabilité"]), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 422
    from vm_centrale.models import Compte

    assert db_session.query(Compte).filter(Compte.identifiant == "n.durand").first() is None


def test_creation_echoue_avec_un_pole_en_double(client, seed_compte, db_session):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(poles=["Foncier", "Foncier"]), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 422
    from vm_centrale.models import Compte

    assert db_session.query(Compte).filter(Compte.identifiant == "n.durand").first() is None


def test_creation_echoue_sans_au_moins_un_pole(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(poles=[]), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 422


def test_creation_echoue_avec_un_identifiant_deja_utilise(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "un-autre-mot-de-passe", agence="Castries", poles=["Foncier"],
        prenom="Autre", nom="Compte",
    )

    reponse = client.post(
        "/comptes", json=_requete_creation(), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 409


def test_creation_echoue_sans_jeton(client):
    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 401


def test_creation_echoue_avec_jeton_invalide(client):
    reponse = client.post(
        "/comptes", json=_requete_creation(), headers=_autorisation("jeton-inconnu")
    )

    assert reponse.status_code == 401


def test_creation_echoue_avec_jeton_d_un_compte_non_admin(client, seed_compte, db_session):
    jeton = _jeton_non_admin(client, seed_compte)

    reponse = client.post(
        "/comptes", json=_requete_creation(), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 403
    from vm_centrale.models import Compte

    assert db_session.query(Compte).filter(Compte.identifiant == "n.durand").first() is None


# --- GET /comptes ------------------------------------------------------------


def test_liste_reussit_avec_jeton_admin_et_retourne_tous_les_comptes(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte, identifiant="a.martin")
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["DAO"],
        prenom="Jean", nom="Dupont",
    )

    reponse = client.get("/comptes", headers=_autorisation(jeton))

    assert reponse.status_code == 200
    identifiants = {compte["identifiant"] for compte in reponse.json()}
    assert identifiants == {"a.martin", "j.dupont"}


def test_liste_ne_retourne_pas_le_mot_de_passe(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.get("/comptes", headers=_autorisation(jeton))

    assert reponse.status_code == 200
    for compte in reponse.json():
        assert "mot_de_passe" not in compte
        assert "mot_de_passe_hash" not in compte


def test_liste_echoue_sans_jeton(client):
    reponse = client.get("/comptes")

    assert reponse.status_code == 401


def test_liste_echoue_avec_jeton_d_un_compte_non_admin(client, seed_compte):
    jeton = _jeton_non_admin(client, seed_compte)

    reponse = client.get("/comptes", headers=_autorisation(jeton))

    assert reponse.status_code == 403


# --- PATCH /comptes/{identifiant} --------------------------------------------


def test_modification_reussit_avec_jeton_admin_et_retourne_le_compte_modifie(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.patch(
        "/comptes/n.durand",
        json=_requete_modification(
            prenom="Nadège", nom="Dupuis", email="n.dupuis@bbass.fr",
            agence="Perpignan", poles=["Urbanisme", "DAO"],
        ),
        headers=_autorisation(jeton),
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["identifiant"] == "n.durand"
    assert corps["prenom"] == "Nadège"
    assert corps["nom"] == "Dupuis"
    assert corps["email"] == "n.dupuis@bbass.fr"
    assert corps["agence"] == "Perpignan"
    assert corps["poles"] == ["DAO", "Urbanisme"]


def test_modification_peut_retirer_l_email_du_compte(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand", email="n.durand@bbass.fr",
    )

    reponse = client.patch(
        "/comptes/n.durand",
        json=_requete_modification(email=None),
        headers=_autorisation(jeton),
    )

    assert reponse.status_code == 200
    assert reponse.json()["email"] is None


def test_modification_ne_change_ni_l_identifiant_ni_le_statut_admin_ni_le_mot_de_passe(
    client, seed_compte
):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.patch(
        "/comptes/n.durand", json=_requete_modification(), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 200
    assert reponse.json()["identifiant"] == "n.durand"
    assert reponse.json()["est_admin"] is False
    reponse_auth = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": "correcthorsebatterystaple"}
    )
    assert reponse_auth.status_code == 200


def test_modification_echoue_avec_un_pole_inconnu(client, seed_compte, db_session):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.patch(
        "/comptes/n.durand",
        json=_requete_modification(poles=["Comptabilité"]),
        headers=_autorisation(jeton),
    )

    assert reponse.status_code == 422
    from vm_centrale.models import Compte

    compte = db_session.query(Compte).filter(Compte.identifiant == "n.durand").first()
    assert [pole.pole for pole in compte.poles] == ["Foncier"]


def test_modification_echoue_avec_un_identifiant_inconnu(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.patch(
        "/comptes/inconnu", json=_requete_modification(), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 404


def test_modification_echoue_sans_jeton(client, seed_compte):
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.patch("/comptes/n.durand", json=_requete_modification())

    assert reponse.status_code == 401


def test_modification_echoue_avec_jeton_d_un_compte_non_admin(client, seed_compte):
    jeton = _jeton_non_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.patch(
        "/comptes/n.durand", json=_requete_modification(), headers=_autorisation(jeton)
    )

    assert reponse.status_code == 403


# --- POST /comptes/{identifiant}/reinitialiser-mot-de-passe ------------------


def test_reinitialisation_reussit_avec_jeton_admin_et_genere_un_nouveau_mot_de_passe(
    client, seed_compte
):
    jeton = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "ancien-mot-de-passe", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.post(
        "/comptes/n.durand/reinitialiser-mot-de-passe", headers=_autorisation(jeton)
    )

    assert reponse.status_code == 200
    nouveau_mot_de_passe = reponse.json()["mot_de_passe"]
    assert nouveau_mot_de_passe

    reponse_auth = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": nouveau_mot_de_passe}
    )
    assert reponse_auth.status_code == 200
    assert reponse_auth.json()["doit_changer_mot_de_passe"] is True

    reponse_ancien_mot_de_passe = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": "ancien-mot-de-passe"}
    )
    assert reponse_ancien_mot_de_passe.status_code == 401


def test_reinitialisation_ne_revoque_pas_les_jetons_actifs_du_compte(
    client, seed_compte, mistral_client_factice
):
    jeton_admin = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "ancien-mot-de-passe", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": "ancien-mot-de-passe"}
    )
    ancien_jeton = reponse_auth.json()["jeton"]
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?")

    reponse = client.post(
        "/comptes/n.durand/reinitialiser-mot-de-passe", headers=_autorisation(jeton_admin)
    )
    assert reponse.status_code == 200

    reponse_relais = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(ancien_jeton)
    )
    assert reponse_relais.status_code == 200


def test_reinitialisation_echoue_avec_un_identifiant_inconnu(client, seed_compte):
    jeton = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes/inconnu/reinitialiser-mot-de-passe", headers=_autorisation(jeton)
    )

    assert reponse.status_code == 404


def test_reinitialisation_echoue_sans_jeton(client, seed_compte):
    seed_compte(
        "n.durand", "ancien-mot-de-passe", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert reponse.status_code == 401


def test_reinitialisation_echoue_avec_jeton_d_un_compte_non_admin(client, seed_compte):
    jeton = _jeton_non_admin(client, seed_compte)
    seed_compte(
        "n.durand", "ancien-mot-de-passe", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.post(
        "/comptes/n.durand/reinitialiser-mot-de-passe", headers=_autorisation(jeton)
    )

    assert reponse.status_code == 403


# --- POST /comptes/{identifiant}/deconnexion-forcee ---------------------------


def test_deconnexion_forcee_reussit_et_revoque_tous_les_jetons_actifs_du_compte_vise(
    client, seed_compte, jeton_store
):
    jeton_admin = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )
    jeton_1 = jeton_store.emettre("n.durand")
    jeton_2 = jeton_store.emettre("n.durand")

    reponse = client.post(
        "/comptes/n.durand/deconnexion-forcee", headers=_autorisation(jeton_admin)
    )

    assert reponse.status_code == 204
    assert client.get("/auth/verifier", headers=_autorisation(jeton_1)).status_code == 401
    assert client.get("/auth/verifier", headers=_autorisation(jeton_2)).status_code == 401


def test_deconnexion_forcee_ne_revoque_pas_les_jetons_des_autres_comptes(
    client, seed_compte, jeton_store
):
    jeton_admin = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )
    jeton_autre_compte = jeton_store.emettre("p.leroy")

    client.post("/comptes/n.durand/deconnexion-forcee", headers=_autorisation(jeton_admin))

    assert (
        client.get("/auth/verifier", headers=_autorisation(jeton_autre_compte)).status_code
        == 200
    )


def test_deconnexion_forcee_rejette_le_relais_avec_l_ancien_jeton(
    client, seed_compte, mistral_client_factice
):
    jeton_admin = _jeton_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )
    reponse_auth = client.post(
        "/auth", json={"identifiant": "n.durand", "mot_de_passe": "correcthorsebatterystaple"}
    )
    jeton_compte = reponse_auth.json()["jeton"]
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    client.post("/comptes/n.durand/deconnexion-forcee", headers=_autorisation(jeton_admin))

    reponse_relais = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton_compte)
    )

    assert reponse_relais.status_code == 401
    assert mistral_client_factice.messages_recus == []


def test_deconnexion_forcee_echoue_avec_un_identifiant_inconnu(client, seed_compte):
    jeton_admin = _jeton_admin(client, seed_compte)

    reponse = client.post(
        "/comptes/inconnu/deconnexion-forcee", headers=_autorisation(jeton_admin)
    )

    assert reponse.status_code == 404


def test_deconnexion_forcee_echoue_sans_jeton(client, seed_compte):
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.post("/comptes/n.durand/deconnexion-forcee")

    assert reponse.status_code == 401


def test_deconnexion_forcee_echoue_avec_jeton_d_un_compte_non_admin(client, seed_compte):
    jeton = _jeton_non_admin(client, seed_compte)
    seed_compte(
        "n.durand", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Nadia", nom="Durand",
    )

    reponse = client.post(
        "/comptes/n.durand/deconnexion-forcee", headers=_autorisation(jeton)
    )

    assert reponse.status_code == 403
