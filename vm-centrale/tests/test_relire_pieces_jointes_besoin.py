import json

import pytest

from vm_centrale.config import MODELE_CHAT
from vm_centrale.models import Consommation, QuestionCouverte
from vm_centrale.outils.piece_jointe import CONSIGNE_RELECTURE_PIECES_JOINTES

# relire_pieces_jointes avec un besoin (spec 1.4.1, #141) : un appel
# d'extraction isolé sur les contenus extraits déjà en base, la réponse (ou
# « non trouvé ») rejoint les questions couvertes de la pièce jointe.

_OUTIL = "relire_pieces_jointes"
_TITRE_MEMOIRE = "Mémoire de la conversation :"
_PDF_PLAN = ("plan.pdf", b"%PDF-1.4 plan factice", "application/pdf")
_PDF_DEVIS = ("devis.pdf", b"%PDF-1.4 devis factice", "application/pdf")
_BESOIN = "Montant HT du devis"


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton: str) -> tuple[int, int, int]:
    # Tour 1 : plan.pdf ; tour 2 : devis.pdf. Ni l'une ni l'autre n'est celle
    # du tour suivant.
    mistral_client_factice.repondre_ocr("Plan de masse, parcelle AB 12, M. Dupont")
    plan = client.post("/pieces-jointes", files={"fichier": _PDF_PLAN}, headers=_autorisation(jeton)).json()[
        "piece_jointe"
    ]["id"]
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde le plan de M. Dupont", "piece_jointe_id": plan},
        headers=_autorisation(jeton),
    ).json()["conversation"]["id"]
    mistral_client_factice.repondre_ocr("Devis : 12 400 € HT")
    devis = client.post(
        f"/conversations/{conversation_id}/pieces-jointes", files={"fichier": _PDF_DEVIS}, headers=_autorisation(jeton)
    ).json()["piece_jointe"]["id"]
    mistral_client_factice.repondre("Deuxième réponse", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et le devis", "piece_jointe_id": devis},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200
    return conversation_id, plan, devis


def _relire(client, mistral_client_factice, jeton: str, conversation_id: int, arguments: dict) -> None:
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre("Réponse.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Combien coûte le bornage ?"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200


def _envoyer(client, mistral_client_factice, jeton: str, conversation_id: int) -> None:
    mistral_client_factice.repondre("Suite.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Suite"}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200


def _message_tool(mistral_client_factice) -> str:
    (message,) = [m for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "tool"]
    return message["content"]


def _questions_besoin(db_session, conversation_id: int) -> list[QuestionCouverte]:
    return (
        db_session.query(QuestionCouverte)
        .filter_by(conversation_id=conversation_id, origine="besoin")
        .order_by(QuestionCouverte.id)
        .all()
    )


def _memoire(mistral_client_factice) -> str:
    (memoire,) = [
        m["content"]
        for m in mistral_client_factice.appels_reponse[-1]
        if m["role"] == "system" and m["content"].startswith(_TITRE_MEMOIRE)
    ]
    return memoire


def test_le_besoin_est_un_parametre_facultatif_de_loutil(client, mistral_client_factice, jeton_valide):
    conversation_id, _, _ = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)

    (outil,) = [o for o in mistral_client_factice.tools_appels_reponse[-1] if o["function"]["name"] == _OUTIL]
    parametres = outil["function"]["parameters"]
    assert "besoin" in parametres["properties"]
    assert parametres["required"] == ["piece_jointe_ids"]


def test_sans_besoin_contenu_complet_sans_appel_dextraction(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, plan, devis = _conversation_avec_deux_pieces_jointes(
        client, mistral_client_factice, jeton_valide
    )
    _relire(client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [plan, devis]})

    assert mistral_client_factice.appels_relecture_pieces_jointes == []
    assert _message_tool(mistral_client_factice) == (
        f"Pièce jointe id {plan} « plan.pdf » :\nPlan de masse, parcelle AB 12, M. Dupont\n\n"
        f"Pièce jointe id {devis} « devis.pdf » :\nDevis : 12 400 € HT"
    )
    assert _questions_besoin(db_session, conversation_id) == []


def test_avec_besoin_un_seul_appel_isole_sur_les_contenus_extraits(client, mistral_client_factice, jeton_valide):
    conversation_id, plan, devis = _conversation_avec_deux_pieces_jointes(
        client, mistral_client_factice, jeton_valide
    )
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "devis.pdf")
    _relire(
        client,
        mistral_client_factice,
        jeton_valide,
        conversation_id,
        {"piece_jointe_ids": [plan, devis], "besoin": _BESOIN},
    )

    (appel,) = mistral_client_factice.appels_relecture_pieces_jointes
    # Consigne fixe, besoin et contenus : jamais la conversation.
    assert [m["role"] for m in appel] == ["system", "user"]
    assert appel[0]["content"] == CONSIGNE_RELECTURE_PIECES_JOINTES
    assert _BESOIN in appel[1]["content"]
    assert "« plan.pdf »" in appel[1]["content"] and "Plan de masse" in appel[1]["content"]
    assert "« devis.pdf »" in appel[1]["content"] and "Devis : 12 400 € HT" in appel[1]["content"]
    assert "Regarde le plan" not in appel[1]["content"] and "bornage" not in appel[1]["content"]
    contenu = _message_tool(mistral_client_factice)
    # La réponse, pas le contenu complet.
    assert "12 400 € HT" in contenu and "devis.pdf" in contenu
    assert "Plan de masse" not in contenu


