import json
from datetime import datetime, timezone

from vm_centrale.config import MODELE_CHAT
from vm_centrale.models import Consommation, PageWebEnCache, QuestionCouverte, ResultatRechercheWeb
from vm_centrale.outils.lire_pages_web import CONSIGNE_LECTURE_PAGE

# Outil lire_pages_web sur les pages trouvées par une recherche (spec 1.4.1,
# #139) : un appel d'extraction isolé sur le texte nettoyé déjà en base,
# jamais de retéléchargement.

_OUTIL = "lire_pages_web"
_TITRE_MEMOIRE = "Mémoire de la conversation :"
_URL_LUE = "https://www.exemple.fr/bornage-a"
_URL_NON_LUE = "https://www.exemple.fr/bornage-b"
_URL_INCONNUE = "https://www.ailleurs.fr/page"
_BESOIN = "Délai moyen d'un bornage"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _page_html(*paragraphes: str) -> str:
    # Assez de texte pour que trafilatura garde l'article comme texte
    # principal (voir test_recherche_web).
    remplissage = (
        "Le bornage fixe la limite entre deux terrains contigus, à la demande d'un "
        "propriétaire, par un géomètre-expert inscrit à l'Ordre.",
        "Il donne lieu à un procès-verbal signé par les propriétaires concernés et "
        "publié, qui s'impose ensuite aux acquéreurs successifs.",
    )
    corps = "".join(f"<p>{paragraphe}</p>" for paragraphe in (*remplissage, *paragraphes))
    return f"<html><body><nav>Menu</nav><article><h1>Bornage</h1>{corps}</article></body></html>"


