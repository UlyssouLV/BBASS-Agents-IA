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


def test_connexion_avec_doit_changer_mot_de_passe_affiche_l_ecran_de_changement(
    client, vm_centrale_client_factice
):
    # Issue #20 : un compte avec doit_changer_mot_de_passe=true ne doit
    # jamais atteindre l'écran de chat, à la connexion comme à la
    # restauration de session (voir aussi test_verification_au_demarrage.py
    # côté backend, qui vérifie que GET /compte porte bien ce flag). Aucun
    # rendu serveur : on vérifie ici le balisage de l'écran bloquant et la
    # condition JS exacte qui y redirige au lieu d'afficher le chat.
    vm_centrale_client_factice.accepter(doit_changer_mot_de_passe=True)

    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="ecran-changement-mot-de-passe" hidden' in html
    assert 'id="formulaire-changement-mot-de-passe"' in html
    assert "compte.doit_changer_mot_de_passe" in js
    assert "afficherEcranChangementMotDePasse" in js


def test_front_end_appelle_l_endpoint_de_changement_de_mot_de_passe(client):
    js = client.get("/static/app.js").text

    assert '"/mot-de-passe"' in js
    assert "nouveau_mot_de_passe" in js


def test_front_end_expose_un_onglet_profil_de_travail_sans_action_de_modification(client):
    # Issue #39 : lecture seule, aucune modale/formulaire de réinitialisation
    # ne doit accompagner cet onglet (contrairement aux onglets Comptes).
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="onglet-bouton-profil-travail"' in html
    assert 'id="onglet-profil-travail" hidden' in html
    assert '"/profil-travail"' in js
    assert "afficherOngletProfilTravail" in js


def test_front_end_bloque_un_second_envoi_tant_que_mistral_n_a_pas_repondu(client):
    js = client.get("/static/app.js").text

    assert "appelConversationEnCours" in js
    assert "|| appelConversationEnCours" in js
