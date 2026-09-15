from sqlalchemy.orm import sessionmaker

from vm_centrale.jetons import JetonStore


def test_jeton_reste_valide_apres_un_redemarrage_simule_du_store(db_session):
    jeton = JetonStore(db_session).emettre("j.dupont")

    autre_session = sessionmaker(bind=db_session.get_bind())()
    try:
        store_redemarre = JetonStore(autre_session)
        assert store_redemarre.est_valide(jeton)
    finally:
        autre_session.close()


def test_jeton_inconnu_est_invalide(db_session):
    store = JetonStore(db_session)

    assert not store.est_valide("jeton-inconnu")


def test_revoquer_invalide_le_jeton(db_session):
    store = JetonStore(db_session)
    jeton = store.emettre("j.dupont")

    store.revoquer(jeton)

    assert not store.est_valide(jeton)


def test_revoquer_un_jeton_deja_absent_ne_plante_pas(db_session):
    store = JetonStore(db_session)

    store.revoquer("jeton-inconnu")


def test_revoquer_tous_invalide_tous_les_jetons_du_compte_mais_pas_les_autres(db_session):
    store = JetonStore(db_session)
    jeton_1 = store.emettre("j.dupont")
    jeton_2 = store.emettre("j.dupont")
    jeton_autre_compte = store.emettre("a.martin")

    store.revoquer_tous("j.dupont")

    assert not store.est_valide(jeton_1)
    assert not store.est_valide(jeton_2)
    assert store.est_valide(jeton_autre_compte)


def test_identifiant_pour_retourne_le_compte_associe_au_jeton(db_session):
    store = JetonStore(db_session)
    jeton = store.emettre("j.dupont")

    assert store.identifiant_pour(jeton) == "j.dupont"


def test_identifiant_pour_retourne_none_pour_un_jeton_inconnu(db_session):
    store = JetonStore(db_session)

    assert store.identifiant_pour("jeton-inconnu") is None
