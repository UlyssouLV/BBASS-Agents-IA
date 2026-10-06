import json

import pytest

from vm_centrale.models import Consommation, Conversation, EchangeInspecteur

_PDF = ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _autorisation_admin(jeton: str, cle_admin: str = "cle-admin-de-test") -> dict[str, str]:
    return {**_autorisation(jeton), "X-Admin-Key": cle_admin}


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": None})


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour") -> int:
    mistral_client_factice.repondre("Réponse assistant", "Titre")
    reponse = client.post(
        "/conversations", json={"message": message}, headers=_autorisation(jeton)
    )
    return reponse.json()["conversation"]["id"]


def _echanges(db_session) -> list[EchangeInspecteur]:
    return db_session.query(EchangeInspecteur).order_by(EchangeInspecteur.id).all()


def _televerser_sans_conversation(client, jeton: str, fichier=_PDF) -> int:
    reponse = client.post(
        "/pieces-jointes", files={"fichier": fichier}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 201
    return reponse.json()["piece_jointe"]["id"]


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def test_premier_message_enregistre_les_echanges_chat_et_titrage_avec_le_bon_payload(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    echanges = _echanges(db_session)

    assert [e.type_appel for e in echanges] == ["chat", "titrage"]
    for echange in echanges:
        assert echange.identifiant_compte == "j.dupont"
        assert echange.conversation_id == conversation_id
        assert echange.piece_jointe_id is None
        assert echange.statut == "succes"
        assert echange.erreur is None
        assert echange.modele == "mistral-small-latest"

    echange_chat = echanges[0]
    assert echange_chat.requete_payload["messages"][-1] == {"role": "user", "content": "Bonjour"}
    assert echange_chat.reponse_payload is not None
    assert echange_chat.reponse_payload["choices"][0]["message"]["content"] == "Réponse assistant"

    echange_titrage = echanges[1]
    assert "Bonjour" in echange_titrage.requete_payload["messages"][-1]["content"]
    assert echange_titrage.reponse_payload is not None
    assert echange_titrage.reponse_payload["choices"][0]["message"]["content"] == "Titre"


def test_message_suivant_avec_messages_sortants_enregistre_un_echange_resume_et_profil(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))

    mistral_client_factice.repondre(
        "Suite", resume_et_profil=_reponse_resume_et_profil("Nouveau résumé")
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 200

    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert sorted(e.type_appel for e in nouveaux_echanges) == ["chat", "resume_et_profil"]
    for echange in nouveaux_echanges:
        assert echange.conversation_id == conversation_id
        assert echange.statut == "succes"


def test_upload_pdf_enregistre_un_echange_ocr_avec_la_bonne_piece_jointe_id(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))
    mistral_client_factice.repondre_ocr("Texte extrait du PDF")

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201
    piece_jointe_id = reponse.json()["piece_jointe"]["id"]

    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert len(nouveaux_echanges) == 1
    echange = nouveaux_echanges[0]
    assert echange.type_appel == "ocr"
    assert echange.modele == "mistral-ocr-latest"
    assert echange.conversation_id == conversation_id
    assert echange.piece_jointe_id == piece_jointe_id
    assert echange.statut == "succes"
    assert echange.reponse_payload is not None
    assert echange.reponse_payload["pages"][0]["markdown"] == "Texte extrait du PDF"


def test_upload_image_enregistre_un_echange_vision_avec_la_bonne_piece_jointe_id(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))
    mistral_client_factice.repondre_vision("Photocopie d'un plan de masse")

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("plan.png", b"contenu factice png", "image/png")},
        headers=_autorisation(jeton_valide),
    )
    assert reponse.status_code == 201
    piece_jointe_id = reponse.json()["piece_jointe"]["id"]

    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert len(nouveaux_echanges) == 1
    echange = nouveaux_echanges[0]
    assert echange.type_appel == "vision"
    assert echange.piece_jointe_id == piece_jointe_id
    assert echange.statut == "succes"


