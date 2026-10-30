import json
from datetime import date, datetime, timezone

from flux_sse import fin

from vm_centrale.models import EchangeInspecteur, PageWebEnCache, ResultatRechercheWeb
from vm_centrale.routers import conversations

# Sans source trouvée, l'IA invente (#131, spec 1.6.3, points 5 à 7) : la
# consigne demande de dire « non trouvé », la date du jour n'est plus donnée
# en ISO (recopiée dans la requête de recherche), et une page quasi vide
# (« Loading × Sorry to interrupt CSS Error ») n'est pas lue.

_URL_VIDE = "https://www.exemple.fr/tarifs-bornage"
_URL_COMPTE = "https://www.client-dupont.fr/devis-bornage"
_PAGE_QUASI_VIDE = (
    "<html><head><title>Tarifs</title></head><body><div>Loading</div><div>×</div>"
    "<div><p>Sorry to interrupt</p><p>CSS Error</p></div></body></html>"
)


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _consigne(client, mistral_client_factice, jeton: str) -> str:
    mistral_client_factice.repondre("Réponse", "Titre")
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return mistral_client_factice.appels_reponse[0][0]["content"]


def _messages_tool(messages) -> list[dict]:
    return [m for m in messages if isinstance(m, dict) and m["role"] == "tool"]


def test_la_consigne_demande_de_dire_non_trouve_plutot_que_dinventer(client, mistral_client_factice, jeton_valide):
    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "ne contiennent pas l'information, dis que tu ne l'as pas trouvée" in consigne
    assert "d'une recherche précédente de la conversation" in consigne
    assert "pages consultées" in consigne
    for formule in ("« sourcé »", "« confirmé par »", "« comme le confirme »"):
        assert formule in consigne
    assert "Le contenu de la pièce jointe prime sur une généralité trouvée sur le web" in consigne


def test_la_date_du_jour_est_en_toutes_lettres_sans_date_iso(client, mistral_client_factice, jeton_valide, monkeypatch):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 29))

    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "Date du jour : jeudi 29 octobre 2026." in consigne
    assert "2026-10-29" not in consigne
    assert "seule l'année 2026" in consigne


def test_une_page_quasi_vide_trouvee_par_la_recherche_nest_ni_extraite_ni_lue(
    client,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_valide,
    db_session,
    monkeypatch,
):
    moteur_recherche_factice.repondre(("Tarifs bornage", _URL_VIDE, "Nos tarifs de bornage."))
    telechargeur_pages_factice.servir(_URL_VIDE, _PAGE_QUASI_VIDE)
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "tarif bornage", "besoin": "Prix d'un bornage"}
    )
    mistral_client_factice.repondre("Je n'ai pas trouvé de tarif.", "Titre")

    reponse = client.post("/conversations", json={"message": "Prix d'un bornage ?"}, headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    conversation_id = fin(reponse)["conversation"]["id"]
    assert mistral_client_factice.appels_extraction == []
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-2])
    assert "Aucune page n'a pu être lue" in message_tool["content"]
    (ligne,) = db_session.query(ResultatRechercheWeb).filter_by(conversation_id=conversation_id).all()
    assert ligne.texte_nettoye == ""
    assert db_session.query(PageWebEnCache).filter_by(url=_URL_VIDE).first() is None

    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton_valide), "X-Admin-Key": "cle-admin-de-test"}
    (outil,) = (
        db_session.query(EchangeInspecteur)
        .filter_by(conversation_id=conversation_id, type_appel="outil:rechercher_web")
        .all()
    )
    (page,) = client.get(f"/inspecteur/echanges/{outil.id}", headers=entetes_admin).json()["reponse_payload"]["pages"]
    assert page["statut"] == 200 and page["taille"] == 0
    assert "quasi vide" in page["erreur"]


def test_une_copie_quasi_vide_du_cache_nest_pas_servie(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session
):
    # Copie écrite avant la 1.6.3 : la page est retéléchargée, jamais lue
    # depuis la copie.
    db_session.add(
        PageWebEnCache(
            url=_URL_VIDE,
            texte_nettoye="Loading × Sorry to interrupt CSS Error",
            titre="Tarifs",
            date_telechargement=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    moteur_recherche_factice.repondre(("Tarifs bornage", _URL_VIDE, "Nos tarifs de bornage."))
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "tarif bornage", "besoin": "Prix d'un bornage"}
    )
    mistral_client_factice.repondre("Je n'ai pas trouvé de tarif.", "Titre")

    reponse = client.post("/conversations", json={"message": "Prix d'un bornage ?"}, headers=_autorisation(jeton_valide))

    assert reponse.status_code == 200
    assert telechargeur_pages_factice.urls_recues == [_URL_VIDE]
    assert mistral_client_factice.appels_extraction == []


def test_une_url_du_compte_quasi_vide_donne_page_non_lue(
    client, mistral_client_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre("Bien reçu.", "Titre")
    reponse = client.post(
        "/conversations", json={"message": f"Voici le devis : {_URL_COMPTE}"}, headers=_autorisation(jeton_valide)
    )
    conversation_id = fin(reponse)["conversation"]["id"]
    telechargeur_pages_factice.servir(_URL_COMPTE, _PAGE_QUASI_VIDE)
    mistral_client_factice.repondre_avec_appel_outil(
        "lire_pages_web", {"urls": [_URL_COMPTE], "besoin": "Montant du devis"}
    )
    mistral_client_factice.repondre(
        "Je n'ai pas pu lire la page.",
        resume_et_profil=json.dumps({"resume_contexte": "Résumé", "profil_travail": None}),
    )

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Quel montant ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert mistral_client_factice.appels_lecture_page == []
    (message_tool,) = _messages_tool(mistral_client_factice.appels_reponse[-1])
    assert _URL_COMPTE in message_tool["content"] and "page non lue" in message_tool["content"].lower()