def _conversation_avec_recherche(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton: str
) -> int:
    # Tour 1 : une recherche, une page lue (_URL_LUE) et une page en échec
    # (_URL_NON_LUE, non servie).
    moteur_recherche_factice.repondre(
        ("Bornage A", _URL_LUE, "Extrait moteur A"), ("Bornage B", _URL_NON_LUE, "Extrait moteur B")
    )
    telechargeur_pages_factice.servir(_URL_LUE, _page_html("Le délai moyen est de trois mois."))
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "bornage", "besoin": "Comprendre le bornage"}
    )
    mistral_client_factice.repondre("Voici.", "Titre")
    reponse = client.post(
        "/conversations", json={"message": "Cherche le bornage pour M. Dupont"}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200
    telechargeur_pages_factice.urls_recues.clear()
    return reponse.json()["conversation"]["id"]


def _lire(client, mistral_client_factice, jeton: str, conversation_id: int, urls: list[str], besoin: str = _BESOIN):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": urls, "besoin": besoin})
    mistral_client_factice.repondre("Réponse.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et le délai ?"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200


def _envoyer(client, mistral_client_factice, jeton: str, conversation_id: int, message: str = "Suite") -> None:
    mistral_client_factice.repondre("Suite.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": message}, headers=_autorisation(jeton)
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


def _noms_outils(tools) -> list[str]:
    return [outil["function"]["name"] for outil in tools or []]


def test_lire_pages_web_nest_declare_quapres_une_recherche_de_la_conversation(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    assert _OUTIL not in _noms_outils(mistral_client_factice.tools_appels_reponse[-1])

    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)

    assert reponse.status_code == 200
    assert _OUTIL in _noms_outils(mistral_client_factice.tools_appels_reponse[-1])


def test_une_url_de_recherche_est_lue_sans_retelechargement_par_un_appel_isole(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    assert telechargeur_pages_factice.urls_recues == []
    (appel,) = mistral_client_factice.appels_lecture_page
    # Consigne fixe, besoin et texte nettoyé : jamais la conversation.
    assert [m["role"] for m in appel] == ["system", "user"]
    assert appel[0]["content"] == CONSIGNE_LECTURE_PAGE
    assert _BESOIN in appel[1]["content"] and "Le délai moyen est de trois mois." in appel[1]["content"]
    assert "Dupont" not in appel[1]["content"] and "Et le délai" not in appel[1]["content"]
    contenu = _message_tool(mistral_client_factice)
    assert _URL_LUE in contenu and "Trois mois en moyenne." in contenu


def test_la_consigne_impose_non_trouve_plutot_quune_estimation():
    assert "non trouvé" in CONSIGNE_LECTURE_PAGE and "estimation" in CONSIGNE_LECTURE_PAGE


def test_une_reponse_trouvee_est_enregistree_et_apparait_dans_la_memoire_au_tour_suivant(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    (question,) = _questions_besoin(db_session, conversation_id)
    resultat = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id, url=_URL_LUE).one()
    assert question.resultat_recherche_web_id == resultat.id and question.piece_jointe_id is None
    assert (question.question, question.reponse, question.source, question.trouvee) == (
        _BESOIN,
        "Trois mois en moyenne.",
        _URL_LUE,
        True,
    )

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)
    assert f"  • {_BESOIN} → Trois mois en moyenne. ({_URL_LUE})" in _memoire(mistral_client_factice).splitlines()


def test_un_non_trouve_est_enregistre_trouvee_faux_et_marque_non_present_dans_la_memoire(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(False)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    (question,) = _questions_besoin(db_session, conversation_id)
    assert (question.question, question.trouvee, question.source) == (_BESOIN, False, _URL_LUE)
    assert "non trouvé" in _message_tool(mistral_client_factice).lower()

    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)
    assert (
        f"  • {_BESOIN} → non présent selon l'extraction ({_URL_LUE})"
        in _memoire(mistral_client_factice).splitlines()
    )


def test_la_reponse_enregistree_est_coupee_a_300_caracteres(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "x" * 400, _URL_LUE)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    (question,) = _questions_besoin(db_session, conversation_id)
    assert question.reponse == "x" * 300


def test_une_url_inconnue_donne_page_introuvable_sans_appel_dextraction(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_INCONNUE])

    assert mistral_client_factice.appels_lecture_page == []
    assert telechargeur_pages_factice.urls_recues == []
    assert "Page introuvable." in _message_tool(mistral_client_factice)
    assert _questions_besoin(db_session, conversation_id) == []


def test_une_url_dune_autre_conversation_est_introuvable(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    # Aucune recherche dans cette conversation : l'outil n'est pas déclaré,
    # mais un appel quand même ne lit jamais la page d'une autre.
    mistral_client_factice.repondre("Réponse", "Titre")
    nouvelle = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    _lire(client, mistral_client_factice, jeton_valide, nouvelle.json()["conversation"]["id"], [_URL_LUE])

    assert mistral_client_factice.appels_lecture_page == []
    assert "Page introuvable." in _message_tool(mistral_client_factice)


def test_une_page_non_lue_en_echec_au_nouvel_essai_renvoie_lextrait_du_moteur_seulement(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_NON_LUE])

    assert mistral_client_factice.appels_lecture_page == []
    # Retentée au tour suivant (#156), toujours injoignable.
    assert telechargeur_pages_factice.urls_recues == [_URL_NON_LUE]
    contenu = _message_tool(mistral_client_factice)
    assert _URL_NON_LUE in contenu and "Extrait moteur B" in contenu
    assert _questions_besoin(db_session, conversation_id) == []


def test_plusieurs_urls_un_appel_dextraction_par_page_lue(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE, _URL_INCONNUE, _URL_NON_LUE])

    assert len(mistral_client_factice.appels_lecture_page) == 1
    contenu = _message_tool(mistral_client_factice)
    assert contenu.index(_URL_LUE) < contenu.index(_URL_INCONNUE) < contenu.index(_URL_NON_LUE)
    assert "Trois mois en moyenne." in contenu and "Page introuvable." in contenu and "Extrait moteur B" in contenu


