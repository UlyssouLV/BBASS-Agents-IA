import json

from poste.session import SessionStore

_POLES = ["Foncier", "Urbanisme"]


def _ouvrir(store, identifiant="j.dupont", prenom="Jean", nom="Dupont", jeton="jeton-abc"):
    store.ouvrir(
        identifiant,
        prenom,
        nom,
        jeton,
        "Castries",
        _POLES,
        True,
        True,
    )


def test_ouvrir_persiste_la_session(keyring_factice):
    store = SessionStore()

    _ouvrir(store)

    autre_store = SessionStore()
    donnees = autre_store.lire_session_persistee()
    assert donnees is not None
    assert donnees.identifiant == "j.dupont"
    assert donnees.prenom == "Jean"
    assert donnees.nom == "Dupont"
    assert donnees.jeton == "jeton-abc"
    assert donnees.agence == "Castries"
    assert donnees.poles == _POLES
    assert donnees.est_admin is True
    assert donnees.doit_changer_mot_de_passe is True


def test_le_mot_de_passe_n_est_jamais_persiste(keyring_factice):
    store = SessionStore()

    _ouvrir(store)

    ((_service, _utilisateur), brut) = next(iter(keyring_factice.items()))
    assert "mot_de_passe" not in json.loads(brut)
    assert "mot-de-passe" not in brut


def test_lire_session_persistee_retourne_none_si_rien_n_est_stocke(keyring_factice):
    store = SessionStore()

    assert store.lire_session_persistee() is None


def test_fermer_supprime_la_session_persistee(keyring_factice):
    store = SessionStore()
    _ouvrir(store)

    store.fermer()

    assert SessionStore().lire_session_persistee() is None


def test_fermer_sans_session_persistee_ne_plante_pas(keyring_factice):
    store = SessionStore()

    store.fermer()


def test_ouvrir_degrade_silencieusement_si_keyring_leve_une_exception(monkeypatch):
    def set_password_en_echec(service_name, username, password):
        raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.set_password", set_password_en_echec)
    store = SessionStore()

    _ouvrir(store)

    assert store.est_connecte
    assert store.identifiant == "j.dupont"
    assert store.persistance_degradee


def test_lire_session_persistee_degrade_silencieusement_si_keyring_leve_une_exception(monkeypatch):
    def get_password_en_echec(service_name, username):
        raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.get_password", get_password_en_echec)
    store = SessionStore()

    donnees = store.lire_session_persistee()

    assert donnees is None
    assert store.persistance_degradee


def test_persistance_degradee_se_reinitialise_apres_un_succes(monkeypatch):
    appels = {"count": 0}

    def set_password_echoue_une_fois(service_name, username, password):
        appels["count"] += 1
        if appels["count"] == 1:
            raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.set_password", set_password_echoue_une_fois)
    store = SessionStore()

    _ouvrir(store, jeton="jeton-1")
    assert store.persistance_degradee

    _ouvrir(store, jeton="jeton-2")
    assert not store.persistance_degradee


def test_marquer_mot_de_passe_change_leve_le_flag_en_memoire_et_dans_le_blob_persiste(keyring_factice):
    store = SessionStore()
    _ouvrir(store)

    store.marquer_mot_de_passe_change()

    assert store.doit_changer_mot_de_passe is False
    donnees = SessionStore().lire_session_persistee()
    assert donnees is not None
    assert donnees.doit_changer_mot_de_passe is False


def test_fermer_ignore_une_exception_du_gestionnaire_d_identifiants(monkeypatch):
    def delete_password_en_echec(service_name, username):
        raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.delete_password", delete_password_en_echec)
    store = SessionStore()
    _ouvrir(store)

    store.fermer()

    assert not store.est_connecte
