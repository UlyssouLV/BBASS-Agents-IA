import json

import httpx
import pytest

from poste import config
from poste.main import app
from poste.routers.configuration import get_client_sante


@pytest.fixture
def fichier_configuration(monkeypatch, tmp_path):
    # Poste installé (mode paquet) : %LOCALAPPDATA%\BBASS\configuration.json, partagé avec le Lanceur.
    chemin = tmp_path / "BBASS" / "configuration.json"
    monkeypatch.setattr(config, "FICHIER_CONFIGURATION", chemin)
    monkeypatch.setattr(config, "EN_MODE_PAQUET", True)
    return chemin


def _ecrire(chemin, contenu):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu), encoding="utf-8")


@pytest.fixture
def serveurs_bbass():
    # Serveurs BBASS simulés, par adresse : réponse de GET /sante, ou absents (injoignables).
    serveurs: dict[str, httpx.Response] = {}
    appels: list[str] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(str(requete.url))
        adresse = f"{requete.url.scheme}://{requete.url.host}:{requete.url.port}"
        if requete.url.path != "/sante" or adresse not in serveurs:
            raise httpx.ConnectError("injoignable", request=requete)
        return serveurs[adresse]

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    app.dependency_overrides[get_client_sante] = lambda: client
    yield serveurs, appels
    app.dependency_overrides.pop(get_client_sante, None)


def _sante(version="1.6.2", statut=200):
    return httpx.Response(statut, json={"statut": "ok" if statut == 200 else "base injoignable", "version": version})


def test_l_etat_du_serveur_bbass_configure_donne_sa_version(client, fichier_configuration, serveurs_bbass):
    serveurs, _ = serveurs_bbass
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}})
    serveurs["http://10.0.0.5:8000"] = _sante("1.6.2")

    reponse = client.get("/serveur-bbass/etat")

    assert reponse.status_code == 200
    assert reponse.json() == {"joignable": True, "version": "1.6.2"}


def test_un_serveur_bbass_injoignable_est_signale_sans_version(client, fichier_configuration, serveurs_bbass):
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}})

    reponse = client.get("/serveur-bbass/etat")

    assert reponse.status_code == 200
    assert reponse.json() == {"joignable": False, "version": None}


def test_un_serveur_bbass_dont_la_base_est_injoignable_n_est_pas_vert(client, fichier_configuration, serveurs_bbass):
    # 503 « base injoignable » : la VM répond, mais le chat ne marcherait pas.
    serveurs, _ = serveurs_bbass
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}})
    serveurs["http://10.0.0.5:8000"] = _sante("1.6.2", statut=503)

    reponse = client.get("/serveur-bbass/etat")

    assert reponse.json() == {"joignable": False, "version": None}


def test_sans_adresse_connue_l_etat_est_injoignable_sans_appel(client, fichier_configuration, serveurs_bbass):
    _, appels = serveurs_bbass

    reponse = client.get("/serveur-bbass/etat")

    assert reponse.json() == {"joignable": False, "version": None}
    assert appels == []


def test_sans_fichier_de_configuration_l_adresse_est_vide_pour_ouvrir_la_configuration(client, fichier_configuration):
    # Adresse prod vide en 1.6.2 : le front ouvre la Configuration au premier lancement.
    reponse = client.get("/configuration")

    assert reponse.status_code == 200
    assert reponse.json() == {"hote": "", "port": 8000, "modifiable": True}


def test_la_configuration_lit_l_adresse_du_fichier(client, fichier_configuration):
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8001}})

    reponse = client.get("/configuration")

    assert reponse.json() == {"hote": "10.0.0.5", "port": 8001, "modifiable": True}


def test_tester_une_adresse_joignable_donne_sa_version(client, fichier_configuration, serveurs_bbass):
    serveurs, _ = serveurs_bbass
    serveurs["http://vm-staging:8000"] = _sante("1.6.3")

    reponse = client.post("/configuration/test", json={"hote": " vm-staging ", "port": 8000})

    assert reponse.status_code == 200
    assert reponse.json() == {"joignable": True, "version": "1.6.3"}


def test_tester_une_adresse_injoignable_est_orange_et_n_enregistre_rien(client, fichier_configuration, serveurs_bbass):
    reponse = client.post("/configuration/test", json={"hote": "10.0.0.9", "port": 8000})

    assert reponse.json() == {"joignable": False, "version": None}
    assert not fichier_configuration.exists()


