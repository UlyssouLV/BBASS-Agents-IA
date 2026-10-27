import httpx

from poste.vm_centrale_client import AccesAdminRequisError, JetonInvalideError, RefusModuleoError


def _connecter(client, vm_centrale_client_factice, est_admin=True):
    vm_centrale_client_factice.accepter(est_admin=est_admin)
    client.post("/connexion", json={"identifiant": "a.martin", "mot_de_passe": "x"})


# Administration Moduléo du Panel (spec 1.5.3, #213) : le poste relaie à la
# VM centrale, qui seule garde les droits admin et le catalogue.


def test_les_groupes_sont_relayes_avec_le_jeton_de_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    groupes = [{"id": 1, "application": "cogeo", "nom": "Admin"}]
    vm_centrale_client_factice.moduleo_repond(groupes)

    reponse = client.get("/moduleo/groupes")

    assert reponse.status_code == 200
    assert reponse.json() == groupes
    assert vm_centrale_client_factice.appels_moduleo == [("jeton-factice", "GET", "groupes", None)]


def test_sans_session_active_est_refuse_sans_appeler_la_vm(client, vm_centrale_client_factice):
    reponse = client.get("/moduleo/groupes")

    assert reponse.status_code == 401
    assert vm_centrale_client_factice.appels_moduleo == []


def test_une_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.moduleo_echoue(AccesAdminRequisError())

    reponse = client.get("/moduleo/groupes")

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_un_jeton_revoque_renvoie_401_et_efface_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.moduleo_echoue(JetonInvalideError())

    assert client.get("/moduleo/groupes").status_code == 401
    assert client.get("/compte").status_code == 401


def test_une_vm_centrale_injoignable_renvoie_une_erreur_propre(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.moduleo_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.get("/moduleo/groupes")

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_la_suppression_d_un_groupe_rattache_relaie_le_refus_de_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    refus = "Ce groupe est encore rattaché à des comptes : n.durand"
    vm_centrale_client_factice.moduleo_echoue(RefusModuleoError(409, refus))

    reponse = client.delete("/moduleo/groupes/3")

    assert reponse.status_code == 409
    assert reponse.json()["detail"] == refus
    assert vm_centrale_client_factice.appels_moduleo == [("jeton-factice", "DELETE", "groupes/3", None)]


def test_un_rattachement_relaie_seulement_les_champs_envoyes(client, vm_centrale_client_factice):
    # Champ absent : inchangé côté VM ; null : retiré. Le relais ne doit pas
    # confondre les deux.
    _connecter(client, vm_centrale_client_factice)
    rattachement = {"identifiant": "n.durand", "groupe_cogeo_id": None, "groupe_planning_id": 2, "id_utilisateur_moduleo": 31}
    vm_centrale_client_factice.moduleo_repond(rattachement)

    reponse = client.patch("/moduleo/rattachements/n.durand", json={"groupe_cogeo_id": None})

    assert reponse.status_code == 200
    assert reponse.json() == rattachement
    assert vm_centrale_client_factice.appels_moduleo == [
        ("jeton-factice", "PATCH", "rattachements/n.durand", {"groupe_cogeo_id": None})
    ]


def test_les_droits_d_un_groupe_sont_relayes_avec_leurs_conditions(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    droits = [{"chemin": "Tâches › Créer une tâche", "conditions": {"Avec conditions sur le créateur": {}}}]
    vm_centrale_client_factice.moduleo_repond(droits)

    reponse = client.put("/moduleo/groupes/4/droits", json=droits)

    assert reponse.status_code == 200
    assert reponse.json() == droits
    assert vm_centrale_client_factice.appels_moduleo == [("jeton-factice", "PUT", "groupes/4/droits", droits)]


def test_la_creation_d_un_groupe_renvoie_201(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.moduleo_repond({"id": 5, "application": "planning", "nom": "Prod"})

    reponse = client.post("/moduleo/groupes", json={"application": "planning", "nom": "Prod"})

    assert reponse.status_code == 201
    assert reponse.json()["id"] == 5


def test_aucune_route_n_edite_le_catalogue_des_cases(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponses = [
        client.post("/moduleo/catalogue", json={}),
        client.put("/moduleo/catalogue", json={}),
        client.delete("/moduleo/catalogue"),
    ]

    assert [r.status_code for r in reponses] == [405, 405, 405]
    assert vm_centrale_client_factice.appels_moduleo == []
