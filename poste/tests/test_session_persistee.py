from poste.session import SessionStore


def test_ouvrir_persiste_la_session(keyring_factice):
    store = SessionStore()

    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-abc")

    autre_store = SessionStore()
    donnees = autre_store.lire_session_persistee()
    assert donnees is not None
    assert donnees.identifiant == "j.dupont"
    assert donnees.prenom == "Jean"
    assert donnees.nom == "Dupont"
    assert donnees.jeton == "jeton-abc"


def test_le_mot_de_passe_n_est_jamais_persiste(keyring_factice):
    store = SessionStore()

    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-abc")

    ((_service, _utilisateur), brut) = next(iter(keyring_factice.items()))
    assert "mot_de_passe" not in brut
    assert "mot-de-passe" not in brut


def test_lire_session_persistee_retourne_none_si_rien_n_est_stocke(keyring_factice):
    store = SessionStore()

    assert store.lire_session_persistee() is None


def test_fermer_supprime_la_session_persistee(keyring_factice):
    store = SessionStore()
    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-abc")

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

    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-abc")

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

    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-1")
    assert store.persistance_degradee

    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-2")
    assert not store.persistance_degradee


def test_fermer_ignore_une_exception_du_gestionnaire_d_identifiants(monkeypatch):
    def delete_password_en_echec(service_name, username):
        raise RuntimeError("Credential Manager indisponible")

    monkeypatch.setattr("poste.session.keyring.delete_password", delete_password_en_echec)
    store = SessionStore()
    store.ouvrir("j.dupont", "Jean", "Dupont", "jeton-abc")

    store.fermer()

    assert not store.est_connecte