def test_la_consigne_impose_non_trouve_plutot_quune_estimation():
    assert "non trouvé" in CONSIGNE_RELECTURE_PIECES_JOINTES
    assert "estimation" in CONSIGNE_RELECTURE_PIECES_JOINTES


def test_une_reponse_trouvee_est_enregistree_sur_la_piece_jointe_source_et_apparait_dans_la_memoire(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, plan, devis = _conversation_avec_deux_pieces_jointes(
        client, mistral_client_factice, jeton_valide
    )
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "devis.pdf")
    _relire(
        client,
        mistral_client_factice,
        jeton_valide,
        conversation_id,
        {"piece_jointe_ids": [plan, devis], "besoin": _BESOIN},
    )

    (question,) = _questions_besoin(db_session, conversation_id)
    assert question.piece_jointe_id == devis and question.resultat_recherche_web_id is None
    assert (question.question, question.reponse, question.source, question.trouvee) == (
        _BESOIN,
        "12 400 € HT",
        "devis.pdf",
        True,
    )

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)
    assert f"  • {_BESOIN} → 12 400 € HT (devis.pdf)" in _memoire(mistral_client_factice).splitlines()


def test_une_seule_piece_jointe_relue_porte_la_reponse_quelle_que_soit_la_source(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "Devis.PDF")
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )

    (question,) = _questions_besoin(db_session, conversation_id)
    assert (question.piece_jointe_id, question.source) == (devis, "devis.pdf")


def test_une_source_qui_nest_pas_une_piece_jointe_relue_nest_pas_enregistree(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, plan, devis = _conversation_avec_deux_pieces_jointes(
        client, mistral_client_factice, jeton_valide
    )
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "facture.pdf")
    _relire(
        client,
        mistral_client_factice,
        jeton_valide,
        conversation_id,
        {"piece_jointe_ids": [plan, devis], "besoin": _BESOIN},
    )

    assert "12 400 € HT" in _message_tool(mistral_client_factice)
    assert _questions_besoin(db_session, conversation_id) == []


def test_un_non_trouve_est_enregistre_trouvee_faux_sur_chaque_piece_jointe_relue_et_marque_dans_la_memoire(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, plan, devis = _conversation_avec_deux_pieces_jointes(
        client, mistral_client_factice, jeton_valide
    )
    mistral_client_factice.repondre_relecture_pieces_jointes(False)
    _relire(
        client,
        mistral_client_factice,
        jeton_valide,
        conversation_id,
        {"piece_jointe_ids": [plan, devis], "besoin": _BESOIN},
    )

    questions = _questions_besoin(db_session, conversation_id)
    assert [(q.piece_jointe_id, q.source, q.trouvee, q.reponse) for q in questions] == [
        (plan, "plan.pdf", False, ""),
        (devis, "devis.pdf", False, ""),
    ]
    assert "non trouvé" in _message_tool(mistral_client_factice).lower()

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)
    lignes = _memoire(mistral_client_factice).splitlines()
    assert f"  • {_BESOIN} → non présent selon l'extraction (plan.pdf)" in lignes
    assert f"  • {_BESOIN} → non présent selon l'extraction (devis.pdf)" in lignes


