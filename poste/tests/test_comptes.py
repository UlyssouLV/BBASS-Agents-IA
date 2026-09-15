import httpx

from poste.vm_centrale_client import (
    AccesAdminRequisError,
    CompteAdmin,
    CompteCree,
    IdentifiantDejaUtiliseError,
    JetonInvalideError,
)


def _connecter(client, vm_centrale_client_factice, est_admin=True):
    vm_centrale_client_factice.accepter(est_admin=est_admin)
    client.post("/connexion", json={"identifiant": "a.martin", "mot_de_passe": "x"})


def _compte_admin(**overrides) -> CompteAdmin:
    base = dict(
        identifiant="j.dupont",
        prenom="Jean",
        nom="Dupont",
        email=None,
        agence="Castries",
        poles=["Foncier"],
        est_admin=False,
        doit_changer_mot_de_passe=True,
    )
    base.update(overrides)
    return CompteAdmin(**base)


# --- GET /comptes ------------------------------------------------------------


def test_liste_avec_session_admin_retourne_les_comptes(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.liste_comptes_retourne(
        [_compte_admin(identifiant="j.dupont"), _compte_admin(identifiant="p.leroy")]
    )

    reponse = client.get("/comptes")

    assert reponse.status_code == 200
    identifiants = {compte["identifiant"] for compte in reponse.json()}
    assert identifiants == {"j.dupont", "p.leroy"}


def test_liste_transmet_le_jeton_de_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.liste_comptes_retourne([])

    client.get("/comptes")

    assert vm_centrale_client_factice._jetons_liste_comptes == ["jeton-factice"]


def test_liste_sans_session_active_est_refusee(client):
    reponse = client.get("/comptes")

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_liste_avec_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.liste_comptes_echoue(AccesAdminRequisError())

    reponse = client.get("/comptes")

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_liste_avec_jeton_revoque_renvoie_401_et_efface_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.liste_comptes_echoue(JetonInvalideError())

    reponse_liste = client.get("/comptes")
    reponse_compte = client.get("/compte")

    assert reponse_liste.status_code == 401
    assert reponse_compte.status_code == 401


def test_liste_avec_vm_centrale_injoignable_retourne_une_erreur_propre(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.liste_comptes_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.get("/comptes")

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


# --- POST /comptes -----------------------------------------------------------


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


def test_creation_avec_session_admin_reussit_et_renvoie_le_mot_de_passe_genere(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_compte_reussit(
        CompteCree(
            identifiant="n.durand",
            prenom="Nadia",
            nom="Durand",
            email=None,
            agence="Castries",
            poles=["Foncier"],
            est_admin=False,
            doit_changer_mot_de_passe=True,
            mot_de_passe="Xk9#mPz2Qw",
        )
    )

    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["identifiant"] == "n.durand"
    assert corps["mot_de_passe"] == "Xk9#mPz2Qw"


def test_creation_transmet_la_requete_et_le_jeton(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_compte_reussit(
        CompteCree(
            identifiant="n.durand",
            prenom="Nadia",
            nom="Durand",
            email="n.durand@bbass.fr",
            agence="Castries",
            poles=["Foncier", "Urbanisme"],
            est_admin=False,
            doit_changer_mot_de_passe=True,
            mot_de_passe="Xk9#mPz2Qw",
        )
    )

    client.post(
        "/comptes", json=_requete_creation(poles=["Foncier", "Urbanisme"], email="n.durand@bbass.fr")
    )

    assert vm_centrale_client_factice._jetons_creation_compte == ["jeton-factice"]
    assert vm_centrale_client_factice._requetes_creation_compte == [
        {
            "identifiant": "n.durand",
            "prenom": "Nadia",
            "nom": "Durand",
            "email": "n.durand@bbass.fr",
            "agence": "Castries",
            "poles": ["Foncier", "Urbanisme"],
        }
    ]


def test_creation_sans_session_active_est_refusee(client, vm_centrale_client_factice):
    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 401
    assert vm_centrale_client_factice._requetes_creation_compte == []


def test_creation_avec_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.creation_compte_echoue(AccesAdminRequisError())

    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_creation_avec_identifiant_deja_utilise_renvoie_409(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_compte_echoue(IdentifiantDejaUtiliseError())

    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 409
    assert reponse.json()["detail"]


def test_creation_sans_au_moins_un_pole_est_rejetee_sans_appeler_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/comptes", json=_requete_creation(poles=[]))

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_creation_compte == []


def test_creation_avec_vm_centrale_injoignable_retourne_une_erreur_propre(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_compte_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/comptes", json=_requete_creation())

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


# --- Visibilité de l'onglet dans le HTML/JS servi -----------------------------


def test_front_end_porte_le_balisage_et_la_logique_de_l_onglet_comptes(client, vm_centrale_client_factice):
    # Aucun rendu côté serveur (fichiers statiques identiques pour tout le
    # monde) : la visibilité de l'onglet dépend de la logique JS exécutée
    # dans le navigateur à partir de compte.est_admin, qu'on ne peut pas
    # exécuter ici. On vérifie donc (a) que le bouton est masqué par défaut
    # dans le HTML servi (un compte non-admin ne le voit jamais si rien ne
    # vient lever ce hidden) et (b) l'expression exacte qui le démasque
    # uniquement quand compte.est_admin est vrai, pas une simple présence du
    # nom du champ qui laisserait passer une condition inversée ou fautive.
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="onglet-bouton-comptes" hidden' in html
    assert 'id="onglet-comptes" hidden' in html
    assert "ongletBoutonComptes.hidden = !compte.est_admin" in js
