import httpx

from poste.vm_centrale_client import JetonInvalideError


def _connecter(client, vm_centrale_client_factice, **overrides):
    vm_centrale_client_factice.accepter(**overrides)
    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "x"})


def test_changement_avec_session_active_reussit_et_leve_le_flag(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)

    reponse = client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["doit_changer_mot_de_passe"] is False
    assert corps["identifiant"] == "j.dupont"


def test_changement_transmet_le_jeton_et_le_nouveau_mot_de_passe(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)

    client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})

    assert vm_centrale_client_factice.appels_changement_mot_de_passe == [
        ("jeton-factice", "un-nouveau-mot-de-passe")
    ]


def test_changement_met_a_jour_la_session_pour_les_appels_suivants(client, vm_centrale_client_factice):
    # Le blocage de l'écran de chat côté poste repose sur la valeur de
    # doit_changer_mot_de_passe renvoyée par GET /compte : elle doit refléter
    # le changement réussi sans nécessiter une reconnexion.
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)

    client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})
    reponse_compte = client.get("/compte")

    assert reponse_compte.status_code == 200
    assert reponse_compte.json()["doit_changer_mot_de_passe"] is False


def test_changement_sans_session_active_est_refuse(client, vm_centrale_client_factice):
    reponse = client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})

    assert reponse.status_code == 401
    assert vm_centrale_client_factice.appels_changement_mot_de_passe == []


def test_changement_avec_jeton_revoque_renvoie_401_et_efface_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)
    vm_centrale_client_factice.changement_mot_de_passe_echoue(JetonInvalideError())

    reponse_changement = client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})
    reponse_compte = client.get("/compte")

    assert reponse_changement.status_code == 401
    assert reponse_compte.status_code == 401


def test_changement_avec_vm_centrale_injoignable_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)
    vm_centrale_client_factice.changement_mot_de_passe_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/mot-de-passe", json={"nouveau_mot_de_passe": "un-nouveau-mot-de-passe"})

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_changement_avec_mot_de_passe_vide_est_rejete_sans_appeler_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, doit_changer_mot_de_passe=True)

    reponse = client.post("/mot-de-passe", json={"nouveau_mot_de_passe": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice.appels_changement_mot_de_passe == []