def test_la_reponse_enregistree_est_coupee_a_300_caracteres(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "x" * 400, "devis.pdf")
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )

    (question,) = _questions_besoin(db_session, conversation_id)
    assert question.reponse == "x" * 300


def test_un_id_introuvable_est_signale_et_seules_les_autres_sont_lues(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "devis.pdf")
    _relire(
        client,
        mistral_client_factice,
        jeton_valide,
        conversation_id,
        {"piece_jointe_ids": [999999, devis], "besoin": _BESOIN},
    )

    (appel,) = mistral_client_factice.appels_relecture_pieces_jointes
    assert "« devis.pdf »" in appel[1]["content"] and "plan.pdf" not in appel[1]["content"]
    contenu = _message_tool(mistral_client_factice)
    assert "Pièce jointe id 999999 : Pièce jointe introuvable." in contenu and "12 400 € HT" in contenu


def test_aucune_piece_jointe_trouvee_pas_dappel_dextraction(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, _, _ = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [999999], "besoin": _BESOIN}
    )

    assert mistral_client_factice.appels_relecture_pieces_jointes == []
    assert "Pièce jointe introuvable." in _message_tool(mistral_client_factice)
    assert _questions_besoin(db_session, conversation_id) == []


def test_extraction_en_echec_reponse_200_sans_question_enregistree(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.echouer_relecture_pieces_jointes(RuntimeError("Mistral injoignable"))
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )

    assert "extraction indisponible" in _message_tool(mistral_client_factice).lower()
    assert _questions_besoin(db_session, conversation_id) == []


def test_un_json_invalide_rend_lextraction_indisponible(client, mistral_client_factice, jeton_valide, db_session):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_relecture_pieces_jointes_brute("12 400 €, pas de JSON.")
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )

    assert "extraction indisponible" in _message_tool(mistral_client_factice).lower()
    assert _questions_besoin(db_session, conversation_id) == []


def test_consommation_et_inspecteur_tracent_loutil_local_et_lextraction_piece_jointe(
    client, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "devis.pdf")
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )

    assert db_session.query(Consommation).filter_by(type_appel="extraction_piece_jointe").count() == 1
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin).json()
    types = [(e["origine"], e["type_appel"]) for e in echanges]
    indice = types.index(("local", f"outil:{_OUTIL}"))
    assert types[indice + 1] == ("mistral", "extraction_piece_jointe")
    detail = client.get(f"/inspecteur/echanges/{echanges[indice + 1]['id']}", headers=entetes_admin).json()
    assert detail["statut"] == "succes" and detail["modele"] == MODELE_CHAT
    assert detail["requete_payload"]["response_format"]["type"] == "json_schema"


def test_lextraction_piece_jointe_est_comptee_dans_la_categorie_chat(
    client, mistral_client_factice, jeton_valide
):
    conversation_id, _, devis = _conversation_avec_deux_pieces_jointes(client, mistral_client_factice, jeton_valide)
    avant = client.get("/consommation", headers=_autorisation(jeton_valide)).json()
    mistral_client_factice.repondre_relecture_pieces_jointes(True, "12 400 € HT", "devis.pdf")
    _relire(
        client, mistral_client_factice, jeton_valide, conversation_id, {"piece_jointe_ids": [devis], "besoin": _BESOIN}
    )
    apres = client.get("/consommation", headers=_autorisation(jeton_valide)).json()

    assert apres["piece_jointe"]["nombre_requetes"] == avant["piece_jointe"]["nombre_requetes"]
