import json
from datetime import datetime, timedelta, timezone

import pytest

from vm_centrale.models import PageWebEnCache, ResultatRechercheWeb

# Cache commun des pages web (spec 1.4.3, ADR-0015, #154) : une page lue
# avec succès dans une conversation est servie à toute autre, de n'importe
# quel compte, pendant 24 h, sans nouveau téléchargement.

_URL = "https://www.legifrance.gouv.fr/loi-climat-resilience"
_URL_COMPTE = "https://www.client-dupont.fr/devis-bornage"
_TITRE_MEMOIRE = "Mémoire de la conversation :"
_AUTRES_RESULTATS = [
    ("Décret d'application", "https://www.legifrance.gouv.fr/decret", "Décret pris pour la loi."),
    ("Analyse", "https://www.vie-publique.fr/loi-climat", "Ce que change la loi."),
]


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _page_html(*paragraphes: str) -> str:
    # Assez de texte pour que trafilatura garde l'article comme texte
    # principal (voir test_recherche_web).
    remplissage = (
        "Cette loi porte lutte contre le dérèglement climatique et renforcement de la "
        "résilience face à ses effets, à partir des propositions de la Convention citoyenne.",
        "Elle touche la consommation, la production, les déplacements, le logement et "
        "l'alimentation, et renforce la protection judiciaire de l'environnement.",
    )
    corps = "".join(f"<p>{paragraphe}</p>" for paragraphe in (*remplissage, *paragraphes))
    return (
        "<html><head><title>Loi Climat</title></head><body><nav>Menu du site</nav>"
        f"<article><h1>Loi Climat et résilience</h1>{corps}</article></body></html>"
    )


def _page_dense(marqueur_de_fin: str) -> str:
    # Environ 80 000 tokens : deux tiennent sous le plafond, pas trois.
    return _page_html(*(f"Ligne {numero} : " + "0123456789" * 100 for numero in range(80)), marqueur_de_fin)


@pytest.fixture
def jeton_autre_compte(jeton_store):
    return jeton_store.emettre("m.martin")


def _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton: str, reponse: str = "Voici.") -> int:
    # Une conversation neuve qui lance une recherche ramenant _URL.
    moteur_recherche_factice.repondre(("Loi Climat et résilience", _URL, "Texte de la loi."))
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "loi climat", "besoin": "Trouver le texte de la loi"}
    )
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post("/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton))
    assert resultat.status_code == 200
    return resultat.json()["conversation"]["id"]


def _lire_url_du_compte(client, mistral_client_factice, jeton: str) -> int:
    # Le compte écrit l'URL, le modèle la lit avec lire_pages_web au même tour.
    mistral_client_factice.repondre_avec_appel_outil("lire_pages_web", {"urls": [_URL_COMPTE]})
    mistral_client_factice.repondre("Lu.", "Titre")
    resultat = client.post(
        "/conversations", json={"message": f"Voici le devis : {_URL_COMPTE}"}, headers=_autorisation(jeton)
    )
    assert resultat.status_code == 200
    return resultat.json()["conversation"]["id"]


def _ligne(db_session, conversation_id: int, url: str = _URL) -> ResultatRechercheWeb:
    return db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id, url=url).one()


def _vieillir(db_session, url: str, age: timedelta) -> None:
    copie = db_session.query(PageWebEnCache).filter_by(url=url).one()
    copie.date_telechargement = datetime.now(timezone.utc) - age
    db_session.commit()


def _trace_outil(client, conversation_id: int, jeton: str, outil: str, monkeypatch) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton), "X-Admin-Key": "cle-admin-de-test"}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{outil}"]
    return client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes_admin).json()["reponse_payload"]


def test_une_page_lue_par_un_compte_est_servie_a_un_autre_sans_telechargement(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
):
    telechargeur_pages_factice.servir(_URL, _page_html("La loi compte 305 articles."))
    premiere = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)
    assert telechargeur_pages_factice.urls_recues == [_URL]
    telechargeur_pages_factice.urls_recues.clear()

    seconde = _rechercher(
        client,
        mistral_client_factice,
        moteur_recherche_factice,
        jeton_autre_compte,
        reponse="La loi compte 305 articles. Elle a 48 décrets.",
    )

    assert telechargeur_pages_factice.urls_recues == []
    assert seconde != premiere
    assert "La loi compte 305 articles." in _ligne(db_session, seconde).texte_nettoye
    assert "La loi compte 305 articles." in mistral_client_factice.appels_extraction[-1][-1]["content"]
    # Source du garde-fou chiffres dans la seconde conversation.
    message = client.get(f"/conversations/{seconde}", headers=_autorisation(jeton_autre_compte)).json()
    reponse = message["messages"][-1]["contenu"]
    assert "305" in reponse and "48" not in reponse


