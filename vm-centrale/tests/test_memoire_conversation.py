import json

import pytest

# Mémoire de la conversation (spec 1.4.1, #133) : message système recalculé
# par la VM à chaque appel de chat principal, hors résumé glissant.

_TITRE_MEMOIRE = "Mémoire de la conversation :"
_PDF = ("devis.pdf", b"%PDF-1.4 contenu factice", "application/pdf")
_URL_A = "https://www.exemple.fr/bornage-a"
_URL_B = "https://www.exemple.fr/bornage-b"


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil(resume_contexte: str = "Résumé") -> str:
    return json.dumps({"resume_contexte": resume_contexte, "profil_travail": None})


def _televerser(client, mistral_client_factice, jeton: str, fichier=_PDF) -> int:
    mistral_client_factice.repondre_ocr("Montant HT : 12 400 €")
    reponse = client.post("/pieces-jointes", files={"fichier": fichier}, headers=_autorisation(jeton))
    assert reponse.status_code == 201
    return reponse.json()["piece_jointe"]["id"]


def _creer_conversation(client, mistral_client_factice, jeton: str, message: str = "Bonjour", **corps) -> int:
    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post("/conversations", json={"message": message, **corps}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    return reponse.json()["conversation"]["id"]


def _envoyer(client, mistral_client_factice, jeton: str, conversation_id: int, message: str, resume="Résumé", **corps):
    mistral_client_factice.repondre("Suite", resume_et_profil=_resume_et_profil(resume))
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": message, **corps},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200


def _rechercher(mistral_client_factice, moteur_recherche_factice, requete: str, *urls: str) -> None:
    moteur_recherche_factice.repondre(*((f"Titre {url}", url, f"Extrait {url}") for url in urls))
    mistral_client_factice.repondre_avec_appel_outil("rechercher_web", {"requete": requete, "besoin": "Besoin"})


def _memoires(messages) -> list[str]:
    return [m["content"] for m in messages if m["role"] == "system" and m["content"].startswith(_TITRE_MEMOIRE)]


def _memoire(mistral_client_factice) -> str:
    (memoire,) = _memoires(mistral_client_factice.appels_reponse[-1])
    return memoire


def test_une_piece_jointe_du_tour_precedent_encore_dans_la_fenetre_est_dans_la_memoire(
    client, mistral_client_factice, jeton_valide
):
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton_valide)
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Voici le devis", piece_jointe_id=piece_jointe_id
    )

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Quel est le montant ?")

    memoire = _memoire(mistral_client_factice)
    assert f"- Tour 1 — pièce jointe id {piece_jointe_id} « devis.pdf »" in memoire
    assert "12 400" not in memoire


def test_une_piece_jointe_et_une_recherche_sorties_de_la_fenetre_restent_avec_un_resume_vide(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton_valide)
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Voici le devis", piece_jointe_id=piece_jointe_id
    )
    _rechercher(mistral_client_factice, moteur_recherche_factice, "tarif bornage 2026", _URL_A, _URL_B)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Cherche le tarif", resume="")
    for message in ("Trois", "Quatre", "Cinq"):
        _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, message, resume="")

    messages = mistral_client_factice.appels_reponse[-1]
    assert all(m["content"] != "" for m in messages)
    memoire = _memoire(mistral_client_factice)
    assert f"- Tour 1 — pièce jointe id {piece_jointe_id} « devis.pdf »" in memoire
    assert f"- Tour 2 — recherche « tarif bornage 2026 » : {_URL_A}, {_URL_B}" in memoire
    assert "Extrait" not in memoire and "Titre https" not in memoire


def test_les_elements_suivent_lordre_des_tours(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)
    _rechercher(mistral_client_factice, moteur_recherche_factice, "première recherche", _URL_A)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Cherche")
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton_valide)
    _envoyer(
        client, mistral_client_factice, jeton_valide, conversation_id, "Voici le devis", piece_jointe_id=piece_jointe_id
    )
    _rechercher(mistral_client_factice, moteur_recherche_factice, "seconde recherche", _URL_B)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Cherche encore")

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Et donc ?")

    lignes = _memoire(mistral_client_factice).splitlines()
    assert lignes == [
        _TITRE_MEMOIRE,
        f"- Tour 2 — recherche « première recherche » : {_URL_A}",
        f"- Tour 3 — pièce jointe id {piece_jointe_id} « devis.pdf »",
        f"- Tour 4 — recherche « seconde recherche » : {_URL_B}",
    ]


