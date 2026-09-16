from datetime import datetime

from vm_centrale.models import Conversation, Message


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour") -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post(
        "/conversations", json={"message": message}, headers=_autorisation(jeton)
    )
    return reponse.json()["conversation"]["id"]


def _jeton_admin(client, seed_compte, identifiant: str = "a.martin") -> str:
    seed_compte(
        identifiant, "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Alice", nom="Martin", est_admin=True,
    )
    reponse = client.post(
        "/auth", json={"identifiant": identifiant, "mot_de_passe": "correcthorsebatterystaple"}
    )
    return reponse.json()["jeton"]


def test_premier_message_cree_la_conversation_persiste_les_messages_et_titre(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?", "Salutations")

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["conversation"]["titre"] == "Salutations"
    assert corps["reponse"] == "Bonjour, comment puis-je vous aider ?"
    assert mistral_client_factice.messages_recus[0] == "Bonjour"

    conversation_id = corps["conversation"]["id"]
    conversation = db_session.get(Conversation, conversation_id)
    assert conversation is not None
    assert conversation.identifiant_compte == "j.dupont"
    assert conversation.titre == "Salutations"

    messages = (
        db_session.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id)
        .all()
    )
    assert [(m.role, m.contenu) for m in messages] == [
        ("user", "Bonjour"),
        ("assistant", "Bonjour, comment puis-je vous aider ?"),
    ]


def test_titre_genere_par_un_appel_mistral_dedie_a_partir_du_premier_echange(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre auto-généré")

    reponse = client.post(
        "/conversations", json={"message": "Question initiale"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json()["conversation"]["titre"] == "Titre auto-généré"
    # Un appel dédié, distinct de celui produisant la réponse de chat.
    assert len(mistral_client_factice.messages_recus) == 2
    assert mistral_client_factice.messages_recus[0] == "Question initiale"
    assert "Question initiale" in mistral_client_factice.messages_recus[1]
    assert "Réponse" in mistral_client_factice.messages_recus[1]


def test_sans_jeton_est_refuse_et_aucune_conversation_nest_creee(
    client, mistral_client_factice, db_session
):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []
    assert db_session.query(Conversation).count() == 0


def test_jeton_invalide_est_refuse_et_aucune_conversation_nest_creee(
    client, mistral_client_factice, db_session
):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation("jeton-inconnu")
    )

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []
    assert db_session.query(Conversation).count() == 0


def test_echec_appel_mistral_ne_cree_aucune_conversation(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 502
    assert db_session.query(Conversation).count() == 0
    assert db_session.query(Message).count() == 0


def test_message_vide_est_rejete(client, jeton_valide):
    reponse = client.post(
        "/conversations", json={"message": ""}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 422


def test_message_trop_long_est_rejete(client, jeton_valide):
    reponse = client.post(
        "/conversations", json={"message": "x" * 8001}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 422


def test_liste_ne_renvoie_que_les_conversations_du_compte_du_jeton(
    client, mistral_client_factice, jeton_valide, jeton_store
):
    id_propre = _creer_conversation(client, mistral_client_factice, jeton_valide, "Sujet A")

    jeton_autre_compte = jeton_store.emettre("n.durand")
    _creer_conversation(client, mistral_client_factice, jeton_autre_compte, "Sujet B")

    reponse = client.get("/conversations", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    corps = reponse.json()
    assert [c["id"] for c in corps] == [id_propre]
    assert corps[0]["titre"] == "Titre"


def test_liste_triee_par_activite_recente(
    client, mistral_client_factice, jeton_valide, db_session
):
    id_ancienne = _creer_conversation(client, mistral_client_factice, jeton_valide, "Ancienne")
    id_recente = _creer_conversation(client, mistral_client_factice, jeton_valide, "Récente")

    conversation_ancienne = db_session.get(Conversation, id_ancienne)
    conversation_ancienne.date_derniere_activite = datetime(2020, 1, 1)
    conversation_recente = db_session.get(Conversation, id_recente)
    conversation_recente.date_derniere_activite = datetime(2024, 1, 1)
    db_session.commit()

    reponse = client.get("/conversations", headers=_autorisation(jeton_valide))

    assert [c["id"] for c in reponse.json()] == [id_recente, id_ancienne]


def test_liste_sans_jeton_est_refusee(client):
    reponse = client.get("/conversations")

    assert reponse.status_code == 401


def test_detail_renvoie_la_conversation_et_ses_messages(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    reponse = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["id"] == conversation_id
    assert corps["titre"] == "Titre"
    assert [(m["role"], m["contenu"]) for m in corps["messages"]] == [
        ("user", "Bonjour"),
        ("assistant", "Réponse assistant"),
    ]


def test_detail_dune_conversation_dun_autre_compte_renvoie_404(
    client, mistral_client_factice, jeton_valide, jeton_store
):
    jeton_autre_compte = jeton_store.emettre("n.durand")
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_autre_compte)

    reponse = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 404


def test_detail_dune_conversation_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_admin))

    assert reponse.status_code == 404


def test_detail_dune_conversation_inexistante_renvoie_404(client, jeton_valide):
    reponse = client.get("/conversations/999", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 404


def test_detail_sans_jeton_est_refuse(client):
    reponse = client.get("/conversations/1")

    assert reponse.status_code == 401


def test_renommer_change_le_titre(client, mistral_client_factice, jeton_valide, db_session):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.patch(
        f"/conversations/{conversation_id}",
        json={"titre": "Nouveau titre"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json()["titre"] == "Nouveau titre"
    assert db_session.get(Conversation, conversation_id).titre == "Nouveau titre"


def test_renommer_une_conversation_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.patch(
        f"/conversations/{conversation_id}",
        json={"titre": "Nouveau titre"},
        headers=_autorisation(jeton_admin),
    )

    assert reponse.status_code == 404


def test_renommer_avec_titre_vide_est_rejete(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.patch(
        f"/conversations/{conversation_id}",
        json={"titre": ""},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 422


def test_renommer_sans_jeton_est_refuse(client):
    reponse = client.patch("/conversations/1", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 401


def test_supprimer_efface_la_conversation_et_ses_messages(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.delete(
        f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 204
    assert db_session.get(Conversation, conversation_id) is None
    assert db_session.query(Message).filter(Message.conversation_id == conversation_id).count() == 0


def test_supprimer_une_conversation_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte, db_session
):
    jeton_admin = _jeton_admin(client, seed_compte)
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_admin))

    assert reponse.status_code == 404
    assert db_session.get(Conversation, conversation_id) is not None


def test_supprimer_sans_jeton_est_refuse(client):
    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 401
