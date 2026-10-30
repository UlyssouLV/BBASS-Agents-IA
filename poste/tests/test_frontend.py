import pytest


def test_front_end_servi_sur_la_racine(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


@pytest.mark.parametrize("chemin", ["/", "/inspecteur"])
def test_la_page_est_revalidee_a_chaque_ouverture(client, chemin):
    # Spec 1.6.4, point 9 : index.html désigne le code de l'interface, propre à
    # chaque version. Sans cet en-tête, le moteur web réutilise l'ancienne page
    # après une mise à jour.
    reponse = client.get(chemin)

    assert reponse.headers["cache-control"] == "no-cache"


def test_front_end_servi_sur_la_route_inspecteur(client):
    # Mode développeur (spec 1.3.0) : /inspecteur est ouvert dans un nouvel
    # onglet (window.open) et doit servir le même front que la racine, sans
    # entrer en collision avec les routes API /inspecteur/*.
    reponse = client.get("/inspecteur")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
