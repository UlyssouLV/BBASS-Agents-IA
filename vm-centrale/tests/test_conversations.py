import json
from datetime import datetime

from fastapi.testclient import TestClient

from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.main import app
from vm_centrale.models import Conversation, ProfilTravail


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour") -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post(
        "/conversations", json={"message": message}, headers=_autorisation(jeton)
    )
    return reponse.json()["conversation"]["id"]


def _reponse_resume_et_profil(resume_contexte: str, profil_travail_delta: str = "") -> str:
    return json.dumps(
        {"resume_contexte": resume_contexte, "profil_travail_delta": profil_travail_delta}
    )


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
    client, mistral_client_factice, jeton_valide
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
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.status_code == 200
    assert detail.json()["titre"] == "Salutations"
    assert [(m["role"], m["contenu"]) for m in detail.json()["messages"]] == [
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
    client, mistral_client_factice
):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    # Aucun appel Mistral : le code ne persiste jamais de conversation sans
    # être passé par cet appel en premier (cf. creer_conversation), donc
    # cette absence suffit à garantir qu'aucune conversation n'a été créée.
    assert mistral_client_factice.messages_recus == []


def test_jeton_invalide_est_refuse_et_aucune_conversation_nest_creee(
    client, mistral_client_factice
):
    mistral_client_factice.repondre("Ne devrait jamais être retournée")

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation("jeton-inconnu")
    )

    assert reponse.status_code == 401
    assert mistral_client_factice.messages_recus == []