def test_extraction_en_echec_reponse_200_sans_question_enregistree(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.echouer_lecture_page(RuntimeError("Mistral injoignable"))
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    assert "extraction indisponible" in _message_tool(mistral_client_factice).lower()
    assert _questions_besoin(db_session, conversation_id) == []


def test_un_json_invalide_rend_lextraction_indisponible(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page_brute("Trois mois, pas de JSON.")
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    assert "extraction indisponible" in _message_tool(mistral_client_factice).lower()
    assert _questions_besoin(db_session, conversation_id) == []


def test_consommation_et_inspecteur_tracent_loutil_local_et_lextraction_web(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    extractions_avant = db_session.query(Consommation).filter_by(type_appel="extraction_web").count()
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    assert db_session.query(Consommation).filter_by(type_appel="extraction_web").count() == extractions_avant + 1
    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    types = [(e["origine"], e["type_appel"]) for e in echanges]
    indice = types.index(("local", f"outil:{_OUTIL}"))
    assert types[indice + 1] == ("mistral", "extraction_web")
    detail = client.get(f"/inspecteur/echanges/{echanges[indice + 1]['id']}", headers=entetes_admin).json()
    assert detail["statut"] == "succes" and detail["modele"] == MODELE_CHAT
    assert detail["requete_payload"]["response_format"]["type"] == "json_schema"
    local = client.get(f"/inspecteur/echanges/{echanges[indice]['id']}", headers=entetes_admin).json()
    assert local["requete_payload"]["arguments"] == {"urls": [_URL_LUE], "besoin": _BESOIN}
    assert "Trois mois en moyenne." in local["reponse_payload"]["contenu"]


# URL écrites par le compte (spec 1.4.1, #140) : téléchargée et nettoyée au
# premier appel, enregistrée avec la provenance `utilisateur`, puis lue comme
# une page trouvée ; une page lue n'est jamais retéléchargée dans la
# conversation (une page en échec est retentée au tour suivant, #156).

_URL_COMPTE = "https://www.client-dupont.fr/devis-bornage"
_URL_COMPTE_PDF = "https://www.client-dupont.fr/devis.pdf"
_TEXTE_COMPTE = "Le délai prévu est de six semaines."


def _conversation_avec_url_du_compte(client, mistral_client_factice, jeton: str, url: str = _URL_COMPTE) -> int:
    # Tour 1 : le compte écrit l'URL, le modèle répond sans outil.
    mistral_client_factice.repondre("Bien reçu.", "Titre")
    reponse = client.post("/conversations", json={"message": f"Voici le devis : {url}"}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    return reponse.json()["conversation"]["id"]


def _lignes_url_du_compte(mistral_client_factice, url: str) -> list[str]:
    return [
        ligne for ligne in _memoire(mistral_client_factice).splitlines() if "URL envoyée" in ligne and url in ligne
    ]


def test_lire_pages_web_est_declare_des_quune_url_du_compte_est_dans_la_conversation(
    client, mistral_client_factice, jeton_valide
):
    _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)

    # Premier appel de chat, dès le message qui porte l'URL (le titrage suit).
    assert _OUTIL in _noms_outils(mistral_client_factice.tools_appels_reponse[0])


def test_une_url_du_compte_est_telechargee_au_premier_appel_puis_jamais_plus(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))
    mistral_client_factice.repondre_lecture_page(True, "Six semaines.", _URL_COMPTE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    (appel,) = mistral_client_factice.appels_lecture_page
    # Même chaîne que rechercher_web : texte principal nettoyé, sans menu.
    assert appel[0]["content"] == CONSIGNE_LECTURE_PAGE
    assert _TEXTE_COMPTE in appel[1]["content"] and "Menu" not in appel[1]["content"]
    assert "Six semaines." in _message_tool(mistral_client_factice)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE], besoin="Prix du bornage")

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert len(mistral_client_factice.appels_lecture_page) == 2


def test_une_url_du_compte_sans_schema_est_telechargee_en_https(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    # « www.… » sans schéma : refusée par le téléchargeur, la page restait
    # non lue toute la conversation.
    url_ecrite = "www.client-dupont.fr/devis-bornage"
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide, url=url_ecrite)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))
    mistral_client_factice.repondre_lecture_page(True, "Six semaines.", url_ecrite)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [url_ecrite])

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert "Six semaines." in _message_tool(mistral_client_factice)
    (page,) = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id).all()
    assert page.url == url_ecrite


def test_une_url_de_recherche_redonnee_sous_une_autre_forme_est_lue(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, ["http://exemple.fr/bornage-a/"])

    assert telechargeur_pages_factice.urls_recues == []
    assert len(mistral_client_factice.appels_lecture_page) == 1
    assert "Trois mois en moyenne." in _message_tool(mistral_client_factice)


