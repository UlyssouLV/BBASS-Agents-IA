from contextlib import contextmanager

from fastapi.testclient import TestClient

from poste.main import app
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import get_vm_centrale_client

_POLES = ["Foncier"]


def _ouvrir(
    identifiant="j.dupont", prenom="Jean", nom="Dupont", jeton="jeton-abc", est_admin=False
):
    SessionStore().ouvrir(
        identifiant, prenom, nom, jeton, "Castries", _POLES, est_admin, False
    )


@contextmanager
def _demarrer_avec(session_store, vm_centrale_client_factice):
    app.dependency_overrides[get_vm_centrale_client] = lambda: vm_centrale_client_factice
    app.dependency_overrides[get_session_store] = lambda: session_store
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_session_valide_au_demarrage_ouvre_directement_le_compte(
    keyring_factice, session_store, vm_centrale_client_factice
):
    _ouvrir()
    vm_centrale_client_factice.verification_reussit("j.dupont")

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "identifiant": "j.dupont",
        "prenom": "Jean",
        "nom": "Dupont",
        "agence": "Castries",
        "poles": _POLES,
        "est_admin": False,
        "doit_changer_mot_de_passe": False,
    }
    assert vm_centrale_client_factice.jetons_verifies == ["jeton-abc"]


def test_session_invalide_au_demarrage_affiche_la_connexion_et_efface_la_persistance(
    keyring_factice, session_store, vm_centrale_client_factice
):
    _ouvrir()
    vm_centrale_client_factice.verification_echoue()

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 401
    assert SessionStore().lire_session_persistee() is None


def test_vm_injoignable_au_demarrage_affiche_la_connexion_sans_effacer_la_persistance(
    keyring_factice, session_store, vm_centrale_client_factice
):
    _ouvrir()
    vm_centrale_client_factice.verification_indisponible(RuntimeError("VM injoignable"))

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 401
    assert SessionStore().lire_session_persistee() is not None


def test_aucune_session_persistee_au_demarrage_affiche_la_connexion_sans_appeler_la_vm(
    keyring_factice, session_store, vm_centrale_client_factice
):
    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 401
    assert vm_centrale_client_factice.jetons_verifies == []


def test_session_valide_au_demarrage_utilise_l_identifiant_verifie_par_la_vm(
    keyring_factice, session_store, vm_centrale_client_factice
):
    # L'identifiant retourné par la VM fait foi, jamais celui du blob local
    # lu depuis keyring (qui ne prouve que la possession du jeton).
    _ouvrir(identifiant="ancien-identifiant")
    vm_centrale_client_factice.verification_reussit("j.dupont")

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 200
    assert reponse.json()["identifiant"] == "j.dupont"


def test_session_valide_au_demarrage_ne_reecrit_pas_le_keyring(
    keyring_factice, session_store, vm_centrale_client_factice, monkeypatch
):
    _ouvrir()
    vm_centrale_client_factice.verification_reussit("j.dupont")

    appels_set_password = []
    monkeypatch.setattr(
        "poste.session.keyring.set_password",
        lambda service_name, username, password: appels_set_password.append(
            (service_name, username, password)
        ),
    )

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        test_client.get("/compte")

    assert appels_set_password == []


def test_est_admin_est_revalide_aupres_de_la_vm_et_non_lu_du_cache(
    keyring_factice, session_store, vm_centrale_client_factice
):
    # La session persistée date d'avant une promotion : est_admin=False en
    # cache, mais la VM répond désormais est_admin=True. La restauration doit
    # refléter la valeur fraîche de la VM, pas le blob local.
    _ouvrir(est_admin=False)
    vm_centrale_client_factice.verification_reussit("j.dupont", est_admin=True)

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 200
    assert reponse.json()["est_admin"] is True


def test_est_admin_retrograde_est_revalide_aupres_de_la_vm_et_non_lu_du_cache(
    keyring_factice, session_store, vm_centrale_client_factice
):
    # Symétrique : un compte rétrogradé pendant que sa session persiste perd
    # est_admin dès la prochaine vérification, même si le cache local dit
    # encore est_admin=True.
    _ouvrir(est_admin=True)
    vm_centrale_client_factice.verification_reussit("j.dupont", est_admin=False)

    with _demarrer_avec(session_store, vm_centrale_client_factice) as test_client:
        reponse = test_client.get("/compte")

    assert reponse.status_code == 200
    assert reponse.json()["est_admin"] is False