def test_upload_word_nenregistre_aucun_echange(client, mistral_client_factice, jeton_valide, db_session):
    from io import BytesIO

    from docx import Document

    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))

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

    assert len(_echanges(db_session)) == echanges_avant


def test_appel_doutil_produit_deux_echanges_chat_distincts(
    client, mistral_client_factice, jeton_valide, db_session
):
    # Scénario de tests/test_tool_calling_piece_jointe.py : une pièce jointe
    # sort de la fenêtre des 3 derniers messages, puis l'IA demande à la
    # relire via l'outil (spec 1.1.2).
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)

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

    echanges_avant = len(_echanges(db_session))
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

    nouveaux_echanges_chat = [
        e for e in _echanges(db_session)[echanges_avant:] if e.type_appel == "chat"
    ]
    # Demande d'outil, puis second appel une fois le résultat réinjecté : deux
    # échanges "chat" distincts, tous deux en succès (spec 1.3.0).
    assert len(nouveaux_echanges_chat) == 2
    demande, second_appel = nouveaux_echanges_chat
    assert demande.statut == "succes"
    assert demande.piece_jointe_id is None
    assert second_appel.statut == "succes"
    # Le second appel porte la référence de la pièce jointe relue par l'outil
    # (spec 1.3.0), distincte de celle jointe au nouveau message de ce tour
    # (il n'y en a pas ici).
    assert second_appel.piece_jointe_id == piece_jointe_id
    messages_outils = [
        m for m in second_appel.requete_payload["messages"] if m["role"] == "tool"
    ]
    assert len(messages_outils) == 1
    assert messages_outils[0]["content"] == "Plan de masse détaillé"


