from vm_centrale.models import Conversation, Message


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


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
