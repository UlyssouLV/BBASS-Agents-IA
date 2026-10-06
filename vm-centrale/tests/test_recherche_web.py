import json

from vm_centrale.models import EchangeInspecteur, ResultatRechercheWeb

# Outil rechercher_web (spec 1.4.0) : SearXNG remplacé par
# MoteurRechercheFactice (conftest), aucun accès réseau.

_OUTIL = "rechercher_web"
_URL_TROUVEE = "https://www.legifrance.gouv.fr/loi-climat-resilience"
_URL_INVENTEE = "https://inventee.example.org/rapport"
_RESULTATS = [
    ("Loi Climat et résilience", _URL_TROUVEE, "Texte de la loi Climat et résilience."),
    ("Décret d'application", "https://www.legifrance.gouv.fr/decret", "Décret pris pour la loi."),
    ("Analyse", "https://www.vie-publique.fr/loi-climat", "Ce que change la loi."),
    ("Fiche pratique", "https://www.service-public.fr/fiche", "Démarches."),
    ("Actualité", "https://www.ecologie.gouv.fr/actualite", "Entrée en vigueur."),
    ("Sixième résultat", "https://www.exemple.fr/sixieme", "Jamais retenu."),
]


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _reponse_resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _demander_recherche(mistral_client_factice, requete: str = "loi climat résilience") -> None:
    mistral_client_factice.repondre_avec_appel_outil(
        _OUTIL, {"requete": requete, "besoin": "Trouver le texte officiel de la loi pour le client Dupont"}
    )


def _creer_conversation(client, jeton: str, message: str = "Trouve la loi Climat") -> int:
    reponse = client.post("/conversations", json={"message": message}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    return reponse.json()["conversation"]["id"]


def _envoyer(client, jeton: str, conversation_id: int, message: str):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": message},
        headers=_autorisation(jeton),
    )


def _noms_outils(tools) -> list[str]:
    return [outil["function"]["name"] for outil in tools or []]


def _messages_tool(messages) -> list[dict]:
    return [m for m in messages if isinstance(m, dict) and m["role"] == "tool"]


def test_rechercher_web_est_declare_sur_lappel_principal_jamais_sur_titrage_ni_resume(
    client, mistral_client_factice, jeton_valide, db_session
):
    mistral_client_factice.repondre("Réponse", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide, "Bonjour")
    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil())
    for message in ("Deux", "Trois"):
        assert _envoyer(client, jeton_valide, conversation_id, message).status_code == 200

    echanges = db_session.query(EchangeInspecteur).filter_by(conversation_id=conversation_id).all()
    par_type: dict[str, list] = {}
    for echange in echanges:
        par_type.setdefault(echange.type_appel, []).append(echange.requete_payload)
    assert len(par_type["chat"]) == 3
    assert all(_OUTIL in _noms_outils(payload.get("tools")) for payload in par_type["chat"])
    assert par_type["titrage"] and par_type["resume_et_profil"]
    for payload in par_type["titrage"] + par_type["resume_et_profil"]:
        assert "tools" not in payload


def test_le_moteur_recoit_la_requete_seule_et_le_modele_les_cinq_premiers_resultats(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    moteur_recherche_factice.repondre(*_RESULTATS)
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    _creer_conversation(client, jeton_valide)

    assert moteur_recherche_factice.requetes_recues == [(("loi climat résilience",), {})]
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    for titre, url, extrait in _RESULTATS[:5]:
        assert titre in contenu and url in contenu and extrait in contenu
    assert "sixieme" not in contenu
    assert "Dupont" not in contenu


def test_les_resultats_sont_persistes_puis_supprimes_avec_la_conversation(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, db_session
):
    moteur_recherche_factice.repondre(*_RESULTATS)
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    lignes = (
        db_session.query(ResultatRechercheWeb)
        .filter_by(conversation_id=conversation_id)
        .order_by(ResultatRechercheWeb.id)
        .all()
    )
    assert [(l.titre, l.url, l.extrait_moteur) for l in lignes] == _RESULTATS[:5]
    assert all(l.requete == "loi climat résilience" and l.texte_nettoye == "" for l in lignes)

    suppression = client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert suppression.status_code == 204
    assert db_session.query(ResultatRechercheWeb).count() == 0


def test_une_url_des_resultats_reste_au_tour_meme_et_au_tour_suivant_une_url_inventee_part(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    moteur_recherche_factice.repondre(*_RESULTATS)
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre(
        f"Le texte est ici : [loi]({_URL_TROUVEE}). Voir aussi {_URL_INVENTEE}", "Titre"
    )
    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    texte = reponse.json()["reponse"]
    assert f"[loi]({_URL_TROUVEE})" in texte
    assert "inventee.example.org" not in texte

    conversation_id = reponse.json()["conversation"]["id"]
    mistral_client_factice.repondre(
        f"Le lien était {_URL_TROUVEE} et non {_URL_INVENTEE}",
        resume_et_profil=_reponse_resume_et_profil(),
    )
    suivante = _envoyer(client, jeton_valide, conversation_id, "Redonne-moi le lien")

    assert suivante.status_code == 200
    assert _URL_TROUVEE in suivante.json()["reponse"]
    assert "inventee.example.org" not in suivante.json()["reponse"]


def test_moteur_injoignable_reponse_200_et_texte_recherche_indisponible(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, db_session
):
    moteur_recherche_factice.echouer()
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Je n'ai pas pu chercher.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Je n'ai pas pu chercher."
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    assert "recherche indisponible" in message_tool["content"].lower()
    assert db_session.query(ResultatRechercheWeb).count() == 0


def test_aucun_resultat_reponse_200_et_texte_aucun_resultat(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    mistral_client_factice.repondre("Première", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide, "Bonjour")

    moteur_recherche_factice.repondre()
    _demander_recherche(mistral_client_factice, "requête introuvable")
    mistral_client_factice.repondre("Rien trouvé.", resume_et_profil=_reponse_resume_et_profil())
    reponse = _envoyer(client, jeton_valide, conversation_id, "Cherche ceci")

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Rien trouvé."
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-1])
    assert "aucun résultat" in message_tool["content"].lower()


def test_inspecteur_trace_la_requete_les_resultats_bruts_et_le_texte_renvoye(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    moteur_recherche_factice.repondre(*_RESULTATS[:2])
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    assert [(e["origine"], e["type_appel"]) for e in echanges] == [
        ("mistral", "chat"),
        ("local", f"outil:{_OUTIL}"),
        ("mistral", "chat"),
        ("mistral", "titrage"),
    ]

    detail = client.get(f"/inspecteur/echanges/{echanges[1]['id']}", headers=entetes_admin).json()
    assert detail["requete_payload"]["arguments"]["requete"] == "loi climat résilience"
    assert detail["reponse_payload"]["resultats"] == [
        {"titre": titre, "url": url, "extrait": extrait} for titre, url, extrait in _RESULTATS[:2]
    ]
    assert _URL_TROUVEE in detail["reponse_payload"]["contenu"]


def test_un_chiffre_dun_extrait_du_moteur_reste_un_chiffre_absent_part_sans_phrase_fixe(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    moteur_recherche_factice.repondre(
        ("Loi Climat et résilience", _URL_TROUVEE, "Promulguée le 22 août 2021, 305 articles."),
    )
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("La loi compte 305 articles et 48 décrets.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "305" in contenu
    assert "48" not in contenu
    assert "page ni document" not in contenu
