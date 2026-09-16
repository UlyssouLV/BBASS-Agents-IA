import json
from pathlib import Path

import pytest

from vm_centrale.models import PieceJointe

_PDF = ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail_delta": ""})


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    # Voir tests/test_pieces_jointes.py : isole chaque test du répertoire par
    # défaut (VM_CENTRALE_PIECES_JOINTES_DIR).
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


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


def _televerser_sans_conversation(client, jeton: str, fichier=_PDF) -> int:
    reponse = client.post(
        "/pieces-jointes", files={"fichier": fichier}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 201
    return reponse.json()["piece_jointe"]["id"]


# --- POST /pieces-jointes (upload sans conversation existante) --------------


def test_upload_sans_conversation_renvoie_201_et_ne_rattache_a_aucune_conversation(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_ocr("Texte extrait")

    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    assert piece_jointe.conversation_id is None
    assert piece_jointe.message_id is None
    assert piece_jointe.identifiant_compte == "j.dupont"
    assert piece_jointe.contenu_extrait == "Texte extrait"


def test_upload_sans_conversation_sans_jeton_est_refuse(client):
    reponse = client.post("/pieces-jointes", files={"fichier": _PDF})

    assert reponse.status_code == 401


def test_upload_sans_conversation_type_non_supporte_renvoie_400(client, jeton_valide):
    reponse = client.post(
        "/pieces-jointes",
        files={"fichier": ("notes.txt", b"du texte", "text/plain")},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 400


# --- Référencer à la création de la conversation (POST /conversations) ------


def test_creer_conversation_avec_piece_jointe_injecte_le_contenu_extrait_et_la_rattache(
    client, mistral_client_factice, jeton_valide, db_session, _repertoire_pieces_jointes
):
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.repondre("Voici mon analyse", "Titre pièce jointe")
    reponse = client.post(
        "/conversations",
        json={"message": "Que penses-tu de ce document ?", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    conversation_id = reponse.json()["conversation"]["id"]

    # Le premier appel .chat() de ce tour est celui de la réponse de chat
    # (le second, le titrage, ne reçoit pas la pièce jointe).
    messages_reponse = mistral_client_factice.messages_recus[0]
    assert isinstance(messages_reponse, list)
    contenus_systeme = [m["content"] for m in messages_reponse if m["role"] == "system"]
    assert any("Plan de masse détaillé" in contenu for contenu in contenus_systeme)

    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    assert piece_jointe.conversation_id == conversation_id
    assert piece_jointe.message_id is not None

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    message_utilisateur_id = detail.json()["messages"][0]["id"]
    assert piece_jointe.message_id == message_utilisateur_id

    # Fichier déplacé du dépôt temporaire vers le chemin canonique de la spec.
    chemin_attendu = (
        Path(_repertoire_pieces_jointes)
        / "j.dupont"
        / str(conversation_id)
        / f"{piece_jointe_id}-document.pdf"
    )
    assert chemin_attendu.exists()
    assert chemin_attendu.read_bytes() == b"%PDF-1.4 contenu factice"


def test_creer_conversation_avec_piece_jointe_dune_autre_conversation_renvoie_404(
    client, mistral_client_factice, jeton_valide
):
    autre_conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Contenu")
    reponse_upload = client.post(
        f"/conversations/{autre_conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = reponse_upload.json()["piece_jointe"]["id"]

    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post(
        "/conversations",
        json={"message": "Bonjour", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404


def test_creer_conversation_avec_piece_jointe_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)
    mistral_client_factice.repondre_ocr("Contenu")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post(
        "/conversations",
        json={"message": "Bonjour", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_admin),
    )

    assert reponse.status_code == 404


def test_creer_conversation_avec_piece_jointe_inexistante_renvoie_404(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post(
        "/conversations",
        json={"message": "Bonjour", "piece_jointe_id": 999},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404


def test_creer_conversation_echec_mistral_ne_rattache_pas_la_piece_jointe(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_ocr("Contenu")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))
    reponse = client.post(
        "/conversations",
        json={"message": "Bonjour", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    assert piece_jointe.conversation_id is None
    assert piece_jointe.message_id is None
    assert client.get("/conversations", headers=_autorisation(jeton_valide)).json() == []


# --- Référencer à l'envoi d'un message (POST /conversations/{id}/messages) --


def test_envoyer_message_avec_piece_jointe_injecte_le_contenu_extrait_et_la_rattache(
    client, mistral_client_factice, jeton_valide, db_session, _repertoire_pieces_jointes
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Tableau de chiffres du devis")
    reponse_upload = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = reponse_upload.json()["piece_jointe"]["id"]

    mistral_client_factice.repondre(
        "Voici mon analyse du devis", resume_et_profil=_reponse_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Regarde ce devis", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    messages_envoyes = mistral_client_factice.appels_reponse[-1]
    contenus_systeme = [m["content"] for m in messages_envoyes if m["role"] == "system"]
    assert any("Tableau de chiffres du devis" in contenu for contenu in contenus_systeme)

    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    assert piece_jointe.message_id is not None
    assert piece_jointe.conversation_id == conversation_id

    # Uploadée directement sur cette conversation (chemin déjà canonique) :
    # aucun déplacement de fichier nécessaire.
    chemin_attendu = (
        Path(_repertoire_pieces_jointes)
        / "j.dupont"
        / str(conversation_id)
        / f"{piece_jointe_id}-document.pdf"
    )
    assert chemin_attendu.exists()


def test_envoyer_message_avec_piece_jointe_televersee_avant_toute_conversation(
    client, mistral_client_factice, jeton_valide, db_session, _repertoire_pieces_jointes
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Notes de chantier")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.repondre("Bien reçu", resume_et_profil=_reponse_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Voici mes notes", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    piece_jointe = db_session.get(PieceJointe, piece_jointe_id)
    assert piece_jointe.conversation_id == conversation_id
    assert piece_jointe.message_id is not None

    chemin_attendu = (
        Path(_repertoire_pieces_jointes)
        / "j.dupont"
        / str(conversation_id)
        / f"{piece_jointe_id}-document.pdf"
    )
    assert chemin_attendu.exists()


def test_envoyer_message_avec_piece_jointe_deja_liee_a_un_message_renvoie_400(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Contenu")
    reponse_upload = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = reponse_upload.json()["piece_jointe"]["id"]

    mistral_client_factice.repondre(
        "Première utilisation", resume_et_profil=_reponse_resume_et_profil()
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Regarde ceci", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    mistral_client_factice.repondre("Ne devrait jamais être appelé")
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et celui-ci aussi ?", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 400


def test_envoyer_message_avec_piece_jointe_dune_autre_conversation_renvoie_404(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Sujet A")
    autre_conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Sujet B")
    mistral_client_factice.repondre_ocr("Contenu")
    reponse_upload = client.post(
        f"/conversations/{autre_conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = reponse_upload.json()["piece_jointe"]["id"]

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 404


def test_envoyer_message_avec_piece_jointe_dun_autre_compte_renvoie_404_meme_avec_un_jeton_admin(
    client, mistral_client_factice, jeton_valide, seed_compte
):
    jeton_admin = _jeton_admin(client, seed_compte)
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_ocr("Contenu")
    reponse_upload = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    piece_jointe_id = reponse_upload.json()["piece_jointe"]["id"]

    autre_conversation_id = _creer_conversation(client, mistral_client_factice, jeton_admin)
    reponse = client.post(
        f"/conversations/{autre_conversation_id}/messages",
        json={"message": "Et ensuite ?", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_admin),
    )

    assert reponse.status_code == 404
