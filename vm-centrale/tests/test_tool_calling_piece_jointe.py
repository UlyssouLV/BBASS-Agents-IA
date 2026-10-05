import json

import pytest

_PDF = ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")
_PDF_PLAN = ("plan.pdf", b"%PDF-1.4 plan factice", "application/pdf")
_PDF_DEVIS = ("devis.pdf", b"%PDF-1.4 devis factice", "application/pdf")


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": None})


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


def test_avec_deux_pieces_jointes_hors_fenetre_le_tool_mentionne_chaque_nom_de_fichier(
    client, mistral_client_factice, jeton_valide
):
    # Ticket #50 : la description de l'outil doit énumérer les pièces
    # jointes éligibles avec leur nom de fichier en face de leur id, pas
    # seulement un entier `piece_jointe_id` que le modèle doit deviner.
    mistral_client_factice.repondre_ocr("Contenu du plan")
    piece_jointe_plan = _televerser_sans_conversation(client, jeton_valide, fichier=_PDF_PLAN)

    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde ce plan", "piece_jointe_id": piece_jointe_plan},
        headers=_autorisation(jeton_valide),
    ).json()["conversation"]["id"]

    mistral_client_factice.repondre_ocr("Contenu du devis")
    upload_devis = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF_DEVIS},
        headers=_autorisation(jeton_valide),
    )
    assert upload_devis.status_code == 201
    piece_jointe_devis = upload_devis.json()["piece_jointe"]["id"]

    mistral_client_factice.repondre(
        "Deuxième réponse", resume_et_profil=_reponse_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et voilà le devis", "piece_jointe_id": piece_jointe_devis},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 200

    # Deux tours de plus pour que les DEUX messages porteurs (plan et devis)
    # sortent de la fenêtre des 3 derniers messages en même temps.
    for message, reponse_attendue in [
        ("Et ensuite ?", "Troisième réponse"),
        ("Une dernière question", "Quatrième réponse"),
    ]:
        mistral_client_factice.repondre(
            reponse_attendue, resume_et_profil=_reponse_resume_et_profil()
        )
        reponse = client.post(
            f"/conversations/{conversation_id}/messages",
            json={"message": message},
            headers=_autorisation(jeton_valide),
        )
        assert reponse.status_code == 200

    tools = mistral_client_factice.tools_appels_reponse[-1]
    assert tools
    description = tools[0]["function"]["description"]
    assert "plan.pdf" in description
    assert "devis.pdf" in description
    assert f"id {piece_jointe_plan}" in description
    assert f"id {piece_jointe_devis}" in description


def test_message_systeme_piece_jointe_precise_que_cest_le_fichier_du_tour_courant(
    client, mistral_client_factice, jeton_valide
):
    # Ticket #50 : le modèle traitait l'extrait injecté comme un exemple ou
    # un rappel d'un tour antérieur (essai du 2026-09-17) au lieu du fichier
    # du message de ce tour précis.
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.repondre("Première réponse", "Titre")
    client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    messages_appel_reponse = mistral_client_factice.appels_reponse[0]
    message_systeme_pj = next(
        m for m in messages_appel_reponse if m["role"] == "system" and "document.pdf" in m["content"]
    )
    assert "ce tour précis" in message_systeme_pj["content"]
    assert "exemple" in message_systeme_pj["content"]
    assert "tour antérieur" in message_systeme_pj["content"]


def test_message_systeme_piece_jointe_interdit_de_redemander_le_fichier_et_dinventer(
    client, mistral_client_factice, jeton_valide
):
    # Spec 1.3.1 (issue #110) : le modèle demandait d'envoyer une image déjà
    # jointe (message au futur), puis la décrivait d'après le profil de travail.
    mistral_client_factice.repondre_ocr("Un chat roux assis sur un canapé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

    mistral_client_factice.repondre("Première réponse", "Titre")
    client.post(
        "/conversations",
        json={"message": "Je vais t'envoyer une image", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    messages_appel_reponse = mistral_client_factice.appels_reponse[0]
    contenu = next(
        m for m in messages_appel_reponse if m["role"] == "system" and "document.pdf" in m["content"]
    )["content"]
    assert "déjà joint" in contenu
    assert "ne demande pas de l'envoyer" in contenu
    assert "futur" in contenu
    assert "seule description autorisée" in contenu
    assert "schéma" in contenu
    assert "profil de travail ne remplace jamais" in contenu


def test_url_inventee_retiree_de_la_reponse_finale_apres_un_appel_doutil(
    client, mistral_client_factice, jeton_valide
):
    # Garde-fou URL (spec 1.3.1) : s'applique aussi à la réponse du second
    # appel, celui qui suit la relecture de la pièce jointe par l'outil.
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide
    )

    mistral_client_factice.repondre_avec_appel_outil(
        "obtenir_contenu_piece_jointe", {"piece_jointe_id": piece_jointe_id}
    )
    mistral_client_factice.repondre(
        "Le plan est [téléchargeable ici](https://plans.example/plan.pdf).",
        resume_et_profil=_reponse_resume_et_profil(),
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Rappelle-moi le plan"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Le plan est téléchargeable ici."
