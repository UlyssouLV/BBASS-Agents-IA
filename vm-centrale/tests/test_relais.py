from fastapi.testclient import TestClient

from vm_centrale.database import get_db
from vm_centrale.main import app


def test_message_transmis_et_reponse_mistral_retournee_telle_quelle(client, mistral_client_factice):
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?")

    reponse = client.post("/relais", json={"message": "Bonjour"})

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Bonjour, comment puis-je vous aider ?"}
    assert mistral_client_factice.messages_recus == ["Bonjour"]


def test_echec_appel_mistral_retourne_une_erreur_propre(client, mistral_client_factice):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post("/relais", json={"message": "Bonjour"})

    assert reponse.status_code == 502


def test_echec_appel_mistral_ne_revele_jamais_la_cle_api(client, mistral_client_factice):
    mistral_client_factice.echouer(RuntimeError("401 Unauthorized: Bearer sk-secrete-cle-api-mistral"))

    reponse = client.post("/relais", json={"message": "Bonjour"})

    assert "sk-secrete-cle-api-mistral" not in reponse.text


def test_cle_api_manquante_retourne_une_erreur_propre_et_pas_un_plantage(db_session, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            reponse = test_client.post("/relais", json={"message": "Bonjour"})
    finally:
        app.dependency_overrides.clear()

    assert reponse.status_code == 502
    assert "MISTRAL_API_KEY" not in reponse.text


def test_message_vide_est_rejete(client):
    reponse = client.post("/relais", json={"message": ""})

    assert reponse.status_code == 422


def test_message_trop_long_est_rejete(client):
    reponse = client.post("/relais", json={"message": "x" * 8001})

    assert reponse.status_code == 422
