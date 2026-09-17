import json
from decimal import Decimal

import pytest

from vm_centrale.models import Consommation

_TAUX_TOLERANCE = Decimal("0.0000001")


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail_delta": ""})


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour") -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post(
        "/conversations", json={"message": message}, headers=_autorisation(jeton)
    )
    return reponse.json()["conversation"]["id"]


def _lignes_consommation(db_session) -> list[Consommation]:
    return db_session.query(Consommation).order_by(Consommation.id).all()


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def test_premier_message_enregistre_une_ligne_chat_et_une_ligne_titrage(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    lignes = _lignes_consommation(db_session)

    assert [l.type_appel for l in lignes] == ["chat", "titrage"]
    for ligne in lignes:
        assert ligne.identifiant_compte == "j.dupont"
        assert ligne.conversation_id == conversation_id
        assert ligne.modele == "mistral-small-latest"
        # Usage factice du double de test (conftest.py) : tokens_entree=10,
        # tokens_sortie=5, tokens_total=15.
        assert ligne.tokens_entree == 10
        assert ligne.tokens_sortie == 5
        assert ligne.tokens_total == 15
        assert ligne.pages_traitees is None
        assert ligne.cout_usd > 0


def test_message_suivant_avec_messages_sortants_enregistre_une_ligne_resume_et_profil(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    lignes_avant = len(_lignes_consommation(db_session))

    mistral_client_factice.repondre(
        "Suite", resume_et_profil=_reponse_resume_et_profil("Nouveau résumé")
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 200

    lignes = _lignes_consommation(db_session)
    nouvelles_lignes = lignes[lignes_avant:]
    assert sorted(l.type_appel for l in nouvelles_lignes) == ["chat", "resume_et_profil"]
    for ligne in nouvelles_lignes:
        assert ligne.conversation_id == conversation_id


def test_upload_pdf_enregistre_une_ligne_ocr_avec_pages_traitees(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    lignes_avant = len(_lignes_consommation(db_session))
    mistral_client_factice.repondre_ocr("Texte extrait du PDF")

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201

    lignes = _lignes_consommation(db_session)
    nouvelles_lignes = lignes[lignes_avant:]
    assert len(nouvelles_lignes) == 1
    ligne = nouvelles_lignes[0]
    assert ligne.type_appel == "ocr"
    assert ligne.modele == "mistral-ocr-latest"
    assert ligne.conversation_id == conversation_id
    assert ligne.pages_traitees == 1
    assert ligne.tokens_entree is None
    assert ligne.tokens_sortie is None
    assert ligne.tokens_total is None
    assert ligne.cout_usd > 0


def test_upload_image_enregistre_une_ligne_vision_avec_tokens(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    lignes_avant = len(_lignes_consommation(db_session))
    mistral_client_factice.repondre_vision("Photocopie d'un plan de masse")

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("plan.png", b"contenu factice png", "image/png")},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201

    lignes = _lignes_consommation(db_session)
    nouvelles_lignes = lignes[lignes_avant:]
    assert len(nouvelles_lignes) == 1
    ligne = nouvelles_lignes[0]
    assert ligne.type_appel == "vision"
    assert ligne.modele == "mistral-small-latest"
    assert ligne.conversation_id == conversation_id
    assert ligne.pages_traitees is None
    assert ligne.tokens_entree == 10
    assert ligne.tokens_sortie == 5
    assert ligne.tokens_total == 15
    assert ligne.cout_usd > 0


def test_upload_word_et_excel_nenregistrent_aucune_ligne_de_consommation(
    client, mistral_client_factice, jeton_valide, db_session
):
    from io import BytesIO

    from docx import Document

    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    lignes_avant = len(_lignes_consommation(db_session))

    document = Document()
    document.add_paragraph("Un paragraphe")
    tampon = BytesIO()
    document.save(tampon)

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={
            "fichier": (
                "document.docx",
                tampon.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201

    assert len(_lignes_consommation(db_session)) == lignes_avant


def test_upload_sans_conversation_enregistre_une_ligne_avec_conversation_id_null(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_ocr("Texte extrait")

    reponse = client.post(
        "/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201

    lignes = _lignes_consommation(db_session)
    assert len(lignes) == 1
    assert lignes[0].type_appel == "ocr"
    assert lignes[0].conversation_id is None


def test_appel_doutil_hors_fenetre_produit_une_ligne_chat_supplementaire(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = client.post(
        "/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 plan factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    ).json()["piece_jointe"]["id"]

    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    ).json()["conversation"]["id"]

    mistral_client_factice.repondre(
        "Deuxième réponse", resume_et_profil=_reponse_resume_et_profil()
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    lignes_avant = len(_lignes_consommation(db_session))
    lignes_chat_avant = len([l for l in _lignes_consommation(db_session) if l.type_appel == "chat"])

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

    lignes = _lignes_consommation(db_session)
    assert len(lignes) > lignes_avant
    lignes_chat_apres = len([l for l in lignes if l.type_appel == "chat"])
    # Le premier appel (qui déclenche AppelOutilDemande) et le second appel
    # (qui répond une fois le contenu injecté) comptent chacun comme une
    # ligne "chat" distincte (spec V1.1.3) : deux lignes de plus, pas une.
    assert lignes_chat_apres - lignes_chat_avant == 2


def test_echec_appel_mistral_ne_persiste_aucune_ligne_de_consommation(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 502
    assert _lignes_consommation(db_session) == []


def test_echec_appel_ocr_ne_persiste_aucune_ligne_de_consommation(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    lignes_avant = len(_lignes_consommation(db_session))
    mistral_client_factice.echouer_ocr(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("document.pdf", b"contenu", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    assert len(_lignes_consommation(db_session)) == lignes_avant


def test_calculer_cout_ocr_est_page_based(db_session):
    from vm_centrale.config import MODELE_OCR, calculer_cout

    cout = calculer_cout("ocr", MODELE_OCR, None, None, 3)
    cout_attendu = Decimal(4) / Decimal(1000) * Decimal(3)
    assert abs(cout - cout_attendu) < _TAUX_TOLERANCE


def test_calculer_cout_chat_est_token_based(db_session):
    from vm_centrale.config import MODELE_CHAT, calculer_cout

    cout = calculer_cout("chat", MODELE_CHAT, 1_000_000, 1_000_000, None)
    cout_attendu = Decimal("0.15") + Decimal("0.60")
    assert abs(cout - cout_attendu) < _TAUX_TOLERANCE
