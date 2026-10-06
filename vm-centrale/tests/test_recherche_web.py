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


def _conversation_avec_recherche(client, mistral_client_factice, moteur_recherche_factice, jeton) -> int:
    moteur_recherche_factice.repondre(*_RESULTATS)
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    return _creer_conversation(client, jeton)


def _assert_mention_courte(texte: str) -> None:
    assert "loi climat résilience" in texte
    for titre, url, extrait in _RESULTATS[:5]:
        assert url in texte
        assert titre not in texte and extrait not in texte


def test_au_tour_suivant_la_fenetre_mentionne_la_requete_et_les_url_jamais_les_extraits(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, jeton_valide
    )

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil())
    assert _envoyer(client, jeton_valide, conversation_id, "Et ensuite ?").status_code == 200

    messages = mistral_client_factice.appels_reponse[-1]
    (assistant,) = [m for m in messages if m["role"] == "assistant"]
    assert assistant["content"].startswith("Voici la loi.")
    _assert_mention_courte(assistant["content"])
    assert not _messages_tool(messages)


def test_la_ligne_envoyee_au_resume_mentionne_la_requete_et_les_url_jamais_les_extraits(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, jeton_valide
    )

    mistral_client_factice.repondre("Suite", resume_et_profil=_reponse_resume_et_profil())
    for message in ("Deux", "Trois"):
        assert _envoyer(client, jeton_valide, conversation_id, message).status_code == 200

    prompt = mistral_client_factice.appels_structures[-1]
    ligne = prompt[prompt.index("assistant : Voici la loi.") :]
    ligne = ligne[: ligne.index("user : Deux")]
    _assert_mention_courte(ligne)


# Pages entières (spec 1.4.0, étapes 2 à 4) : servies par
# TelechargeurPagesFactice (conftest), nettoyées par le vrai trafilatura.

_URL_DECRET = _RESULTATS[1][1]
_URL_ANALYSE = _RESULTATS[2][1]


def _page_html(*paragraphes: str) -> str:
    # Deux paragraphes de remplissage : sur une page minuscule, trafilatura
    # garde aussi le menu, faute de texte principal assez long.
    remplissage = (
        "Cette loi porte lutte contre le dérèglement climatique et renforcement de la "
        "résilience face à ses effets, à partir des propositions de la Convention citoyenne.",
        "Elle touche la consommation, la production, les déplacements, le logement et "
        "l'alimentation, et renforce la protection judiciaire de l'environnement.",
    )
    corps = "".join(f"<p>{paragraphe}</p>" for paragraphe in (*remplissage, *paragraphes))
    return (
        "<html><head><title>Page</title><script>var suivi = 1;</script></head><body>"
        "<nav><a href='/'>Accueil</a> Menu du site</nav>"
        f"<article><h1>Loi Climat et résilience</h1>{corps}</article>"
        "<footer>Mentions légales</footer></body></html>"
    )


def _page_longue(marqueur_de_fin: str, nombre_paragraphes: int) -> str:
    return _page_html(
        *(
            f"Article {numero} de la loi, assez long pour compter comme texte principal."
            for numero in range(nombre_paragraphes)
        ),
        marqueur_de_fin,
    )