def test_une_url_du_message_du_tour_est_lue_au_meme_tour(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    conversation_id = client.post(
        "/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide)
    ).json()["conversation"]["id"]
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))
    mistral_client_factice.repondre_lecture_page(True, "Six semaines.", _URL_COMPTE)

    _lire_avec_message(client, mistral_client_factice, jeton_valide, conversation_id, f"Quel délai dans {_URL_COMPTE} ?")

    assert _OUTIL in _noms_outils(mistral_client_factice.tools_appels_reponse[-2])
    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert "Six semaines." in _message_tool(mistral_client_factice)


def _lire_avec_message(client, mistral_client_factice, jeton: str, conversation_id: int, message: str):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": [_URL_COMPTE], "besoin": _BESOIN})
    mistral_client_factice.repondre("Six semaines.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": message}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200


def test_la_page_du_compte_est_enregistree_avec_la_provenance_utilisateur_et_une_requete_vide(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id, f"Et ce devis : {_URL_COMPTE}")
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))
    mistral_client_factice.repondre_lecture_page(True, "Six semaines.", _URL_COMPTE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    resultats = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id).all()
    provenances = {resultat.url: (resultat.provenance, resultat.requete) for resultat in resultats}
    assert provenances[_URL_COMPTE] == ("utilisateur", "")
    assert provenances[_URL_LUE] == ("recherche", "bornage")
    (page,) = [resultat for resultat in resultats if resultat.url == _URL_COMPTE]
    assert _TEXTE_COMPTE in page.texte_nettoye
    (question,) = _questions_besoin(db_session, conversation_id)
    assert question.resultat_recherche_web_id == page.id


def test_un_chiffre_de_la_page_du_compte_passe_le_garde_fou_chiffres(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html("Le devis s'élève à 4870 euros hors taxes."))
    mistral_client_factice.repondre_lecture_page(True, "4870 euros HT.", _URL_COMPTE)
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": [_URL_COMPTE], "besoin": "Montant"})
    mistral_client_factice.repondre(
        "Le devis est de 4870 euros, plus 735 euros de frais.", resume_et_profil=_resume_et_profil()
    )

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Quel montant ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    contenu = reponse.json()["reponse"]
    assert "4870" in contenu
    assert "735" not in contenu


def test_une_url_du_compte_vers_un_pdf_donne_page_non_lue_a_chaque_essai(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(
        client, mistral_client_factice, jeton_valide, url=_URL_COMPTE_PDF
    )
    telechargeur_pages_factice.servir(_URL_COMPTE_PDF, "", type_contenu="application/pdf")

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE_PDF])

    assert mistral_client_factice.appels_lecture_page == []
    contenu = _message_tool(mistral_client_factice)
    assert _URL_COMPTE_PDF in contenu and "page non lue" in contenu.lower()
    assert _questions_besoin(db_session, conversation_id) == []

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE_PDF])

    # Retentée au tour suivant (#156), toujours un PDF.
    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE_PDF, _URL_COMPTE_PDF]
    assert "page non lue" in _message_tool(mistral_client_factice).lower()


def test_une_url_du_compte_injoignable_donne_page_non_lue(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert "page non lue" in _message_tool(mistral_client_factice).lower()


def test_la_memoire_passe_de_pas_encore_lue_a_lue(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)
    assert _lignes_url_du_compte(mistral_client_factice, _URL_COMPTE) == [
        f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_COMPTE} (pas encore lue)"
    ]

    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))
    mistral_client_factice.repondre_lecture_page(True, "Six semaines.", _URL_COMPTE)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)

    ligne_url = f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_COMPTE} (lue)"
    assert _lignes_url_du_compte(mistral_client_factice, _URL_COMPTE) == [ligne_url]
    # Ses questions couvertes sous la ligne de l'URL, jamais une recherche à
    # requête vide.
    lignes = _memoire(mistral_client_factice).splitlines()
    assert lignes[lignes.index(ligne_url) + 1] == f"  • {_BESOIN} → Six semaines. ({_URL_COMPTE})"
    assert not any("recherche « »" in ligne for ligne in lignes)


