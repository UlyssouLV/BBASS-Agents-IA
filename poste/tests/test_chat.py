import httpx


def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def test_message_avec_session_active_est_transmis_et_la_reponse_est_retournee(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.repondre("Bonjour, comment puis-je vous aider ?")

    reponse = client.post("/chat", json={"message": "Bonjour"})

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Bonjour, comment puis-je vous aider ?"}
    assert vm_centrale_client_factice.messages_recus == ["Bonjour"]


def test_le_jeton_recu_a_la_connexion_est_transmis_au_relais(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    client.post("/chat", json={"message": "Bonjour"})

    assert vm_centrale_client_factice.jetons_recus == ["jeton-factice"]


def test_message_sans_session_active_est_refuse(client):
    reponse = client.post("/chat", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_relais_injoignable_retourne_une_erreur_propre_pas_un_plantage(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.echouer(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/chat", json={"message": "Bonjour"})

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_apres_deconnexion_le_chat_redevient_inaccessible(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    client.post("/deconnexion")

    reponse = client.post("/chat", json={"message": "Bonjour"})

    assert reponse.status_code == 401


def test_message_vide_est_rejete_sans_appeler_le_relais(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/chat", json={"message": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice.messages_recus == []


def test_message_trop_long_est_rejete_sans_appeler_le_relais(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/chat", json={"message": "x" * 8001})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice.messages_recus == []
