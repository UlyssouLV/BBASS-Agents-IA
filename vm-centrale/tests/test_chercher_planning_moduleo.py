from datetime import date

import pytest

from flux_sse import fin, statuts

from vm_centrale.models import LectureOutil, QuestionCouverte
from vm_centrale.moduleo.droits import GROUPE_DEV, rattacher
from vm_centrale.outils.moduleo.planning import outil as outil_planning

# chercher_planning_moduleo (spec 1.5.1, #192) : tâches du planning par
# collaborateur (participant), période, activité (lue dans Moduléo) ou
# mot-clé du libellé ; sans critère, aujourd'hui + 7 jours, période
# annoncée. Aucun droit de consultation : un groupe Planning suffit.
# Faux Moduléo : tests/faux_moduleo.py.

_OUTIL = "chercher_planning_moduleo"
_RECHERCHE = "planning/tacheplanning?libelle="
_MULTI = "planning/tacheplanning/multi?ids={ids}"
_ADMIN = "cle-admin-de-test"
_SANS_GROUPE_PLANNING = "Votre compte n'est rattaché à aucun groupe Moduléo Planning."


@pytest.fixture(autouse=True)
def _aujourdhui(monkeypatch):
    monkeypatch.setattr(outil_planning, "_date_du_jour", lambda: date(2026, 10, 9))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici le planning."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Qui est sur le terrain cette semaine ?"}, headers=_autorisation(jeton)
    )


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _outils_proposes(mistral_client_factice) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []}


def _rattacher(db_session, groupe_cogeo: str | None, groupe_planning: str | None) -> None:
    rattacher(db_session, "j.dupont", groupe_cogeo, groupe_planning, None)
    db_session.commit()


def _semaine(faux_moduleo) -> None:
    # Jean Martin (planning 70) et Sophie Bernard (planning 80) : bornage
    # du lot B lundi matin avec le GPS, bureau mardi pour Sophie seule.
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(8, "Sophie", "Bernard")
    faux_moduleo.ajouter_utilisateur_planning(70, 7)
    faux_moduleo.ajouter_utilisateur_planning(80, 8)
    faux_moduleo.ajouter_activite(1, "Terrain")
    faux_moduleo.ajouter_activite(2, "Bureau")
    faux_moduleo.ajouter_equipement(5, "GPS Trimble R10")
    faux_moduleo.ajouter_equipement(6, "Station totale")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")
    faux_moduleo.ajouter_tache(
        501,
        "Bornage lot B",
        "2026-10-12T08:00:00+02:00",
        "2026-10-12T12:00:00+02:00",
        Participants=[70, 80],
        Equipements=[5, 6],
        IdActivite=1,
        IdAffaire=101,
        Emplacement="Castries",
    )
    faux_moduleo.ajouter_tache(
        502,
        "Calculs lot B",
        "2026-10-13T09:00:00+02:00",
        "2026-10-13T17:30:00+02:00",
        Participants=[80],
        IdActivite=2,
    )


# Schéma et proposition.


def test_le_schema_decrit_les_filtres_et_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    proprietes = schema["function"]["parameters"]["properties"]
    assert set(proprietes) == {"date_min", "date_max", "collaborateur", "activite", "mot_cle", "nb_max"}
    assert "aujourd'hui et les 7 jours suivants" in schema["function"]["description"]


def test_sans_groupe_planning_loutil_nest_pas_propose(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _rattacher(db_session, GROUPE_DEV, None)
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    proposes = _outils_proposes(mistral_client_factice)
    assert _OUTIL not in proposes and "chercher_affaires_moduleo" in proposes


def test_sans_groupe_planning_appele_quand_meme_phrase_fixe_et_rien_nest_lu(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    _rattacher(db_session, GROUPE_DEV, None)
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"collaborateur": "Jean Martin"})

    assert _contenu_outil(mistral_client_factice).startswith(_SANS_GROUPE_PLANNING)
    assert faux_moduleo.appels == []
    assert db_session.query(LectureOutil).count() == 0
    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    conversation_id = fin(reponse)["conversation"]["id"]
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["garde_des_droits"] == "refusé, groupe Planning manquant"


def test_un_groupe_planning_seul_suffit(client, faux_moduleo, mistral_client_factice, jeton_valide, db_session):
    # Aucun droit de consultation dans Moduléo pour le planning ; sans
    # groupe Cogeo, l'affaire liée n'est pas lue.
    _rattacher(db_session, None, GROUPE_DEV)
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    moduleo = {nom for nom in _outils_proposes(mistral_client_factice) if nom.endswith("_moduleo")}
    assert moduleo == {_OUTIL}


