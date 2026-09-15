from fastapi.testclient import TestClient

from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.main import app


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def test_message_transmis_et_reponse_mistral_retournee_telle_quelle(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?")

    reponse = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Bonjour, comment puis-je vous aider ?"}
    assert mistral_client_factice.messages_recus == ["Bonjour"]


def test_echec_appel_mistral_retourne_une_erreur_propre(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 502


def test_echec_appel_mistral_ne_revele_jamais_la_cle_api(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.echouer(RuntimeError("401 Unauthorized: Bearer sk-secrete-cle-api-mistral"))

    reponse = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert "sk-secrete-cle-api-mistral" not in reponse.text


def test_cle_api_manquante_retourne_une_erreur_propre_et_pas_un_plantage(db_session, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    def override_get_db():
        yield db_session

    jeton_store = JetonStore(db_session)
    jeton = jeton_store.emettre("j.dupont")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_jeton_store] = lambda: jeton_store
    try:
        with TestClient(app) as test_client:
            reponse = test_client.post(
                "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton)
            )
    finally:
        app.dependency_overrides.clear()

    assert reponse.status_code == 502
    assert "MISTRAL_API_KEY" not in reponse.text


def test_message_vide_est_rejete(client, jeton_valide):
    reponse = client.post(
        "/relais", json={"message": ""}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 422


def test_message_trop_long_est_rejete(client, jeton_valide):
    reponse = client.post(
        "/relais", json={"message": "x" * 8001}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 422


def test_relais_sans_jeton_est_refuse_sans_appeler_mistral(client, mistral_client_factice):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post("/relais", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []


def test_relais_avec_jeton_invalide_est_refuse_sans_appeler_mistral(client, mistral_client_factice):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation("jeton-inconnu")
    )

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []


def test_jeton_emis_par_auth_autorise_le_relais(client, mistral_client_factice, seed_compte):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?")

    reponse_auth = client.post(
        "/auth", json={"identifiant": "j.dupont", "mot_de_passe": "correcthorsebatterystaple"}
    )
    jeton = reponse_auth.json()["jeton"]

    reponse_relais = client.post(
        "/relais", json={"message": "Bonjour"}, headers=_autorisation(jeton)
    )

    assert reponse_relais.status_code == 200
    assert reponse_relais.json() == {"reponse": "Bonjour, comment puis-je vous aider ?"}
