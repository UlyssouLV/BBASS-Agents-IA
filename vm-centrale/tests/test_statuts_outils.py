import json

import pytest

from flux_sse import fin, statuts

from vm_centrale.config import LONGUEUR_MAX_DETAIL_STATUT

# Statuts publiés par les outils (spec 1.4.4, #165) : la recherche, chaque
# page lue (téléchargement ou cache) et chaque pièce jointe relue, avec leur
# détail ; l'appel principal suivant republie « Réflexion… ».

_URL_LEGIFRANCE = "https://www.legifrance.gouv.fr/loi-climat"
_URL_VIE_PUBLIQUE = "https://vie-publique.fr/loi-climat"


@pytest.fixture(autouse=True)
def _repertoire_pieces_jointes(tmp_path, monkeypatch):
    # Voir tests/test_pieces_jointes.py.
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _page_html(texte: str) -> str:
    # Assez de texte pour que trafilatura garde l'article (voir
    # test_recherche_web).
    remplissage = (
        "La loi Climat et résilience a été promulguée le 22 août 2021 après un long "
        "débat parlementaire sur la transition écologique du pays.",
        "Elle reprend une partie des propositions de la Convention citoyenne pour le "
        "climat, réunie de 2019 à 2020 à la demande du gouvernement.",
    )
    corps = "".join(f"<p>{paragraphe}</p>" for paragraphe in (*remplissage, texte))
    return f"<html><body><article><h1>Loi Climat</h1>{corps}</article></body></html>"


def _rechercher(client, mistral_client_factice, jeton: str, requete: str = "loi climat résilience"):
    mistral_client_factice.repondre_avec_appel_outil("rechercher_web", {"requete": requete, "besoin": "Le texte"})
    mistral_client_factice.repondre("Voici.", "Titre")
    return client.post("/conversations", json={"message": "Trouve la loi Climat"}, headers=_autorisation(jeton))


def _servir_deux_pages(moteur_recherche_factice, telechargeur_pages_factice) -> None:
    moteur_recherche_factice.repondre(
        ("Loi Climat", _URL_LEGIFRANCE, "Texte de la loi."), ("Analyse", _URL_VIE_PUBLIQUE, "Ce qui change.")
    )
    telechargeur_pages_factice.servir(_URL_LEGIFRANCE, _page_html("Article premier."))
    telechargeur_pages_factice.servir(_URL_VIE_PUBLIQUE, _page_html("Analyse de la loi."))


def test_rechercher_web_publie_la_requete_puis_chaque_domaine_lu_puis_reflexion(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _servir_deux_pages(moteur_recherche_factice, telechargeur_pages_factice)

    reponse = _rechercher(client, mistral_client_factice, jeton_valide)

    assert statuts(reponse) == [
        "Réflexion…",
        "Recherche sur le web : “loi climat résilience”",
        "Lecture de legifrance.gouv.fr",
        "Lecture de vie-publique.fr",
        "Réflexion…",
        "Vérification de la réponse…",
        "Titre de la conversation…",
    ]


def test_une_page_servie_par_le_cache_publie_aussi_sa_lecture(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _servir_deux_pages(moteur_recherche_factice, telechargeur_pages_factice)
    assert _rechercher(client, mistral_client_factice, jeton_valide).status_code == 200
    telechargeur_pages_factice.urls_recues.clear()

    reponse = _rechercher(client, mistral_client_factice, jeton_valide)

    assert telechargeur_pages_factice.urls_recues == []
    assert "Lecture de legifrance.gouv.fr" in statuts(reponse)
    assert "Lecture de vie-publique.fr" in statuts(reponse)


def test_une_requete_trop_longue_est_tronquee(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    requete = "réglementation " * 20

    reponse = _rechercher(client, mistral_client_factice, jeton_valide, requete)

    (libelle,) = [statut for statut in statuts(reponse) if statut.startswith("Recherche sur le web")]
    assert libelle == f"Recherche sur le web : “{requete.strip()[:LONGUEUR_MAX_DETAIL_STATUT]}…”"


def test_lire_pages_web_publie_un_statut_par_page_lue(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    _servir_deux_pages(moteur_recherche_factice, telechargeur_pages_factice)
    conversation_id = fin(_rechercher(client, mistral_client_factice, jeton_valide))["conversation"]["id"]
    mistral_client_factice.repondre_avec_appel_outil(
        "lire_pages_web", {"urls": [_URL_VIE_PUBLIQUE, "https://www.ailleurs.fr/page", _URL_LEGIFRANCE]}
    )
    mistral_client_factice.repondre("Réponse.", resume_et_profil=_resume_et_profil())

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Relis ces pages"},
        headers=_autorisation(jeton_valide),
    )

    assert statuts(reponse) == [
        "Réflexion…",
        "Lecture de vie-publique.fr",
        "Lecture de legifrance.gouv.fr",
        "Réflexion…",
        "Vérification de la réponse…",
    ]


def _relire_piece_jointe(client, mistral_client_factice, jeton: str, nom_fichier: str):
    # Pièce jointe d'un tour précédent : relire_pieces_jointes est éligible.
    mistral_client_factice.repondre_ocr("Plan de masse détaillé")
    televersement = client.post(
        "/pieces-jointes",
        files={"fichier": (nom_fichier, b"%PDF-1.4 contenu factice", "application/pdf")},
        headers=_autorisation(jeton),
    )
    assert televersement.status_code == 201
    piece_jointe_id = televersement.json()["piece_jointe"]["id"]
    mistral_client_factice.repondre("Première réponse", "Titre")
    conversation_id = fin(
        client.post(
            "/conversations",
            json={"message": "Regarde ce document", "piece_jointe_id": piece_jointe_id},
            headers=_autorisation(jeton),
        )
    )["conversation"]["id"]
    mistral_client_factice.repondre_avec_appel_outil("relire_pieces_jointes", {"piece_jointe_ids": [piece_jointe_id]})
    mistral_client_factice.repondre("Voici le plan.", resume_et_profil=_resume_et_profil())
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Relis le plan"},
        headers=_autorisation(jeton),
    )


def test_relire_pieces_jointes_publie_le_nom_du_fichier(client, mistral_client_factice, jeton_valide):
    reponse = _relire_piece_jointe(client, mistral_client_factice, jeton_valide, "plan-de-masse.pdf")

    assert statuts(reponse) == [
        "Réflexion…",
        "Relecture de plan-de-masse.pdf",
        "Réflexion…",
        "Vérification de la réponse…",
    ]
    assert fin(reponse)["reponse"] == "Voici le plan."


def test_un_nom_de_fichier_trop_long_est_tronque(client, mistral_client_factice, jeton_valide):
    nom_fichier = "plan-" * 30 + ".pdf"

    reponse = _relire_piece_jointe(client, mistral_client_factice, jeton_valide, nom_fichier)

    assert f"Relecture de {nom_fichier[:LONGUEUR_MAX_DETAIL_STATUT]}…" in statuts(reponse)
