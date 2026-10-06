import json

import pytest

from vm_centrale.models import Consommation, EchangeInspecteur

# Boucle de tool calling (spec 1.4.0) : tous les appels d'une réponse, au plus
# 3 appels de chat principaux par message, le 3e sans `tools`.

_PDF = ("document.pdf", b"%PDF-1.4 contenu factice", "application/pdf")
_OUTIL_PJ = "obtenir_contenu_piece_jointe"


def _reponse_resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": None})


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _autorisation_admin(jeton: str) -> dict[str, str]:
    return {**_autorisation(jeton), "X-Admin-Key": "cle-admin-de-test"}


def _amener_piece_jointe_hors_fenetre(client, mistral_client_factice, jeton: str) -> tuple[int, int]:
    # Voir tests/test_tool_calling_piece_jointe.py : l'outil pièce jointe
    # n'est éligible qu'avec une pièce jointe sortie de la fenêtre.
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    piece_jointe_id = client.post(
        "/pieces-jointes", files={"fichier": _PDF}, headers=_autorisation(jeton)
    ).json()["piece_jointe"]["id"]

    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = client.post(
        "/conversations",
        json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
        headers=_autorisation(jeton),
    ).json()["conversation"]["id"]

    mistral_client_factice.repondre("Deuxième réponse", resume_et_profil=_reponse_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200
    return conversation_id, piece_jointe_id


def _envoyer(client, jeton: str, conversation_id: int, message: str = "Relis le plan"):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": message},
        headers=_autorisation(jeton),
    )


def _demande(piece_jointe_id: int, *ids_appels: str) -> list[tuple[str, dict, str]]:
    return [(_OUTIL_PJ, {"piece_jointe_id": piece_jointe_id}, id_appel) for id_appel in ids_appels]


def test_deux_appels_doutil_dans_une_reponse_font_partir_deux_messages_tool(
    client, mistral_client_factice, jeton_valide
):
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide
    )
    appels_avant = len(mistral_client_factice.appels_reponse)

    mistral_client_factice.repondre_avec_appels_outils(_demande(piece_jointe_id, "call_a", "call_b"))
    mistral_client_factice.repondre("Réponse finale", resume_et_profil=_reponse_resume_et_profil())
    reponse = _envoyer(client, jeton_valide, conversation_id)

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Réponse finale"
    assert len(mistral_client_factice.appels_reponse) - appels_avant == 2
    messages_outils = [
        m for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "tool"
    ]
    assert [m["tool_call_id"] for m in messages_outils] == ["call_a", "call_b"]
    assert all(m["content"] == "Plan de masse détaillé" for m in messages_outils)


def test_le_troisieme_appel_principal_part_sans_tools_et_sa_reponse_est_persistee(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide
    )
    appels_avant = len(mistral_client_factice.appels_reponse)
    consommations_avant = db_session.query(Consommation).count()

    # Le modèle redemande un outil à chaque appel qui en propose : seuls les
    # deux premiers appels principaux portent `tools`.
    mistral_client_factice.repondre_avec_appels_outils(
        _demande(piece_jointe_id, "call_1"),
        _demande(piece_jointe_id, "call_2"),
        _demande(piece_jointe_id, "call_3"),
    )
    mistral_client_factice.repondre("Réponse forcée", resume_et_profil=_reponse_resume_et_profil())
    reponse = _envoyer(client, jeton_valide, conversation_id)

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Réponse forcée"
    tools_du_message = mistral_client_factice.tools_appels_reponse[appels_avant:]
    assert len(tools_du_message) == 3
    assert tools_du_message[0] and tools_du_message[1]
    assert tools_du_message[2] is None
    messages_outils = [m for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in messages_outils] == ["call_1", "call_2"]

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert detail.json()["messages"][-1]["contenu"] == "Réponse forcée"

    # Une ligne `chat` par appel principal, plus le résumé et profil.
    nouvelles = db_session.query(Consommation).order_by(Consommation.id).all()[consommations_avant:]
    assert sorted(c.type_appel for c in nouvelles) == ["chat", "chat", "chat", "resume_et_profil"]


def test_un_tour_qui_echoue_ne_laisse_ni_consommation_ni_echange_succes(
    client, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide
    )
    consommations_avant = db_session.query(Consommation).count()
    echanges_avant = db_session.query(EchangeInspecteur).count()

    mistral_client_factice.repondre_avec_appels_outils(
        _demande(piece_jointe_id, "call_1"), _demande(piece_jointe_id, "call_2")
    )
    mistral_client_factice.echouer_apres_demandes_outils(RuntimeError("troisième appel indisponible"))
    mistral_client_factice.repondre("Inutilisée", resume_et_profil=_reponse_resume_et_profil())
    reponse = _envoyer(client, jeton_valide, conversation_id)

    assert reponse.status_code == 502
    assert db_session.query(Consommation).count() == consommations_avant
    nouveaux = db_session.query(EchangeInspecteur).order_by(EchangeInspecteur.id).all()[echanges_avant:]
    assert [(e.type_appel, e.statut) for e in nouveaux] == [("chat", "echec")]


def test_inspecteur_place_les_echanges_locaux_des_outils_entre_les_appels_mistral(
    client, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    conversation_id, piece_jointe_id = _amener_piece_jointe_hors_fenetre(
        client, mistral_client_factice, jeton_valide
    )
    echanges_avant = len(
        client.get(
            f"/inspecteur/conversations/{conversation_id}/echanges",
            headers=_autorisation_admin(jeton_valide),
        ).json()
    )

    mistral_client_factice.repondre_avec_appels_outils(
        _demande(piece_jointe_id, "call_a", "call_b"), _demande(piece_jointe_id, "call_c")
    )
    mistral_client_factice.repondre("Réponse finale", resume_et_profil=_reponse_resume_et_profil())
    assert _envoyer(client, jeton_valide, conversation_id).status_code == 200

    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges",
        headers=_autorisation_admin(jeton_valide),
    ).json()[echanges_avant:]
    outil = f"outil:{_OUTIL_PJ}"
    assert [(e["origine"], e["type_appel"]) for e in echanges] == [
        ("mistral", "chat"),
        ("local", outil),
        ("local", outil),
        ("mistral", "chat"),
        ("local", outil),
        ("mistral", "chat"),
        ("mistral", "resume_et_profil"),
        ("local", "garde_fous"),
    ]

    detail_outil = client.get(
        f"/inspecteur/echanges/{echanges[1]['id']}", headers=_autorisation_admin(jeton_valide)
    ).json()
    assert detail_outil["origine"] == "local"
    assert detail_outil["statut"] == "succes"
    assert detail_outil["requete_payload"]["arguments"] == {"piece_jointe_id": piece_jointe_id}
    assert detail_outil["reponse_payload"]["contenu"] == "Plan de masse détaillé"
    assert detail_outil["piece_jointe_id"] == piece_jointe_id
