import json

import httpx
import pytest

from poste import config
from poste.main import app
from poste.routers.configuration import get_client_sante
from poste.routers.mise_a_jour import get_demandeur_de_verification

# Écrit par le Lanceur à chaque lancement (lanceur/coeur/src/mise_a_jour.rs).
_A_JOUR = {
    "date": "2026-10-28T09:00:00+01:00",
    "version_poste": "1.6.2",
    "version_serveur": "1.6.2",
    "resultat": "a_jour",
    "detail": "BBASS est à jour (v1.6.2).",
    "bandeau": None,
}


@pytest.fixture
def poste_installe(monkeypatch, tmp_path):
    # Mode paquet : backend démarré par le Lanceur, qui lui donne sa version et son exe.
    dossier = tmp_path / "BBASS"
    dossier.mkdir()
    monkeypatch.setattr(config, "EN_MODE_PAQUET", True)
    monkeypatch.setattr(config, "FICHIER_CONFIGURATION", dossier / "configuration.json")
    monkeypatch.setattr(config, "FICHIER_ETAT_MISE_A_JOUR", dossier / "mise-a-jour.json")
    monkeypatch.setattr(config, "VERSION_POSTE", "1.6.2")
    monkeypatch.setattr(config, "LANCEUR", str(tmp_path / "BBASS.exe"))
    (dossier / "configuration.json").write_text(
        json.dumps({"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}}), encoding="utf-8"
    )
    return dossier


@pytest.fixture
def serveur_bbass():
    # Serveur BBASS simulé : réponse de GET /sante, ou None (injoignable).
    etat = {"sante": httpx.Response(200, json={"statut": "ok", "version": "1.6.3"})}

    def repondre(requete: httpx.Request) -> httpx.Response:
        if etat["sante"] is None:
            raise httpx.ConnectError("injoignable", request=requete)
        return etat["sante"]

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    app.dependency_overrides[get_client_sante] = lambda: client
    yield etat
    app.dependency_overrides.pop(get_client_sante, None)


@pytest.fixture
def demandes():
    # Demandes de vérification passées au Lanceur.
    faites: list[bool] = []
    app.dependency_overrides[get_demandeur_de_verification] = lambda: lambda: faites.append(True)
    yield faites
    app.dependency_overrides.pop(get_demandeur_de_verification, None)


def test_a_propos_donne_les_deux_versions_et_la_derniere_verification(client, poste_installe, serveur_bbass):
    (poste_installe / "mise-a-jour.json").write_text(json.dumps(_A_JOUR), encoding="utf-8")

    reponse = client.get("/a-propos")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "version_poste": "1.6.2",
        "version_serveur": "1.6.3",
        "derniere_verification": _A_JOUR,
        "verification_possible": True,
    }


def test_a_propos_avec_un_serveur_bbass_injoignable_n_a_pas_de_version_de_la_vm(client, poste_installe, serveur_bbass):
    serveur_bbass["sante"] = None

    reponse = client.get("/a-propos")

    assert reponse.status_code == 200
    assert reponse.json()["version_serveur"] is None
    assert reponse.json()["version_poste"] == "1.6.2"


def test_a_propos_sans_verification_encore_faite(client, poste_installe, serveur_bbass):
    reponse = client.get("/a-propos")

    assert reponse.json()["derniere_verification"] is None


def test_a_propos_est_accessible_sans_session(client, poste_installe, serveur_bbass):
    # Menu « … » de l'écran de connexion : on en a besoin quand on ne peut pas se connecter.
    client.cookies.clear()

    assert client.get("/a-propos").status_code == 200


def test_en_dev_a_propos_ne_propose_pas_de_verification(client, poste_installe, serveur_bbass, monkeypatch):
    # lancer-logiciel.* : pas de Lanceur, ni version de paquet, ni mise à jour.
    monkeypatch.setattr(config, "EN_MODE_PAQUET", False)
    monkeypatch.setattr(config, "VM_CENTRALE_BASE_URL", "http://localhost:8000")
    (poste_installe / "mise-a-jour.json").write_text(json.dumps(_A_JOUR), encoding="utf-8")

    reponse = client.get("/a-propos")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "version_poste": None,
        "version_serveur": "1.6.3",
        "derniere_verification": None,
        "verification_possible": False,
    }


def test_verifier_maintenant_demande_au_lanceur_de_redemarrer_en_mode_verification(client, poste_installe, demandes):
    reponse = client.post("/mise-a-jour/verifier")

    assert reponse.status_code == 202
    assert demandes == [True]


def test_en_dev_verifier_maintenant_est_refuse_avec_un_message_clair(client, poste_installe, demandes, monkeypatch):
    monkeypatch.setattr(config, "EN_MODE_PAQUET", False)

    reponse = client.post("/mise-a-jour/verifier")

    assert reponse.status_code == 409
    assert "Lanceur" in reponse.json()["detail"]
    assert demandes == []


def test_un_lanceur_introuvable_donne_un_message_clair(client, poste_installe):
    def echouer():
        raise OSError("introuvable")

    app.dependency_overrides[get_demandeur_de_verification] = lambda: echouer
    try:
        reponse = client.post("/mise-a-jour/verifier")
    finally:
        app.dependency_overrides.pop(get_demandeur_de_verification, None)

    assert reponse.status_code == 500
    assert reponse.json()["detail"] == "La vérification des mises à jour n'a pas pu être lancée. Relancez BBASS."