def test_echec_appel_mistral_ne_cree_aucune_conversation(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 502
    assert client.get("/conversations", headers=_autorisation(jeton_valide)).json() == []


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


def test_renommer_change_le_titre(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.patch(
        f"/conversations/{conversation_id}",
        json={"titre": "Nouveau titre"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json()["titre"] == "Nouveau titre"
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.json()["titre"] == "Nouveau titre"


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
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.delete(
        f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 204
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.status_code == 404


def test_supprimer_une_conversation_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_admin))

    assert reponse.status_code == 404
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.status_code == 200


def test_supprimer_sans_jeton_est_refuse(client):
    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 401


def test_envoyer_message_persiste_le_message_et_la_reponse(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    mistral_client_factice.repondre(
        "Suite de la réponse", resume_et_profil=_reponse_resume_et_profil("Résumé")
    )

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Suite de la réponse"}

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert [(m["role"], m["contenu"]) for m in detail.json()["messages"]] == [
        ("user", "Bonjour"),
        ("assistant", "Réponse assistant"),
        ("user", "Et ensuite ?"),
        ("assistant", "Suite de la réponse"),
    ]


def test_envoyer_message_met_a_jour_la_date_derniere_activite(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    conversation = db_session.get(Conversation, conversation_id)
    conversation.date_derniere_activite = datetime(2020, 1, 1)
    db_session.commit()

    mistral_client_factice.repondre(
        "Suite de la réponse", resume_et_profil=_reponse_resume_et_profil("Résumé")
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.json()["date_derniere_activite"] > "2020-01-01T00:00:00"


def test_prompt_envoye_ne_contient_jamais_lintegralite_de_lhistorique(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Message 1")
    for i in range(2, 5):
        mistral_client_factice.repondre(
            f"Réponse {i}", resume_et_profil=_reponse_resume_et_profil(f"Résumé {i}")
        )
        client.post(
            f"/conversations/{conversation_id}/messages",
            json={"message": f"Message {i}"},
            headers=_autorisation(jeton_valide),
        )

    conversation = db_session.get(Conversation, conversation_id)
    conversation.resume_contexte = "Résumé glissant"
    db_session.commit()

    mistral_client_factice.repondre(
        "Réponse finale", resume_et_profil=_reponse_resume_et_profil("Résumé final")
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Dernier message"},
        headers=_autorisation(jeton_valide),
    )

    # Appel de réponse de chat de ce tour (distinct de l'appel résumé+profil,
    # lancé en parallèle — voir ClientMistralFactice.appels_reponse) :
    # l'ordre d'arrivée entre les deux n'est pas garanti, donc pas question
    # d'indexer messages_recus par position ici.
    messages_envoyes = mistral_client_factice.appels_reponse[-1]
    assert messages_envoyes[0] == {"role": "system", "content": "Résumé glissant"}
    assert messages_envoyes[-1] == {"role": "user", "content": "Dernier message"}
    contenus = [m["content"] for m in messages_envoyes]
    assert "Message 1" not in contenus
    # Résumé + au plus 3 derniers messages + le nouveau message (le profil de
    # travail est vide dans ce test, donc pas de message système en plus).
    assert len(messages_envoyes) <= 5


def test_envoyer_message_echec_appel_mistral_ne_persiste_rien(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert len(detail.json()["messages"]) == 2


def test_envoyer_message_dans_une_conversation_dun_autre_compte_renvoie_404(
    client, mistral_client_factice, jeton_valide, jeton_store
):
    jeton_autre_compte = jeton_store.emettre("n.durand")
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_autre_compte)

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404


def test_envoyer_message_dans_une_conversation_inexistante_renvoie_404(client, jeton_valide):
    reponse = client.post(
        "/conversations/999/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404


def test_envoyer_message_sans_jeton_est_refuse(client):
    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 401


def test_envoyer_message_vide_est_rejete(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": ""},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 422


def test_envoyer_message_trop_long_est_rejete(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "x" * 8001},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 422


def test_resume_et_profil_se_mettent_a_jour_une_fois_le_seuil_de_3_messages_depasse(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre(
        "Suite",
        resume_et_profil=_reponse_resume_et_profil("Nouveau résumé", "Travaille sur des devis Foncier"),
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    # resume_contexte n'est exposé par aucun endpoint (mémoire de travail
    # interne, jamais affichée) : seule façon de l'observer ici.
    conversation = db_session.get(Conversation, conversation_id)
    assert conversation.resume_contexte == "Nouveau résumé"

    profil = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))
    assert "Travaille sur des devis Foncier" in profil.json()["contenu"]


def test_resume_se_met_a_jour_meme_sans_delta_de_profil(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Nouveau résumé"))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    conversation = db_session.get(Conversation, conversation_id)
    assert conversation.resume_contexte == "Nouveau résumé"
    profil = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))
    assert profil.json()["contenu"] == ""


def test_prompt_resume_et_profil_ninclut_jamais_lidentite_comme_a_determiner(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    seed_compte(
        "j.dupont", "correcthorsebatterystaple", agence="Castries", poles=["Foncier"],
        prenom="Jean", nom="Dupont",
    )
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé"))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    # L'appel résumé+profil de ce tour (distinct de l'appel de réponse de
    # chat, lancé en parallèle — voir ClientMistralFactice.appels_structures).
    prompt_resume = mistral_client_factice.appels_structures[-1]
    assert "Jean Dupont" in prompt_resume
    assert "Foncier" in prompt_resume
    assert "jamais" in prompt_resume
    assert "identité" in prompt_resume


def test_profil_travail_renvoie_le_contenu_du_compte_du_jeton(client, jeton_valide, db_session):
    db_session.add(
        ProfilTravail(
            identifiant_compte="j.dupont",
            contenu="Aime les tableaux de suivi",
            date_derniere_maj=datetime(2024, 1, 1),
        )
    )
    db_session.commit()

    reponse = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    assert reponse.json()["contenu"] == "Aime les tableaux de suivi"


def test_profil_travail_vide_si_jamais_calcule(client, jeton_valide):
    reponse = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    assert reponse.json()["contenu"] == ""


def test_profil_travail_dun_autre_compte_renvoie_403(client, jeton_store):
    jeton_autre_compte = jeton_store.emettre("n.durand")

    reponse = client.get(
        "/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_autre_compte)
    )

    assert reponse.status_code == 403


def test_profil_travail_dun_autre_compte_renvoie_403_meme_avec_un_jeton_admin(
    client, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)

    reponse = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_admin))

    assert reponse.status_code == 403


def test_profil_travail_sans_jeton_est_refuse(client):
    reponse = client.get("/comptes/j.dupont/profil-travail")

    assert reponse.status_code == 401


def test_profil_travail_patch_nexiste_pas(client, jeton_valide):
    reponse = client.patch(
        "/comptes/j.dupont/profil-travail",
        json={"contenu": "x"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code in (404, 405)


def test_profil_travail_delete_nexiste_pas(client, jeton_valide):
    reponse = client.delete(
        "/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code in (404, 405)


# --- Profil de travail inclus dans le prompt de réponse de chat -------------


def test_profil_de_travail_est_inclus_dans_le_prompt_de_reponse_de_chat(
    client, mistral_client_factice, jeton_valide, db_session
):
    db_session.add(
        ProfilTravail(
            identifiant_compte="j.dupont",
            contenu="Travaille sur des dossiers Foncier",
            date_derniere_maj=datetime(2024, 1, 1),
        )
    )
    db_session.commit()
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé"))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    messages_envoyes = mistral_client_factice.appels_reponse[-1]
    contenus_systeme = [m["content"] for m in messages_envoyes if m["role"] == "system"]
    assert any("Travaille sur des dossiers Foncier" in contenu for contenu in contenus_systeme)


# --- Réponse résumé+profil malformée -----------------------------------------


def test_envoyer_message_reponse_resume_et_profil_malformee_retourne_une_erreur_propre(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    mistral_client_factice.repondre("Suite", resume_et_profil="ceci n'est pas du JSON valide")

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert len(detail.json()["messages"]) == 2


# --- Clé d'idempotence (déduplication d'une requête rejouée) ----------------


def test_creer_conversation_avec_la_meme_cle_idempotence_ne_cree_quune_conversation(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour, comment puis-je vous aider ?", "Salutations")

    premiere = client.post(
        "/conversations",
        json={"message": "Bonjour", "cle_idempotence": "cle-1"},
        headers=_autorisation(jeton_valide),
    )
    seconde = client.post(
        "/conversations",
        json={"message": "Bonjour", "cle_idempotence": "cle-1"},
        headers=_autorisation(jeton_valide),
    )

    assert premiere.status_code == 200
    assert seconde.status_code == 200
    assert seconde.json() == premiere.json()
    # Un seul tour d'appels Mistral (réponse + titrage) : la seconde requête
    # n'a rien rejoué.
    assert len(mistral_client_factice.messages_recus) == 2
    assert len(client.get("/conversations", headers=_autorisation(jeton_valide)).json()) == 1


def test_envoyer_message_avec_la_meme_cle_idempotence_ne_persiste_quune_fois(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé"))

    premiere = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?", "cle_idempotence": "cle-msg-1"},
        headers=_autorisation(jeton_valide),
    )
    seconde = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?", "cle_idempotence": "cle-msg-1"},
        headers=_autorisation(jeton_valide),
    )

    assert premiere.status_code == 200
    assert seconde.json() == premiere.json()
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert [(m["role"], m["contenu"]) for m in detail.json()["messages"]] == [
        ("user", "Bonjour"),
        ("assistant", "Réponse assistant"),
        ("user", "Et ensuite ?"),
        ("assistant", "Suite"),
    ]


# --- La clé API Mistral ne fuite jamais --------------------------------------
# Restaure la couverture de l'ancien test_relais.py (retiré avec /relais,
# #36) : le même bloc except Exception large existe toujours ici
# (creer_conversation, envoyer_message).


def test_creer_conversation_echec_mistral_ne_revele_jamais_la_cle_api(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.echouer(RuntimeError("401 Unauthorized: Bearer sk-secrete-cle-api-mistral"))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert "sk-secrete-cle-api-mistral" not in reponse.text


def test_envoyer_message_echec_mistral_ne_revele_jamais_la_cle_api(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.echouer(RuntimeError("401 Unauthorized: Bearer sk-secrete-cle-api-mistral"))

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert "sk-secrete-cle-api-mistral" not in reponse.text


def test_cle_api_manquante_retourne_une_erreur_propre_et_pas_un_plantage(db_session, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    def override_get_db():
        yield db_session

    jeton_store = JetonStore(db_session)
    jeton = jeton_store.emettre("j.dupont")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_jeton_store] = lambda: jeton_store
    try:
        with TestClient(app) as test_client:
            reponse = test_client.post(
                "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton)
            )
    finally:
        app.dependency_overrides.clear()

    assert reponse.status_code == 502
    assert "MISTRAL_API_KEY" not in reponse.text
