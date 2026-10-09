import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from vm_centrale.moduleo import client as client_module
from vm_centrale.moduleo.client import (
    ClientModuleo,
    TransportHttp,
    ModuleoIndisponible,
    ModuleoIntrouvable,
    ModuleoRefuse,
    RequeteInterdite,
)
from vm_centrale.moduleo.droits import GROUPE_DEV, DroitsModuleo
from vm_centrale.moduleo.routes import ROUTES_GET

# Client Moduléo en lecture seule (spec 1.5.0, ADR-0017) : le client HTTP
# est remplacé, aucun accès réseau.

_DOCS = Path(client_module.__file__).parent / "docs"
_WADL = "{http://wadl.dev.java.net/2009/02}"


def _client(monkeypatch, gestionnaire) -> ClientModuleo:
    monkeypatch.setattr(
        client_module, "_http_client", httpx.Client(transport=httpx.MockTransport(gestionnaire))
    )
    return ClientModuleo(TransportHttp("https://moduleo.local/api/", "cle-api", "code-securite"))


# Affaires et référentiels : il suffit d'un groupe Cogeo (garde des droits,
# #188, tests/test_garde_droits_moduleo.py).
_DROITS = DroitsModuleo(groupe_cogeo=GROUPE_DEV)


def _enregistreur(requetes: list[httpx.Request], reponse: httpx.Response):
    def _gestionnaire(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        return reponse

    return _gestionnaire


def test_lire_envoie_un_get_avec_les_en_tetes_et_renvoie_le_json(monkeypatch):
    requetes: list[httpx.Request] = []
    client = _client(monkeypatch, _enregistreur(requetes, httpx.Response(200, json={"IdAffaire": 12})))

    resultat = client.lire("cogeo/affaire/{idAffaire}", {"idAffaire": 12}, _DROITS)

    assert resultat == {"IdAffaire": 12}
    assert len(requetes) == 1
    assert requetes[0].method == "GET"
    assert str(requetes[0].url) == "https://moduleo.local/api/cogeo/affaire/12"
    assert requetes[0].headers["ApiKey"] == "cle-api"
    assert requetes[0].headers["SecurityCode"] == "code-securite"


def test_lire_envoie_seulement_les_parametres_de_requete_fournis(monkeypatch):
    requetes: list[httpx.Request] = []
    client = _client(monkeypatch, _enregistreur(requetes, httpx.Response(200, json=[])))
    route = next(r for r in ROUTES_GET if r.startswith("cogeo/affaire?texte="))

    client.lire(route, {"texte": "Castries", "nbMaxResultats": 5, "etatAffaire": None}, _DROITS)

    assert requetes[0].url.path == "/api/cogeo/affaire"
    assert dict(requetes[0].url.params) == {"texte": "Castries", "nbMaxResultats": "5"}


@pytest.mark.parametrize("methode", ["POST", "PUT", "DELETE", "PATCH", "HEAD"])
def test_une_autre_methode_que_get_est_refusee_sans_requete(monkeypatch, methode):
    requetes: list[httpx.Request] = []
    client = _client(monkeypatch, _enregistreur(requetes, httpx.Response(200, json={})))

    with pytest.raises(RequeteInterdite):
        client.envoyer(methode, "cogeo/affaire/{idAffaire}", {"idAffaire": 12}, _DROITS)

    assert requetes == []


@pytest.mark.parametrize(
    ("route", "parametres"),
    [
        ("cogeo/affaire/12", {}),
        ("api/cogeo/affaire/{idAffaire}", {"idAffaire": 12}),
        ("cogeo/inconnue", {}),
        # Route connue, paramètre absent de la route ou paramètre de chemin manquant.
        ("cogeo/affaire/{idAffaire}", {"idAffaire": 12, "autre": 1}),
        ("cogeo/affaire/{idAffaire}", {}),
    ],
)
def test_une_route_hors_table_ou_mal_remplie_est_refusee_sans_requete(monkeypatch, route, parametres):
    requetes: list[httpx.Request] = []
    client = _client(monkeypatch, _enregistreur(requetes, httpx.Response(200, json={})))

    with pytest.raises(RequeteInterdite):
        client.lire(route, parametres, _DROITS)

    assert requetes == []


@pytest.mark.parametrize("statut", [401, 403])
def test_cle_ou_droit_refuse_leve_moduleo_refuse(monkeypatch, statut):
    client = _client(monkeypatch, lambda _: httpx.Response(statut, text="Accès refusé"))

    with pytest.raises(ModuleoRefuse):
        client.lire("cogeo/affaire/{idAffaire}", {"idAffaire": 12}, _DROITS)


def test_element_inexistant_leve_moduleo_introuvable_une_panne_pour_qui_ne_lattend_pas(monkeypatch):
    client = _client(monkeypatch, lambda _: httpx.Response(404, text="Introuvable"))

    with pytest.raises(ModuleoIntrouvable) as erreur:
        client.lire("cogeo/affaire/numeroAffaire?numAffaire={numAffaire}", {"numAffaire": "1999-001"}, _DROITS)

    assert isinstance(erreur.value, ModuleoIndisponible)


def _delai_depasse(requete: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("délai dépassé", request=requete)


def _injoignable(requete: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connexion refusée", request=requete)


@pytest.mark.parametrize(
    "gestionnaire",
    [
        _delai_depasse,
        _injoignable,
        lambda _: httpx.Response(500, text="Erreur serveur"),
        lambda _: httpx.Response(200, text="<html>pas du json</html>"),
    ],
)
def test_delai_depasse_ou_serveur_en_erreur_leve_moduleo_indisponible(monkeypatch, gestionnaire):
    client = _client(monkeypatch, gestionnaire)

    with pytest.raises(ModuleoIndisponible):
        client.lire("cogeo/affaire/{idAffaire}", {"idAffaire": 12}, _DROITS)


def _routes_get_du_wadl() -> set[str]:
    racine = ET.parse(_DOCS / "wadl.xml").getroot()
    routes = set()
    for ressource in racine.iter(f"{_WADL}resource"):
        methodes = {m.get("name") for m in ressource.findall(f"{_WADL}method")}
        if "GET" in methodes:
            routes.add(ressource.get("path", "").removeprefix("api/"))
    return routes


def test_routes_contient_exactement_les_routes_get_du_wadl_versionne():
    assert ROUTES_GET == _routes_get_du_wadl()
    assert len(ROUTES_GET) == 207


def test_index_des_routes_liste_chaque_route_get_avec_parametres_et_description():
    index = (_DOCS / "index-routes.md").read_text(encoding="utf-8")
    lignes = {
        ligne.split("|")[1].strip().strip("`"): ligne
        for ligne in index.splitlines()
        if ligne.startswith("| `")
    }

    assert set(lignes) == ROUTES_GET
    for route, ligne in lignes.items():
        # Une barre verticale dans une description est échappée (« \| »).
        colonnes = [c.strip() for c in re.split(r"(?<!\\)\|", ligne.strip("|"))]
        assert colonnes[2], f"description manquante : {route}"
        for parametre in re.findall(r"\{(\w+)\}", route):
            assert parametre in colonnes[1], f"paramètre {parametre} absent : {route}"
