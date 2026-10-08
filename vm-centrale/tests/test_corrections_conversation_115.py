import json
from datetime import date

from flux_sse import fin

from vm_centrale.outils.moduleo.affaires import outil as outil_affaires
from vm_centrale.routers import conversations

# Corrections du test humain 1.5.0 (conversation 115, « Affaires judiciaires
# récentes non documentées », #182) : affaires récentes sans critère, plus
# récentes d'abord, refus sans invention, date du jour comme source, phrase
# fixe Moduléo, titrage et note après une réponse remplacée.

_AFFAIRES = "chercher_affaires_moduleo"
_RECHERCHE = "cogeo/affaire?texte="
_PHRASE_MODULEO = "Moduléo n'a rien renvoyé pour cette demande. Précise un numéro d'affaire, un nom ou une période."
_PHRASE_SANS_DONNEES = "Je n'ai trouvé ni page ni document pour appuyer une réponse chiffrée."
_REPONSE_INVENTEE = "Voici les 10 dernières affaires : 2024-871, 2024-872 et 2024-873."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _appeler(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici."):
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post("/conversations", json={"message": "Les dernières affaires"}, headers=_autorisation(jeton))


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def test_une_recherche_affiche_les_affaires_les_plus_recentes_dabord(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    for id_affaire in (101, 305, 202):
        faux_moduleo.ajouter_affaire(id_affaire, f"2024-{id_affaire}", "Bornage Castries")

    _appeler(client, mistral_client_factice, jeton_valide, {"texte": "castries", "nb_max": 2})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.index("Affaire 2024-305") < contenu.index("Affaire 2024-202")
    assert "Affaire 2024-101" not in contenu


def test_sans_critere_lit_les_affaires_creees_ces_90_derniers_jours(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(outil_affaires, "_date_du_jour", lambda: date(2026, 10, 8))
    faux_moduleo.ajouter_affaire(1, "2026-001", "Bornage", DateCreation="2026-08-01T09:00:00+02:00")
    faux_moduleo.ajouter_affaire(2, "2026-002", "Division", DateCreation="2026-09-15T09:00:00+02:00")
    faux_moduleo.ajouter_affaire(3, "2025-900", "Ancienne", DateCreation="2025-01-15T09:00:00+01:00")

    _appeler(client, mistral_client_factice, jeton_valide, {"nb_max": 10})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["dateCreationMin"] == "2026-07-10"
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("2 affaires créées depuis le 10/07/2026, 2 plus récentes affichées")
    assert contenu.index("Affaire 2026-002") < contenu.index("Affaire 2026-001")
    assert "Affaire 2025-900" not in contenu


def test_sans_aucun_argument_lit_aussi_les_affaires_recentes(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(outil_affaires, "_date_du_jour", lambda: date(2026, 10, 8))
    for id_affaire in range(1, 8):
        faux_moduleo.ajouter_affaire(id_affaire, f"2026-00{id_affaire}", "Bornage", DateCreation="2026-09-01")

    _appeler(client, mistral_client_factice, jeton_valide, {})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("7 affaires créées depuis le 10/07/2026, 5 plus récentes affichées")
    assert "Affaire 2026-007" in contenu and "Affaire 2026-002" not in contenu


def test_sans_affaire_recente_le_resultat_dit_la_periode(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(outil_affaires, "_date_du_jour", lambda: date(2026, 10, 8))

    _appeler(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == "Aucune affaire créée dans Moduléo depuis le 10/07/2026."


def test_le_schema_dit_quun_appel_sans_critere_lit_les_affaires_recentes(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _AFFAIRES]
    assert "90 derniers jours" in schema["function"]["description"]


def test_un_etat_inconnu_dit_quaucune_lecture_na_ete_faite_et_interdit_dinventer(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _appeler(client, mistral_client_factice, jeton_valide, {"etat": "judiciaire"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Aucune lecture faite dans Moduléo" in contenu
    assert "n'invente aucune affaire" in contenu
    assert "demande" in contenu
    assert _recherches(faux_moduleo) == []


def test_un_nom_non_resolu_dit_quaucune_lecture_na_ete_faite_et_interdit_dinventer(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _appeler(client, mistral_client_factice, jeton_valide, {"suivi_par": "Inconnu"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Aucune lecture faite dans Moduléo" in contenu
    assert "n'invente aucune affaire" in contenu
    assert _recherches(faux_moduleo) == []


def test_une_question_qui_cite_la_date_du_jour_nest_pas_remplacee(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 8))
    mistral_client_factice.repondre("Depuis le 1er septembre 2026 ?", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Les dernières affaires"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == "Depuis le 1er septembre 2026 ?"


def test_un_autre_chiffre_hors_source_reste_retire_meme_dans_une_question(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 8))
    mistral_client_factice.repondre("Voulez-vous les 37 affaires depuis le 1er septembre 2026 ?", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Les dernières affaires"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == _PHRASE_SANS_DONNEES


def test_apres_un_appel_moduleo_la_reponse_remplacee_parle_de_moduleo(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    reponse = _appeler(client, mistral_client_factice, jeton_valide, {"texte": "judiciaire"}, _REPONSE_INVENTEE)

    assert fin(reponse)["reponse"] == _PHRASE_MODULEO


def test_une_premiere_reponse_remplacee_est_titree_sur_le_message_du_collaborateur(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _appeler(client, mistral_client_factice, jeton_valide, {"texte": "judiciaire"}, _REPONSE_INVENTEE)

    prompt_titrage = mistral_client_factice.appels_reponse[-1]
    assert isinstance(prompt_titrage, str)
    assert "Les dernières affaires" in prompt_titrage
    assert "Moduléo n'a rien renvoyé" not in prompt_titrage
    assert "Assistant" not in prompt_titrage
    assert "aucun mot absent" in prompt_titrage


def test_le_prompt_de_titrage_interdit_tout_mot_absent_de_lechange(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour, que puis-je faire ?", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    prompt_titrage = mistral_client_factice.appels_reponse[-1]
    assert "Assistant : Bonjour, que puis-je faire ?" in prompt_titrage
    assert "aucun mot absent" in prompt_titrage


def test_le_tour_suivant_une_reponse_remplacee_envoie_une_note_jamais_la_reponse_brute(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    reponse = _appeler(client, mistral_client_factice, jeton_valide, {"texte": "judiciaire"}, _REPONSE_INVENTEE)
    conversation_id = fin(reponse)["conversation"]["id"]

    mistral_client_factice.repondre("Pour quelle période ?", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et alors ?"},
        headers=_autorisation(jeton_valide),
    )

    messages = mistral_client_factice.appels_reponse[-1]
    notes = [m["content"] for m in messages if m["role"] == "system" and "remplacée par la VM" in m["content"]]
    assert len(notes) == 1
    assert "aucun chiffre" in notes[0] and "critère" in notes[0]
    assert messages[-1] == {"role": "user", "content": "Et alors ?"}
    assert "2024-871" not in json.dumps(messages, ensure_ascii=False)


def test_pas_de_note_quand_la_reponse_precedente_na_pas_ete_remplacee(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    conversation_id = fin(reponse)["conversation"]["id"]

    mistral_client_factice.repondre("Oui.", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Et alors ?"}, headers=_autorisation(jeton_valide)
    )

    messages = mistral_client_factice.appels_reponse[-1]
    assert not [m for m in messages if m["role"] == "system" and "remplacée par la VM" in m["content"]]