def test_echec_appel_mistral_principal_produit_un_echange_echec_malgre_le_rollback(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 502
    # Aucune conversation n'a survécu au rollback (non-régression spec 1.1.2).
    assert db_session.query(Conversation).count() == 0

    echanges = _echanges(db_session)
    assert len(echanges) == 1
    echange = echanges[0]
    assert echange.type_appel == "chat"
    assert echange.statut == "echec"
    assert echange.conversation_id is None
    assert echange.reponse_payload is None
    assert echange.erreur is not None
    assert "service Mistral indisponible" in echange.erreur
    assert echange.requete_payload["messages"][-1] == {"role": "user", "content": "Bonjour"}


def test_echec_appel_ocr_produit_un_echange_echec_malgre_le_rollback(
    client, mistral_client_factice, jeton_valide, db_session
):
    from vm_centrale.models import PieceJointe

    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))
    mistral_client_factice.echouer_ocr(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    assert db_session.query(PieceJointe).count() == 0

    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert len(nouveaux_echanges) == 1
    echange = nouveaux_echanges[0]
    assert echange.type_appel == "ocr"
    assert echange.statut == "echec"
    assert echange.conversation_id == conversation_id
    assert echange.piece_jointe_id is None
    assert echange.erreur is not None
    assert "service Mistral indisponible" in echange.erreur


def test_aucun_echange_ne_contient_la_cle_api_ni_lentete_authorization(
    client, mistral_client_factice, jeton_valide, db_session
):
    # Garantie forte (payload jamais construit avec la clé) testée au niveau
    # de MistralClient lui-même dans tests/test_mistral_client.py ; ce test-ci
    # vérifie seulement qu'aucune étape de persistance de l'inspecteur
    # n'introduit "Authorization" ou un en-tête quelconque dans la ligne
    # stockée.
    _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")

    for echange in _echanges(db_session):
        assert "Authorization" not in echange.requete_payload
        assert "headers" not in echange.requete_payload
        if echange.reponse_payload is not None:
            assert "Authorization" not in echange.reponse_payload


def test_suppression_conversation_supprime_ses_echanges_mais_pas_sa_consommation(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    assert len(_echanges(db_session)) > 0
    assert db_session.query(Consommation).filter(
        Consommation.conversation_id == conversation_id
    ).count() > 0

    reponse = client.delete(
        f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)
    )
    assert reponse.status_code == 204

    assert _echanges(db_session) == []
    # Non-régression 1.1.3 : Consommation survit, seul le rattachement
    # disparaît.
    lignes_consommation = db_session.query(Consommation).all()
    assert len(lignes_consommation) > 0
    assert all(l.conversation_id is None for l in lignes_consommation)


# --- API de lecture GET /inspecteur/* (spec 1.3.0, ticket #107) --------------


def test_inspecteur_sans_jeton_est_refuse(client, monkeypatch):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get("/inspecteur/comptes", headers={"X-Admin-Key": "cle-admin-de-test"})

    assert reponse.status_code == 401


def test_inspecteur_avec_jeton_mais_sans_cle_admin_est_refuse(client, jeton_valide, monkeypatch):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get("/inspecteur/comptes", headers=_autorisation(jeton_valide))

    assert reponse.status_code == 401


def test_inspecteur_avec_jeton_et_mauvaise_cle_admin_est_refuse(client, jeton_valide, monkeypatch):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get(
        "/inspecteur/comptes", headers=_autorisation_admin(jeton_valide, "mauvaise-cle")
    )

    assert reponse.status_code == 401


def test_inspecteur_avec_jeton_de_nimporte_quel_compte_et_bonne_cle_est_autorise(
    client, jeton_valide, monkeypatch
):
    # Pas besoin d'un compte est_admin (spec 1.3.0, ADR-0012) : n'importe quel
    # jeton valide suffit, contrairement à get_compte_admin (routers/comptes.py).
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get("/inspecteur/comptes", headers=_autorisation_admin(jeton_valide))

    assert reponse.status_code == 200


def test_navigation_comptes_conversations_echanges_dans_lordre_chronologique(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    entetes = _autorisation_admin(jeton_valide)

    reponse_comptes = client.get("/inspecteur/comptes", headers=entetes)
    assert reponse_comptes.status_code == 200
    assert {c["identifiant_compte"] for c in reponse_comptes.json()} == {"j.dupont"}

    reponse_conversations = client.get("/inspecteur/comptes/j.dupont/conversations", headers=entetes)
    assert reponse_conversations.status_code == 200
    assert [c["id"] for c in reponse_conversations.json()] == [conversation_id]

    reponse_echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes
    )
    assert reponse_echanges.status_code == 200
    echanges = reponse_echanges.json()
    assert [e["type_appel"] for e in echanges] == ["chat", "titrage"]
    assert [e["statut"] for e in echanges] == ["succes", "succes"]


def test_comptes_sans_aucune_conversation_nest_jamais_liste(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    # Aucune conversation créée dans ce test : la liste des comptes de
    # l'inspecteur doit rester vide (spec 1.3.0 — "comptes ayant au moins une
    # conversation").
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get("/inspecteur/comptes", headers=_autorisation_admin(jeton_valide))

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_conversations_dun_compte_inconnu_renvoie_une_liste_vide(client, jeton_valide, monkeypatch):
    # Portée volontairement sans restriction par compte (spec 1.3.0) : jamais
    # de 404 pour un identifiant_compte qui n'existe pas, juste une liste vide.
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get(
        "/inspecteur/comptes/inconnu/conversations", headers=_autorisation_admin(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_detail_dun_echange_reussi_contient_le_payload_et_la_reponse(
    client, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    echange_chat = _echanges(db_session)[0]

    reponse = client.get(
        f"/inspecteur/echanges/{echange_chat.id}", headers=_autorisation_admin(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "succes"
    assert corps["erreur"] is None
    assert corps["requete_payload"]["messages"][-1] == {"role": "user", "content": "Bonjour"}
    assert corps["reponse_payload"]["choices"][0]["message"]["content"] == "Réponse assistant"


def test_detail_dun_echange_en_echec_contient_le_statut_sans_reponse(
    client, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    echange_echec = _echanges(db_session)[0]

    reponse = client.get(
        f"/inspecteur/echanges/{echange_echec.id}", headers=_autorisation_admin(jeton_valide)
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "echec"
    assert corps["reponse_payload"] is None
    assert "service Mistral indisponible" in corps["erreur"]


def test_echange_introuvable_renvoie_404(client, jeton_valide, monkeypatch):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")

    reponse = client.get("/inspecteur/echanges/9999", headers=_autorisation_admin(jeton_valide))

    assert reponse.status_code == 404


def test_echec_resume_apres_chat_reussi_ne_persiste_ni_consommation_ni_echange_succes(
    client, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))
    consommations_avant = db_session.query(Consommation).count()

    def _resume_en_echec(*args, **kwargs):
        raise RuntimeError("résumé indisponible")

    monkeypatch.setattr(
        "vm_centrale.routers.conversations._appeler_resume_et_profil", _resume_en_echec
    )
    mistral_client_factice.repondre("Suite")
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    # Le chat a réussi, mais le tour a échoué : ni son coût ni son échange
    # « succès » ne doivent survivre (sinon comptés deux fois à la relance).
    assert db_session.query(Consommation).count() == consommations_avant
    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert [(e.type_appel, e.statut) for e in nouveaux_echanges] == [("resume_et_profil", "echec")]
    assert nouveaux_echanges[0].conversation_id == conversation_id


def test_echec_second_appel_outil_ne_persiste_pas_la_demande_doutil(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    ).json()["conversation"]["id"]
    mistral_client_factice.repondre("Deuxième réponse", resume_et_profil=_reponse_resume_et_profil())
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    echanges_avant = len(_echanges(db_session))
    consommations_avant = db_session.query(Consommation).count()

    mistral_client_factice.repondre_avec_appel_outil(
        "obtenir_contenu_piece_jointe", {"piece_jointe_id": piece_jointe_id}
    )
    mistral_client_factice.echouer_apres_demandes_outils(RuntimeError("second appel indisponible"))
    mistral_client_factice.repondre("Inutilisée", resume_et_profil=_reponse_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Rappelle-moi le contenu exact du plan"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    assert db_session.query(Consommation).count() == consommations_avant
    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert [(e.type_appel, e.statut) for e in nouveaux_echanges] == [("chat", "echec")]


def test_reponse_vision_illisible_conserve_payload_et_reponse_brute(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    echanges_avant = len(_echanges(db_session))
    mistral_client_factice.repondre("Inutilisée", resume_et_profil="pas du JSON")

    reponse = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("plan.png", b"contenu factice png", "image/png")},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    nouveaux_echanges = _echanges(db_session)[echanges_avant:]
    assert len(nouveaux_echanges) == 1
    echange = nouveaux_echanges[0]
    assert echange.type_appel == "vision"
    assert echange.statut == "echec"
    assert echange.requete_payload["response_format"]["json_schema"]["name"] == "analyse_image"
    assert echange.reponse_payload == {"choices": [{"message": {"content": "pas du JSON"}}]}


def test_echec_premier_message_avec_piece_jointe_ne_la_reference_pas(
    client, mistral_client_factice, jeton_valide, db_session
):
    # L'échange en échec n'a pas de conversation : il ne doit pas non plus
    # garder une référence vers une pièce jointe qui pourra être supprimée
    # plus tard avec une autre conversation.
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = _televerser_sans_conversation(client, jeton_valide)
    mistral_client_factice.echouer(RuntimeError("service Mistral indisponible"))

    reponse = client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 502
    echanges = _echanges(db_session)
    assert len(echanges) == 1
    assert echanges[0].statut == "echec"
    assert echanges[0].conversation_id is None
    assert echanges[0].piece_jointe_id is None
