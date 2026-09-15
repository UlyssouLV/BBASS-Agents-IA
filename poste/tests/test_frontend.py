def test_front_end_servi_sur_la_racine(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


def test_front_end_ne_contient_aucun_balisage_de_pole_ou_d_agence(client):
    reponse = client.get("/")

    assert "agence" not in reponse.text.lower()
    assert "pôle" not in reponse.text.lower()
    assert "pole" not in reponse.text.lower()
    assert "<select" not in reponse.text.lower()