def test_une_url_du_compte_en_pdf_est_marquee_page_non_lue_dans_la_memoire(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(
        client, mistral_client_factice, jeton_valide, url=_URL_COMPTE_PDF
    )
    telechargeur_pages_factice.servir(_URL_COMPTE_PDF, "", type_contenu="application/pdf")
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE_PDF])
    _envoyer(client, mistral_client_factice, jeton_valide, conversation_id)

    assert _lignes_url_du_compte(mistral_client_factice, _URL_COMPTE_PDF) == [
        f"- Tour 1 — URL envoyée par l'utilisateur : {_URL_COMPTE_PDF} (page non lue)"
    ]


# Sans besoin (essai 1.4.1, conversation 95) : avec une URL seule, le modèle
# devinait un besoin (« EPF » lu comme établissement public foncier, page
# d'une école d'ingénieurs) et ne recevait que « non trouvé ». Sans besoin,
# il reçoit le texte nettoyé de la page pour découvrir de quoi elle parle.


def _lire_sans_besoin(client, mistral_client_factice, jeton: str, conversation_id: int, urls: list[str]) -> None:
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": urls})
    mistral_client_factice.repondre("Réponse.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "De quoi parle-t-elle ?"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200


def test_le_besoin_est_un_parametre_facultatif(client, mistral_client_factice, jeton_valide):
    _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)

    (outil,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    parametres = outil["function"]["parameters"]
    assert "besoin" in parametres["properties"]
    assert parametres["required"] == ["urls"]


def test_sans_besoin_une_url_du_compte_renvoie_le_texte_nettoye_sans_appel_dextraction(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert mistral_client_factice.appels_lecture_page == []
    contenu = _message_tool(mistral_client_factice)
    assert _URL_COMPTE in contenu and _TEXTE_COMPTE in contenu and "Menu" not in contenu
    assert _questions_besoin(db_session, conversation_id) == []

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])
    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]


def test_sans_besoin_une_page_de_recherche_est_relue_depuis_la_base(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE, _URL_NON_LUE])

    # Seule la page sans texte est retentée (#156), toujours injoignable.
    assert telechargeur_pages_factice.urls_recues == [_URL_NON_LUE]
    assert mistral_client_factice.appels_lecture_page == []
    contenu = _message_tool(mistral_client_factice)
    assert "Le délai moyen est de trois mois." in contenu
    assert "Extrait moteur B" in contenu


def test_sans_besoin_un_long_texte_est_coupe_et_signale(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    long_paragraphe = "Paragraphe de remplissage sur le bornage des terrains. " * 600
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(long_paragraphe, "FIN-DE-PAGE-UNIQUE"))

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    contenu = _message_tool(mistral_client_factice)
    assert "FIN-DE-PAGE-UNIQUE" not in contenu
    assert "texte coupé" in contenu
    assert len(contenu) < 12_000


# Plafond en tokens de la page relue avec un besoin (spec 1.4.2, #147) : le
# même que rechercher_web, 80 % de la fenêtre de la fiche MODELE_CHAT.
_PLAFOND_TOKENS = int(262_144 * 0.8)
# Consigne de réponse honnête (#151, durcie en #152) : le contenu n'a pas
# été transmis, le modèle ne doit pas deviner de quoi parle la page.
_PAGE_TROP_LONGUE = (
    "Page trop longue pour être lue : son contenu ne t'a pas été transmis. "
    "Dis au collaborateur que la page était trop longue pour être lue. Tu ne "
    "connais de cette page que son URL et, s'il est donné, son titre : "
    "n'affirme rien d'autre sur ce qu'elle contient. Réponds sur le sujet "
    "seulement s'il est connu (titre de la page ou message du collaborateur), "
    "en précisant que cela vient de tes connaissances et non de la page."
)


def _page_dense(nombre_paragraphes: int) -> str:
    # Des chiffres : environ un token par caractère. Paragraphes tous
    # différents : trafilatura retire les doublons.
    return _page_html(*(f"Ligne {numero} : " + "0123456789" * 100 for numero in range(nombre_paragraphes)))


def _echange_local(client, conversation_id: int, jeton: str, monkeypatch) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton), "X-Admin-Key": "cle-admin-de-test"}
    echanges = client.get(
        f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin
    ).json()
    *_, outil = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    return client.get(f"/inspecteur/echanges/{outil['id']}", headers=entetes_admin).json()


