import json
from datetime import datetime, timezone

from vm_centrale.models import Message

# Jauge de contexte (spec 1.4.2) : le message `assistant` porte le
# prompt_tokens du dernier appel principal du tour, jamais celui d'un appel
# isolé (extraction, résumé, titrage) ; la fenêtre vient de la fiche de
# MODELE_CHAT.

_FENETRE = 262_144


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _reponse_resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _creer_conversation(client, jeton: str) -> int:
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    return reponse.json()["conversation"]["id"]


def _envoyer(client, jeton: str, conversation_id: int, message: str = "Trouve la loi Climat"):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": message},
        headers=_autorisation(jeton),
    )


def test_un_envoi_avec_un_tour_doutils_renvoie_le_prompt_tokens_du_dernier_appel_principal(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "loi climat", "besoin": "Trouver le texte officiel"}
    )
    mistral_client_factice.repondre("Réponse finale", resume_et_profil=_reponse_resume_et_profil())
    mistral_client_factice.fixer_prompt_tokens_principaux(1_200, 45_210)
    reponse = _envoyer(client, jeton_valide, conversation_id)

    assert reponse.status_code == 200
    assert reponse.json()["tokens_contexte"] == 45_210
    assert reponse.json()["fenetre_contexte"] == _FENETRE

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()
    assistant = detail["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["tokens_contexte"] == 45_210
    assert assistant["fenetre_contexte"] == _FENETRE
    assert detail["messages"][-2]["tokens_contexte"] is None


def test_le_premier_message_porte_aussi_le_prompt_tokens_de_son_appel_principal(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Première réponse", "Titre")
    mistral_client_factice.fixer_prompt_tokens_principaux(3_000)
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert reponse.json()["tokens_contexte"] == 3_000
    assert reponse.json()["fenetre_contexte"] == _FENETRE
    conversation_id = reponse.json()["conversation"]["id"]
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()
    assert detail["messages"][-1]["tokens_contexte"] == 3_000


def test_un_ancien_message_renvoie_null(client, mistral_client_factice, jeton_valide, db_session):
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)
    # Message persisté avant la 1.4.2 : colonne à NULL, jamais recalculée.
    db_session.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            contenu="Réponse d'avant la jauge",
            date_creation=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()

    assert detail["messages"][-1]["tokens_contexte"] is None
    assert detail["messages"][-1]["fenetre_contexte"] == _FENETRE