def test_sans_groupe_cogeo_laffaire_liee_est_remplacee_par_une_mention(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _rattacher(db_session, None, GROUPE_DEV)
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"mot_cle": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire : non autorisée pour votre compte" in contenu
    assert "2024-123" not in contenu
    assert not any(route.startswith("cogeo/") for route in faux_moduleo.routes_appelees())


# Fiche et synthèse.


def test_fiche_dune_tache_et_synthese(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"mot_cle": "lot B", "nb_max": 1})

    assert reponse.status_code == 200
    synthese, fiche = _contenu_outil(mistral_client_factice).split("\n\n")
    assert synthese == (
        "2 tâches trouvées au planning (mot-clé lot B). "
        "Participants : Sophie Bernard (2 tâches), Jean Martin (1 tâche). "
        "La première affichée, précise la recherche."
    )
    assert fiche == (
        "Tâche « Bornage lot B »\n"
        "Date : 12/10/2026, 08:00 – 12:00\n"
        "Participants : Jean Martin, Sophie Bernard\n"
        "Activité : Terrain\n"
        "Matériel : GPS Trimble R10, Station totale\n"
        "Affaire : 2024-123\n"
        "Lieu : Castries"
    )


def test_une_tache_sur_plusieurs_jours(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_tache(
        503, "Chantier A9", "2026-10-14T08:00:00+02:00", "2026-10-15T17:00:00+02:00", Participants=[70]
    )

    _chercher(client, mistral_client_factice, jeton_valide, {"mot_cle": "Chantier"})

    assert "Date : du 14/10/2026 08:00 au 15/10/2026 17:00" in _contenu_outil(mistral_client_factice)


# Filtres.


@pytest.mark.parametrize(
    ("arguments", "attendu"),
    [
        ({"date_min": "2026-10-13"}, {"dateDebut": "2026-10-13"}),
        ({"date_max": "12/10/2026"}, {"dateFin": "2026-10-12"}),
        ({"collaborateur": "Martin"}, {"idsParticipants": "70"}),
        ({"activite": "Terrain"}, {"idActivite": 1}),
        ({"mot_cle": "Bornage"}, {"libelle": "Bornage"}),
    ],
)
def test_chaque_filtre_est_transmis_les_noms_resolus_en_ids(
    client, faux_moduleo, mistral_client_factice, jeton_valide, arguments, attendu
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    (recherche,) = _recherches(faux_moduleo)
    assert {
        cle: valeur
        for cle, valeur in recherche.items()
        if valeur is not None and cle != "recupererTachesSupprimees"
    } == attendu
    assert recherche["recupererTachesSupprimees"] == "false"
    assert "Tâche « " in _contenu_outil(mistral_client_factice)


@pytest.mark.parametrize("nom", ["Topo drone", "topo DRONE", "drone"])
def test_une_activite_creee_dans_moduleo_est_reconnue(
    client, faux_moduleo, mistral_client_factice, jeton_valide, nom
):
    # Lue dans planning/activite, jamais une liste du code.
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_activite(42, "Topo drone")
    faux_moduleo.ajouter_tache(
        504, "Vol Castries", "2026-10-15T10:00:00+02:00", "2026-10-15T11:00:00+02:00", IdActivite=42
    )

    _chercher(client, mistral_client_factice, jeton_valide, {"activite": nom})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idActivite"] == 42
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(f"1 tâche trouvée au planning (activité {nom}).")
    assert "Activité : Topo drone" in contenu


@pytest.mark.parametrize(
    ("arguments", "debut"),
    [
        ({"collaborateur": "Inconnu"}, "Aucun utilisateur Moduléo ne correspond à « Inconnu »"),
        ({"collaborateur": "Paul Durand"}, "Paul Durand n'est pas au planning Moduléo"),
        ({"activite": "Plongée"}, "Aucune activité Moduléo ne correspond à « Plongée »"),
        ({"activite": "e"}, "Plusieurs activités Moduléo correspondent à « e » : Bureau, Terrain."),
        ({"date_min": "lundi"}, "Date « lundi » illisible"),
    ],
)
def test_un_nom_non_resolu_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session, arguments, debut
):
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_utilisateur(9, "Paul", "Durand")

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(debut)
    assert "n'invente aucune tâche" in contenu
    assert _recherches(faux_moduleo) == []
    assert db_session.query(LectureOutil).count() == 0


# Période par défaut.


def test_sans_critere_aujourdhui_et_7_jours_periode_annoncee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_tache(505, "Réunion", "2026-10-30T09:00:00+01:00", "2026-10-30T10:00:00+01:00")

    _chercher(client, mistral_client_factice, jeton_valide, {})

    (recherche,) = _recherches(faux_moduleo)
    assert (recherche["dateDebut"], recherche["dateFin"]) == ("2026-10-09", "2026-10-16")
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "2 tâches au planning du 09/10/2026 au 16/10/2026 (aujourd'hui et les 7 jours suivants)."
    )
    assert "Réunion" not in contenu


