import json

import pytest

from vm_centrale.models import Consommation, EchangeInspecteur, Message, QuestionCouverte

# Questions couvertes d'une pièce jointe (spec 1.4.1, #138) : un appel
# Mistral à l'envoi du message qui porte la pièce jointe, en parallèle de la
# réponse de chat, jamais au téléversement.

_PDF = ("devis.pdf", b"%PDF-1.4 contenu factice", "application/pdf")
_CONTENU = "Montant HT : 12 400 €"


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _televerser(client, mistral_client_factice, jeton: str) -> int:
    mistral_client_factice.repondre_ocr(_CONTENU)
    reponse = client.post("/pieces-jointes", files={"fichier": _PDF}, headers=_autorisation(jeton))
    assert reponse.status_code == 201
    return reponse.json()["piece_jointe"]["id"]


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour", **corps) -> int:
    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post("/conversations", json={"message": message, **corps}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    return reponse.json()["conversation"]["id"]


def _envoyer(client, mistral_client_factice, jeton: str, conversation_id: int, message: str, **corps):
    mistral_client_factice.repondre("Suite", resume_et_profil=_resume_et_profil())
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": message, **corps},
        headers=_autorisation(jeton),
    )


def _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton: str, message: str = "Quel est le montant HT ?"):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton)
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton)
    reponse = _envoyer(
        client, mistral_client_factice, jeton, conversation_id, message, piece_jointe_id=piece_jointe_id
    )
    return reponse, conversation_id, piece_jointe_id


def _questions(db_session, conversation_id: int) -> list[QuestionCouverte]:
    return (
        db_session.query(QuestionCouverte)
        .filter_by(conversation_id=conversation_id)
        .order_by(QuestionCouverte.id)
        .all()
    )


def test_lenvoi_avec_piece_jointe_enregistre_les_questions_une_consommation_et_un_echange(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_questions_piece_jointe([("Quel est le montant HT ?", "12 400 €")])

    reponse, conversation_id, piece_jointe_id = _envoyer_avec_piece_jointe(
        client, mistral_client_factice, jeton_valide
    )

    assert reponse.status_code == 200
    assert len(mistral_client_factice.appels_questions_piece_jointe) == 1
    [question] = _questions(db_session, conversation_id)
    assert (question.piece_jointe_id, question.resultat_recherche_web_id) == (piece_jointe_id, None)
    assert (question.question, question.reponse, question.source) == ("Quel est le montant HT ?", "12 400 €", "devis.pdf")
    assert (question.trouvee, question.origine) == (True, "initiale")
    consommations = (
        db_session.query(Consommation).filter_by(conversation_id=conversation_id, type_appel="questions_piece_jointe").all()
    )
    assert len(consommations) == 1
    [echange] = (
        db_session.query(EchangeInspecteur)
        .filter_by(conversation_id=conversation_id, type_appel="questions_piece_jointe")
        .all()
    )
    assert (echange.origine, echange.statut, echange.piece_jointe_id) == ("mistral", "succes", piece_jointe_id)


def test_la_creation_dune_conversation_avec_piece_jointe_fait_aussi_lappel(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_questions_piece_jointe([("Quel est le montant HT ?", "12 400 €")])
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton_valide)

    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Voici le devis", piece_jointe_id=piece_jointe_id
    )

    [question] = _questions(db_session, conversation_id)
    assert question.piece_jointe_id == piece_jointe_id
    assert db_session.query(Consommation).filter_by(
        conversation_id=conversation_id, type_appel="questions_piece_jointe"
    ).count() == 1


def test_lappel_recoit_le_contenu_extrait_et_le_message_du_tour_en_json_strict(
    client, mistral_client_factice, jeton_valide
):
    _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton_valide, "Combien coûte le bornage ?")

    [messages] = mistral_client_factice.appels_questions_piece_jointe
    envoye = "\n".join(message["content"] for message in messages)
    assert _CONTENU in envoye
    assert "Combien coûte le bornage ?" in envoye
    assert "devis.pdf" in envoye


def test_lappel_demande_un_json_strict(client, mistral_client_factice, jeton_valide, db_session):
    _, conversation_id, _ = _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton_valide)

    [echange] = (
        db_session.query(EchangeInspecteur)
        .filter_by(conversation_id=conversation_id, type_appel="questions_piece_jointe")
        .all()
    )
    assert echange.requete_payload["response_format"]["type"] == "json_schema"
    assert echange.requete_payload["response_format"]["json_schema"]["strict"] is True


def test_au_dela_de_huit_questions_seules_les_huit_premieres_et_reponse_tronquee_a_300(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_questions_piece_jointe(
        [(f"Question {numero} ?", "x" * 400) for numero in range(1, 11)]
    )

    _, conversation_id, _ = _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton_valide)

    questions = _questions(db_session, conversation_id)
    assert [question.question for question in questions] == [f"Question {numero} ?" for numero in range(1, 9)]
    assert all(len(question.reponse) == 300 for question in questions)


def test_un_echec_de_lappel_nempeche_ni_la_reponse_ni_sa_persistance(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.echouer_questions_piece_jointe(RuntimeError("Mistral indisponible"))

    reponse, conversation_id, piece_jointe_id = _envoyer_avec_piece_jointe(
        client, mistral_client_factice, jeton_valide
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Suite"
    assert db_session.query(Message).filter_by(conversation_id=conversation_id).count() == 4
    assert _questions(db_session, conversation_id) == []
    assert not db_session.query(Consommation).filter_by(type_appel="questions_piece_jointe").count()
    [echange] = db_session.query(EchangeInspecteur).filter_by(type_appel="questions_piece_jointe").all()
    assert (echange.statut, echange.piece_jointe_id) == ("echec", piece_jointe_id)


def test_une_reponse_hors_du_json_attendu_ne_donne_aucune_question_mais_reste_comptee(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre_questions_piece_jointe_brute("pas du JSON")

    reponse, conversation_id, _ = _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton_valide)

    assert reponse.status_code == 200
    assert _questions(db_session, conversation_id) == []
    assert db_session.query(Consommation).filter_by(type_appel="questions_piece_jointe").count() == 1


def test_les_questions_apparaissent_dans_la_memoire_au_tour_suivant(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre_questions_piece_jointe([("Quel est le montant HT ?", "12 400 €")])
    _, conversation_id, _ = _envoyer_avec_piece_jointe(client, mistral_client_factice, jeton_valide)

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Et la TVA ?")

    dernier_appel = mistral_client_factice.appels_reponse[-1]
    [memoire] = [
        message["content"]
        for message in dernier_appel
        if message["role"] == "system" and message["content"].startswith("Mémoire de la conversation :")
    ]
    assert "  • Quel est le montant HT ? → 12 400 € (devis.pdf)" in memoire


def test_un_televersement_sans_envoi_ne_fait_aucun_appel(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": _PDF},
        headers=_autorisation(jeton_valide),
    )
    _televerser(client, mistral_client_factice, jeton_valide)

    assert mistral_client_factice.appels_questions_piece_jointe == []


def test_un_envoi_sans_piece_jointe_ne_fait_aucun_appel(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Bonjour encore")

    assert mistral_client_factice.appels_questions_piece_jointe == []
