import json

from vm_centrale.config import MODELE_CHAT
from vm_centrale.models import Consommation, QuestionCouverte, ResultatRechercheWeb
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


def test_une_page_non_lue_renvoie_lextrait_du_moteur_seulement(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    conversation_id = _conversation_avec_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
    )
    _lire(client, mistral_client_factice, jeton_valide, conversation_id, [_URL_NON_LUE])

    assert mistral_client_factice.appels_lecture_page == []
    assert telechargeur_pages_factice.urls_recues == []
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
