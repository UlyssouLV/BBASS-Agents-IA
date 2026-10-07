import json
import re

from vm_centrale.config import MODELE_CHAT
from vm_centrale.models import Consommation, EchangeInspecteur, QuestionCouverte, ResultatRechercheWeb
from vm_centrale.outils.lire_pages_web import CONSIGNE_LECTURE_PAGE, CONSIGNE_REVERIFICATION_PAGE
from vm_centrale.outils.recherche_web import CONSIGNE_EXTRACTION

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


def test_la_description_de_requete_renvoie_a_la_date_du_jour_sans_annee_en_dur(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre")
    _creer_conversation(client, jeton_valide, "Bonjour")

    outil = next(t for t in mistral_client_factice.tools_appels_reponse[0] if t["function"]["name"] == _OUTIL)
    description = outil["function"]["parameters"]["properties"]["requete"]["description"]
    assert "date du jour" in description
    assert not re.search(r"\b(19|20)\d{2}\b", description)


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
        ("local", "garde_fous"),
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
    mistral_client_factice.repondre("La loi compte 305 articles. Elle a 48 décrets.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "305" in contenu
    assert "48" not in contenu
    assert "page ni document" not in contenu


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


def _pages_envoyees_a_lextraction(mistral_client_factice) -> str:
    (appel,) = mistral_client_factice.appels_extraction
    return appel[-1]["content"]


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
    contenu = _pages_envoyees_a_lextraction(mistral_client_factice)
    for titre, url, _ in _RESULTATS[:3]:
        assert f"--- Page : {url} ---" in contenu
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
    contenu = _pages_envoyees_a_lextraction(mistral_client_factice)
    assert "Texte de la loi lue." in contenu
    assert "Introuvable" not in contenu and "%PDF" not in contenu
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    for _, url, _ in _RESULTATS[:4]:
        assert url in message_tool["content"]
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

    contenu = _pages_envoyees_a_lextraction(mistral_client_factice)
    assert "Article 0 de la loi" in contenu
    assert "Article 1499 de la loi" in contenu
    assert "FIN DE LA PAGE LONGUE" in contenu
    (texte,) = _textes_nettoyes(db_session, conversation_id)
    assert len(texte) > 100_000 and texte.endswith("FIN DE LA PAGE LONGUE")


# Plafond en vrais tokens (spec 1.4.2) : 80 % de la fenêtre de la fiche
# MODELE_CHAT, compté par le tokenizer de Mistral Small 4.
_PLAFOND_TOKENS = int(262_144 * 0.8)
# Texte nettoyé de _page_html("Bonjour le monde") : titre, remplissage et
# paragraphe, 352 caractères, 71 tokens pour le tokenizer de Mistral Small 4.
_TAILLE_PAGE_CONNUE = 352
_TOKENS_PAGE_CONNUE = 71


def _page_dense(marqueur_de_fin: str, nombre_paragraphes: int) -> str:
    # Des chiffres : environ un token par caractère, bien plus que 3
    # caractères ≈ 1 token. Paragraphes tous différents : trafilatura
    # retire les doublons.
    return _page_html(
        *(f"Ligne {numero} : " + "0123456789" * 100 for numero in range(nombre_paragraphes)),
        marqueur_de_fin,
    )


def _page_legere(marqueur_de_fin: str, nombre_paragraphes: int) -> str:
    # Un mot courant répété : plus de 10 caractères par token.
    return _page_html(
        *(f"Paragraphe {numero} : " + "environnement " * 70 for numero in range(nombre_paragraphes)),
        marqueur_de_fin,
    )


def test_le_tokenizer_compte_les_tokens_dune_page_connue_dans_linspecteur(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    moteur_recherche_factice.repondre(_RESULTATS[0])
    telechargeur_pages_factice.servir(_URL_TROUVEE, _page_html("Bonjour le monde"))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    (texte, *_) = _textes_nettoyes(db_session, conversation_id)
    assert texte.endswith("Bonjour le monde")
    (page,) = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert len(texte) == page["taille"] == _TAILLE_PAGE_CONNUE
    assert page["tokens"] == _TOKENS_PAGE_CONNUE


def test_au_dela_du_plafond_en_tokens_la_derniere_page_entiere_est_retiree_et_linspecteur_le_montre(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    # Trois pages d'environ 80 000 tokens et autant de caractères : leur
    # total dépasse le plafond en tokens, deux d'entre elles tiennent, bien
    # que le total en caractères soit loin de l'ancien plafond estimé.
    moteur_recherche_factice.repondre(*_RESULTATS[:3])
    for numero, (_, url, _) in enumerate(_RESULTATS[:3]):
        telechargeur_pages_factice.servir(url, _page_dense(f"FIN DE LA PAGE {numero}", 80))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    contenu = _pages_envoyees_a_lextraction(mistral_client_factice)
    assert "FIN DE LA PAGE 0" in contenu and "FIN DE LA PAGE 1" in contenu
    assert "FIN DE LA PAGE 2" not in contenu
    textes = _textes_nettoyes(db_session, conversation_id)
    assert textes[0].endswith("FIN DE LA PAGE 0") and textes[1].endswith("FIN DE LA PAGE 1")
    assert textes[2] == ""

    pages = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert [page["retiree_par_plafond"] for page in pages] == [False, False, True]
    assert all(page["statut"] == 200 and page["tokens"] > 70_000 for page in pages)
    assert pages[0]["tokens"] + pages[1]["tokens"] <= _PLAFOND_TOKENS < sum(page["tokens"] for page in pages)
    assert sum(page["taille"] for page in pages) < int(262_144 * 0.8 * 3)


def test_des_pages_qui_tiennent_en_tokens_ne_sont_pas_retirees_quelle_que_soit_leur_taille(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    monkeypatch,
):
    # Trois pages d'environ 250 000 caractères : au-dessus de l'ancien
    # plafond estimé à 3 caractères par token, bien sous le plafond en
    # tokens.
    moteur_recherche_factice.repondre(*_RESULTATS[:3])
    for numero, (_, url, _) in enumerate(_RESULTATS[:3]):
        telechargeur_pages_factice.servir(url, _page_legere(f"FIN DE LA PAGE {numero}", 250))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    contenu = _pages_envoyees_a_lextraction(mistral_client_factice)
    assert all(f"FIN DE LA PAGE {numero}" in contenu for numero in range(3))
    pages = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]["pages"]
    assert [page["retiree_par_plafond"] for page in pages] == [False, False, False]
    assert sum(page["taille"] for page in pages) > int(262_144 * 0.8 * 3)
    assert sum(page["tokens"] for page in pages) <= _PLAFOND_TOKENS


def test_un_chiffre_present_seulement_dans_le_texte_dune_page_reste_dans_la_reponse(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    moteur_recherche_factice.repondre(_RESULTATS[0])
    telechargeur_pages_factice.servir(
        _URL_TROUVEE, _page_html("La loi a été promulguée en 2021 et compte 305 articles.")
    )
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("La loi compte 305 articles. Elle a 48 décrets.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "305" in contenu
    assert "48" not in contenu


# Appel d'extraction isolé (spec 1.4.0, étapes 5 et 6 ; ADR-0014).

_BESOIN = "Trouver le texte officiel de la loi pour le client Dupont"


def _recherche_avec_page(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, texte: str):
    moteur_recherche_factice.repondre(*_RESULTATS)
    telechargeur_pages_factice.servir(_URL_TROUVEE, _page_html(texte))
    _demander_recherche(mistral_client_factice)


def test_lappel_dextraction_recoit_le_besoin_et_les_pages_jamais_la_conversation(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide, "Message confidentiel du premier tour")

    _recherche_avec_page(
        moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, "Texte de la loi lue."
    )
    mistral_client_factice.repondre("Voici la loi.", resume_et_profil=_reponse_resume_et_profil())
    assert _envoyer(client, jeton_valide, conversation_id, "Cherche la loi Climat").status_code == 200

    (appel,) = mistral_client_factice.appels_extraction
    assert [message["role"] for message in appel] == ["system", "user"]
    contenu = appel[-1]["content"]
    assert _BESOIN in contenu
    assert f"--- Page : {_URL_TROUVEE} ---" in contenu and "Texte de la loi lue." in contenu
    tout = json.dumps(appel, ensure_ascii=False)
    for absent in ("Message confidentiel", "Première réponse", "Cherche la loi Climat", "Résumé"):
        assert absent not in tout


def test_le_message_tool_porte_lextrait_et_la_liste_jamais_les_pages(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _recherche_avec_page(
        moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, "Texte de la loi lue."
    )
    mistral_client_factice.repondre_extraction([("La loi est publiée sur Légifrance.", _URL_TROUVEE)])
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    _creer_conversation(client, jeton_valide)

    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    assert "La loi est publiée sur Légifrance" in contenu
    for titre, url, extrait in _RESULTATS[:5]:
        assert titre in contenu and url in contenu
        assert extrait not in contenu
    assert "Texte de la loi lue." not in contenu


def test_un_chiffre_present_seulement_dans_lextrait_est_retire_de_la_reponse(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _recherche_avec_page(
        moteur_recherche_factice,
        telechargeur_pages_factice,
        mistral_client_factice,
        "La loi a été promulguée en 2021 et compte 305 articles.",
    )
    mistral_client_factice.repondre_extraction([("La loi compte 305 articles et 48 décrets.", _URL_TROUVEE)])
    mistral_client_factice.repondre("La loi compte 305 articles. Elle a 48 décrets.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "305" in contenu
    assert "48" not in contenu


def test_une_ligne_extraction_web_par_appel_dextraction_et_aucune_pour_le_moteur(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_page(
        moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, "Texte de la loi lue."
    )
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    lignes = db_session.query(Consommation).filter_by(conversation_id=conversation_id).all()
    assert sorted(ligne.type_appel for ligne in lignes) == ["chat", "chat", "extraction_web", "titrage"]
    (extraction,) = [ligne for ligne in lignes if ligne.type_appel == "extraction_web"]
    assert extraction.modele == MODELE_CHAT and extraction.identifiant_compte == "j.dupont"
    assert extraction.cout_usd > 0

    total = client.get("/consommation", headers=_autorisation(jeton_valide)).json()
    assert total["chat"]["nombre_requetes"] == 4


def test_sans_page_lue_aucun_appel_dextraction_et_les_extraits_du_moteur_vont_au_modele(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide, db_session
):
    moteur_recherche_factice.repondre(*_RESULTATS)
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    assert mistral_client_factice.appels_extraction == []
    assert not db_session.query(Consommation).filter_by(type_appel="extraction_web").count()
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    for _, url, extrait in _RESULTATS[:5]:
        assert url in message_tool["content"] and extrait in message_tool["content"]


def test_extraction_en_erreur_reponse_200_et_liste_des_resultats_avec_extraction_indisponible(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    _recherche_avec_page(
        moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, "Texte de la loi lue."
    )
    mistral_client_factice.echouer_extraction(RuntimeError("Mistral injoignable"))
    mistral_client_factice.repondre("Voici les résultats.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == "Voici les résultats."
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    assert "extraction indisponible" in contenu.lower()
    for titre, url, extrait in _RESULTATS[:5]:
        assert titre in contenu and url in contenu and extrait in contenu
    assert "Texte de la loi lue." not in contenu

    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    conversation_id = reponse.json()["conversation"]["id"]
    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    (extraction,) = [e for e in echanges if e["type_appel"] == "extraction_web"]
    assert extraction["origine"] == "mistral" and extraction["statut"] == "echec"


def test_inspecteur_place_lextraction_entre_loutil_et_lappel_principal_suivant(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    _recherche_avec_page(
        moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice, "Texte de la loi lue."
    )
    mistral_client_factice.repondre_extraction([("Extrait de la loi.", _URL_TROUVEE)])
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    assert [(e["origine"], e["type_appel"]) for e in echanges] == [
        ("mistral", "chat"),
        ("local", f"outil:{_OUTIL}"),
        ("mistral", "extraction_web"),
        ("mistral", "chat"),
        ("local", "garde_fous"),
        ("mistral", "titrage"),
    ]
    detail = client.get(f"/inspecteur/echanges/{echanges[2]['id']}", headers=entetes_admin).json()
    assert detail["statut"] == "succes" and detail["modele"] == MODELE_CHAT
    assert "Texte de la loi lue." in detail["requete_payload"]["messages"][-1]["content"]
    assert "Extrait de la loi." in json.dumps(detail["reponse_payload"], ensure_ascii=False)


# Le garde-fou des chiffres ne touche jamais une URL (#128, conversation 87).

_URL_DATEE = "https://www.anah.gouv.fr/sites/default/files/2025-03/202503-guide-aides-financieres.pdf"


def _repondre_apres_recherche_datee(client, mistral_client_factice, moteur_recherche_factice, jeton, reponse: str) -> str:
    moteur_recherche_factice.repondre(("Guide des aides", _URL_DATEE, "Les aides de l'Anah."))
    _demander_recherche(mistral_client_factice, "maprimerenov guide")
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post(
        "/conversations", json={"message": "Trouve le guide MaPrimeRénov'"}, headers=_autorisation(jeton)
    )
    assert resultat.status_code == 200
    return resultat.json()["reponse"]


def test_un_lien_markdown_vers_un_resultat_garde_ses_nombres_un_chiffre_hors_source_part(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    contenu = _repondre_apres_recherche_datee(
        client,
        mistral_client_factice,
        moteur_recherche_factice,
        jeton_valide,
        f"Voir le [guide]({_URL_DATEE}). Il recense 48 aides.",
    )

    assert f"[guide]({_URL_DATEE})" in contenu
    assert "48" not in contenu


def test_une_url_nue_dun_resultat_garde_ses_nombres(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    contenu = _repondre_apres_recherche_datee(
        client,
        mistral_client_factice,
        moteur_recherche_factice,
        jeton_valide,
        f"Le guide est ici : {_URL_DATEE}.",
    )

    assert f"{_URL_DATEE}." in contenu


def test_un_chiffre_hors_source_dans_le_texte_dun_lien_markdown_est_retire(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    contenu = _repondre_apres_recherche_datee(
        client,
        mistral_client_factice,
        moteur_recherche_factice,
        jeton_valide,
        f"Le guide est en ligne. Voir le [Guide 2031]({_URL_DATEE}).",
    )

    # Depuis la 1.4.3 (#160), la phrase du chiffre part entière, lien compris.
    assert contenu == "Le guide est en ligne."


def test_une_url_de_resultat_avec_parentheses_reste_entiere_une_url_inventee_avec_parentheses_part(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    # Wikipédia met souvent des parenthèses dans ses URL ; une URL citée
    # entre parenthèses garde sa parenthèse fermante dans la phrase.
    url = "https://fr.wikipedia.org/wiki/Loi_(France)"
    moteur_recherche_factice.repondre(("Loi (France)", url, "Article sur la loi."))
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre(
        f"Voir [Loi]({url}) et {url}. (Source : {url}) Faux : https://inventee.example.org/a_(b) fin",
        "Titre",
    )

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == f"Voir [Loi]({url}) et {url}. (Source : {url}) Faux : fin"


# Questions couvertes de l'appel d'extraction (spec 1.4.1, #136) : JSON
# strict, enregistrées sur le résultat de la page source.

_URL_JAMAIS_LUE = _RESULTATS[3][1]


def _questions_couvertes(db_session, conversation_id: int) -> list[QuestionCouverte]:
    return (
        db_session.query(QuestionCouverte)
        .filter_by(conversation_id=conversation_id)
        .order_by(QuestionCouverte.id)
        .all()
    )


def _resultat(db_session, conversation_id: int, url: str) -> ResultatRechercheWeb:
    return db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id, url=url).one()


def _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice):
    moteur_recherche_factice.repondre(*_RESULTATS)
    telechargeur_pages_factice.servir(_URL_TROUVEE, _page_html("Texte de la loi lue."))
    telechargeur_pages_factice.servir(_URL_DECRET, _page_html("Texte du décret lu."))
    _demander_recherche(mistral_client_factice)


def test_les_questions_de_lextraction_sont_enregistrees_sur_la_page_source(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction(
        [("La loi est sur Légifrance.", _URL_TROUVEE)],
        [
            ("Où lire la loi ?", "Sur Légifrance.", _URL_TROUVEE),
            ("Quel décret l'applique ?", "Le décret d'application.", _URL_DECRET),
        ],
    )
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    questions = _questions_couvertes(db_session, conversation_id)
    assert [(q.question, q.reponse, q.source) for q in questions] == [
        ("Où lire la loi ?", "Sur Légifrance.", _URL_TROUVEE),
        ("Quel décret l'applique ?", "Le décret d'application.", _URL_DECRET),
    ]
    assert questions[0].resultat_recherche_web_id == _resultat(db_session, conversation_id, _URL_TROUVEE).id
    assert questions[1].resultat_recherche_web_id == _resultat(db_session, conversation_id, _URL_DECRET).id
    assert all(
        q.piece_jointe_id is None and q.trouvee and q.origine == "initiale" and q.date_creation for q in questions
    )

    # Les faits partent au modèle, un par ligne avec leur URL, jamais le JSON brut.
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    assert f"- La loi est sur Légifrance. (source : {_URL_TROUVEE})" in message_tool["content"]
    assert "questions_couvertes" not in message_tool["content"]


def test_lappel_dextraction_demande_un_json_strict(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)

    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    (extraction,) = [e for e in echanges if e["type_appel"] == "extraction_web"]
    detail = client.get(f"/inspecteur/echanges/{extraction['id']}", headers=entetes_admin).json()
    format_demande = detail["requete_payload"]["response_format"]
    assert format_demande["type"] == "json_schema" and format_demande["json_schema"]["strict"] is True
    consigne = detail["requete_payload"]["messages"][0]["content"]
    assert "8" in consigne and "300" in consigne and "non trouvé" in consigne


def test_au_dela_de_huit_questions_seules_les_huit_premieres_et_reponse_tronquee_a_300(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    longue = "x" * 450
    mistral_client_factice.repondre_extraction(
        [], [(f"Question {n} ?", longue if n == 1 else f"Réponse {n}", _URL_TROUVEE) for n in range(1, 11)]
    )
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    questions = _questions_couvertes(db_session, conversation_id)
    assert [q.question for q in questions] == [f"Question {n} ?" for n in range(1, 9)]
    assert questions[0].reponse == "x" * 300


def test_une_question_dont_la_source_nest_pas_une_page_lue_est_ignoree(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction(
        [],
        [
            ("Inventée ?", "Oui.", _URL_INVENTEE),
            ("Jamais lue ?", "Oui.", _URL_JAMAIS_LUE),
            ("Où lire la loi ?", "Sur Légifrance.", _URL_TROUVEE),
        ],
    )
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    conversation_id = _creer_conversation(client, jeton_valide)

    assert [q.question for q in _questions_couvertes(db_session, conversation_id)] == ["Où lire la loi ?"]


def test_un_json_invalide_rend_lextraction_indisponible_comme_en_1_4_0(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction_brute("La loi est sur Légifrance, pas de JSON.")
    mistral_client_factice.repondre("Voici les résultats.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    contenu = message_tool["content"]
    assert "extraction indisponible" in contenu.lower()
    assert "pas de JSON" not in contenu
    for _, url, extrait in _RESULTATS[:5]:
        assert url in contenu and extrait in contenu
    assert _questions_couvertes(db_session, reponse.json()["conversation"]["id"]) == []


def test_supprimer_la_conversation_supprime_ses_questions_couvertes(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction([], [("Où lire la loi ?", "Sur Légifrance.", _URL_TROUVEE)])
    mistral_client_factice.repondre("Voici la loi.", "Titre")
    conversation_id = _creer_conversation(client, jeton_valide)
    assert _questions_couvertes(db_session, conversation_id)

    suppression = client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))

    assert suppression.status_code == 204
    assert db_session.query(QuestionCouverte).count() == 0


# Corrections du test humain 1.4.3 (#160, conversation 103) : un fait, une
# source ; portée gardée ; ligne « Sources : » ajoutée par le code ; plus de
# fragment vide laissé par le garde-fou chiffres.

_TITRE_TROUVEE = _RESULTATS[0][0]


def test_chaque_fait_de_lextraction_arrive_au_modele_avec_son_url_un_fait_sans_page_lue_est_ecarte(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction(
        [
            ("La loi est publiée sur Légifrance.", _URL_TROUVEE),
            ("Le décret applique la loi.", _URL_DECRET),
            ("Le rapport compte 48 pages.", _URL_INVENTEE),
            ("La loi est commentée.", _URL_JAMAIS_LUE),
        ]
    )
    mistral_client_factice.repondre("Voici la loi.", "Titre")

    _creer_conversation(client, jeton_valide)

    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    lignes = message_tool["content"].splitlines()
    assert f"- La loi est publiée sur Légifrance. (source : {_URL_TROUVEE})" in lignes
    assert f"- Le décret applique la loi. (source : {_URL_DECRET})" in lignes
    assert "48 pages" not in message_tool["content"]
    assert "La loi est commentée." not in message_tool["content"]


def test_sans_fait_le_message_tool_dit_que_les_pages_ne_repondent_pas(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _recherche_avec_deux_pages(moteur_recherche_factice, telechargeur_pages_factice, mistral_client_factice)
    mistral_client_factice.repondre_extraction([("Inventé.", _URL_INVENTEE)])
    mistral_client_factice.repondre("Rien trouvé.", "Titre")

    _creer_conversation(client, jeton_valide)

    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    assert "ne répondent pas à ce besoin" in message_tool["content"]


def _reponse_sur_page_de_bornage(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton: str,
    reponse: str,
    message: str = "Combien de temps dure un bornage amiable ?",
) -> str:
    moteur_recherche_factice.repondre(_RESULTATS[0])
    telechargeur_pages_factice.servir(
        _URL_TROUVEE, _page_html("En Savoie, un bornage amiable dure de 6 à 12 semaines.")
    )
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post("/conversations", json={"message": message}, headers=_autorisation(jeton))
    assert resultat.status_code == 200
    return resultat.json()["reponse"]


def test_un_chiffre_garde_venu_dune_page_ajoute_une_ligne_sources_avec_son_lien(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "En Savoie, un bornage amiable dure 6 à 12 semaines.",
    )

    assert contenu == (
        "En Savoie, un bornage amiable dure 6 à 12 semaines.\n\n"
        f"Sources : [{_TITRE_TROUVEE}]({_URL_TROUVEE})"
    )


def test_un_chiffre_venu_seulement_du_message_du_compte_najoute_pas_de_ligne_sources(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Votre bornage a duré 14 semaines.",
        message="Mon bornage a duré 14 semaines, est-ce normal ?",
    )

    assert contenu == "Votre bornage a duré 14 semaines."


def test_un_lien_deja_present_dans_la_reponse_najoute_pas_de_doublon(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    reponse = f"Selon [cette page]({_URL_TROUVEE}), un bornage dure 6 à 12 semaines en Savoie."
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, reponse
    )

    assert contenu == reponse


def test_la_ligne_sources_est_visible_dans_lechange_garde_fous_de_linspecteur(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Un bornage dure 6 à 12 semaines en Savoie.",
    )
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    (conversation,) = client.get("/conversations", headers=_autorisation(jeton_valide)).json()
    echanges = client.get(
        f"/inspecteur/conversations/{conversation['id']}/echanges", headers=entetes_admin
    ).json()
    (garde_fous,) = [e for e in echanges if e["type_appel"] == "garde_fous"]
    detail = client.get(f"/inspecteur/echanges/{garde_fous['id']}", headers=entetes_admin).json()

    assert detail["requete_payload"]["reponse_brute"] == "Un bornage dure 6 à 12 semaines en Savoie."
    assert detail["reponse_payload"]["reponse_visible"] == contenu
    assert "Sources : " in contenu


def test_un_chiffre_hors_source_entre_parentheses_emporte_sa_parenthese_pas_la_phrase(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Un bornage dure 6 à 12 semaines (soit 1,5 à 3 mois).",
    )

    assert contenu.split("\n\nSources : ")[0] == "Un bornage dure 6 à 12 semaines."


def test_un_chiffre_hors_source_hors_parenthese_emporte_sa_phrase_la_voisine_reste(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Un bornage dure 6 à 12 semaines. Il coûte environ 1 500 € TTC. Le géomètre fixe les limites.",
    )

    assert contenu.split("\n\nSources : ")[0] == "Un bornage dure 6 à 12 semaines. Le géomètre fixe les limites."


def test_une_reponse_dont_toutes_les_phrases_sont_retirees_devient_la_phrase_fixe(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Un bornage coûte 1 500 €.",
    )

    assert contenu == "Je n'ai trouvé ni page ni document pour appuyer une réponse chiffrée."


def test_une_phrase_retiree_dans_une_puce_ou_un_tableau_ne_casse_pas_la_ligne(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_sur_page_de_bornage(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "- Délai : 6 à 12 semaines. Coût : 1 500 €.\n"
        "- Coût moyen : 1 500 €.\n"
        "- Acteur : le géomètre.\n\n"
        "| Étape | Délai |\n| --- | --- |\n| Bornage | 6 à 12 semaines |\n| Recours | 18 mois |",
    )

    assert contenu.split("\n\nSources : ")[0] == (
        "- Délai : 6 à 12 semaines.\n"
        "- Acteur : le géomètre.\n\n"
        "| Étape | Délai |\n| --- | --- |\n| Bornage | 6 à 12 semaines |\n| Recours | |"
    )


def test_la_regle_de_portee_est_dans_lextraction_lire_pages_web_et_la_reponse_de_chat(
    client, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    _creer_conversation(client, jeton_valide, "Bonjour")

    consigne_chat = mistral_client_factice.appels_reponse[0][0]["content"]
    for consigne in (CONSIGNE_EXTRACTION, CONSIGNE_LECTURE_PAGE, CONSIGNE_REVERIFICATION_PAGE, consigne_chat):
        assert "le lieu, la période et la population" in consigne
        assert "« en Savoie » ne devient jamais « en France »" in consigne
        assert "conversion" in consigne and "calcul" in consigne


def test_une_page_connue_seulement_par_lextrait_du_moteur_nest_pas_citee(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    # #162, conversation 106 : travaux.com cité sans avoir été lu.
    moteur_recherche_factice.repondre(
        (_TITRE_TROUVEE, _URL_TROUVEE, "Un bornage amiable dure de 6 à 12 semaines.")
    )
    _demander_recherche(mistral_client_factice)
    mistral_client_factice.repondre("Un bornage amiable dure 6 à 12 semaines.", "Titre")

    resultat = client.post(
        "/conversations", json={"message": "Durée d'un bornage ?"}, headers=_autorisation(jeton_valide)
    )

    assert resultat.json()["reponse"] == "Un bornage amiable dure 6 à 12 semaines."
