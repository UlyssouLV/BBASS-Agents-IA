import json
from datetime import datetime, timezone

from flux_sse import erreur, evenements, fin, statuts

from vm_centrale.models import Message, PieceJointe

# Envoi d'un message en flux SSE (spec 1.4.4, ADR-0016) : des statuts, puis
# `fin` (le JSON d'avant) ou `erreur` ; les refus d'avant le tour restent de
# vrais statuts HTTP.


_RESUME = json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _creer_conversation(client, mistral_client_factice, jeton: str) -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return fin(reponse)["conversation"]["id"]


def test_envoi_sans_outil_publie_reflexion_puis_verification_puis_la_fin(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre("Voici la suite", resume_et_profil=_RESUME)

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert evenements(reponse) == [
        ("statut", {"libelle": "Réflexion…"}),
        ("statut", {"libelle": "Vérification de la réponse…"}),
        ("fin", {"reponse": "Voici la suite", "tokens_contexte": 10, "fenetre_contexte": 262_144}),
    ]


def test_premier_message_publie_le_titrage_avant_la_fin(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour, que puis-je faire ?", "Salutations")

    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert statuts(reponse) == ["Réflexion…", "Vérification de la réponse…", "Titre de la conversation…"]
    corps = fin(reponse)
    assert corps["conversation"]["titre"] == "Salutations"
    assert corps["reponse"] == "Bonjour, que puis-je faire ?"


def test_echec_mistral_pendant_le_tour_donne_un_evenement_erreur_et_rien_d_enregistre(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert erreur(reponse) == {"status": 502, "detail": "Le relais Mistral est indisponible"}
    assert db_session.query(Message).filter(Message.conversation_id == conversation_id).count() == 2


def test_conversation_introuvable_reste_un_vrai_404(client, jeton_valide):
    reponse = client.post(
        "/conversations/999/messages", json={"message": "Et ensuite ?"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 404
    assert reponse.json() == {"detail": "Conversation introuvable"}


def test_jeton_invalide_reste_un_vrai_401(client):
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation("inconnu"))

    assert reponse.status_code == 401


def test_piece_jointe_deja_liee_reste_un_vrai_400(client, mistral_client_factice, jeton_valide, db_session):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    message = db_session.query(Message).filter(Message.conversation_id == conversation_id).first()
    piece_jointe = PieceJointe(
        identifiant_compte="j.dupont",
        conversation_id=conversation_id,
        message_id=message.id,
        nom_fichier="note.txt",
        type_mime="text/plain",
        taille_octets=1,
        chemin_fichier="j.dupont/note.txt",
        contenu_extrait="x",
        echec_analyse=False,
        date_creation=datetime.now(timezone.utc),
    )
    db_session.add(piece_jointe)
    db_session.commit()

    reponse = client.post(
        "/conversations", json={"message": "Bonjour", "piece_jointe_id": piece_jointe.id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?", "piece_jointe_id": piece_jointe.id},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 400
    assert reponse.json() == {"detail": "Pièce jointe déjà liée à un message"}


def test_le_tour_est_enregistre_meme_si_le_client_ferme_le_flux(
    client, mistral_client_factice, jeton_valide, fabrique_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre("Réponse jamais lue", resume_et_profil=_RESUME)

    with client.stream(
        "POST",
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    ) as flux:
        premier = next(flux.iter_lines())
    assert premier == "event: statut"

    # Les deux tours (création, puis celui-ci) sont allés au bout.
    assert fabrique_session.attendre_tours(2)
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert [m["contenu"] for m in detail.json()["messages"]][-2:] == ["Et ensuite ?", "Réponse jamais lue"]


def test_rejeu_avec_la_meme_cle_ne_renvoie_que_la_fin(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre("Réponse unique", resume_et_profil=_RESUME)
    requete = {"message": "Et ensuite ?", "cle_idempotence": "cle-1"}
    premiere = client.post(
        f"/conversations/{conversation_id}/messages", json=requete, headers=_autorisation(jeton_valide)
    )
    appels_avant_rejeu = len(mistral_client_factice.messages_recus)

    rejeu = client.post(
        f"/conversations/{conversation_id}/messages", json=requete, headers=_autorisation(jeton_valide)
    )

    assert evenements(rejeu) == [("fin", fin(premiere))]
    assert len(mistral_client_factice.messages_recus) == appels_avant_rejeu