def test_une_url_ecrite_par_le_compte_deja_en_cache_est_servie_sans_telechargement(
    client,
    mistral_client_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
):
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html("Le délai prévu est de six semaines."))
    _lire_url_du_compte(client, mistral_client_factice, jeton_valide)
    telechargeur_pages_factice.urls_recues.clear()

    seconde = _lire_url_du_compte(client, mistral_client_factice, jeton_autre_compte)

    assert telechargeur_pages_factice.urls_recues == []
    assert "six semaines" in _ligne(db_session, seconde, _URL_COMPTE).texte_nettoye
    # Avant-dernier appel : le dernier est le titrage.
    (tool,) = [m for m in mistral_client_factice.appels_reponse[-2] if m["role"] == "tool"]
    assert "six semaines" in tool["content"]


def test_une_copie_de_plus_de_24_h_est_ignoree_la_page_retelechargee_et_la_ligne_ecrasee(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
):
    telechargeur_pages_factice.servir(_URL, _page_html("Ancienne version de la page."))
    _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)
    _vieillir(db_session, _URL, timedelta(hours=24, minutes=1))
    telechargeur_pages_factice.servir(_URL, _page_html("Nouvelle version de la page."))
    telechargeur_pages_factice.urls_recues.clear()

    seconde = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_autre_compte)

    assert telechargeur_pages_factice.urls_recues == [_URL]
    assert "Nouvelle version" in _ligne(db_session, seconde).texte_nettoye
    db_session.expire_all()
    (copie,) = db_session.query(PageWebEnCache).all()
    assert "Nouvelle version" in copie.texte_nettoye
    date = copie.date_telechargement.replace(tzinfo=copie.date_telechargement.tzinfo or timezone.utc)
    assert datetime.now(timezone.utc) - date < timedelta(minutes=1)


@pytest.mark.parametrize(
    "servir",
    [
        lambda telechargeur: telechargeur.servir(_URL, "<html>Interdit</html>", statut=403),
        lambda telechargeur: telechargeur.servir(_URL, "%PDF-1.7 Loi", type_contenu="application/pdf"),
        lambda telechargeur: None,  # délai dépassé
        lambda telechargeur: telechargeur.servir(_URL, "<html><body></body></html>"),
    ],
    ids=["403", "non HTML", "délai", "aucun texte"],
)
def test_un_echec_nest_jamais_mis_en_cache_et_la_conversation_suivante_retente(
    servir,
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
):
    servir(telechargeur_pages_factice)
    _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)
    assert db_session.query(PageWebEnCache).count() == 0
    telechargeur_pages_factice.urls_recues.clear()
    telechargeur_pages_factice.servir(_URL, _page_html("Page enfin lisible."))

    seconde = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_autre_compte)

    assert telechargeur_pages_factice.urls_recues == [_URL]
    assert "Page enfin lisible." in _ligne(db_session, seconde).texte_nettoye


def test_supprimer_une_conversation_laisse_le_cache_intact(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    telechargeur_pages_factice.servir(_URL, _page_html("Texte de la loi."))
    conversation_id = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)

    suppression = client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))

    assert suppression.status_code == 204
    assert db_session.query(ResultatRechercheWeb).count() == 0
    (copie,) = db_session.query(PageWebEnCache).all()
    assert copie.url == _URL and "Texte de la loi." in copie.texte_nettoye


