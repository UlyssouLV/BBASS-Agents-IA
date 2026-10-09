from datetime import date

import pytest

from flux_sse import fin, statuts

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit, LectureOutil, QuestionCouverte
from vm_centrale.moduleo.droits import COGEO, chemin, charger_catalogue, rattacher
from vm_centrale.outils.moduleo.temps_passes import outil as outil_temps_passes

# chercher_temps_passes_moduleo (spec 1.5.1, #191) : temps passés par
# période, collaborateur, code activité ou affaire ; totaux général, par
# collaborateur et par code activité calculés par la VM sur l'ensemble
# trouvé ; sans le droit « … des autres collaborateurs », seulement les
# temps de l'utilisateur Moduléo lié au compte. Faux Moduléo :
# tests/faux_moduleo.py.

_OUTIL = "chercher_temps_passes_moduleo"
_RECHERCHE = "cogeo/tempspasse?dateMin="
_MULTI = "cogeo/tempspasse/multi?ids={ids}"
_ADMIN = "cle-admin-de-test"
_AUTRES = chemin(
    "Temps passés et frais des temps passés",
    "Consulter les temps passés et les frais des temps passés des autres collaborateurs",
)
_PRIX_DE_VENTE = chemin(
    "Affaires, groupes et archivage", "Voir l'onglet prix de revient", "Voir le prix de vente des temps passés"
)
_PRIX_DE_REVIENT = chemin(
    "Affaires, groupes et archivage", "Voir l'onglet prix de revient", "Voir le prix de revient des temps passés"
)
_REFUS_AUTRES = (
    "Votre compte n'a pas le droit Moduléo « Consulter les temps passés et les frais des temps passés des autres "
    "collaborateurs ». Aucune lecture n'a été faite. Demandez à un compte administrateur si vous en avez besoin."
)


@pytest.fixture(autouse=True)
def _aujourdhui(monkeypatch):
    monkeypatch.setattr(outil_temps_passes, "_date_du_jour", lambda: date(2026, 10, 9))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici les temps."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Combien d'heures cette semaine ?"}, headers=_autorisation(jeton)
    )


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _outils_proposes(mistral_client_factice) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []}


def _semaine(faux_moduleo) -> None:
    # Affaire 2024-123 : Jean Martin 4 h + 2 h de relevé, Sophie Bernard
    # 1,5 h de bureau.
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(8, "Sophie", "Bernard")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")
    faux_moduleo.ajouter_code_activite(1, "Relevé terrain", "RT")
    faux_moduleo.ajouter_code_activite(2, "Bureau", "BU")
    faux_moduleo.ajouter_temps_passe(
        901,
        "2026-10-07T00:00:00+02:00",
        4.0,
        7,
        IdAffaire=101,
        IdCodeActivite=1,
        NombreKilometre=12,
        Lieu="Castries",
        Commentaire="Relevé du lot B",
        PrixVenteCollaborateur=60.0,
        PrixRevientCollaborateur=35.0,
    )
    faux_moduleo.ajouter_temps_passe(902, "2026-10-06T00:00:00+02:00", 2.0, 7, IdAffaire=101, IdCodeActivite=1)
    faux_moduleo.ajouter_temps_passe(903, "2026-10-05T00:00:00+02:00", 1.5, 8, IdAffaire=101, IdCodeActivite=2)


@pytest.fixture
def compte_restreint(db_session):
    # j.dupont dans un groupe Cogeo qui a les droits `chemins`, lié ou non
    # à l'utilisateur Moduléo 7 (Jean Martin).
    def _rattacher(*chemins: str, id_utilisateur: int | None = 7) -> None:
        charger_catalogue(db_session)
        groupe = GroupeModuleo(application=COGEO, nom="Restreint")
        db_session.add(groupe)
        db_session.flush()
        for droit in db_session.query(DroitModuleo).filter(DroitModuleo.chemin.in_(chemins)):
            db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
        rattacher(db_session, "j.dupont", "Restreint", None, id_utilisateur)
        db_session.commit()

    return _rattacher


# Schéma et proposition.


def test_le_schema_decrit_les_filtres_et_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    proprietes = schema["function"]["parameters"]["properties"]
    assert set(proprietes) == {"date_min", "date_max", "collaborateur", "code_activite", "affaire", "nb_max"}
    assert "7 derniers jours" in schema["function"]["description"]