def _echange_outil(client, conversation_id: int, jeton: str, monkeypatch) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton), "X-Admin-Key": "cle-admin-de-test"}
    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    (outil,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    return client.get(f"/inspecteur/echanges/{outil['id']}", headers=entetes_admin).json()


def _textes_nettoyes(db_session, conversation_id: int) -> list[str]:
    lignes = (
        db_session.query(ResultatRechercheWeb)
        .filter_by(conversation_id=conversation_id)
        .order_by(ResultatRechercheWeb.id)
        .all()
    )
    return [ligne.texte_nettoye for ligne in lignes]


def test_seules_les_trois_premieres_pages_sont_telechargees_et_leur_texte_nettoye_va_au_modele(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    moteur_recherche_factice.repondre(*_RESULTATS)
    for titre, url, _ in _RESULTATS:
        telechargeur_pages_factice.servir(url, _page_html(f"Texte complet de la page {titre}."))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    assert sorted(telechargeur_pages_factice.urls_recues) == sorted(url for _, url, _ in _RESULTATS[:3])
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    for _, url, extrait in _RESULTATS[:5]:
        assert url in contenu and extrait in contenu
    for titre, _, _ in _RESULTATS[:3]:
        assert f"Texte complet de la page {titre}." in contenu
    assert "Texte complet de la page Fiche pratique." not in contenu
    assert "var suivi" not in contenu and "Menu du site" not in contenu

    textes = _textes_nettoyes(db_session, conversation_id)
    for (titre, _, _), texte in zip(_RESULTATS[:3], textes):
        assert f"Texte complet de la page {titre}." in texte
    assert textes[3:] == ["", ""]


def test_une_page_en_echec_est_ignoree_et_son_extrait_de_moteur_reste(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    moteur_recherche_factice.repondre(*_RESULTATS[:4])
    telechargeur_pages_factice.servir(_URL_TROUVEE, _page_html("Texte de la loi lue."))
    telechargeur_pages_factice.servir(_URL_DECRET, "<html>Introuvable</html>", statut=404)
    telechargeur_pages_factice.servir(
        _URL_ANALYSE, "%PDF-1.7 Texte de l'analyse", type_contenu="application/pdf"
    )
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    conversation_id = reponse.json()["conversation"]["id"]
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    assert "Texte de la loi lue." in contenu
    assert "Introuvable" not in contenu and "%PDF" not in contenu
    for _, url, extrait in _RESULTATS[:4]:
        assert url in contenu and extrait in contenu
    assert _textes_nettoyes(db_session, conversation_id)[1:] == ["", "", ""]

    pages = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert [(page["url"], page["statut"]) for page in pages] == [
        (_URL_TROUVEE, 200),
        (_URL_DECRET, 404),
        (_URL_ANALYSE, 200),
    ]
    assert pages[0]["taille"] > 0 and not pages[0]["retiree_par_plafond"]
    assert all(page["taille"] == 0 and page["erreur"] for page in pages[1:])


def test_une_page_injoignable_est_ignoree_avec_son_erreur_dans_linspecteur(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, monkeypatch
):
    moteur_recherche_factice.repondre(_RESULTATS[0])
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    (page,) = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert page["url"] == _URL_TROUVEE and page["statut"] is None and page["taille"] == 0
    assert "délai" in page["erreur"]


def test_une_page_longue_nest_jamais_tronquee(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    moteur_recherche_factice.repondre(_RESULTATS[0])
    telechargeur_pages_factice.servir(_URL_TROUVEE, _page_longue("FIN DE LA PAGE LONGUE", 1500))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    assert "Article 0 de la loi" in message_tool["content"]
    assert "Article 1499 de la loi" in message_tool["content"]
    assert "FIN DE LA PAGE LONGUE" in message_tool["content"]
    (texte,) = _textes_nettoyes(db_session, conversation_id)
    assert len(texte) > 100_000 and texte.endswith("FIN DE LA PAGE LONGUE")


def test_au_dela_du_plafond_global_la_derniere_page_entiere_est_retiree_et_linspecteur_le_montre(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    # Trois pages d'environ 140 000 caractères : leur total dépasse 80 % de
    # la fenêtre du modèle d'extraction, deux d'entre elles tiennent.
    moteur_recherche_factice.repondre(*_RESULTATS[:3])
    for numero, (_, url, _) in enumerate(_RESULTATS[:3]):
        telechargeur_pages_factice.servir(url, _page_longue(f"FIN DE LA PAGE {numero}", 1900))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    assert "FIN DE LA PAGE 0" in contenu and "FIN DE LA PAGE 1" in contenu
    assert "FIN DE LA PAGE 2" not in contenu
    assert _RESULTATS[2][2] in contenu
    textes = _textes_nettoyes(db_session, conversation_id)
    assert textes[0].endswith("FIN DE LA PAGE 0") and textes[1].endswith("FIN DE LA PAGE 1")
    assert textes[2] == ""

    pages = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert [page["retiree_par_plafond"] for page in pages] == [False, False, True]
    assert all(page["statut"] == 200 and page["taille"] > 100_000 for page in pages)


def test_un_chiffre_present_seulement_dans_le_texte_dune_page_reste_dans_la_reponse(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    moteur_recherche_factice.repondre(_RESULTATS[0])
    telechargeur_pages_factice.servir(
        _URL_TROUVEE, _page_html("La loi a été promulguée en 2021 et compte 305 articles.")
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
