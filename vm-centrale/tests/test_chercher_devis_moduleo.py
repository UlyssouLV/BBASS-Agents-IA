from datetime import date

import pytest

from flux_sse import fin, statuts

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit, LectureOutil, QuestionCouverte
from vm_centrale.moduleo.droits import COGEO, chemin, charger_catalogue, rattacher
from vm_centrale.outils.moduleo.devis import outil as outil_devis

# chercher_devis_moduleo (spec 1.5.1, #189) : devis par texte, émission,
# dates, service, responsable, rédacteur ou affaire, totaux calculés par la
# VM sur l'ensemble trouvé, avec un faux Moduléo (tests/faux_moduleo.py).

_OUTIL = "chercher_devis_moduleo"
_RECHERCHE = "cogeo/devis?texte="
_ADMIN = "cle-admin-de-test"
_CONSULTER_DEVIS = chemin("Devis, factures et avoirs", "Consulter les devis")
_REFUS = (
    "Votre compte n'a pas le droit Moduléo « Consulter les devis ». Aucune lecture n'a été faite. "
    "Demandez à un compte administrateur si vous en avez besoin."
)


@pytest.fixture(autouse=True)
def _aujourdhui(monkeypatch):
    monkeypatch.setattr(outil_devis, "_date_du_jour", lambda: date(2026, 10, 9))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici les devis."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post("/conversations", json={"message": "Où en sont les devis ?"}, headers=_autorisation(jeton))


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _outils_proposes(mistral_client_factice) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []}


def _bornage(faux_moduleo) -> None:
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(8, "Sophie", "Bernard")
    faux_moduleo.ajouter_contact(30, "Étude Dupont")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B", IdClient=30)
    faux_moduleo.ajouter_devis(
        501,
        "D-2026-042",
        "Bornage du lot B",
        IdAffaire=101,
        IdResponsable=7,
        IdRedacteur=8,
        DateCreation="2026-09-10T00:00:00+02:00",
        DateEmission="2026-09-15T00:00:00+02:00",
        DateReponse="2026-09-28T00:00:00+02:00",
        MontantTotalHT=1200.0,
        MontantTotalTVA=240.0,
        MontantTotalTTC=1440.0,
    )


# Proposition et garde des droits.


def test_le_schema_decrit_les_filtres_en_noms_et_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    proprietes = schema["function"]["parameters"]["properties"]
    assert set(proprietes) == {
        "texte",
        "emis",
        "date_emission_min",
        "date_emission_max",
        "date_reponse_min",
        "date_reponse_max",
        "service",
        "responsable",
        "redacteur",
        "affaire",
        "nb_max",
    }
    assert proprietes["emis"]["type"] == "boolean"
    assert "30 derniers jours" in schema["function"]["description"]


@pytest.fixture
def compte_sans_devis(db_session):
    # j.dupont dans un groupe Cogeo qui n'a pas « Consulter les devis ».
    charger_catalogue(db_session)
    groupe = GroupeModuleo(application=COGEO, nom="Sans devis")
    db_session.add(groupe)
    db_session.flush()
    droit = db_session.query(DroitModuleo).filter_by(chemin=chemin("Contacts", "Rechercher des contacts")).one()
    db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
    rattacher(db_session, "j.dupont", "Sans devis", None, None)
    db_session.commit()