@pytest.mark.parametrize(
    "corps",
    [
        {"hote": "", "port": 8000},
        {"hote": "http://10.0.0.5", "port": 8000},
        {"hote": "10.0.0.5", "port": 0},
        {"hote": "10.0.0.5", "port": 70000},
    ],
)
def test_une_adresse_invalide_est_refusee(client, fichier_configuration, serveurs_bbass, corps):
    assert client.post("/configuration/test", json=corps).status_code == 422
    assert client.put("/configuration", json=corps).status_code == 422
    assert not fichier_configuration.exists()


def test_enregistrer_ecrit_l_adresse_et_garde_les_autres_reglages(client, fichier_configuration):
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}, "demarrage_avec_windows": False})

    reponse = client.put("/configuration", json={"hote": " 10.0.0.6 ", "port": 8001})

    assert reponse.status_code == 200
    assert reponse.json() == {"hote": "10.0.0.6", "port": 8001, "modifiable": True}
    assert json.loads(fichier_configuration.read_text(encoding="utf-8")) == {
        "serveur_bbass": {"hote": "10.0.0.6", "port": 8001},
        "demarrage_avec_windows": False,
    }
    assert client.get("/configuration").json()["hote"] == "10.0.0.6"


def test_la_pastille_suit_la_nouvelle_adresse_sans_redemarrer(client, fichier_configuration, serveurs_bbass):
    serveurs, _ = serveurs_bbass
    serveurs["http://10.0.0.6:8000"] = _sante("1.6.2")
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}})
    assert client.get("/serveur-bbass/etat").json()["joignable"] is False

    client.put("/configuration", json={"hote": "10.0.0.6", "port": 8000})

    assert client.get("/serveur-bbass/etat").json() == {"joignable": True, "version": "1.6.2"}


def test_le_chat_appelle_la_nouvelle_adresse_sans_reinstaller(client, fichier_configuration, monkeypatch):
    # Vrai client de la VM centrale, réseau simulé : la connexion part vers l'adresse enregistrée.
    from poste import vm_centrale_client
    from poste.vm_centrale_client import VmCentraleClient, get_vm_centrale_client

    appels: list[str] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(str(requete.url))
        return httpx.Response(401, json={"detail": "Identifiants invalides."})

    monkeypatch.setattr(vm_centrale_client, "_http_client", httpx.Client(transport=httpx.MockTransport(repondre)))
    app.dependency_overrides[get_vm_centrale_client] = VmCentraleClient
    _ecrire(fichier_configuration, {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}})
    client.put("/configuration", json={"hote": "10.0.0.6", "port": 8001})

    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "mauvais"})

    assert appels == ["http://10.0.0.6:8001/auth"]


def test_en_dev_l_adresse_vient_du_env_et_ne_s_enregistre_pas(client, fichier_configuration, monkeypatch):
    monkeypatch.setattr(config, "EN_MODE_PAQUET", False)
    monkeypatch.setattr(config, "VM_CENTRALE_BASE_URL", "http://vm-centrale.interne:9000")

    assert client.get("/configuration").json() == {"hote": "vm-centrale.interne", "port": 9000, "modifiable": False}
    reponse = client.put("/configuration", json={"hote": "10.0.0.6", "port": 8000})
    assert reponse.status_code == 409
    assert ".env" in reponse.json()["detail"]
    assert not fichier_configuration.exists()


def test_ouvrir_le_dossier_de_configuration_ouvre_localappdata_bbass(client, fichier_configuration):
    from poste.routers.configuration import get_ouvreur_de_dossier

    ouverts = []
    app.dependency_overrides[get_ouvreur_de_dossier] = lambda: ouverts.append

    reponse = client.post("/configuration/ouvrir-dossier")

    assert reponse.status_code == 204
    assert ouverts == [fichier_configuration.parent]
    assert fichier_configuration.parent.is_dir()


def test_un_dossier_impossible_a_ouvrir_donne_un_message_clair(client, fichier_configuration):
    from poste.routers.configuration import get_ouvreur_de_dossier

    def echouer(dossier):
        raise OSError("aucune application associée")

    app.dependency_overrides[get_ouvreur_de_dossier] = lambda: echouer

    reponse = client.post("/configuration/ouvrir-dossier")

    assert reponse.status_code == 500
    assert reponse.json()["detail"] == "Le dossier de configuration n'a pas pu être ouvert."


def test_la_configuration_est_accessible_sans_session(client, fichier_configuration, serveurs_bbass):
    # Menu « … » de l'écran de connexion : on en a besoin quand on ne peut pas se connecter.
    for methode, chemin in [("get", "/configuration"), ("get", "/serveur-bbass/etat")]:
        assert getattr(client, methode)(chemin).status_code == 200
    assert client.put("/configuration", json={"hote": "10.0.0.6", "port": 8000}).status_code == 200
