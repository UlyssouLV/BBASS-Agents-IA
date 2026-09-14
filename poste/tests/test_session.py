def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def test_chat_reste_accessible_sans_re_authentification(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.appels.clear()

    premier_acces = client.get("/compte")
    second_acces = client.get("/compte")

    assert premier_acces.status_code == 200
    assert second_acces.status_code == 200
    assert vm_centrale_client_factice.appels == []


def test_compte_connecte_affiche_l_identifiant_sans_agence_ni_pole(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, identifiant="j.dupont")

    reponse = client.get("/compte")

    assert reponse.status_code == 200
    assert reponse.json() == {"identifiant": "j.dupont", "prenom": "Jean", "nom": "Dupont"}


def test_deconnexion_efface_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse_deconnexion = client.post("/deconnexion")
    reponse_compte = client.get("/compte")

    assert reponse_deconnexion.status_code == 204
    assert reponse_compte.status_code == 401


def test_deconnexion_sans_session_active_ne_plante_pas(client):
    reponse = client.post("/deconnexion")

    assert reponse.status_code == 204


def test_acces_au_compte_sans_connexion_prealable_echoue(client):
    reponse = client.get("/compte")

    assert reponse.status_code == 401
