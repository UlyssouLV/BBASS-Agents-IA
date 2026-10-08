import json
import re

from flux_sse import fin

from vm_centrale.models import QuestionCouverte
from vm_centrale.routers.conversations import NOTE_MEMOIRE

# Lectures Moduléo dans la Mémoire de la conversation (spec 1.5.0, #177) :
# chaque fiche lue est listée avec sa date et des questions couvertes
# écrites par script, sans appel Mistral.

_TITRE_MEMOIRE = "Mémoire de la conversation :"
_TEL_RESPONSABLE = "04 67 12 34 56"
_TEL_DUPONT = "04 67 98 76 54"
_DATE_LECTURE = r"\(lue le \d{2}/\d{2}/\d{4} à \d{2}:\d{2} UTC\)"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _memoire(mistral_client_factice) -> str:
    (memoire,) = [
        m["content"]
        for m in mistral_client_factice.appels_reponse[-1]
        if m["role"] == "system" and m["content"].startswith(_TITRE_MEMOIRE)
    ]
    return memoire


def _affaire_2024_123(faux_moduleo) -> None:
    faux_moduleo.ajouter_commune(5, "Castries", "34160")
    faux_moduleo.ajouter_contact(20, "SCI Les Oliviers")
    faux_moduleo.ajouter_contact(30, "Office notarial Rives")
    faux_moduleo.ajouter_contact(31, "Claire Rives")
    faux_moduleo.ajouter_utilisateur(1, "Jean", "Martin", tel_fixe=_TEL_RESPONSABLE)
    faux_moduleo.ajouter_utilisateur(2, "Sophie", "Bernard")
    faux_moduleo.ajouter_affaire(
        101,
        "2024-123",
        "Bornage du lot B",
        Etat=1,
        DateOuverture="2024-03-11T00:00:00+01:00",
        Adresse="12 chemin des Oliviers",
        IdCommune=5,
        IdClient=20,
        QualiteClient="Propriétaire",
        IdResponsable=1,
        IdActeurEnCharge=2,
    )
    faux_moduleo.ajouter_intervenant(900, 101, 30, "Notaire", id_representant=31, qualite_representant="Clerc")


def _dupont(faux_moduleo) -> None:
    faux_moduleo.ajouter_commune(5, "Castries", "34160")
    faux_moduleo.ajouter_contact(40, "Étude Dupont", type_contact=3)
    faux_moduleo.ajouter_telephone(1, 40, _TEL_DUPONT, "Bureau")
    faux_moduleo.ajouter_email(3, 40, "contact@etude-dupont.fr", "Travail")
    faux_moduleo.ajouter_adresse(4, 40, "3 rue de la Mairie", "Siège", id_commune=5)
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")
    faux_moduleo.ajouter_affaire(102, "2023-050", "Division")
    faux_moduleo.lier_affaire(40, 101, "client")
    faux_moduleo.lier_affaire(40, 102, "intervenant")


def _lire_puis_suivre(client, mistral_client_factice, jeton: str, outil: str, arguments: dict) -> int:
    # Tour 1 : le modèle appelle l'outil ; tour 2 : une question de suivi,
    # répondue sans outil.
    mistral_client_factice.repondre_avec_appel_outil(outil, arguments)
    mistral_client_factice.repondre("Voici la fiche.", "Titre")
    reponse = client.post("/conversations", json={"message": "Retrouve-la"}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    conversation_id = fin(reponse)["conversation"]["id"]
    mistral_client_factice.repondre("Suite", resume_et_profil=_resume_et_profil())
    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Et alors ?"}, headers=_autorisation(jeton)
    )
    assert reponse.status_code == 200
    return conversation_id


