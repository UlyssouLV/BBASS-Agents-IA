import json

import pytest

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


def _televerser_sans_conversation(client, jeton: str, fichier=_PDF) -> int:
    reponse = client.post(
        "/pieces-jointes", files={"fichier": fichier}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 201
    return reponse.json()["piece_jointe"]["id"]


def _amener_piece_jointe_hors_fenetre(
    client, mistral_client_factice, jeton: str, contenu_extrait: str = "Plan de masse détaillé"
) -> tuple[int, int]:
    # Fenêtre de 3 derniers messages (spec V1.1.1) : il faut deux tours après
    # celui qui porte la pièce jointe pour que son message n'y soit plus (le
    # tour suivant la fait déjà sortir du résumé, mais elle reste encore dans
    # `derniers_messages` jusqu'au tour d'après — voir
    # vm_centrale.routers.conversations.envoyer_message).
    mistral_client_factice.repondre_ocr(contenu_extrait)
    piece_jointe_id = _televerser_sans_conversation(client, jeton)

    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton),
    ).json()["conversation"]["id"]

    mistral_client_factice.repondre(
        "Deuxième réponse", resume_et_profil=_reponse_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200

    return conversation_id, piece_jointe_id


def test_avec_piece_jointe_hors_fenetre_lappel_recoit_un_parametre_tools_non_vide(
    client, mistral_client_factice, jeton_valide
):
    conversation_id, _ = _amener_piece_jointe_hors_fenetre(client, mistral_client_factice, jeton_valide)

    mistral_client_factice.repondre("Troisième réponse", resume_et_profil=_reponse_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Une dernière question"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert mistral_client_factice.tools_appels_reponse[-1]


def test_sans_piece_jointe_hors_fenetre_aucun_tools_nest_passe(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre")
    conversation_id = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    ).json()["conversation"]["id"]

    mistral_client_factice.repondre(
        "Toujours pas de pièce jointe", resume_et_profil=_reponse_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et toi ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert mistral_client_factice.tools_appels_reponse[-1] is None


def test_appel_doutil_relance_un_second_appel_avec_le_contenu_injecte_et_en_renvoie_la_reponse(
    client, mistral_client_factice, jeton_valide
):
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide, contenu_extrait="Plan de masse détaillé"
    )

    mistral_client_factice.repondre_avec_appel_outil(
        "obtenir_contenu_piece_jointe", {"piece_jointe_id": piece_jointe_id}
    )
    mistral_client_factice.repondre(
        "Réponse finale après relecture du plan", resume_et_profil=_reponse_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Rappelle-moi le contenu exact du plan"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Réponse finale après relecture du plan"

    # Le premier appel (avec tools) a bien déclenché un second appel dont les
    # messages portent le contenu de la pièce jointe injecté via un message
    # `role: tool` (spec 1.1.2).
    assert mistral_client_factice.tools_appels_reponse[-2]
    messages_second_appel = mistral_client_factice.appels_reponse[-1]
    messages_outils = [m for m in messages_second_appel if m["role"] == "tool"]
    assert len(messages_outils) == 1
    assert messages_outils[0]["content"] == "Plan de masse détaillé"