def test_avec_besoin_une_page_au_dela_du_plafond_nest_ni_coupee_ni_relue(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session, monkeypatch
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))
    extractions_avant = db_session.query(Consommation).filter_by(type_appel="extraction_web").count()

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert mistral_client_factice.appels_lecture_page == []
    assert db_session.query(Consommation).filter_by(type_appel="extraction_web").count() == extractions_avant
    assert _questions_besoin(db_session, conversation_id) == []
    contenu = _message_tool(mistral_client_factice)
    assert contenu == f"Page {_URL_COMPTE} : {_PAGE_TROP_LONGUE}\nTitre de la page : Bornage"
    reponse = _echange_local(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]
    assert reponse["plafond_tokens"] == _PLAFOND_TOKENS
    (page,) = reponse["pages_relues"]
    assert page["url"] == _URL_COMPTE and page["trop_longue"] is True
    assert page["tokens"] > _PLAFOND_TOKENS


def test_avec_besoin_une_page_sous_le_plafond_est_relue_et_linspecteur_montre_ses_tokens(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    mistral_client_factice.repondre_lecture_page(True, "Trois mois en moyenne.", _URL_LUE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_LUE])

    assert len(mistral_client_factice.appels_lecture_page) == 1
    assert "Trois mois en moyenne." in _message_tool(mistral_client_factice)
    assert len(_questions_besoin(db_session, conversation_id)) == 1
    reponse = _echange_local(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]
    assert reponse["plafond_tokens"] == _PLAFOND_TOKENS
    (page,) = reponse["pages_relues"]
    assert page["url"] == _URL_LUE and page["trop_longue"] is False
    assert 0 < page["tokens"] <= _PLAFOND_TOKENS


def test_sans_besoin_une_page_au_dela_du_plafond_est_coupee_a_8000_caracteres(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    contenu = _message_tool(mistral_client_factice)
    assert _PAGE_TROP_LONGUE not in contenu
    assert "texte coupé" in contenu and len(contenu) < 12_000


# Page trop longue (#151) : pas d'aperçu en douce dans le même tour, mention
# garantie à la fin de la réponse visible.
_MENTION_TROP_LONGUE = f"La page {_URL_COMPTE} était trop longue pour être lue en entier."


def _lire_puis_relire_sans_besoin(client, mistral_client_factice, jeton: str, conversation_id: int):
    mistral_client_factice.repondre_avec_appels_outils(
        [(_OUTIL, {"urls": [_URL_COMPTE], "besoin": _BESOIN}, "call_1")],
        [(_OUTIL, {"urls": [_URL_COMPTE]}, "call_2")],
    )
    mistral_client_factice.repondre("Résumé de mémoire.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Résume-moi cette page"},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200
    return reponse.json()


def _messages_tool(mistral_client_factice) -> list[str]:
    return [m["content"] for m in mistral_client_factice.appels_reponse[-1] if m["role"] == "tool"]


def test_une_page_trop_longue_relue_sans_besoin_dans_le_meme_tour_renvoie_le_meme_refus(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))
    extractions_avant = db_session.query(Consommation).filter_by(type_appel="extraction_web").count()

    _lire_puis_relire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id)

    refus = f"Page {_URL_COMPTE} : {_PAGE_TROP_LONGUE}\nTitre de la page : Bornage"
    assert _messages_tool(mistral_client_factice) == [refus, refus]
    assert mistral_client_factice.appels_lecture_page == []
    assert db_session.query(Consommation).filter_by(type_appel="extraction_web").count() == extractions_avant


def test_au_tour_suivant_une_page_trop_longue_retrouve_son_apercu_sans_besoin(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    contenu = _message_tool(mistral_client_factice)
    assert _PAGE_TROP_LONGUE not in contenu
    assert "texte coupé" in contenu


def test_un_tour_avec_une_page_trop_longue_se_termine_par_la_mention_fixe(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))

    corps = _lire_puis_relire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id)

    assert corps["reponse"] == f"Résumé de mémoire.\n\n{_MENTION_TROP_LONGUE}"
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()
    assert detail["messages"][-1]["contenu"] == corps["reponse"]
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin).json()
    *_, garde_fous = [e for e in echanges if e["type_appel"] == "garde_fous"]
    garde_fous = client.get(f"/inspecteur/echanges/{garde_fous['id']}", headers=entetes_admin).json()
    assert garde_fous["requete_payload"] == {"reponse_brute": "Résumé de mémoire."}
    assert garde_fous["reponse_payload"] == {"reponse_visible": corps["reponse"]}