def test_sans_le_droit_autres_et_sans_lien_loutil_nest_pas_propose(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint(id_utilisateur=None)
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    proposes = _outils_proposes(mistral_client_factice)
    assert _OUTIL not in proposes and "chercher_affaires_moduleo" in proposes


def test_sans_lien_appele_quand_meme_phrase_fixe_et_rien_nest_lu(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide, db_session
):
    compte_restreint(id_utilisateur=None)
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == _REFUS_AUTRES
    assert faux_moduleo.appels == []
    assert db_session.query(LectureOutil).count() == 0


def test_sans_le_droit_autres_avec_lien_loutil_est_propose(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint()
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _OUTIL in _outils_proposes(mistral_client_factice)


def test_avec_le_droit_autres_sans_lien_loutil_est_propose(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _OUTIL in _outils_proposes(mistral_client_factice)


# Temps du compte seulement, sans le droit « autres ».


def test_sans_le_droit_autres_seuls_les_temps_du_compte_lie(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint()
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsUtilisateurs"] == "7"
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("2 temps passés trouvés (affaire 2024-123, vos temps seulement), total 6 h.")
    assert "Sophie Bernard" not in contenu


def test_sans_le_droit_autres_un_autre_collaborateur_est_refuse_par_le_garde(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide, db_session, monkeypatch
):
    compte_restreint()
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"collaborateur": "Sophie Bernard"})

    assert _contenu_outil(mistral_client_factice) == _REFUS_AUTRES
    assert not any(route.startswith("cogeo/tempspasse") for route in faux_moduleo.routes_appelees())
    assert db_session.query(LectureOutil).count() == 0
    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    conversation_id = fin(reponse)["conversation"]["id"]
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["garde_des_droits"].startswith(f"refusé, droit manquant « {_AUTRES} »")


def test_sans_le_droit_autres_son_propre_nom_est_accepte(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint()
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"collaborateur": "Jean Martin"})

    assert _contenu_outil(mistral_client_factice).startswith(
        "2 temps passés trouvés (collaborateur Jean Martin), total 6 h."
    )


def test_un_temps_dun_autre_renvoye_par_moduleo_est_refuse_par_le_garde(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide, db_session
):
    # Un serveur qui ignorerait `idsUtilisateurs` : le garde relit
    # l'utilisateur de chaque temps passé reçu.
    compte_restreint()
    _semaine(faux_moduleo)
    faux_moduleo.ignorer_filtre_utilisateurs()

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    assert _contenu_outil(mistral_client_factice) == _REFUS_AUTRES
    assert db_session.query(LectureOutil).count() == 0


# Fiche, prix et sous-droits.


def test_fiche_dun_temps_passe_et_synthese(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123", "nb_max": 1})

    assert reponse.status_code == 200
    synthese, fiche = _contenu_outil(mistral_client_factice).split("\n\n")
    assert synthese == (
        "3 temps passés trouvés (affaire 2024-123), total 7,5 h. "
        "Par collaborateur : Jean Martin 6 h, Sophie Bernard 1,5 h. "
        "Par code activité : Relevé terrain 6 h, Bureau 1,5 h. "
        "Le plus récent affiché, précise la recherche."
    )
    assert fiche == (
        "Temps passé du 07/10/2026\n"
        "Collaborateur : Jean Martin\n"
        "Affaire : 2024-123\n"
        "Code activité : Relevé terrain\n"
        "Heures : 4 h\n"
        "Kilomètres : 12\n"
        "Lieu : Castries\n"
        "Commentaire : Relevé du lot B\n"
        "Prix de vente : 60,00 €\n"
        "Prix de revient : 35,00 €"
    )


def test_sans_les_sous_droits_les_prix_sont_remplaces_par_une_mention(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint(_AUTRES)
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Prix de vente : non autorisés pour votre compte" in contenu
    assert "Prix de revient : non autorisés pour votre compte" in contenu
    assert "60,00" not in contenu and "35,00" not in contenu


def test_un_seul_sous_droit_un_seul_prix(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint(_AUTRES, _PRIX_DE_VENTE)
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Prix de vente : 60,00 €" in contenu
    assert "Prix de revient : non autorisés pour votre compte" in contenu and "35,00" not in contenu


# Filtres.


@pytest.mark.parametrize(
    ("arguments", "attendu"),
    [
        ({"date_min": "2026-10-01"}, {"dateMin": "2026-10-01"}),
        ({"date_max": "07/10/2026"}, {"dateMax": "2026-10-07"}),
        ({"collaborateur": "Martin"}, {"idsUtilisateurs": "7"}),
        ({"code_activite": "Relevé terrain"}, {"idCodeActivite": 1}),
        ({"affaire": "2024-123"}, {"idAffaire": 101}),
    ],
)
def test_chaque_filtre_est_transmis_les_noms_resolus_en_ids(
    client, faux_moduleo, mistral_client_factice, jeton_valide, arguments, attendu
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    (recherche,) = _recherches(faux_moduleo)
    assert {cle: valeur for cle, valeur in recherche.items() if valeur is not None} == attendu
    assert "Temps passé du " in _contenu_outil(mistral_client_factice)


@pytest.mark.parametrize("nom", ["Topo drone", "topo DRONE", "TD", "drone"])
def test_un_code_activite_cree_dans_moduleo_est_reconnu(
    client, faux_moduleo, mistral_client_factice, jeton_valide, nom
):
    # Lu dans cogeo/codeactivite, jamais une liste du code.
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_code_activite(42, "Topo drone", "TD")
    faux_moduleo.ajouter_temps_passe(904, "2026-10-08", 3.0, 8, IdCodeActivite=42)

    _chercher(client, mistral_client_factice, jeton_valide, {"code_activite": nom})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idCodeActivite"] == 42
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(f"1 temps passé trouvé (code activité {nom}), total 3 h.")
    assert "Code activité : Topo drone" in contenu


@pytest.mark.parametrize(
    ("arguments", "debut"),
    [
        ({"affaire": "2099-999"}, "Aucune affaire Moduléo ne porte le numéro « 2099-999 »"),
        ({"collaborateur": "Inconnu"}, "Aucun utilisateur Moduléo ne correspond à « Inconnu »"),
        ({"code_activite": "Plongée"}, "Aucun code activité Moduléo ne correspond à « Plongée »"),
        ({"code_activite": "r"}, "Plusieurs codes activité Moduléo correspondent à « r » : Bureau, Relevé terrain."),
        ({"date_min": "lundi"}, "Date « lundi » illisible"),
    ],
)
def test_un_nom_non_resolu_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session, arguments, debut
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(debut)
    assert "n'invente aucun temps passé" in contenu
    assert _recherches(faux_moduleo) == []
    assert db_session.query(LectureOutil).count() == 0


# Période par défaut.


def test_sans_critere_les_7_derniers_jours_periode_annoncee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _semaine(faux_moduleo)
    faux_moduleo.ajouter_temps_passe(905, "2026-09-20", 8.0, 7)

    _chercher(client, mistral_client_factice, jeton_valide, {"nb_max": 10})

    (recherche,) = _recherches(faux_moduleo)
    assert (recherche["dateMin"], recherche["dateMax"]) == ("2026-10-02", "2026-10-09")
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("3 temps passés saisis du 02/10/2026 au 09/10/2026 (7 derniers jours), total 7,5 h.")
    assert "20/09/2026" not in contenu


def test_sans_critere_et_sans_le_droit_autres_la_periode_et_la_portee_sont_annoncees(
    client, faux_moduleo, compte_restreint, mistral_client_factice, jeton_valide
):
    compte_restreint()
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice).startswith(
        "2 temps passés saisis du 02/10/2026 au 09/10/2026 (7 derniers jours, vos temps seulement), total 6 h."
    )


def test_sans_temps_recent_le_resultat_dit_la_periode(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == (
        "Aucun temps passé saisi dans Moduléo du 02/10/2026 au 09/10/2026 (7 derniers jours)."
    )


def test_un_critere_donne_supprime_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche.get("dateMin") is None and recherche.get("dateMax") is None


def test_aucun_temps_passe_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-12-01"})

    assert _contenu_outil(mistral_client_factice) == "Aucun temps passé Moduléo ne correspond à cette recherche."
    assert _MULTI not in faux_moduleo.routes_appelees()


# Plafond et totaux.


def _temps_de_septembre(faux_moduleo, nombre: int) -> None:
    # 1,5 h chacun, en alternance Jean Martin / Sophie Bernard.
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(8, "Sophie", "Bernard")
    for n in range(1, nombre + 1):
        faux_moduleo.ajouter_temps_passe(2000 + n, f"2026-09-{n % 28 + 1:02d}", 1.5, 7 if n % 2 else 8)


def test_cinq_lignes_par_defaut_les_plus_recentes(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _temps_de_septembre(faux_moduleo, 7)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-09-01"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "7 temps passés trouvés (depuis le 01/09/2026), total 10,5 h. "
        "Par collaborateur : Jean Martin 6 h, Sophie Bernard 4,5 h. "
        "Par code activité : sans code activité 10,5 h. "
        "Les 5 plus récents affichés, précise la recherche."
    )
    assert contenu.count("Temps passé du ") == 5
    assert "Temps passé du 08/09/2026" in contenu and "Temps passé du 02/09/2026" not in contenu


def test_le_detail_est_plafonne_a_dix_lignes(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _temps_de_septembre(faux_moduleo, 12)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-09-01", "nb_max": 50})

    assert _contenu_outil(mistral_client_factice).count("Temps passé du ") == 10


def test_totaux_calcules_sur_tout_lensemble_trouve_par_lots_de_200(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _temps_de_septembre(faux_moduleo, 250)

    _chercher(client, mistral_client_factice, jeton_valide, {"date_min": "2026-09-01"})

    assert _contenu_outil(mistral_client_factice).startswith(
        "250 temps passés trouvés (depuis le 01/09/2026), total 375 h. "
        "Par collaborateur : Jean Martin 187,5 h, Sophie Bernard 187,5 h."
    )
    assert faux_moduleo.routes_appelees().count(_MULTI) == 2


def test_le_statut_nomme_le_domaine(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    assert "Consultation Moduléo : temps passés" in statuts(reponse)


# Lectures, garde-fous et questions couvertes.


def test_fiches_et_totaux_enregistres_dans_les_lectures(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123", "nb_max": 2})

    conversation_id = fin(reponse)["conversation"]["id"]
    references = [
        lecture.reference
        for lecture in db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).order_by(LectureOutil.id)
    ]
    assert references == [
        "temps passés (affaire 2024-123)",
        "temps passé du 07/10/2026, Jean Martin, affaire 2024-123",
        "temps passé du 06/10/2026, Jean Martin, affaire 2024-123",
    ]


def test_un_total_lu_reste_un_total_absent_est_retire(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _semaine(faux_moduleo)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"affaire": "2024-123", "nb_max": 1},
        reponse="7,5 heures ont été passées sur l'affaire 2024-123, dont 6 h par Jean Martin.\nSoit 13 heures facturables.",
    )

    assert fin(reponse)["reponse"] == (
        "7,5 heures ont été passées sur l'affaire 2024-123, dont 6 h par Jean Martin.\n\n"
        "Sources : Moduléo, temps passés (affaire 2024-123), "
        "Moduléo, temps passé du 07/10/2026, Jean Martin, affaire 2024-123"
    )


def test_questions_couvertes_ecrites_par_script(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _semaine(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123", "nb_max": 1})

    questions = {q.question: q.reponse for q in db_session.query(QuestionCouverte)}
    assert questions["Combien d'heures dans les temps passés (affaire 2024-123) ?"] == "7,5 h"
    assert questions["Combien d'heures par collaborateur dans les temps passés (affaire 2024-123) ?"] == (
        "Jean Martin 6 h, Sophie Bernard 1,5 h"
    )
    assert questions["Combien d'heures par code activité dans les temps passés (affaire 2024-123) ?"] == (
        "Relevé terrain 6 h, Bureau 1,5 h"
    )
    reference = "temps passé du 07/10/2026, Jean Martin, affaire 2024-123"
    assert questions[f"Combien d'heures pour le {reference} ?"] == "4 h"
    assert questions[f"Quel code activité pour le {reference} ?"] == "Relevé terrain"
    # Aucun appel Mistral pour les écrire : appel d'outil, réponse, titrage.
    assert len(mistral_client_factice.appels_reponse) == 3
    assert not mistral_client_factice.appels_extraction


def test_inspecteur_trace_les_routes_et_la_synthese(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    _semaine(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    conversation_id = fin(reponse)["conversation"]["id"]
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["trouvees"] == 3
    assert detail["reponse_payload"]["synthese"].startswith("3 temps passés trouvés")
    assert any(r["route"].startswith(_RECHERCHE) for r in detail["reponse_payload"]["routes"])
