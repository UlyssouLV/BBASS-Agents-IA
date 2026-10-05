def test_front_end_servi_sur_la_racine(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


def test_front_end_servi_sur_la_route_inspecteur(client):
    # Mode développeur (spec 1.3.0) : /inspecteur est ouvert dans un nouvel
    # onglet (window.open) et doit servir le même front que la racine, sans
    # entrer en collision avec les routes API /inspecteur/*.
    reponse = client.get("/inspecteur")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