def test_une_affaire_lue_est_dans_la_memoire_avec_sa_date_et_ses_questions_couvertes(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    _lire_puis_suivre(
        client, mistral_client_factice, jeton_valide, "chercher_affaires_moduleo", {"numero": "2024-123"}
    )

    lignes = _memoire(mistral_client_factice).splitlines()
    assert re.fullmatch(rf"- Tour 1 — Moduléo, affaire 2024-123 {_DATE_LECTURE}", lignes[1])
    source = "(Moduléo, affaire 2024-123)"
    assert f"  • Quel est l'état de l'affaire 2024-123 ? → Production {source}" in lignes
    assert f"  • Quel est l'objet de l'affaire 2024-123 ? → Bornage du lot B {source}" in lignes
    assert (
        "  • Qui sont les intervenants de l'affaire 2024-123 ? → "
        f"Office notarial Rives (Notaire), représenté par Claire Rives (Clerc) {source}"
    ) in lignes
    assert (
        "  • Qui suit l'affaire 2024-123 ? → "
        f"Responsable : Jean Martin (tél. {_TEL_RESPONSABLE}) ; Chargé d'affaire : Sophie Bernard {source}"
    ) in lignes
    assert f"  • Qui est le client de l'affaire 2024-123 ? → SCI Les Oliviers (Propriétaire) {source}" in lignes
    assert (
        f"  • Où se trouve l'affaire 2024-123 ? → 12 chemin des Oliviers, Castries (34160) {source}"
    ) in lignes
    assert f"  • Quelles sont les dates de l'affaire 2024-123 ? → Date d'ouverture : 11/03/2024 {source}" in lignes


def test_un_contact_lu_est_dans_la_memoire_avec_sa_date_et_ses_questions_couvertes(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _dupont(faux_moduleo)

    _lire_puis_suivre(client, mistral_client_factice, jeton_valide, "chercher_contacts_moduleo", {"texte": "Dupont"})

    lignes = _memoire(mistral_client_factice).splitlines()
    assert re.fullmatch(rf"- Tour 1 — Moduléo, contact Étude Dupont {_DATE_LECTURE}", lignes[1])
    source = "(Moduléo, contact Étude Dupont)"
    assert (
        f"  • Comment joindre Étude Dupont ? → {_TEL_DUPONT} (Bureau) ; contact@etude-dupont.fr (Travail) {source}"
    ) in lignes
    assert (
        f"  • Quelle est l'adresse de Étude Dupont ? → 3 rue de la Mairie, Castries (34160) (Siège) {source}"
    ) in lignes
    assert (
        "  • Dans quelles affaires apparaît Étude Dupont ? → "
        f"Client des affaires : 2024-123 ; Intervenant dans les affaires : 2023-050 {source}"
    ) in lignes


def test_un_champ_vide_na_pas_de_question(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")

    _lire_puis_suivre(
        client, mistral_client_factice, jeton_valide, "chercher_affaires_moduleo", {"numero": "2024-123"}
    )

    questions = [ligne for ligne in _memoire(mistral_client_factice).splitlines() if ligne.startswith("  • ")]
    assert questions == ["  • Quel est l'objet de l'affaire 2024-123 ? → Bornage du lot B (Moduléo, affaire 2024-123)"]


def test_les_questions_dune_fiche_ne_demandent_aucun_appel_mistral(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _affaire_2024_123(faux_moduleo)

    _lire_puis_suivre(
        client, mistral_client_factice, jeton_valide, "chercher_affaires_moduleo", {"numero": "2024-123"}
    )

    questions = db_session.query(QuestionCouverte).all()
    assert questions and all(q.lecture_outil_id is not None and q.origine == "initiale" for q in questions)
    # Tour 1 : appel d'outil, réponse, titrage ; tour 2 : résumé (structuré)
    # et réponse. Aucun autre appel.
    assert len(mistral_client_factice.appels_reponse) == 4
    assert len(mistral_client_factice.appels_structures) == 1
    assert not mistral_client_factice.appels_extraction
    assert not mistral_client_factice.appels_questions_piece_jointe
    assert not mistral_client_factice.appels_lecture_page


def test_une_question_de_suivi_sur_une_affaire_lue_se_repond_sans_rappel_de_loutil(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)
    mistral_client_factice.repondre_avec_appel_outil("chercher_affaires_moduleo", {"numero": "2024-123"})
    mistral_client_factice.repondre("Voici l'affaire.", "Titre")
    reponse = client.post("/conversations", json={"message": "Retrouve 2024-123"}, headers=_autorisation(jeton_valide))
    conversation_id = fin(reponse)["conversation"]["id"]
    routes_tour_1 = len(faux_moduleo.appels)

    mistral_client_factice.repondre(
        f"Jean Martin suit l'affaire, joignable au {_TEL_RESPONSABLE}.", resume_et_profil=_resume_et_profil()
    )
    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Qui suit l'affaire 2024-123 ?"},
        headers=_autorisation(jeton_valide),
    )

    assert reponse.status_code == 200
    assert len(faux_moduleo.appels) == routes_tour_1
    assert "Qui suit l'affaire 2024-123 ?" in _memoire(mistral_client_factice)
    contenu = fin(reponse)["reponse"]
    assert _TEL_RESPONSABLE in contenu
    assert "Moduléo, affaire 2024-123" in contenu


def test_la_memoire_dit_de_rappeler_moduleo_pour_letat_actuel_ou_une_lecture_ancienne(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    _lire_puis_suivre(
        client, mistral_client_factice, jeton_valide, "chercher_affaires_moduleo", {"numero": "2024-123"}
    )

    memoire = _memoire(mistral_client_factice)
    assert "état actuel" in memoire and "ancienne" in memoire and "rappelle" in memoire
    assert memoire.splitlines()[-1] == NOTE_MEMOIRE


def test_sans_lecture_moduleo_la_memoire_ne_parle_pas_de_moduleo(
    client, mistral_client_factice, moteur_recherche_factice, jeton_valide
):
    moteur_recherche_factice.repondre(("Titre", "https://www.exemple.fr/a", "Extrait"))
    mistral_client_factice.repondre_avec_appel_outil("rechercher_web", {"requete": "bornage", "besoin": "Besoin"})
    mistral_client_factice.repondre("Réponse", "Titre")
    reponse = client.post("/conversations", json={"message": "Cherche"}, headers=_autorisation(jeton_valide))
    mistral_client_factice.repondre("Suite", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{fin(reponse)['conversation']['id']}/messages",
        json={"message": "Et alors ?"},
        headers=_autorisation(jeton_valide),
    )

    assert "Moduléo" not in _memoire(mistral_client_factice)