def test_sans_tache_le_resultat_dit_la_periode(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == (
        "Aucune tâche au planning Moduléo du 09/10/2026 au 16/10/2026 (aujourd'hui et les 7 jours suivants)."
    )


def test_un_critere_donne_supprime_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"collaborateur": "Sophie Bernard"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche.get("dateDebut") is None and recherche.get("dateFin") is None


def test_aucune_tache_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"mot_cle": "Piscine"})

    assert _contenu_outil(mistral_client_factice) == "Aucune tâche du planning Moduléo ne correspond à cette recherche."
    assert _MULTI not in faux_moduleo.routes_appelees()


# Plafond.


def _taches_de_novembre(faux_moduleo, nombre: int) -> None:
    for n in range(1, nombre + 1):
        jour = f"2026-11-{n % 28 + 1:02d}"
        faux_moduleo.ajouter_tache(3000 + n, f"Tâche {n}", f"{jour}T08:00:00+01:00", f"{jour}T09:00:00+01:00")


def test_cinq_taches_par_defaut_les_premieres(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _taches_de_novembre(faux_moduleo, 7)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-11-01"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "7 tâches trouvées au planning (depuis le 01/11/2026). Les 5 premières affichées, précise la recherche."
    )
    assert contenu.count("Tâche « ") == 5
    assert "Date : 02/11/2026" in contenu and "Date : 08/11/2026" not in contenu


def test_le_detail_est_plafonne_a_dix_taches(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _taches_de_novembre(faux_moduleo, 12)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-11-01", "nb_max": 50})

    assert _contenu_outil(mistral_client_factice).count("Tâche « ") == 10


def test_le_statut_nomme_le_domaine(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {})

    assert "Consultation Moduléo : planning" in statuts(reponse)


# Lectures, garde-fous et questions couvertes.


def test_synthese_et_fiches_enregistrees_dans_les_lectures(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {})

    conversation_id = fin(reponse)["conversation"]["id"]
    references = [
        lecture.reference
        for lecture in db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).order_by(LectureOutil.id)
    ]
    assert references == [
        "planning du 09/10/2026 au 16/10/2026",
        "tâche « Bornage lot B » du 12/10/2026",
        "tâche « Calculs lot B » du 13/10/2026",
    ]


def test_une_heure_lue_reste_une_heure_absente_est_retiree(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _semaine(faux_moduleo)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"mot_cle": "Bornage"},
        reponse="Jean Martin borne le lot B le 12/10/2026 de 08:00 à 12:00.\nIl rentre à 19:45.",
    )

    assert fin(reponse)["reponse"] == (
        "Jean Martin borne le lot B le 12/10/2026 de 08:00 à 12:00.\n\n"
        "Sources : Moduléo, tâche « Bornage lot B » du 12/10/2026"
    )


def test_questions_couvertes_ecrites_par_script(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {})

    questions = {q.question: q.reponse for q in db_session.query(QuestionCouverte)}
    assert questions["Combien de tâches au planning du 09/10/2026 au 16/10/2026 ?"] == "2"
    assert questions["Qui est au planning du 09/10/2026 au 16/10/2026 ?"] == (
        "Sophie Bernard (2 tâches), Jean Martin (1 tâche)"
    )
    reference = "tâche « Bornage lot B » du 12/10/2026"
    assert questions[f"Quand a lieu la {reference} ?"] == "12/10/2026, 08:00 – 12:00"
    assert questions[f"Qui participe à la {reference} ?"] == "Jean Martin, Sophie Bernard"
    assert questions[f"Quelle activité pour la {reference} ?"] == "Terrain"
    assert questions[f"Quel matériel pour la {reference} ?"] == "GPS Trimble R10, Station totale"
    assert questions[f"Quelle affaire pour la {reference} ?"] == "2024-123"
    # Aucun appel Mistral pour les écrire : appel d'outil, réponse, titrage.
    assert len(mistral_client_factice.appels_reponse) == 3
    assert not mistral_client_factice.appels_extraction


def test_inspecteur_trace_les_routes_et_la_synthese(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {})

    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    conversation_id = fin(reponse)["conversation"]["id"]
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["trouvees"] == 2
    assert detail["reponse_payload"]["synthese"].startswith("2 tâches au planning du 09/10/2026")
    assert any(r["route"].startswith(_RECHERCHE) for r in detail["reponse_payload"]["routes"])
