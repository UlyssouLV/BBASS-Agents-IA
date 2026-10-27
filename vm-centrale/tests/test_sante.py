from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from vm_centrale.database import get_db
from vm_centrale.main import app

# GET /sante (spec 1.6.1, #230) : sans authentification, 200 avec la version
# de l'image quand la base répond, 503 sinon. Ni Mistral, ni Moduléo, ni
# SearXNG ne sont vérifiés.


def test_la_sante_repond_ok_avec_la_version_quand_la_base_repond(client, monkeypatch):
    monkeypatch.setenv("VM_CENTRALE_VERSION", "1.6.1")

    reponse = client.get("/sante")

    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "version": "1.6.1"}


def test_la_sante_repond_503_quand_la_base_ne_repond_pas(client, tmp_path):
    # Fichier SQLite dans un dossier absent : la connexion échoue, comme un
    # Postgres arrêté.
    base_injoignable = create_engine(f"sqlite:///{tmp_path / 'absent' / 'base.db'}")

    def session_injoignable():
        with Session(base_injoignable) as db:
            yield db

    app.dependency_overrides[get_db] = session_injoignable

    reponse = client.get("/sante")

    assert reponse.status_code == 503
    assert reponse.json()["statut"] == "base injoignable"
