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


def test_front_end_expose_un_onglet_consommation_sans_action_de_modification(client):
    # Issue #58 : lecture seule, comme l'onglet Profil de travail — un total
    # global et un classement des conversations par coût, jamais d'action.
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="onglet-bouton-consommation"' in html
    assert 'id="onglet-consommation" hidden' in html
    assert '"/consommation"' in js
    assert "afficherOngletConsommation" in js


def test_front_end_bloque_un_second_envoi_tant_que_mistral_n_a_pas_repondu(client):
    js = client.get("/static/app.js").text

    assert "appelConversationEnCours" in js
    assert "|| appelConversationEnCours" in js


def test_front_end_envoie_une_cle_idempotence_a_chaque_envoi(client):
    # Défense en profondeur côté poste (cf. vm_centrale.concurrence.CacheIdempotence)
    # contre une requête rejouée au niveau réseau : une clé aléatoire par
    # tentative, jamais réutilisée d'un envoi à l'autre.
    js = client.get("/static/app.js").text

    assert js.count("crypto.randomUUID()") >= 2
    assert "cle_idempotence: cleIdempotence" in js


def test_front_end_expose_une_zone_de_depot_de_fichier_pour_les_deux_formulaires_denvoi(client):
    # Issue #49 : zone de dépôt minimale, non stylisée (le style est le sujet
    # de la 1.2.0) sur le premier message d'une conversation et sur l'envoi
    # dans une conversation déjà ouverte.
    html = client.get("/").text

    assert 'id="piece-jointe-nouvelle-conversation"' in html
    assert 'id="piece-jointe-message"' in html
    assert 'type="file"' in html


def test_front_end_televerse_la_piece_jointe_avant_denvoyer_le_message(client):
    js = client.get("/static/app.js").text

    assert "/conversations/${idConversationCiblee}/pieces-jointes" in js
    assert "televerserPieceJointe" in js
    assert "piece_jointe_id: pieceJointeId" in js


def test_front_end_televerse_la_piece_jointe_sans_conversation_pour_le_premier_message(client):
    # Ticket #45 : POST /pieces-jointes, sans conversation, seule façon de
    # joindre un fichier dès le tout premier message.
    js = client.get("/static/app.js").text

    assert '"/pieces-jointes"' in js


def test_front_end_signale_un_echec_danalyse_sans_bloquer_lenvoi(client):
    # User Story 2 : un échec d'analyse (ex. image ambiguë) doit être signalé
    # au collaborateur, jamais ignoré silencieusement.
    js = client.get("/static/app.js").text

    assert "echec_analyse" in js
    assert "pieceJointeMessageStatut" in js
    assert "pieceJointeNouvelleConversationStatut" in js


def test_front_end_expose_un_onglet_consommations_administrateur_separe_de_l_onglet_comptes(client):
    # Issue #59 : onglet séparé de l'onglet Comptes, masqué par défaut comme
    # lui (voir test_liste_avec_session_admin_retourne_les_comptes côté
    # backend pour l'API consommée), jamais de détail par conversation.
    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert 'id="onglet-bouton-consommations" hidden' in html
    assert 'id="onglet-consommations" hidden' in html
    assert "ongletBoutonConsommations.hidden = !compte.est_admin" in js
    assert '"/comptes/consommation"' in js
    assert "afficherOngletConsommations" in js


def test_front_end_naffiche_pas_la_reponse_dans_la_mauvaise_conversation(client):
    # La réponse d'un envoi ne doit s'afficher que si la conversation ouverte
    # à la résolution du fetch est toujours celle ciblée par la requête.
    js = client.get("/static/app.js").text

    assert "idConversationCiblee" in js
    assert "conversationOuverteId === idConversationCiblee" in js
