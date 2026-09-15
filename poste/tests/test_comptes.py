import httpx

from poste.vm_centrale_client import (
    AccesAdminRequisError,
    CompteAdmin,
    CompteCree,
    CompteInexistantError,
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


# --- PATCH /comptes/{identifiant} ---------------------------------------------


def _requete_modification(**overrides) -> dict:
    base = {
        "prenom": "Nadège",
        "nom": "Dupuis",
        "email": "n.dupuis@bbass.fr",
        "agence": "Perpignan",
        "poles": ["Urbanisme", "DAO"],
    }
    base.update(overrides)
    return base


def test_modification_avec_session_admin_reussit_et_renvoie_le_compte_modifie(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.modification_compte_reussit(
        _compte_admin(
            identifiant="n.durand",
            prenom="Nadège",
            nom="Dupuis",
            email="n.dupuis@bbass.fr",
            agence="Perpignan",
            poles=["Urbanisme", "DAO"],
        )
    )

    reponse = client.patch("/comptes/n.durand", json=_requete_modification())

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["identifiant"] == "n.durand"
    assert corps["prenom"] == "Nadège"
    assert corps["nom"] == "Dupuis"
    assert corps["email"] == "n.dupuis@bbass.fr"
    assert corps["agence"] == "Perpignan"
    assert corps["poles"] == ["Urbanisme", "DAO"]


def test_modification_transmet_la_requete_et_le_jeton(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.modification_compte_reussit(_compte_admin(identifiant="n.durand"))

    client.patch("/comptes/n.durand", json=_requete_modification())

    assert vm_centrale_client_factice._jetons_modification_compte == ["jeton-factice"]
    assert vm_centrale_client_factice._requetes_modification_compte == [
        {
            "identifiant": "n.durand",
            "prenom": "Nadège",
            "nom": "Dupuis",
            "email": "n.dupuis@bbass.fr",
            "agence": "Perpignan",
            "poles": ["Urbanisme", "DAO"],
        }
    ]


def test_modification_sans_session_active_est_refusee(client, vm_centrale_client_factice):
    reponse = client.patch("/comptes/n.durand", json=_requete_modification())

    assert reponse.status_code == 401
    assert vm_centrale_client_factice._requetes_modification_compte == []


def test_modification_avec_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.modification_compte_echoue(AccesAdminRequisError())

    reponse = client.patch("/comptes/n.durand", json=_requete_modification())

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_modification_avec_identifiant_inconnu_renvoie_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.modification_compte_echoue(CompteInexistantError())

    reponse = client.patch("/comptes/inconnu", json=_requete_modification())

    assert reponse.status_code == 404
    assert reponse.json()["detail"]


def test_modification_sans_au_moins_un_pole_est_rejetee_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.patch("/comptes/n.durand", json=_requete_modification(poles=[]))

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_modification_compte == []


def test_modification_avec_vm_centrale_injoignable_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.modification_compte_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.patch("/comptes/n.durand", json=_requete_modification())

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


# --- POST /comptes/{identifiant}/reinitialiser-mot-de-passe ------------------


def test_reinitialisation_avec_session_admin_reussit_et_renvoie_le_mot_de_passe_genere(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_reussit("Xk9#mPz2Qw")

    reponse = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert reponse.status_code == 200
    assert reponse.json()["mot_de_passe"] == "Xk9#mPz2Qw"


def test_reinitialisation_transmet_le_jeton_et_l_identifiant(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_reussit("Xk9#mPz2Qw")

    client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert vm_centrale_client_factice._jetons_reinitialisation_mot_de_passe == ["jeton-factice"]
    assert vm_centrale_client_factice._identifiants_reinitialisation_mot_de_passe == ["n.durand"]


def test_reinitialisation_sans_session_active_est_refusee(client, vm_centrale_client_factice):
    reponse = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert reponse.status_code == 401
    assert vm_centrale_client_factice._identifiants_reinitialisation_mot_de_passe == []


def test_reinitialisation_avec_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_echoue(AccesAdminRequisError())

    reponse = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_reinitialisation_avec_identifiant_inconnu_renvoie_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_echoue(CompteInexistantError())

    reponse = client.post("/comptes/inconnu/reinitialiser-mot-de-passe")

    assert reponse.status_code == 404
    assert reponse.json()["detail"]


def test_reinitialisation_avec_jeton_revoque_renvoie_401_et_efface_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_echoue(JetonInvalideError())

    reponse_reinitialisation = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")
    reponse_compte = client.get("/compte")

    assert reponse_reinitialisation.status_code == 401
    assert reponse_compte.status_code == 401


def test_reinitialisation_avec_vm_centrale_injoignable_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.reinitialisation_mot_de_passe_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/comptes/n.durand/reinitialiser-mot-de-passe")

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


# --- POST /comptes/{identifiant}/deconnexion-forcee ---------------------------


def test_deconnexion_forcee_avec_session_admin_reussit(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/comptes/n.durand/deconnexion-forcee")

    assert reponse.status_code == 204


def test_deconnexion_forcee_transmet_le_jeton_et_l_identifiant(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    client.post("/comptes/n.durand/deconnexion-forcee")

    assert vm_centrale_client_factice._jetons_deconnexion_forcee == ["jeton-factice"]
    assert vm_centrale_client_factice._identifiants_deconnexion_forcee == ["n.durand"]


def test_deconnexion_forcee_sans_session_active_est_refusee(client, vm_centrale_client_factice):
    reponse = client.post("/comptes/n.durand/deconnexion-forcee")

    assert reponse.status_code == 401
    assert vm_centrale_client_factice._identifiants_deconnexion_forcee == []


def test_deconnexion_forcee_avec_session_non_admin_est_refusee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.deconnexion_forcee_echoue(AccesAdminRequisError())

    reponse = client.post("/comptes/n.durand/deconnexion-forcee")

    assert reponse.status_code == 403
    assert reponse.json()["detail"]


def test_deconnexion_forcee_avec_identifiant_inconnu_renvoie_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.deconnexion_forcee_echoue(CompteInexistantError())

    reponse = client.post("/comptes/inconnu/deconnexion-forcee")

    assert reponse.status_code == 404
    assert reponse.json()["detail"]


def test_deconnexion_forcee_avec_jeton_revoque_renvoie_401_et_efface_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.deconnexion_forcee_echoue(JetonInvalideError())

    reponse_deconnexion = client.post("/comptes/n.durand/deconnexion-forcee")
    reponse_compte = client.get("/compte")

    assert reponse_deconnexion.status_code == 401
    assert reponse_compte.status_code == 401


def test_deconnexion_forcee_avec_vm_centrale_injoignable_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.deconnexion_forcee_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/comptes/n.durand/deconnexion-forcee")

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


def test_front_end_porte_le_balisage_et_l_appel_de_reinitialisation_du_mot_de_passe(
    client, vm_centrale_client_factice
):
    # Même limite que le test précédent (aucun rendu côté serveur) : on
    # vérifie ici que le HTML sert bien la zone où afficher le mot de passe
    # régénéré, et que le JS appelle le bon endpoint plutôt qu'une simple
    # présence du texte du bouton, qui laisserait passer un mauvais chemin.
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="mot-de-passe-reinitialise" role="status" hidden' in html
    assert 'id="mot-de-passe-reinitialise-valeur"' in html
    assert "/reinitialiser-mot-de-passe" in js


def test_front_end_porte_le_balisage_et_l_appel_de_deconnexion_forcee(
    client, vm_centrale_client_factice
):
    # Même limite que les tests précédents (aucun rendu côté serveur) : on
    # vérifie que le HTML sert bien la zone de confirmation, et que le JS
    # appelle le bon endpoint plutôt qu'une simple présence du texte du
    # bouton, qui laisserait passer un mauvais chemin.
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="deconnexion-forcee-confirmation" role="status" hidden' in html
    assert 'id="deconnexion-forcee-identifiant"' in html
    assert "/deconnexion-forcee" in js
