def test_front_end_servi_sur_la_racine(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]


def test_front_end_affiche_le_pole_et_l_agence_du_compte_connecte(client, vm_centrale_client_factice):
    # V1.1 referme la US #11 : le pôle et l'agence redeviennent visibles dans
    # l'écran de chat, à côté de « Prénom Nom (identifiant) ». La session
    # connectée expose ces champs via /compte ; on vérifie ici que le
    # HTML/JS servi porte bien le balisage et la logique d'affichage
    # correspondants.
    vm_centrale_client_factice.accepter(agence="Castries", poles=["Foncier", "Urbanisme"])
    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "x"})

    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="pole-agence-connecte"' in html
    assert "compte.agence" in js
    assert "compte.poles" in js