def test_pas_de_memoire_sans_element(client, mistral_client_factice, jeton_valide):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide)

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Suite")

    assert _memoires(mistral_client_factice.appels_reponse[-1]) == []
    assert all(_memoires(appel) == [] for appel in mistral_client_factice.appels_reponse if not isinstance(appel, str))


def test_la_memoire_suit_le_resume_et_le_profil_et_precede_la_piece_jointe_du_tour(
    client, mistral_client_factice, jeton_valide
):
    premiere_id = _televerser(client, mistral_client_factice, jeton_valide)
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Voici le devis", piece_jointe_id=premiere_id
    )
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Deux", resume="Résumé du devis")
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Trois", resume="Résumé du devis")
    seconde_id = _televerser(client, mistral_client_factice, jeton_valide, ("plan.pdf", b"%PDF-1.4", "application/pdf"))

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Et ce plan ?", piece_jointe_id=seconde_id)

    systemes = [m["content"] for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "system"]
    position = next(i for i, contenu in enumerate(systemes) if contenu.startswith(_TITRE_MEMOIRE))
    assert systemes[position - 1] == "Résumé du devis"
    assert systemes[position + 1].startswith("Pièce jointe « plan.pdf »")
    assert "plan.pdf" not in systemes[position]


def test_le_prompt_resume_ne_porte_plus_les_mentions_ni_lextrait_de_piece_jointe(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    piece_jointe_id = _televerser(client, mistral_client_factice, jeton_valide)
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, "Voici le devis", piece_jointe_id=piece_jointe_id
    )
    _rechercher(mistral_client_factice, moteur_recherche_factice, "tarif bornage 2026", _URL_A)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Cherche")
    for message in ("Trois", "Quatre"):
        _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, message)

    prompt = "\n".join(mistral_client_factice.appels_structures)
    assert "user : Voici le devis" in prompt and "assistant : Suite" in prompt
    for absent in ("12 400", "devis.pdf", "mention courte", "requête et les URL", "tarif bornage", _URL_A):
        assert absent not in prompt


# URL du compte (#134) : repérées dans les messages user et le message du
# tour, même règle que garde_fous/urls.py, recalculées à chaque tour.


def test_une_url_du_compte_ecrite_au_tour_1_est_dans_la_memoire_au_tour_5(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(
        client, mistral_client_factice, jeton_valide, f"Regarde {_URL_A}, puis dis-moi."
    )
    for message in ("Deux", "Trois", "Quatre"):
        _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, message, resume="")

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Cinq", resume="")

    assert f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_A}" in _memoire(mistral_client_factice).splitlines()


def test_une_url_du_message_du_tour_est_dans_la_memoire_des_le_premier_message(
    client, mistral_client_factice, jeton_valide
):
    _creer_conversation(client, mistral_client_factice, jeton_valide, f"Lis <{_URL_A}>")

    (appel_chat,) = [appel for appel in mistral_client_factice.appels_reponse if not isinstance(appel, str)]
    (memoire,) = _memoires(appel_chat)
    assert memoire.splitlines() == [
        _TITRE_MEMOIRE,
        f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_A}",
    ]


def test_une_url_ecrite_par_lassistant_nest_jamais_dans_la_memoire(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    # URL de recherche : le garde-fou URL la laisse dans la réponse enregistrée.
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, f"Lis {_URL_A}")
    _rechercher(mistral_client_factice, moteur_recherche_factice, "tarif bornage", _URL_B)
    mistral_client_factice.repondre(f"Voir aussi {_URL_B}", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Cherche"},
        headers=_autorisation(jeton_valide),
    )
    assert _URL_B in reponse.json()["reponse"]

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Suite")

    lignes = _memoire(mistral_client_factice).splitlines()
    assert f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_A}" in lignes
    assert not any("URL envoyée" in ligne and "bornage-b" in ligne for ligne in lignes)


def test_une_meme_url_ecrite_deux_fois_napparait_quune_fois_au_premier_tour(
    client, mistral_client_factice, jeton_valide
):
    conversation_id = _creer_conversation(client, mistral_client_factice, jeton_valide, "Bonjour")
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, f"Lis {_URL_A}.")
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, f"Relis {_URL_A} et {_URL_B}")

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, "Relis http://exemple.fr/bornage-a/")

    assert _memoire(mistral_client_factice).splitlines() == [
        _TITRE_MEMOIRE,
        f"- Tour 2 — URL envoyée par l'utilisateur : {_URL_A}",
        f"- Tour 3 — URL envoyée par l'utilisateur : {_URL_B}",
    ]