def test_un_tour_sans_page_trop_longue_na_pas_de_mention(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    mistral_client_factice.repondre("Suite.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Merci"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.json()["reponse"] == "Suite."


def test_au_premier_message_une_page_trop_longue_est_mentionnee(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": [_URL_COMPTE], "besoin": _BESOIN})
    mistral_client_factice.repondre("Résumé de mémoire.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": f"Résume-moi {_URL_COMPTE}"}, headers=_autorisation(jeton_valide)
    )

    assert reponse.status_code == 200
    assert reponse.json()["reponse"] == f"Résumé de mémoire.\n\n{_MENTION_TROP_LONGUE}"


def test_linspecteur_montre_les_vrais_tokens_dune_page_du_compte_telechargee(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense(220))

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    reponse = _echange_local(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]
    (telechargee,) = reponse["pages_telechargees"]
    (relue,) = reponse["pages_relues"]
    assert telechargee["tokens"] == relue["tokens"] > _PLAFOND_TOKENS


def test_sans_besoin_linspecteur_naffiche_pas_de_tokens_non_comptes(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    reponse = _echange_local(client, conversation_id, jeton_valide, monkeypatch)["reponse_payload"]
    (telechargee,) = reponse["pages_telechargees"]
    assert "tokens" not in telechargee


# Titre de la page dans le refus (#152) : sans lui, le modèle devinait le
# livre à partir de l'URL (Les Trois Mousquetaires pour Les Misérables).
def _page_dense_sans_titre(titre_html: str = "") -> str:
    lignes = "".join(f"<p>Ligne {numero} : {'0123456789' * 100}</p>" for numero in range(220))
    return f"<html><head>{titre_html}</head><body><article>{lignes}</article></body></html>"


def test_le_refus_dune_page_trop_longue_porte_son_titre_sans_rien_de_son_texte(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(
        _URL_COMPTE, _page_dense_sans_titre("<title>Les Misérables, by Victor Hugo</title>")
    )

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    contenu = _message_tool(mistral_client_factice)
    assert contenu == (
        f"Page {_URL_COMPTE} : {_PAGE_TROP_LONGUE}\nTitre de la page : Les Misérables, by Victor Hugo"
    )
    assert "0123456789" not in contenu


def test_le_refus_dune_page_trop_longue_sans_titre_na_pas_de_ligne_de_titre(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_dense_sans_titre())

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert _message_tool(mistral_client_factice) == f"Page {_URL_COMPTE} : {_PAGE_TROP_LONGUE}"


# Page sans texte retentée à un tour suivant (spec 1.4.3, #156) : remplace la
# règle 1.4.1 « jamais retéléchargée ensuite dans la conversation ». Au même
# tour, pas de nouvel essai.


def _lire_deux_fois_au_meme_tour(client, mistral_client_factice, jeton: str, conversation_id: int, url: str):
    mistral_client_factice.repondre_avec_appels_outils(
        [(_OUTIL, {"urls": [url], "besoin": _BESOIN}, "call_1")],
        [(_OUTIL, {"urls": [url], "besoin": _BESOIN}, "call_2")],
    )
    mistral_client_factice.repondre("Réponse.", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Elle est accessible."},
        headers=_autorisation(jeton),
    )
    assert reponse.status_code == 200


def test_une_url_du_compte_en_echec_redemandee_au_meme_tour_nest_pas_retentee(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)

    _lire_deux_fois_au_meme_tour(client, mistral_client_factice, jeton_valide, conversation_id, _URL_COMPTE)

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert all("page non lue" in contenu.lower() for contenu in _messages_tool(mistral_client_factice))


def test_une_url_du_compte_en_echec_est_retentee_au_tour_suivant_et_sert_au_garde_fou_chiffres(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html("Le devis s'élève à 4870 euros hors taxes."))
    mistral_client_factice.repondre_lecture_page(True, "4870 euros HT.", _URL_COMPTE)
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"urls": [_URL_COMPTE], "besoin": "Montant"})
    mistral_client_factice.repondre(
        "Le devis est de 4870 euros, plus 735 euros de frais.", resume_et_profil=_resume_et_profil()
    )

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Pour moi elle est accessible, quel montant ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE, _URL_COMPTE]
    assert "4870 euros HT." in _message_tool(mistral_client_factice)
    (ligne,) = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id).all()
    assert "4870 euros" in ligne.texte_nettoye
    contenu = reponse.json()["reponse"]
    assert "4870" in contenu and "735" not in contenu