def test_sans_le_droit_loutil_nest_pas_propose(
    client, faux_moduleo, compte_sans_devis, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _OUTIL not in _outils_proposes(mistral_client_factice)


def test_appele_sans_le_droit_phrase_fixe_et_rien_nest_lu(
    client, faux_moduleo, compte_sans_devis, mistral_client_factice, jeton_valide, db_session
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert _contenu_outil(mistral_client_factice) == _REFUS
    assert faux_moduleo.appels == []
    assert db_session.query(LectureOutil).count() == 0


def test_avec_le_droit_loutil_est_propose(client, faux_moduleo, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _OUTIL in _outils_proposes(mistral_client_factice)


# Fiche.


def test_fiche_dun_devis_en_noms_avec_affaire_client_dates_et_montants(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert reponse.status_code == 200
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("1 devis trouvé (texte « Bornage »), total 1 200,00 € HT, 1 440,00 € TTC.")
    fiche = contenu.split("\n\n", 1)[1]
    assert fiche == (
        "Devis D-2026-042\n"
        "Objet : Bornage du lot B\n"
        "Affaire : 2024-123\n"
        "Client : Étude Dupont\n"
        "Date de création : 10/09/2026\n"
        "Date d'émission : 15/09/2026\n"
        "Date de réponse : 28/09/2026\n"
        "Responsable : Jean Martin\n"
        "Rédacteur : Sophie Bernard\n"
        "Montant HT : 1 200,00 €\n"
        "Montant TTC : 1 440,00 €"
    )


def test_un_devis_non_emis_le_dit(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_devis(502, "D-2026-050", "Division", MontantTotalHT=800.0, MontantTotalTTC=960.0)

    _chercher(client, mistral_client_factice, jeton_valide, {"emis": False})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["emis"] == "false"
    assert "Date d'émission : non émis" in _contenu_outil(mistral_client_factice)


# Filtres.


@pytest.mark.parametrize(
    ("arguments", "attendu"),
    [
        ({"texte": "Bornage"}, {"texte": "Bornage"}),
        ({"emis": True}, {"emis": "true"}),
        ({"date_emission_min": "2026-09-01"}, {"dateEmissionMin": "2026-09-01"}),
        ({"date_emission_max": "30/09/2026"}, {"dateEmissionMax": "2026-09-30"}),
        ({"date_reponse_min": "2026-09-20"}, {"dateReponseMin": "2026-09-20"}),
        ({"date_reponse_max": "2026-09-30"}, {"dateReponseMax": "2026-09-30"}),
        ({"responsable": "Martin"}, {"idsResponsable": "7"}),
        ({"redacteur": "Sophie Bernard"}, {"idsRedacteur": "8"}),
        ({"service": "Topographie"}, {"idsService": "3"}),
    ],
)
def test_chaque_filtre_est_transmis_les_noms_resolus_en_ids(
    client, faux_moduleo, mistral_client_factice, jeton_valide, arguments, attendu
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_service(3, "Topographie")
    faux_moduleo.ajouter_devis(503, "D-2026-060", "Autre", IdService=3, DateEmission="2026-09-20")

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    (recherche,) = _recherches(faux_moduleo)
    assert {cle: valeur for cle, valeur in recherche.items() if valeur is not None} == attendu
    assert "Devis D-20" in _contenu_outil(mistral_client_factice)


def test_filtre_par_affaire_lit_les_devis_de_laffaire(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_devis(504, "D-2026-070", "Autre affaire", DateEmission="2026-09-20")

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Devis D-2026-042" in contenu and "D-2026-070" not in contenu
    assert ("cogeo/affaire/{idAffaire}/devis", {"idAffaire": 101}) in faux_moduleo.appels
    assert _recherches(faux_moduleo) == []


def test_affaire_et_autre_filtre_se_combinent(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_devis(505, "D-2026-080", "Complément", IdAffaire=101, IdResponsable=8)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123", "responsable": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Devis D-2026-042" in contenu and "D-2026-080" not in contenu


@pytest.mark.parametrize(
    ("arguments", "debut"),
    [
        ({"affaire": "2099-999"}, "Aucune affaire Moduléo ne porte le numéro « 2099-999 »"),
        ({"responsable": "Inconnu"}, "Aucun utilisateur Moduléo ne correspond à « Inconnu »"),
        ({"service": "Lyon"}, "Aucun service Moduléo ne correspond à « Lyon »"),
        ({"date_emission_min": "hier"}, "Date « hier » illisible"),
    ],
)
def test_un_nom_non_resolu_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session, arguments, debut
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(debut)
    assert "n'invente aucun devis" in contenu
    assert _recherches(faux_moduleo) == []
    assert db_session.query(LectureOutil).count() == 0


# Période par défaut.


def test_sans_critere_les_devis_emis_ces_30_derniers_jours_periode_annoncee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_devis(506, "D-2026-001", "Ancien", DateEmission="2026-08-01", MontantTotalHT=999.0)

    _chercher(client, mistral_client_factice, jeton_valide, {"nb_max": 10})

    (recherche,) = _recherches(faux_moduleo)
    assert (recherche["emis"], recherche["dateEmissionMin"]) == ("true", "2026-09-09")
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "1 devis émis depuis le 09/09/2026 (30 derniers jours), total 1 200,00 € HT, 1 440,00 € TTC."
    )
    assert "D-2026-001" not in contenu


def test_sans_devis_recent_le_resultat_dit_la_periode(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == (
        "Aucun devis émis dans Moduléo depuis le 09/09/2026 (30 derniers jours)."
    )


def test_un_critere_donne_supprime_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"responsable": "Martin"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche.get("dateEmissionMin") is None and recherche.get("emis") is None


def test_aucun_devis_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Introuvable"})

    assert _contenu_outil(mistral_client_factice) == "Aucun devis Moduléo ne correspond à cette recherche."
    assert "cogeo/devis/multi?ids={ids}" not in faux_moduleo.routes_appelees()


# Plafond et totaux.


def _devis_de_septembre(faux_moduleo, nombre: int) -> None:
    for n in range(1, nombre + 1):
        faux_moduleo.ajouter_devis(
            1000 + n,
            f"D-2026-{n:03d}",
            "Bornage",
            DateEmission=f"2026-09-{n % 28 + 1:02d}",
            MontantTotalHT=100.0,
            MontantTotalTTC=120.0,
        )


def test_cinq_fiches_par_defaut_les_plus_recentes_avec_le_nombre_trouve(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _devis_de_septembre(faux_moduleo, 7)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "7 devis trouvés (texte « Bornage »), total 700,00 € HT, 840,00 € TTC. "
        "Les 5 plus récents affichés, précise la recherche."
    )
    assert contenu.count("Devis D-2026-") == 5
    assert "D-2026-007" in contenu and "D-2026-001" not in contenu


def test_nb_max_est_plafonne_a_dix(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _devis_de_septembre(faux_moduleo, 12)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage", "nb_max": 50})

    assert _contenu_outil(mistral_client_factice).count("Devis D-2026-") == 10


def test_totaux_calcules_sur_tout_lensemble_trouve_par_lots_de_200(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _devis_de_septembre(faux_moduleo, 250)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("250 devis trouvés (texte « Bornage »), total 25 000,00 € HT, 30 000,00 € TTC.")
    assert faux_moduleo.routes_appelees().count("cogeo/devis/multi?ids={ids}") == 2


def test_le_statut_nomme_le_domaine(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert "Consultation Moduléo : devis" in statuts(reponse)


# Lectures, garde-fous et questions couvertes.


def test_fiches_et_totaux_enregistres_dans_les_lectures(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    conversation_id = fin(reponse)["conversation"]["id"]
    references = [
        lecture.reference
        for lecture in db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).order_by(LectureOutil.id)
    ]
    assert references == ["devis (texte « Bornage »)", "devis D-2026-042"]


def test_un_montant_et_un_total_lus_restent_un_total_absent_est_retire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_devis(507, "D-2026-090", "Bornage complémentaire", MontantTotalHT=600.0)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"texte": "Bornage"},
        reponse="Le devis D-2026-042 vaut 1 200 € HT. Les deux devis totalisent 1 800 € HT.\nEn tout 4 500 € TTC.",
    )

    assert fin(reponse)["reponse"] == (
        "Le devis D-2026-042 vaut 1 200 € HT. Les deux devis totalisent 1 800 € HT.\n\n"
        "Sources : Moduléo, devis (texte « Bornage »), Moduléo, devis D-2026-042"
    )


def test_questions_couvertes_du_devis_et_des_totaux_ecrites_par_script(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    questions = {q.question: q.reponse for q in db_session.query(QuestionCouverte)}
    assert questions["Quel est le montant du devis D-2026-042 ?"] == "1 200,00 € HT, 1 440,00 € TTC"
    assert questions["Où en est le devis D-2026-042 ?"] == "Émis le 15/09/2026 ; réponse le 28/09/2026"
    assert questions["À quelle affaire se rattache le devis D-2026-042 ?"] == "2024-123, client Étude Dupont"
    assert questions["Combien de devis (texte « Bornage ») ?"] == "1"
    assert questions["Quel est le montant total des devis (texte « Bornage ») ?"] == "1 200,00 € HT, 1 440,00 € TTC"
    # Aucun appel Mistral pour les écrire : appel d'outil, réponse, titrage.
    assert len(mistral_client_factice.appels_reponse) == 3
    assert not mistral_client_factice.appels_extraction


def test_inspecteur_trace_les_routes_et_les_fiches(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    conversation_id = fin(reponse)["conversation"]["id"]
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["trouvees"] == 1
    assert any(r["route"].startswith(_RECHERCHE) for r in detail["reponse_payload"]["routes"])
