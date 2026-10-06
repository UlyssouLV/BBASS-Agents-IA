import json
from decimal import Decimal

import pytest

from vm_centrale.models import Consommation

_TAUX_TOLERANCE = Decimal("0.0000001")


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": None})


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
        assert ligne.modele == "mistral-small-2603"
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
    assert ligne.modele == "mistral-small-2603"
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
        "relire_pieces_jointes", {"piece_jointe_ids": [piece_jointe_id]}
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


def test_chaque_modele_utilise_a_une_fiche_complete(db_session):
    from vm_centrale.config import FICHES_MODELES, MODELE_CHAT, MODELE_OCR

    fiche_chat = FICHES_MODELES[MODELE_CHAT]
    assert fiche_chat.fenetre_tokens == 262_144
    assert fiche_chat.prix_usd_par_token_entree > 0 and fiche_chat.prix_usd_par_token_sortie > 0
    assert FICHES_MODELES[MODELE_OCR].prix_usd_par_page > 0


def test_get_consommation_apres_premier_message_puis_message_suivant(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    mistral_client_factice.repondre(
        "Suite", resume_et_profil=_reponse_resume_et_profil("Nouveau résumé")
    )
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    reponse = client.get("/consommation", headers=_autorisation(jeton_valide))
    assert reponse.status_code == 200
    corps = reponse.json()

    lignes = _lignes_consommation(db_session)
    lignes_chat = [l for l in lignes if l.type_appel in ("chat", "titrage", "resume_et_profil")]
    assert corps["chat"]["nombre_requetes"] == len(lignes_chat)
    assert corps["chat"]["tokens_total"] == sum(l.tokens_total or 0 for l in lignes_chat)
    assert Decimal(corps["chat"]["cout_usd"]) == sum((l.cout_usd for l in lignes_chat), Decimal(0))
    assert corps["piece_jointe"] == {
        "tokens_total": 0,
        "pages_traitees": 0,
        "cout_usd": "0",
        "nombre_requetes": 0,
    }

    assert len(corps["conversations"]) == 1
    conversation = corps["conversations"][0]
    assert conversation["id"] == conversation_id
    assert conversation["chat"]["nombre_requetes"] == len(lignes_chat)


def test_get_consommation_distingue_pages_et_tokens_pour_piece_jointe(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    mistral_client_factice.repondre_ocr("Texte extrait du PDF")
    client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton_valide),
    )
    mistral_client_factice.repondre_vision("Photocopie d'un plan de masse")
    client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("plan.png", b"contenu factice png", "image/png")},
        headers=_autorisation(jeton_valide),
    )

    reponse = client.get("/consommation", headers=_autorisation(jeton_valide))
    assert reponse.status_code == 200
    corps = reponse.json()

    assert corps["piece_jointe"]["nombre_requetes"] == 2
    # Une ligne "ocr" (1 page, spec 1.1.3) et une ligne "vision" (tokens
    # factices du double de test : tokens_total=15).
    assert corps["piece_jointe"]["pages_traitees"] == 1
    assert corps["piece_jointe"]["tokens_total"] == 15

    conversation = corps["conversations"][0]
    assert conversation["piece_jointe"]["pages_traitees"] == 1
    assert conversation["piece_jointe"]["tokens_total"] == 15


def test_get_consommation_inclut_lappel_de_chat_declenche_par_tool_calling(
    client, mistral_client_factice, jeton_valide
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

    nombre_requetes_chat_avant = client.get(
        "/consommation", headers=_autorisation(jeton_valide)
    ).json()["chat"]["nombre_requetes"]

    mistral_client_factice.repondre_avec_appel_outil(
        "relire_pieces_jointes", {"piece_jointe_ids": [piece_jointe_id]}
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

    corps = client.get("/consommation", headers=_autorisation(jeton_valide)).json()
    # Le premier appel (qui déclenche AppelOutilDemande) et le second appel
    # (qui répond une fois le contenu injecté) comptent chacun comme une
    # ligne "chat" de plus (spec V1.1.3), plus la ligne "resume_et_profil" de
    # ce même tour (messages_sortants non vide) — la catégorie Chat regroupe
    # chat/titrage/resume_et_profil (spec 1.1.3), donc ces trois lignes
    # apparaissent ensemble dans son total.
    assert corps["chat"]["nombre_requetes"] - nombre_requetes_chat_avant == 3


def test_get_consommation_401_sans_jeton(client):
    reponse = client.get("/consommation")
    assert reponse.status_code == 401


def test_supprimer_conversation_ne_change_pas_le_total_mais_disparait_du_classement(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    avant = client.get("/consommation", headers=_autorisation(jeton_valide)).json()
    assert any(c["id"] == conversation_id for c in avant["conversations"])

    reponse = client.delete(
        f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)
    )
    assert reponse.status_code == 204

    apres = client.get("/consommation", headers=_autorisation(jeton_valide)).json()
    assert apres["chat"] == avant["chat"]
    assert apres["piece_jointe"] == avant["piece_jointe"]
    assert all(c["id"] != conversation_id for c in apres["conversations"])


def test_get_consommation_ne_voit_que_ses_propres_donnees(
    client, mistral_client_factice, jeton_valide, jeton_store
):
    _creer_conversation(client, mistral_client_factice, jeton_valide)

    autre_jeton = jeton_store.emettre("a.autre")
    reponse = client.get("/consommation", headers=_autorisation(autre_jeton))
    assert reponse.status_code == 200
    corps = reponse.json()

    assert corps["chat"]["nombre_requetes"] == 0
    assert corps["conversations"] == []
