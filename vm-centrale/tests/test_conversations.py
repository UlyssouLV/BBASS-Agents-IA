import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vm_centrale.database import get_db
from vm_centrale.jetons import JetonStore, get_jeton_store
from vm_centrale.main import app
from vm_centrale.models import Conversation, PieceJointe, ProfilTravail


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour") -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post(
        "/conversations", json={"message": message}, headers=_autorisation(jeton)
    )
    return reponse.json()["conversation"]["id"]


def _reponse_resume_et_profil(resume_contexte: str, profil_travail: str | None = None) -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": profil_travail})


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
    # Prompt de style de l'appel de chat principal (spec 1.2.2), en tête.
    assert mistral_client_factice.messages_recus[0][-1] == {"role": "user", "content": "Bonjour"}

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
    # Prompt de style de l'appel de chat principal (spec 1.2.2), en tête.
    assert mistral_client_factice.messages_recus[0][-1] == {
        "role": "user",
        "content": "Question initiale",
    }
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


# --- Pagination par curseur (issue #103) -------------------------------------


def _envoyer_messages(client, mistral_client_factice, jeton, conversation_id, nombre):
    # Chaque envoi ajoute 2 messages (user + assistant) à la conversation déjà
    # créée par _creer_conversation (elle-même en compte déjà 2). Contenu
    # distinct de celui du premier échange pour ne jamais prêter à confusion
    # dans les assertions ci-dessous.
    for i in range(nombre):
        mistral_client_factice.repondre(
            f"Réponse suite {i}", resume_et_profil=_reponse_resume_et_profil(f"Résumé {i}")
        )
        client.post(
            f"/conversations/{conversation_id}/messages",
            json={"message": f"Suite {i}"},
            headers=_autorisation(jeton),
        )


