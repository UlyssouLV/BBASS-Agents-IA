import httpx
import pytest

from vm_centrale import moteur_recherche as moteur_recherche_module
from vm_centrale.moteur_recherche import MoteurIndisponible, MoteurSearxng, ResultatRecherche

# Implémentation SearXNG de MoteurRecherche (spec 1.4.0) : le client HTTP
# est remplacé, aucun accès réseau.


def _transport(gestionnaire) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(gestionnaire))


def test_searxng_recoit_la_requete_en_json_et_renvoie_titre_url_extrait(monkeypatch):
    requetes = []

    def _gestionnaire(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Loi", "url": "https://exemple.fr/loi", "content": "Texte de la loi"},
                    {"title": "Sans URL", "content": "Ignoré"},
                    {"title": None, "url": "https://exemple.fr/sans-titre", "content": None},
                ]
            },
        )

    monkeypatch.setattr(moteur_recherche_module, "_http_client", _transport(_gestionnaire))

    resultats = MoteurSearxng("http://searxng.local/").rechercher("loi climat")

    assert requetes[0].url.path == "/search"
    assert requetes[0].url.params["q"] == "loi climat"
    assert requetes[0].url.params["format"] == "json"
    assert resultats == [
        ResultatRecherche("Loi", "https://exemple.fr/loi", "Texte de la loi"),
        ResultatRecherche("", "https://exemple.fr/sans-titre", ""),
    ]


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(403, text="Format json désactivé"),
        httpx.Response(200, text="<html>pas du json</html>"),
        httpx.Response(200, json={"autre": []}),
    ],
)
def test_searxng_en_erreur_leve_moteur_indisponible(monkeypatch, reponse):
    monkeypatch.setattr(moteur_recherche_module, "_http_client", _transport(lambda _: reponse))

    with pytest.raises(MoteurIndisponible):
        MoteurSearxng("http://searxng.local").rechercher("loi climat")


def test_searxng_injoignable_leve_moteur_indisponible(monkeypatch):
    def _gestionnaire(requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connexion refusée", request=requete)

    monkeypatch.setattr(moteur_recherche_module, "_http_client", _transport(_gestionnaire))

    with pytest.raises(MoteurIndisponible):
        MoteurSearxng("http://searxng.local").rechercher("loi climat")
