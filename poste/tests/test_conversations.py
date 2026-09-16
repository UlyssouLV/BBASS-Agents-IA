from datetime import datetime, timezone

import httpx

from poste.vm_centrale_client import (
    Conversation,
    ConversationCree,
    ConversationDetail,
    ConversationIntrouvableError,
    ConversationResume,
    JetonInvalideError,
    Message,
)


def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def test_creer_une_conversation_avec_session_active_retourne_le_titre_et_la_reponse(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(
        ConversationCree(
            conversation=ConversationResume(id=1, titre="Salutations"),
            reponse="Bonjour, comment puis-je vous aider ?",
        )
    )

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 200
    assert reponse.json() == {
        "conversation": {"id": 1, "titre": "Salutations"},
        "reponse": "Bonjour, comment puis-je vous aider ?",
    }
    assert vm_centrale_client_factice._messages_creation_conversation == ["Bonjour"]
    assert vm_centrale_client_factice._jetons_creation_conversation == ["jeton-factice"]


def test_creer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_creer_une_conversation_message_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations", json={"message": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._messages_creation_conversation == []


def test_creer_une_conversation_message_trop_long_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations", json={"message": "x" * 8001})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._messages_creation_conversation == []


def test_creer_une_conversation_vm_indisponible_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_creer_une_conversation_jeton_invalide_ferme_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_echoue(JetonInvalideError())

    reponse_creation = client.post("/conversations", json={"message": "Bonjour"})
    reponse_compte = client.get("/compte")

    assert reponse_creation.status_code == 401
    assert reponse_compte.status_code == 401


def test_lister_les_conversations_avec_session_active(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    date_activite = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.liste_conversations_retourne(
        [Conversation(id=1, titre="Salutations", date_derniere_activite=date_activite)]
    )

    reponse = client.get("/conversations")

    assert reponse.status_code == 200
    assert reponse.json() == [
        {"id": 1, "titre": "Salutations", "date_derniere_activite": "2026-09-10T12:00:00Z"}
    ]


def test_lister_les_conversations_sans_session_active_est_refuse(client):
    reponse = client.get("/conversations")

    assert reponse.status_code == 401


def test_consulter_une_conversation_retourne_le_detail_et_les_messages(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    maintenant = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.detail_conversation_retourne(
        ConversationDetail(
            id=1,
            titre="Salutations",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
            messages=[
                Message(id=1, role="user", contenu="Bonjour", date_creation=maintenant),
                Message(id=2, role="assistant", contenu="Bonjour !", date_creation=maintenant),
            ],
        )
    )

    reponse = client.get("/conversations/1")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["titre"] == "Salutations"
    assert [(m["role"], m["contenu"]) for m in corps["messages"]] == [
        ("user", "Bonjour"),
        ("assistant", "Bonjour !"),
    ]
    assert vm_centrale_client_factice._ids_detail_conversation == [1]


def test_consulter_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.detail_conversation_echoue(ConversationIntrouvableError())

    reponse = client.get("/conversations/42")

    assert reponse.status_code == 404
    assert reponse.json()["detail"]


def test_consulter_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.get("/conversations/1")

    assert reponse.status_code == 401


def test_renommer_une_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    date_activite = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.renommage_conversation_reussit(
        Conversation(id=1, titre="Nouveau titre", date_derniere_activite=date_activite)
    )

    reponse = client.patch("/conversations/1", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 200
    assert reponse.json()["titre"] == "Nouveau titre"
    assert vm_centrale_client_factice._requetes_renommage_conversation == [
        {"conversation_id": 1, "titre": "Nouveau titre"}
    ]


def test_renommer_une_conversation_titre_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.patch("/conversations/1", json={"titre": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_renommage_conversation == []


def test_renommer_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.renommage_conversation_echoue(ConversationIntrouvableError())

    reponse = client.patch("/conversations/42", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 404


def test_renommer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.patch("/conversations/1", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 401


def test_supprimer_une_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 204
    assert vm_centrale_client_factice._ids_suppression_conversation == [1]


def test_supprimer_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.suppression_conversation_echoue(ConversationIntrouvableError())

    reponse = client.delete("/conversations/42")

    assert reponse.status_code == 404


def test_supprimer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 401


def test_envoyer_un_message_dans_une_conversation_existante(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_reussit("Réponse suivante")

    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Réponse suivante"}
    assert vm_centrale_client_factice._requetes_envoi_message_conversation == [
        {"conversation_id": 1, "message": "Et ensuite ?"}
    ]
    assert vm_centrale_client_factice._jetons_envoi_message_conversation == ["jeton-factice"]


def test_envoyer_un_message_message_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations/1/messages", json={"message": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_envoi_message_conversation == []


def test_envoyer_un_message_dans_une_conversation_introuvable_retourne_404(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_echoue(ConversationIntrouvableError())

    reponse = client.post("/conversations/42/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 404


def test_envoyer_un_message_sans_session_active_est_refuse(client):
    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 401


def test_envoyer_un_message_jeton_revoque_pendant_l_usage_ferme_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_echoue(JetonInvalideError())

    reponse_message = client.post("/conversations/1/messages", json={"message": "Bonjour"})
    reponse_compte = client.get("/compte")

    assert reponse_message.status_code == 401
    assert reponse_compte.status_code == 401


def test_creer_une_conversation_relaie_la_cle_idempotence_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(
        ConversationCree(conversation=ConversationResume(id=1, titre="Salutations"), reponse="Bonjour")
    )

    client.post("/conversations", json={"message": "Bonjour", "cle_idempotence": "cle-1"})

    assert vm_centrale_client_factice._cles_idempotence_creation_conversation == ["cle-1"]


def test_creer_une_conversation_sans_cle_idempotence_en_relaie_labsence(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(
        ConversationCree(conversation=ConversationResume(id=1, titre="Salutations"), reponse="Bonjour")
    )

    client.post("/conversations", json={"message": "Bonjour"})

    assert vm_centrale_client_factice._cles_idempotence_creation_conversation == [None]


def test_envoyer_un_message_relaie_la_cle_idempotence_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_reussit("Réponse")

    client.post(
        "/conversations/1/messages",
        json={"message": "Et ensuite ?", "cle_idempotence": "cle-msg-1"},
    )

    assert vm_centrale_client_factice._cles_idempotence_envoi_message_conversation == ["cle-msg-1"]