def test_une_page_retentee_avec_succes_entre_dans_le_cache(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])
    assert db_session.query(PageWebEnCache).filter_by(url=_URL_COMPTE).first() is None
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html(_TEXTE_COMPTE))

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])

    assert _TEXTE_COMPTE in _message_tool(mistral_client_factice)
    copie = db_session.query(PageWebEnCache).filter_by(url=_URL_COMPTE).one()
    assert _TEXTE_COMPTE in copie.texte_nettoye


def test_une_page_retentee_en_echec_ne_lest_quune_fois_par_tour(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_url_du_compte(client, mistral_client_factice, jeton_valide)
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_COMPTE])
    telechargeur_pages_factice.urls_recues.clear()

    _lire_deux_fois_au_meme_tour(client, mistral_client_factice, jeton_valide, conversation_id, _URL_COMPTE)

    assert telechargeur_pages_factice.urls_recues == [_URL_COMPTE]
    assert all("page non lue" in contenu.lower() for contenu in _messages_tool(mistral_client_factice))
    (ligne,) = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id).all()
    assert ligne.texte_nettoye == ""


def test_une_page_de_recherche_sans_texte_est_lue_au_tour_suivant(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    telechargeur_pages_factice.servir(_URL_NON_LUE, _page_html("Le délai est de deux mois à Lyon."))
    mistral_client_factice.repondre_lecture_page(True, "Deux mois.", _URL_NON_LUE)

    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_NON_LUE])

    assert telechargeur_pages_factice.urls_recues == [_URL_NON_LUE]
    (appel,) = mistral_client_factice.appels_lecture_page
    assert "deux mois à Lyon" in appel[1]["content"]
    assert "Deux mois." in _message_tool(mistral_client_factice)
    ligne = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id, url=_URL_NON_LUE).one()
    assert "deux mois à Lyon" in ligne.texte_nettoye


def test_une_page_de_recherche_sans_texte_est_servie_par_le_cache_au_tour_suivant(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    db_session.add(
        PageWebEnCache(
            url=_URL_NON_LUE,
            texte_nettoye="Le délai est de deux mois à Lyon.",
            titre="Bornage à Lyon",
            date_telechargement=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    _lire_sans_besoin(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_NON_LUE])

    assert telechargeur_pages_factice.urls_recues == []
    assert "Le délai est de deux mois à Lyon." in _message_tool(mistral_client_factice)
    ligne = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id, url=_URL_NON_LUE).one()
    assert ligne.titre == "Bornage à Lyon"


def test_une_page_de_recherche_sans_texte_au_meme_tour_donne_lextrait_du_moteur_seulement(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    moteur_recherche_factice.repondre(
        ("Bornage A", _URL_LUE, "Extrait moteur A"), ("Bornage B", _URL_NON_LUE, "Extrait moteur B")
    )
    telechargeur_pages_factice.servir(_URL_LUE, _page_html("Le délai moyen est de trois mois."))
    mistral_client_factice.repondre_avec_appels_outils(
        [("rechercher_web", {"requete": "bornage", "besoin": "Comprendre le bornage"}, "call_1")],
        [(_OUTIL, {"urls": [_URL_NON_LUE], "besoin": _BESOIN}, "call_2")],
    )
    mistral_client_factice.repondre("Voici.", "Titre")

    reponse = client.post("/conversations", json={"message": "Cherche le bornage"}, headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    assert telechargeur_pages_factice.urls_recues.count(_URL_NON_LUE) == 1
    # Dernier appel principal (le titrage suit, sans message `tool`).
    *_, lecture = [
        m["content"]
        for appel in mistral_client_factice.appels_reponse
        if isinstance(appel, list)
        for m in appel
        if m["role"] == "tool"
    ]
    assert "Extrait moteur B" in lecture
