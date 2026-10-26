import json

import pytest

from flux_sse import fin

# Compte sans groupe Moduléo (#199, test humain #195 scénario 7) : la VM
# dit au modèle que Moduléo lui est fermé, et rechercher_web n'envoie
# jamais une référence interne (devis, facture, affaire) au moteur.

_OUTIL = "rechercher_web"
_MODULEO_FERME = (
    "Votre compte n'est rattaché à aucun groupe Moduléo. Aucune lecture n'a été faite. "
    "Demandez à un compte administrateur si vous en avez besoin."
)
_DONNEE_INTERNE = "donnée interne"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _consignes_du_premier_appel(client, mistral_client_factice, jeton: str) -> str:
    mistral_client_factice.repondre("Bonjour.", "Titre")
    reponse = client.post(
        "/conversations", json={"message": "Où en est le devis 202610-31284 ?"}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200
    fin(reponse)
    return "\n".join(m["content"] for m in mistral_client_factice.appels_reponse[0] if m["role"] == "system")


def _rechercher(client, mistral_client_factice, jeton: str, requete: str) -> tuple[int, str]:
    # Le message `tool` que le modèle relit, et la conversation.
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"requete": requete, "besoin": "Savoir où en est"})
    mistral_client_factice.repondre("Réponse.", "Titre")
    reponse = client.post("/conversations", json={"message": "Question"}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    conversation_id = fin(reponse)["conversation"]["id"]
    (message,) = [m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"]
    return conversation_id, message["content"]


def test_compte_sans_groupe_la_consigne_dit_moduleo_ferme_avec_la_phrase(
    client, faux_moduleo, mistral_client_factice, jeton_store
):
    assert _MODULEO_FERME in _consignes_du_premier_appel(client, mistral_client_factice, jeton_store.emettre("n.durand"))


def test_compte_rattache_na_pas_la_consigne(client, faux_moduleo, mistral_client_factice, jeton_valide):
    assert "aucun groupe Moduléo" not in _consignes_du_premier_appel(client, mistral_client_factice, jeton_valide)


def test_sans_config_moduleo_pas_de_consigne(client, mistral_client_factice, jeton_store):
    assert "aucun groupe Moduléo" not in _consignes_du_premier_appel(
        client, mistral_client_factice, jeton_store.emettre("n.durand")
    )


def test_la_consigne_vaut_aussi_au_tour_suivant(client, faux_moduleo, mistral_client_factice, jeton_store):
    jeton = jeton_store.emettre("n.durand")
    mistral_client_factice.repondre("Bonjour.", "Titre")
    conversation_id = fin(client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton)))[
        "conversation"
    ]["id"]
    mistral_client_factice.repondre(
        "Suite.", resume_et_profil=json.dumps({"resume_contexte": "Résumé", "profil_travail": None})
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Et la facture ?"}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200
    fin(reponse)

    consignes = [m["content"] for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "system"]
    assert any(_MODULEO_FERME in consigne for consigne in consignes)


@pytest.mark.parametrize(
    "requete",
    ["devis 202610-31284 état 2026", "facture 202609-1234", "affaire 2024-123 avancement", "2026-002"],
)
def test_une_reference_interne_ne_part_pas_au_moteur(
    requete, client, mistral_client_factice, moteur_recherche_factice, jeton_store
):
    _, contenu = _rechercher(client, mistral_client_factice, jeton_store.emettre("n.durand"), requete)

    assert moteur_recherche_factice.requetes_recues == []
    assert _DONNEE_INTERNE in contenu


def test_linspecteur_montre_la_requete_refusee(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    conversation_id, _ = _rechercher(client, mistral_client_factice, jeton_valide, "devis 202610-31284 état 2026")

    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin).json()
    (outil,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{outil['id']}", headers=entetes_admin).json()

    assert detail["requete_payload"]["arguments"]["requete"] == "devis 202610-31284 état 2026"
    assert detail["reponse_payload"]["refusee"] == "référence interne : 202610-31284"
    assert _DONNEE_INTERNE in detail["reponse_payload"]["contenu"]


@pytest.mark.parametrize("requete", ["loi climat résilience 2026", "loi de finances 2024-2025", "saison 2025-26"])
def test_une_question_generale_dun_compte_sans_groupe_passe_au_moteur(
    requete, client, faux_moduleo, mistral_client_factice, moteur_recherche_factice, jeton_store
):
    moteur_recherche_factice.repondre(("Loi", "https://www.legifrance.gouv.fr/loi", "Texte."))

    _, contenu = _rechercher(client, mistral_client_factice, jeton_store.emettre("n.durand"), requete)

    assert moteur_recherche_factice.requetes_recues == [((requete,), {})]
    assert _DONNEE_INTERNE not in contenu
