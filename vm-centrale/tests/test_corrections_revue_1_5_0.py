import json
from datetime import date, timedelta

from flux_sse import fin

from vm_centrale.garde_fous import remplacer_contact_non_lu
from vm_centrale.garde_fous.sources import LectureSource, ajouter_sources
from vm_centrale.moduleo.client import ModuleoIntrouvable
from vm_centrale.outils.moduleo.affaires import outil as outil_affaires
from vm_centrale.routers import conversations

# Corrections de la revue de code de la 1.5.0 (/code-review main) :
# recherche d'affaires plafonnée à 200 ids, date du jour dans le garde-fou
# chiffres, contact lu à un tour précédent, garde-fou contact sans Moduléo
# ou sur « n'hésitez pas », citation préfixe d'une autre, 404 sur une
# lecture secondaire.

_AFFAIRES = "chercher_affaires_moduleo"
_CONTACTS = "chercher_contacts_moduleo"
_PHRASE_CONTACT = "Moduléo n'a pas encore été consulté pour ce contact. Précisez son nom pour que je le cherche."
_PHRASE_SANS_DONNEES = "Je n'ai trouvé ni page ni document pour appuyer une réponse chiffrée."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _introuvable_sur(faux_moduleo, route_refusee: str, parametres_refuses: dict) -> None:
    # La lecture `route_refusee` avec ces paramètres répond 404, comme un
    # élément supprimé entre la recherche et sa lecture.
    lire = faux_moduleo.lire

    def lire_ou_404(route, parametres=None):
        if route == route_refusee and parametres_refuses.items() <= (parametres or {}).items():
            faux_moduleo.appels.append((route, parametres or {}))
            raise ModuleoIntrouvable(f"404 sur {route}")
        return lire(route, parametres)

    faux_moduleo.lire = lire_ou_404


def test_au_dela_de_200_affaires_les_plus_recentes_sont_quand_meme_affichees(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    # Le faux Moduléo renvoie les 200 premiers ids créés : les plus récents
    # manquent à la première recherche.
    monkeypatch.setattr(outil_affaires, "_date_du_jour", lambda: date(2026, 10, 8))
    for i in range(1, 251):
        creation = (date(2026, 1, 1) + timedelta(days=i)).isoformat()
        faux_moduleo.ajouter_affaire(i, f"2026-{i:03d}", "Bornage", DateCreation=f"{creation}T00:00:00")
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, {"texte": "bornage", "nb_max": 3})
    mistral_client_factice.repondre("Voici.", "Titre")

    client.post("/conversations", json={"message": "Affaires de bornage"}, headers=_autorisation(jeton_valide))

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("Au moins 200 affaires trouvées, 3 affichées")
    assert contenu.index("Affaire 2026-250") < contenu.index("Affaire 2026-249") < contenu.index("Affaire 2026-248")
    assert "Affaire 2026-200" not in contenu


def test_un_nombre_egal_au_jour_du_mois_reste_controle(client, mistral_client_factice, jeton_valide, monkeypatch):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 15))
    mistral_client_factice.repondre("Vous avez 15 affaires en cours.", "Titre")

    reponse = client.post("/conversations", json={"message": "Mes affaires"}, headers=_autorisation(jeton_valide))

    assert fin(reponse)["reponse"] == _PHRASE_SANS_DONNEES


def test_la_date_du_jour_ecrite_en_lettres_reste(client, mistral_client_factice, jeton_valide, monkeypatch):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 15))
    mistral_client_factice.repondre("Nous sommes le 15 octobre 2026.", "Titre")

    reponse = client.post("/conversations", json={"message": "Quel jour ?"}, headers=_autorisation(jeton_valide))

    assert fin(reponse)["reponse"] == "Nous sommes le 15 octobre 2026."


def test_un_contact_lu_a_un_tour_precedent_permet_de_dire_une_absence(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_contact(20, "Céline Bourdoncle")
    mistral_client_factice.repondre_avec_appel_outil(_CONTACTS, {"texte": "Bourdoncle"})
    mistral_client_factice.repondre("Voici le contact.", "Titre")
    reponse = client.post(
        "/conversations", json={"message": "Céline Bourdoncle"}, headers=_autorisation(jeton_valide)
    )
    conversation_id = fin(reponse)["conversation"]["id"]
    absence = "Moduléo ne contient aucun email pour Céline Bourdoncle."
    mistral_client_factice.repondre(absence, resume_et_profil=_resume_et_profil())

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Et son email ?"},
        headers=_autorisation(jeton_valide),
    )

    assert fin(reponse)["reponse"] == absence


def test_sans_moduleo_le_garde_fou_contact_ne_promet_pas_de_recherche(client, mistral_client_factice, jeton_valide):
    sans_acces = "Je n'ai pas accès à Moduléo pour retrouver son téléphone."
    mistral_client_factice.repondre(sans_acces, "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Téléphone de Dupont"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == sans_acces


def test_nhesitez_pas_nest_pas_une_absence_de_coordonnees():
    reponse = "Voici les affaires. N'hésitez pas à me demander ses coordonnées dans Moduléo."

    assert remplacer_contact_non_lu(reponse, contacts_lus=False) == reponse
    assert remplacer_contact_non_lu(reponse, contacts_lus=False) != _PHRASE_CONTACT


def test_une_citation_prefixe_dune_autre_est_quand_meme_ajoutee():
    sources = [
        LectureSource("Moduléo, affaire 2024-12", "Surface : 4521 m²"),
        LectureSource("Moduléo, affaire 2024-123", "Surface : 7788 m²"),
    ]
    reponse = "L'affaire 2024-12 fait 4521 m², la 2024-123 fait 7788 m².\n\nSources : Moduléo, affaire 2024-123"

    visible = ajouter_sources(reponse, [], sources)

    assert visible.endswith("Sources : Moduléo, affaire 2024-123, Moduléo, affaire 2024-12")


def test_un_404_sur_les_coordonnees_dun_contact_garde_les_autres_fiches(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_contact(1, "Dupont Alain")
    faux_moduleo.ajouter_contact(2, "Dupont Bernard")
    faux_moduleo.ajouter_telephone(10, 1, "04 67 98 76 54")
    _introuvable_sur(faux_moduleo, "cogeo/contact/{idContact}/telephones", {"idContact": 2})
    mistral_client_factice.repondre_avec_appel_outil(_CONTACTS, {"texte": "Dupont"})
    mistral_client_factice.repondre("Voici.", "Titre")

    client.post("/conversations", json={"message": "Dupont"}, headers=_autorisation(jeton_valide))

    contenu = _contenu_outil(mistral_client_factice)
    assert "Dupont Alain" in contenu
    assert "Dupont Bernard" in contenu
    assert "04 67 98 76 54" in contenu
    assert "indisponible" not in contenu


def test_un_404_sur_un_dossier_de_production_candidat_nest_pas_une_panne(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_dossier_production(1, "Production Est")
    faux_moduleo.ajouter_dossier_production(2, "Production Ouest")
    _introuvable_sur(faux_moduleo, "fileo/dossierproduction/{idDossierProduction}", {"idDossierProduction": 2})
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, {"dossier_production": "Production"})
    mistral_client_factice.repondre("Lequel ?", "Titre")

    client.post("/conversations", json={"message": "Affaires Production"}, headers=_autorisation(jeton_valide))

    contenu = _contenu_outil(mistral_client_factice)
    assert "Production Est" in contenu
    assert "indisponible" not in contenu