def test_les_questions_couvertes_dun_compte_napparaissent_pas_dans_la_memoire_dun_autre(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
):
    telechargeur_pages_factice.servir(_URL, _page_html("La loi compte 305 articles."))
    mistral_client_factice.repondre_extraction(
        [("305 articles.", _URL)], [("Combien d'articles pour le dossier Dupont ?", "305 articles", _URL)]
    )
    _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)
    mistral_client_factice.repondre_extraction()

    seconde = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_autre_compte)
    mistral_client_factice.repondre("Suite.", resume_et_profil=_resume_et_profil())
    suite = client.post(
        f"/conversations/{seconde}/messages", json={"message": "Et ensuite ?"}, headers=_autorisation(jeton_autre_compte)
    )

    assert suite.status_code == 200
    (memoire,) = [
        m["content"]
        for m in mistral_client_factice.appels_reponse[-1]
        if m["role"] == "system" and m["content"].startswith(_TITRE_MEMOIRE)
    ]
    assert _URL in memoire
    assert "Dupont" not in memoire and "305 articles" not in memoire


def test_le_plafond_de_tokens_sapplique_aux_pages_servies_par_le_cache(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
    monkeypatch,
):
    resultats = [("Loi Climat et résilience", _URL, "Texte de la loi."), *_AUTRES_RESULTATS]
    for numero, (_, url, _) in enumerate(resultats):
        telechargeur_pages_factice.servir(url, _page_dense(f"FIN DE LA PAGE {numero}"))
    moteur_recherche_factice.repondre(*resultats)
    mistral_client_factice.repondre_avec_appel_outil("rechercher_web", {"requete": "loi", "besoin": "La loi"})
    mistral_client_factice.repondre("Voici.", "Titre")
    assert client.post("/conversations", json={"message": "Loi"}, headers=_autorisation(jeton_valide)).status_code == 200
    # Les trois pages sont en cache, avant plafond : la troisième aussi.
    assert db_session.query(PageWebEnCache).count() == 3
    telechargeur_pages_factice.urls_recues.clear()

    mistral_client_factice.repondre_avec_appel_outil("rechercher_web", {"requete": "loi", "besoin": "La loi"})
    mistral_client_factice.repondre("Voici.", "Titre")
    seconde = client.post("/conversations", json={"message": "Loi"}, headers=_autorisation(jeton_autre_compte))

    assert telechargeur_pages_factice.urls_recues == []
    pages = _trace_outil(client, seconde.json()["conversation"]["id"], jeton_autre_compte, "rechercher_web", monkeypatch)[
        "pages"
    ]
    assert [page["origine"] for page in pages] == ["cache", "cache", "cache"]
    assert [page["retiree_par_plafond"] for page in pages] == [False, False, True]
    assert "FIN DE LA PAGE 2" not in mistral_client_factice.appels_extraction[-1][-1]["content"]


def test_linspecteur_montre_lorigine_et_lage_de_la_copie_de_chaque_page(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    jeton_autre_compte,
    db_session,
    monkeypatch,
):
    telechargeur_pages_factice.servir(_URL, _page_html("Texte de la loi."))
    premiere = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_valide)
    _vieillir(db_session, _URL, timedelta(hours=2))

    seconde = _rechercher(client, mistral_client_factice, moteur_recherche_factice, jeton_autre_compte)

    (telechargee,) = _trace_outil(client, premiere, jeton_valide, "rechercher_web", monkeypatch)["pages"]
    assert telechargee["origine"] == "telechargement" and "age_copie_secondes" not in telechargee
    (en_cache,) = _trace_outil(client, seconde, jeton_autre_compte, "rechercher_web", monkeypatch)["pages"]
    assert en_cache["origine"] == "cache" and en_cache["statut"] == 200 and en_cache["taille"] > 0
    assert 2 * 3600 <= en_cache["age_copie_secondes"] < 2 * 3600 + 60


def test_linspecteur_montre_lorigine_dune_url_du_compte_servie_par_le_cache(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide, jeton_autre_compte, monkeypatch
):
    telechargeur_pages_factice.servir(_URL_COMPTE, _page_html("Le délai prévu est de six semaines."))
    premiere = _lire_url_du_compte(client, mistral_client_factice, jeton_valide)
    seconde = _lire_url_du_compte(client, mistral_client_factice, jeton_autre_compte)

    (telechargee,) = _trace_outil(client, premiere, jeton_valide, "lire_pages_web", monkeypatch)["pages_telechargees"]
    (en_cache,) = _trace_outil(client, seconde, jeton_autre_compte, "lire_pages_web", monkeypatch)[
        "pages_telechargees"
    ]
    assert telechargee["origine"] == "telechargement"
    assert en_cache["origine"] == "cache" and en_cache["age_copie_secondes"] < 60
