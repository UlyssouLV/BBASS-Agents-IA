import json

from flux_sse import fin

from vm_centrale.models import Consommation

# Relecture isolée après un retrait de garde-fou (#131, spec 1.6.3, point 9,
# ADR-0023) : un appel Mistral à part, sans outils ni historique, réécrit la
# réponse marquée à partir des seuls résultats d'outils ; les garde-fous
# repassent sur sa sortie, et elle n'est retenue que s'ils n'y retirent rien.

_URL_PAGE = "https://www.leboncoin.fr/aide/tarifs"
_PAGE = (
    "<html><head><title>Tarifs</title></head><body><nav>Menu du site</nav><article>"
    "<h1>Tarifs des options</h1>"
    "<p>Les options de mise en avant d'une annonce rendent celle-ci plus visible auprès des acheteurs "
    "pendant toute leur durée, sur le site comme dans l'application mobile du service.</p>"
    "<p>Chaque option se commande depuis la page de l'annonce, au moment du dépôt ou plus tard, "
    "et son prix est affiché avant le paiement, toutes taxes comprises.</p>"
    "<p>La remontée en tête de liste coûte 5 € pour une durée de 7 jours.</p>"
    "</article><footer>Mentions légales</footer></body></html>"
)
_QUESTION = "Combien coûtent les options ?"
_REPONSE_INVENTEE = "La remontée coûte 5 € pour 7 jours. Le pack urgent coûte **4,99 €**."
_REPONSE_MARQUEE = "La remontée coûte 5 € pour 7 jours. Le pack urgent coûte **[non trouvé] €**."
_RELECTURE_PROPRE = (
    "La remontée en tête de liste coûte 5 € pour 7 jours. Le prix du pack urgent n'a pas été trouvé "
    "sur la page d'aide consultée."
)
_PHRASE_FIXE = "Certaines informations n'ont pas été trouvées dans les sources consultées."
_RESUME_ET_PROFIL = json.dumps({"resume_contexte": "Résumé secret Dupont", "profil_travail": "Profil secret Dupont"})


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _preparer_recherche(mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice) -> None:
    moteur_recherche_factice.repondre(("Tarifs", _URL_PAGE, "Les options de mise en avant."))
    telechargeur_pages_factice.servir(_URL_PAGE, _PAGE)
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "tarif mise en avant", "besoin": "Prix des options"}
    )


def _premier_tour(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton: str, reponse: str
) -> tuple[int, str]:
    _preparer_recherche(mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice)
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post("/conversations", json={"message": _QUESTION}, headers=_autorisation(jeton))
    corps = fin(resultat)
    return corps["conversation"]["id"], corps["reponse"]


def _sans_sources(contenu: str) -> str:
    return contenu.split("\n\nSources : ")[0]


def _dernier_message(client, jeton: str, conversation_id: int) -> str:
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton)).json()
    return detail["messages"][-1]["contenu"]


def test_une_reponse_sans_retrait_ne_declenche_aucune_relecture(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "La remontée en tête de liste coûte 5 € pour 7 jours.",
    )

    assert mistral_client_factice.appels_relecture == []


