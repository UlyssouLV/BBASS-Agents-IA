from datetime import datetime, timedelta, timezone

import pytest

from vm_centrale.exploitation import main
from vm_centrale.models import PageWebEnCache, ResultatRechercheWeb

# Purge du cache commun des pages web (spec 1.4.3, #155) : les copies de
# plus de 24 h sont supprimées, jamais les copies des conversations. Tâche
# planifiée `tache purger-cache-pages` de l'image (spec 1.6.1, #234), lancée
# toutes les heures par le timer bbass-<env>-purger-cache-pages.

_URL = "https://www.legifrance.gouv.fr/loi-climat-resilience"
_MAINTENANT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def tache(db_session, monkeypatch):
    # La sous-commande ouvre sa session sur la base des tests, à l'heure dite.
    monkeypatch.setattr("vm_centrale.database.init_db", lambda: None)
    monkeypatch.setattr("vm_centrale.database.SessionLocal", lambda: db_session)

    def _lancer(maintenant: datetime = _MAINTENANT) -> None:
        monkeypatch.setattr("vm_centrale.taches.maintenant", lambda: maintenant)
        main(["tache", "purger-cache-pages"])

    return _lancer


def _copie(url: str, age: timedelta) -> PageWebEnCache:
    return PageWebEnCache(url=url, texte_nettoye="Texte", titre="Titre", date_telechargement=_MAINTENANT - age)


def test_la_tache_supprime_les_copies_expirees_et_garde_les_fraiches(db_session, tache, capsys):
    db_session.add_all(
        [
            _copie("https://exemple.fr/ancienne", timedelta(hours=30)),
            _copie("https://exemple.fr/limite", timedelta(hours=24, seconds=1)),
            _copie("https://exemple.fr/fraiche", timedelta(hours=23)),
        ]
    )
    db_session.commit()

    tache()

    assert capsys.readouterr().out.strip() == "Copies du cache des pages web supprimées : 2"
    assert [copie.url for copie in db_session.query(PageWebEnCache).all()] == ["https://exemple.fr/fraiche"]


def test_une_tache_inconnue_est_refusee(capsys):
    with pytest.raises(SystemExit) as sortie:
        main(["tache", "tache-inconnue"])

    assert sortie.value.code != 0
    assert "tache-inconnue" in capsys.readouterr().err


def test_la_tache_ne_touche_pas_aux_copies_des_conversations(
    client, jeton_valide, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, db_session,
    tache,
):
    telechargeur_pages_factice.servir(
        _URL,
        "<html><head><title>Loi Climat</title></head><body><article><h1>Loi Climat</h1>"
        # Paragraphes distincts : trafilatura retire les doublons, et une
        # page sous le seuil de texte est quasi vide (#131).
        + "".join(
            f"<p>Le titre {numero} de la loi traite du climat et de la résilience des territoires.</p>"
            for numero in range(5)
        )
        + "</article></body></html>",
    )
    moteur_recherche_factice.repondre(("Loi Climat", _URL, "Texte de la loi."))
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "loi climat", "besoin": "Trouver le texte de la loi"}
    )
    mistral_client_factice.repondre("Voici.", "Titre")
    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers={"Authorization": f"Bearer {jeton_valide}"}
    )
    assert reponse.status_code == 200
    copie_conversation = db_session.query(ResultatRechercheWeb).filter_by(url=_URL).one()
    texte_conversation = copie_conversation.texte_nettoye
    assert texte_conversation
    assert db_session.query(PageWebEnCache).count() == 1

    tache(datetime.now(timezone.utc) + timedelta(days=2))

    db_session.expire_all()
    assert db_session.query(PageWebEnCache).count() == 0
    assert db_session.query(ResultatRechercheWeb).filter_by(url=_URL).one().texte_nettoye == texte_conversation