def test_detail_fenetre_par_defaut_renvoie_les_plus_recents_et_signale_les_plus_anciens(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Premier message")
    _envoyer_messages(client, mistral_client_factice, jeton_valide, conversation_id, 2)
    # 6 messages en tout : le premier échange, puis 2 échanges supplémentaires.

    reponse = client.get(
        f"/conversations/{conversation_id}?limite=2", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    # La fenêtre la plus récente (pas le premier échange de la conversation),
    # dans l'ordre chronologique.
    assert [m["contenu"] for m in corps["messages"]] == ["Suite 1", "Réponse suite 1"]
    assert corps["a_des_messages_plus_anciens"] is True


def test_detail_curseur_recupere_la_page_plus_ancienne_dans_lordre(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Premier message")
    _envoyer_messages(client, mistral_client_factice, jeton_valide, conversation_id, 2)

    fenetre_recente = client.get(
        f"/conversations/{conversation_id}?limite=2", headers=_autorisation(jeton_valide)
    ).json()
    id_plus_ancien_de_la_fenetre = fenetre_recente["messages"][0]["id"]

    page_precedente = client.get(
        f"/conversations/{conversation_id}?limite=2&avant_id={id_plus_ancien_de_la_fenetre}",
        headers=_autorisation(jeton_valide),
    )

    assert page_precedente.status_code == 200
    corps = page_precedente.json()
    assert [m["contenu"] for m in corps["messages"]] == ["Suite 0", "Réponse suite 0"]
    assert corps["a_des_messages_plus_anciens"] is True


def test_detail_arrive_au_premier_message_naffiche_plus_de_messages_plus_anciens(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Premier message")
    _envoyer_messages(client, mistral_client_factice, jeton_valide, conversation_id, 2)

    fenetre_recente = client.get(
        f"/conversations/{conversation_id}?limite=2", headers=_autorisation(jeton_valide)
    ).json()
    page_intermediaire = client.get(
        f"/conversations/{conversation_id}?limite=2&avant_id={fenetre_recente['messages'][0]['id']}",
        headers=_autorisation(jeton_valide),
    ).json()

    toute_la_conversation = client.get(
        f"/conversations/{conversation_id}?limite=2&avant_id={page_intermediaire['messages'][0]['id']}",
        headers=_autorisation(jeton_valide),
    )

    assert toute_la_conversation.status_code == 200
    corps = toute_la_conversation.json()
    assert [m["contenu"] for m in corps["messages"]] == ["Premier message", "Réponse assistant"]
    # Plus aucun message avant le tout premier : aucun chargement
    # supplémentaire ne doit se déclencher côté front.
    assert corps["a_des_messages_plus_anciens"] is False


def test_detail_conversation_plus_courte_que_la_fenetre_ne_declenche_pas_de_pagination(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    reponse = client.get(
        f"/conversations/{conversation_id}?limite=20", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps["messages"]) == 2
    assert corps["a_des_messages_plus_anciens"] is False


def test_detail_conversation_plus_courte_que_la_fenetre_ne_declenche_pas_de_pagination(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    reponse = client.get(
        f"/conversations/{conversation_id}?limite=20", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps["messages"]) == 2
    assert corps["a_des_messages_plus_anciens"] is False


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


@pytest.fixture
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    # Isole les tests du répertoire par défaut (VM_CENTRALE_PIECES_JOINTES_DIR,
    # ./pieces_jointes), même convention que test_pieces_jointes.py.
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def test_supprimer_efface_les_pieces_jointes_en_base_et_sur_disque(
    client, mistral_client_factice, jeton_valide, db_session, _repertoire_pieces_jointes
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Texte extrait du PDF")
    upload = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = upload.json()["piece_jointe"]["id"]
    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    chemin_fichier = Path(_repertoire_pieces_jointes) / piece_jointe.chemin_fichier
    assert chemin_fichier.exists()

    reponse = client.delete(
        f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 204
    assert db_session.get(PieceJointe, piece_jointe_id) is None
    assert not chemin_fichier.exists()


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
    # Prompt de style (spec 1.2.2) toujours en tête, avant le résumé glissant.
    assert messages_envoyes[1] == {"role": "system", "content": "Résumé glissant"}
    assert messages_envoyes[-1] == {"role": "user", "content": "Dernier message"}
    contenus = [m["content"] for m in messages_envoyes]
    assert "Message 1" not in contenus
    # Style + résumé + au plus 3 derniers messages + le nouveau message (le
    # profil de travail est vide dans ce test, donc pas de message système en
    # plus).
    assert len(messages_envoyes) <= 6


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


def _envoyer_tour(client, mistral_client_factice, jeton: str, conversation_id: int, profil: str | None):
    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé", profil))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton),
    )


def test_profil_persiste_est_le_dernier_renvoye_remplace_pas_concatene(
    client, mistral_client_factice, jeton_valide
):
    # #110, conversation 76 : onze deltas concaténés en onze minutes, avec
    # doublons et traits de l'assistant (spec 1.3.1).
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    _envoyer_tour(client, mistral_client_factice, jeton_valide, conversation_id, "Prépare des devis Foncier.")
    _envoyer_tour(
        client, mistral_client_factice, jeton_valide, conversation_id,
        "Prépare des devis Foncier. Veut des tableaux.",
    )

    profil = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))
    assert profil.json()["contenu"] == "Prépare des devis Foncier. Veut des tableaux."


@pytest.mark.parametrize("profil_renvoye", [None, ""])
def test_profil_null_ou_vide_laisse_le_profil_intact(
    client, mistral_client_factice, jeton_valide, profil_renvoye
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    _envoyer_tour(client, mistral_client_factice, jeton_valide, conversation_id, "Prépare des devis Foncier.")
    _envoyer_tour(client, mistral_client_factice, jeton_valide, conversation_id, profil_renvoye)

    profil = client.get("/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide))
    assert profil.json()["contenu"] == "Prépare des devis Foncier."


def test_profil_au_dela_du_plafond_est_persiste_coupe_en_fin_de_phrase(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    profil_trop_long = "Prépare des devis Foncier pour Castries. " * 40

    _envoyer_tour(client, mistral_client_factice, jeton_valide, conversation_id, profil_trop_long)

    contenu = client.get(
        "/comptes/j.dupont/profil-travail", headers=_autorisation(jeton_valide)
    ).json()["contenu"]
    assert len(contenu) <= 800
    assert contenu.endswith("Castries.")
    assert profil_trop_long.startswith(contenu)


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


def test_prompt_resume_et_profil_exclut_les_traits_de_comportement_de_lassistant(
    client, mistral_client_factice, jeton_valide
):
    # Ticket #50 : l'essai du 2026-09-17 a montré le profil s'auto-renforcer
    # sur les tics de l'IA elle-même (ton coach, suggestions d'outils
    # externes) plutôt que sur une caractéristique observée chez le compte.
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé"))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    prompt_resume = mistral_client_factice.appels_structures[-1]
    assert "comportement" in prompt_resume
    assert "assistant" in prompt_resume
    assert "profil_travail" in prompt_resume
    assert "profil_travail_delta" not in prompt_resume


def test_prompt_resume_et_profil_reecrit_le_profil_depuis_les_seuls_messages_du_compte(
    client, mistral_client_factice, jeton_valide
):
    # #110, conversation 76 : le profil empilait des traits tirés des
    # réponses de l'assistant (liens, PDF, vérification) (spec 1.3.1).
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    _envoyer_tour(client, mistral_client_factice, jeton_valide, conversation_id, None)

    prompt_resume = mistral_client_factice.appels_structures[-1]
    assert "user" in prompt_resume
    assert "jamais sur une réponse de l'assistant" in prompt_resume
    for trait in ("liens", "PDF", "vérification", "ton"):
        assert trait in prompt_resume
    assert "réécrit en entier" in prompt_resume
    assert "doublon" in prompt_resume
    assert "null" in prompt_resume
    assert "800 caractères" in prompt_resume


def test_prompt_resume_et_profil_ne_fige_pas_les_propositions_de_lassistant(
    client, mistral_client_factice, jeton_valide
):
    # #110, conversation 76 : le rapport OCDE inventé par l'assistant est
    # devenu « Admin BBASS a partagé un rapport OCDE… », un lien envoyé par
    # l'assistant un lien partagé par le compte, et les « oublie Citrix »
    # n'ont pas fait sortir Citrix du résumé (spec 1.3.1).
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil("Résumé"))
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    prompt_resume = mistral_client_factice.appels_structures[-1]
    assert "proposé, non vérifié" in prompt_resume
    assert "abandonne" in prompt_resume
    assert "à l'identique" in prompt_resume
    assert "URL écrite par l'assistant" in prompt_resume
    assert "1500 caractères" in prompt_resume


def test_resume_au_dela_du_plafond_est_persiste_coupe_en_fin_de_phrase(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    phrase = "Le compte prépare un devis Foncier pour Castries. "
    resume_trop_long = phrase * 40

    mistral_client_factice.repondre(
        "Suite", resume_et_profil=_reponse_resume_et_profil(resume_trop_long)
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    conversation = db_session.get(Conversation, conversation_id)
    assert len(conversation.resume_contexte) <= 1500
    assert conversation.resume_contexte.endswith("Castries.")
    assert resume_trop_long.startswith(conversation.resume_contexte)


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


# Garde-fou URL (spec 1.3.1) : le modèle n'a aucun accès à Internet, toute
# URL que le compte n'a pas lui-même écrite dans la conversation est
# inventée.
def test_premier_message_url_inventee_ni_renvoyee_ni_persistee_texte_du_lien_conserve(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre(
        "Voir le [rapport OCDE](https://www.oecd.org/rapport-2024.pdf) et "
        "https://exemple.org/annexe.pdf pour le détail.",
        "Titre",
    )

    reponse = client.post(
        "/conversations",
        json={"message": "Raconte-moi un rapport"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert "http" not in corps["reponse"]
    assert "rapport OCDE" in corps["reponse"]
    detail = client.get(
        f"/conversations/{corps['conversation']['id']}", headers=_autorisation(jeton_valide)
    )
    contenu_assistant = detail.json()["messages"][-1]["contenu"]
    assert "http" not in contenu_assistant
    assert "rapport OCDE" in contenu_assistant


def test_premier_message_url_ecrite_par_le_compte_est_conservee(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre(
        "Votre lien : [la page](https://bbass.fr/projets/42).", "Titre"
    )

    reponse = client.post(
        "/conversations",
        json={"message": "Résume https://bbass.fr/projets/42 s'il vous plaît"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.json()["reponse"] == "Votre lien : [la page](https://bbass.fr/projets/42)."


def test_url_du_compte_sortie_de_la_fenetre_passe_et_url_inventee_est_retiree(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Mon dossier : https://bbass.fr/dossier/7"
    )
    # Deux tours de plus : le premier message utilisateur sort de la
    # fenêtre des 3 derniers messages.
    _envoyer_messages(client, mistral_client_factice, jeton_valide, conversation_id, 2)

    mistral_client_factice.repondre(
        "Votre dossier : https://bbass.fr/dossier/7 ; source : "
        "[étude](https://invente.example/etude).",
        resume_et_profil=_reponse_resume_et_profil("Résumé"),
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Redonne-moi mon lien"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "https://bbass.fr/dossier/7" in contenu
    assert "invente.example" not in contenu
    assert "étude" in contenu
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.json()["messages"][-1]["contenu"] == contenu


_REPONSE_SANS_DONNEES = (
    "Je n'ai pas accès à Internet et je n'ai pas de document pour appuyer une réponse."
)


def test_chiffre_absent_sans_document_est_remplace_par_la_phrase_fixe(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre(
        "Écart de 52,3 ans, soit 22 % de plus.",
        "Titre",
    )

    reponse = client.post(
        "/conversations",
        json={"message": "Raconte-moi un rapport avec des données"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == _REPONSE_SANS_DONNEES
    detail = client.get(
        f"/conversations/{reponse.json()['conversation']['id']}",
        headers=_autorisation(jeton_valide),
    )
    assert detail.json()["messages"][-1]["contenu"] == _REPONSE_SANS_DONNEES


def test_demande_explicite_d_inventer_conserve_le_chiffre(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Écart imaginé : 52,3 ans.", "Titre")

    reponse = client.post(
        "/conversations",
        json={"message": "Imagine un rapport avec des données"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.json()["reponse"] == "Écart imaginé : 52,3 ans."


def test_chiffre_ecrit_par_le_compte_reste_et_le_chiffre_absent_part(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre(
        "Le taux est 1,7 %, et l'écart atteint 52,3 ans.",
        "Titre",
    )

    reponse = client.post(
        "/conversations",
        json={"message": "Le taux indiqué est 1,7 %. Résume-le."},
        headers=_autorisation(jeton_valide),
    )

    contenu = reponse.json()["reponse"]
    assert "1,7" in contenu
    assert "52,3" not in contenu
    assert contenu != _REPONSE_SANS_DONNEES


def test_piece_jointe_conserve_le_chiffre_de_lextrait(
    client, mistral_client_factice, jeton_valide, _repertoire_pieces_jointes
):
    mistral_client_factice.repondre_ocr("Besoins non satisfaits : 1,7 %.")
    upload = client.post(
        "/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = upload.json()["piece_jointe"]["id"]
    mistral_client_factice.repondre(
        "Le document indique 1,7 % et un écart de 52,3 ans.",
        "Titre",
    )

    reponse = client.post(
        "/conversations",
        json={"message": "Que dit ce document ?", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    contenu = reponse.json()["reponse"]
    assert reponse.status_code == 200
    assert "1,7" in contenu
    assert "52,3" not in contenu
    assert contenu != _REPONSE_SANS_DONNEES


def test_consigne_de_style_commence_par_la_capacite_reelle(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    consigne = mistral_client_factice.appels_reponse[0][0]
    assert consigne["role"] == "system"
    premiere_ligne = consigne["content"].splitlines()[0]
    assert "aucun accès à Internet" in premiere_ligne
    assert "lien" in premiere_ligne
    assert "vérifié" in premiere_ligne
    assert "n'inventes jamais" in premiere_ligne
    assert "question de confirmation" in premiere_ligne
    assert "que l'utilisateur a lui-même écrite dans cette conversation" in consigne["content"]
    assert "que tu connais avec certitude" not in consigne["content"]


def test_titre_genere_est_nettoye_de_sa_mise_en_forme_markdown(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "## **Bilan** du projet 10*2")

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.json()["conversation"]["titre"] == "Bilan du projet 10*2"