def test_la_relecture_recoit_la_question_la_reponse_marquee_et_les_resultats_doutils_sans_lhistorique(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre("Volontiers, parlons de l'annonce Dupont.", "Titre")
    corps = fin(client.post("/conversations", json={"message": "Mon annonce Dupont"}, headers=_autorisation(jeton_valide)))
    conversation_id = corps["conversation"]["id"]
    _preparer_recherche(mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice)
    mistral_client_factice.repondre(_REPONSE_INVENTEE, resume_et_profil=_RESUME_ET_PROFIL)
    mistral_client_factice.repondre_relecture(_RELECTURE_PROPRE)

    fin(
        client.post(
            f"/conversations/{conversation_id}/messages",
            json={"message": _QUESTION},
            headers=_autorisation(jeton_valide),
        )
    )

    assert len(mistral_client_factice.appels_relecture) == 1
    assert mistral_client_factice.tools_appels_relecture == [None]
    entree = "\n".join(message["content"] for message in mistral_client_factice.appels_relecture[0])
    resultat_outil = next(
        message["content"] for message in mistral_client_factice.appels_reponse[-1] if message["role"] == "tool"
    )
    assert _QUESTION in entree
    assert _REPONSE_MARQUEE in entree
    assert resultat_outil in entree
    assert "Dupont" not in entree


def test_une_relecture_qui_ne_fait_rien_retirer_est_enregistree_et_renvoyee(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre_relecture(_RELECTURE_PROPRE)

    conversation_id, contenu = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    assert _sans_sources(contenu) == _RELECTURE_PROPRE
    assert _PHRASE_FIXE not in contenu
    assert _dernier_message(client, jeton_valide, conversation_id) == contenu


def test_une_relecture_qui_invente_un_chiffre_est_ecartee(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.repondre_relecture("La remontée coûte 5 € pour 7 jours, le pack urgent 6,99 €.")

    conversation_id, contenu = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    assert contenu.startswith(_REPONSE_MARQUEE)
    assert contenu.endswith(f"\n\n{_PHRASE_FIXE}")
    assert "6,99" not in contenu
    assert _dernier_message(client, jeton_valide, conversation_id) == contenu


def test_une_relecture_en_erreur_laisse_la_reponse_marquee_et_la_phrase_fixe(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    mistral_client_factice.echouer_relecture(RuntimeError("Mistral injoignable"))

    _, contenu = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    assert contenu.startswith(_REPONSE_MARQUEE)
    assert contenu.endswith(f"\n\n{_PHRASE_FIXE}")


def _ligne_relecture(client, jeton: str, conversation_id: int, monkeypatch) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", "cle-admin-de-test")
    entetes_admin = {**_autorisation(jeton), "X-Admin-Key": "cle-admin-de-test"}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes_admin).json()
    relectures = [e for e in echanges if (e["origine"], e["type_appel"]) == ("mistral", "relecture")]
    assert len(relectures) == 1
    return client.get(f"/inspecteur/echanges/{relectures[0]['id']}", headers=entetes_admin).json()


def test_la_relecture_retenue_a_sa_ligne_dinspecteur_et_de_consommation(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session,
    monkeypatch,
):
    mistral_client_factice.repondre_relecture(_RELECTURE_PROPRE)

    conversation_id, _ = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    detail = _ligne_relecture(client, jeton_valide, conversation_id, monkeypatch)
    assert detail["statut"] == "succes"
    assert _REPONSE_MARQUEE in json.dumps(detail["requete_payload"], ensure_ascii=False)
    assert _RELECTURE_PROPRE in json.dumps(detail["reponse_payload"], ensure_ascii=False)
    assert detail["reponse_payload"]["relecture"] == "retenue"
    assert db_session.query(Consommation).filter_by(type_appel="relecture").count() == 1


def test_la_relecture_ecartee_a_sa_ligne_dinspecteur_et_de_consommation(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, db_session,
    monkeypatch,
):
    mistral_client_factice.repondre_relecture("Le pack urgent coûte 6,99 €.")

    conversation_id, _ = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    detail = _ligne_relecture(client, jeton_valide, conversation_id, monkeypatch)
    assert detail["reponse_payload"]["relecture"] == "écartée"
    assert db_session.query(Consommation).filter_by(type_appel="relecture").count() == 1


def test_la_relecture_en_erreur_a_sa_ligne_dinspecteur_ecartee(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide, monkeypatch
):
    mistral_client_factice.echouer_relecture(RuntimeError("Mistral injoignable"))

    conversation_id, _ = _premier_tour(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        _REPONSE_INVENTEE,
    )

    detail = _ligne_relecture(client, jeton_valide, conversation_id, monkeypatch)
    assert detail["statut"] == "echec"
    assert detail["reponse_payload"]["relecture"] == "écartée"
