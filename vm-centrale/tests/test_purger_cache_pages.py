import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vm_centrale.models import PageWebEnCache, ResultatRechercheWeb

# Purge du cache commun des pages web (spec 1.4.3, #155) : les copies de
# plus de 24 h sont supprimées, jamais les copies des conversations.

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "purger_cache_pages.py"
_URL = "https://www.legifrance.gouv.fr/loi-climat-resilience"
_MAINTENANT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def _charger_script():
    spec = importlib.util.spec_from_file_location("purger_cache_pages", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copie(url: str, age: timedelta) -> PageWebEnCache:
    return PageWebEnCache(url=url, texte_nettoye="Texte", titre="Titre", date_telechargement=_MAINTENANT - age)


def test_le_script_supprime_les_copies_expirees_et_garde_les_fraiches(db_session):
    db_session.add_all(
        [
            _copie("https://exemple.fr/ancienne", timedelta(hours=30)),
            _copie("https://exemple.fr/limite", timedelta(hours=24, seconds=1)),
            _copie("https://exemple.fr/fraiche", timedelta(hours=23)),
        ]
    )
    db_session.commit()

    nombre = _charger_script().purger(db_session, _MAINTENANT)

    assert nombre == 2
    assert [copie.url for copie in db_session.query(PageWebEnCache).all()] == ["https://exemple.fr/fraiche"]


def test_le_script_affiche_le_nombre_supprime(db_session, monkeypatch, capsys):
    db_session.add(_copie("https://exemple.fr/ancienne", timedelta(days=3)))
    db_session.commit()
    module = _charger_script()
    monkeypatch.setattr(module, "init_db", lambda: None)
    monkeypatch.setattr(module, "SessionLocal", lambda: db_session)

    module.main()

    assert capsys.readouterr().out.strip() == "Copies du cache des pages web supprimées : 1"


def test_le_script_ne_touche_pas_aux_copies_des_conversations(
    client, jeton_valide, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, db_session
):
    telechargeur_pages_factice.servir(
        _URL,
        "<html><head><title>Loi Climat</title></head><body><article><h1>Loi Climat</h1>"
        + "<p>La loi compte 305 articles sur le climat et la résilience des territoires.</p>" * 5
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

    _charger_script().purger(db_session, datetime.now(timezone.utc) + timedelta(days=2))

    db_session.expire_all()
    assert db_session.query(PageWebEnCache).count() == 0
    assert db_session.query(ResultatRechercheWeb).filter_by(url=_URL).one().texte_nettoye == texte_conversation
