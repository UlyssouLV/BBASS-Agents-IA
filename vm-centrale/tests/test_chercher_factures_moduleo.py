from datetime import date

import pytest

from flux_sse import fin, statuts

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit, LectureOutil, QuestionCouverte
from vm_centrale.moduleo.droits import COGEO, chemin, charger_catalogue, rattacher
from vm_centrale.outils.moduleo.factures import outil as outil_factures

# chercher_factures_moduleo (spec 1.5.1, #190) : factures par texte,
# émission, dates, service, responsable, rédacteur ou affaire ; échéances,
# règlements et reste à payer quand Moduléo permet de le déduire ; totaux
# calculés par la VM sur l'ensemble trouvé, avec un faux Moduléo
# (tests/faux_moduleo.py).

_OUTIL = "chercher_factures_moduleo"
_RECHERCHE = "cogeo/facture?texte="
_ADMIN = "cle-admin-de-test"
_REFUS = (
    "Votre compte n'a pas le droit Moduléo « Consulter les factures et les avoirs ». Aucune lecture n'a été "
    "faite. Demandez à un compte administrateur si vous en avez besoin."
)


@pytest.fixture(autouse=True)
def _aujourdhui(monkeypatch):
    monkeypatch.setattr(outil_factures, "_date_du_jour", lambda: date(2026, 10, 9))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici les factures."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Où en sont les factures ?"}, headers=_autorisation(jeton)
    )


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _outils_proposes(mistral_client_factice) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []}


def _bornage(faux_moduleo, **champs) -> None:
    # Facture F-2026-118 : 1 440 € TTC, un acompte de 600 € réglé sur sa
    # première échéance.
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(8, "Sophie", "Bernard")
    faux_moduleo.ajouter_contact(30, "Étude Dupont")
    faux_moduleo.ajouter_contact(31, "SCI Les Pins")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B", IdClient=30)
    faux_moduleo.ajouter_destinataire(60, 31)
    faux_moduleo.ajouter_echeance(70, 600.0, "2026-09-30T00:00:00+02:00", IdFacture=601, IdReglement=80)
    faux_moduleo.ajouter_reglement(80, 600.0, "2026-09-25T00:00:00+02:00", Mode="Virement", IdEcheance=70)
    facture = {
        "IdAffaire": 101,
        "IdDestinataire": 60,
        "IdResponsable": 7,
        "IdRedacteur": 8,
        "IdsReglements": [80],
        "DateCreation": "2026-09-10T00:00:00+02:00",
        "DateEmission": "2026-09-15T00:00:00+02:00",
        "MontantTotalHT": 1200.0,
        "MontantTotalTVA": 240.0,
        "MontantTotalTTC": 1440.0,
    }
    faux_moduleo.ajouter_facture(601, "F-2026-118", "Bornage du lot B", **{**facture, **champs})


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
        "emise",
        "date_emission_min",
        "date_emission_max",
        "service",
        "responsable",
        "redacteur",
        "affaire",
        "nb_max",
    }
    assert proprietes["emise"]["type"] == "boolean"
    assert "30 derniers jours" in schema["function"]["description"]


@pytest.fixture
def compte_sans_factures(db_session):
    # j.dupont dans un groupe Cogeo qui a « Consulter les devis », pas les
    # factures.
    charger_catalogue(db_session)
    groupe = GroupeModuleo(application=COGEO, nom="Sans factures")
    db_session.add(groupe)
    db_session.flush()
    droit = db_session.query(DroitModuleo).filter_by(chemin=chemin("Devis, factures et avoirs", "Consulter les devis")).one()
    db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
    rattacher(db_session, "j.dupont", "Sans factures", None, None)
    db_session.commit()


def test_sans_le_droit_loutil_nest_pas_propose(
    client, faux_moduleo, compte_sans_factures, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    proposes = _outils_proposes(mistral_client_factice)
    assert _OUTIL not in proposes and "chercher_devis_moduleo" in proposes


def test_appele_sans_le_droit_phrase_fixe_et_rien_nest_lu(
    client, faux_moduleo, compte_sans_factures, mistral_client_factice, jeton_valide, db_session
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


# Fiche, échéances, règlements et reste à payer.


def test_fiche_dune_facture_avec_echeances_reglements_et_reste_a_payer(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert reponse.status_code == 200
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "1 facture trouvée (texte « Bornage »), total 1 200,00 € HT, 1 440,00 € TTC, reste à payer 840,00 €."
    )
    fiche = contenu.split("\n\n", 1)[1]
    assert fiche == (
        "Facture F-2026-118\n"
        "Objet : Bornage du lot B\n"
        "Affaire : 2024-123\n"
        "Client : SCI Les Pins\n"
        "Date de création : 10/09/2026\n"
        "Date d'émission : 15/09/2026\n"
        "Responsable : Jean Martin\n"
        "Rédacteur : Sophie Bernard\n"
        "Montant HT : 1 200,00 €\n"
        "Montant TTC : 1 440,00 €\n"
        "Échéances et règlements :\n"
        "- Règlement du 25/09/2026 : 600,00 € TTC (Virement), échéance du 30/09/2026 de 600,00 €\n"
        "Reste à payer : 840,00 €"
    )


def test_sans_destinataire_le_client_est_celui_de_laffaire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo, IdDestinataire=None)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert "Client : Étude Dupont" in _contenu_outil(mistral_client_factice)


def test_une_facture_sans_reglement_reste_due_en_entier(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo, IdsReglements=[])

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Échéances et règlements : aucun règlement" in contenu
    assert "Reste à payer : 1 440,00 €" in contenu


def test_une_facture_reglee_en_totalite(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo, IdsReglements=[80, 81])
    faux_moduleo.ajouter_reglement(81, 840.0, "2026-10-02", Mode="Chèque")

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "- Règlement du 02/10/2026 : 840,00 € TTC (Chèque)\n" in contenu
    assert "Reste à payer : 0,00 €" in contenu


@pytest.mark.parametrize(
    "cas",
    ["reglement_illisible", "avoir", "penalites", "non_emise"],
)
def test_reste_a_payer_jamais_estime_quand_moduleo_ne_permet_pas_de_le_deduire(
    client, faux_moduleo, mistral_client_factice, jeton_valide, cas
):
    if cas == "reglement_illisible":
        _bornage(faux_moduleo, IdsReglements=[80, 99])
    elif cas == "avoir":
        _bornage(faux_moduleo)
        faux_moduleo.ajouter_avoir(90, 601)
    elif cas == "penalites":
        _bornage(faux_moduleo)
        faux_moduleo.ajouter_reglement(80, 600.0, "2026-09-25", MontantReglementPenalitesTTC=40.0)
    else:
        _bornage(faux_moduleo, DateEmission=None, IdsReglements=[])

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Reste à payer" not in contenu and "reste à payer 840" not in contenu
    assert "840,00" not in contenu


def test_une_facture_non_emise_le_dit(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_facture(602, "F-2026-130", "Division", MontantTotalHT=800.0, MontantTotalTTC=960.0)

    _chercher(client, mistral_client_factice, jeton_valide, {"emise": False})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["emise"] == "false"
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("1 facture trouvée (non émise), total 800,00 € HT, 960,00 € TTC.")
    assert "Date d'émission : non émise" in contenu


# Filtres.


@pytest.mark.parametrize(
    ("arguments", "attendu"),
    [
        ({"texte": "Bornage"}, {"texte": "Bornage"}),
        ({"emise": True}, {"emise": "true"}),
        ({"date_emission_min": "2026-09-01"}, {"dateEmissionMin": "2026-09-01"}),
        ({"date_emission_max": "30/09/2026"}, {"dateEmissionMax": "2026-09-30"}),
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
    faux_moduleo.ajouter_facture(603, "F-2026-140", "Autre", IdService=3, DateEmission="2026-09-20")

    _chercher(client, mistral_client_factice, jeton_valide, arguments)

    (recherche,) = _recherches(faux_moduleo)
    assert {cle: valeur for cle, valeur in recherche.items() if valeur is not None} == attendu
    assert "Facture F-20" in _contenu_outil(mistral_client_factice)


def test_filtre_par_affaire_lit_les_factures_de_laffaire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_facture(604, "F-2026-150", "Autre affaire", DateEmission="2026-09-20")

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Facture F-2026-118" in contenu and "F-2026-150" not in contenu
    assert contenu.startswith("1 facture trouvée (affaire 2024-123)")
    assert ("cogeo/affaire/{idAffaire}/factures", {"idAffaire": 101}) in faux_moduleo.appels
    assert _recherches(faux_moduleo) == []


def test_affaire_et_autre_filtre_se_combinent(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_facture(605, "F-2026-160", "Complément", IdAffaire=101, IdResponsable=8)

    _chercher(client, mistral_client_factice, jeton_valide, {"affaire": "2024-123", "responsable": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Facture F-2026-118" in contenu and "F-2026-160" not in contenu


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
    assert "n'invente aucune facture" in contenu
    assert _recherches(faux_moduleo) == []
    assert db_session.query(LectureOutil).count() == 0


# Période par défaut.


def test_sans_critere_les_factures_emises_ces_30_derniers_jours_periode_annoncee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_facture(606, "F-2026-001", "Ancienne", DateEmission="2026-08-01", MontantTotalHT=999.0)

    _chercher(client, mistral_client_factice, jeton_valide, {"nb_max": 10})

    (recherche,) = _recherches(faux_moduleo)
    assert (recherche["emise"], recherche["dateEmissionMin"]) == ("true", "2026-09-09")
    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "1 facture émise depuis le 09/09/2026 (30 derniers jours), "
        "total 1 200,00 € HT, 1 440,00 € TTC, reste à payer 840,00 €."
    )
    assert "F-2026-001" not in contenu


def test_sans_facture_recente_le_resultat_dit_la_periode(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {})

    assert _contenu_outil(mistral_client_factice) == (
        "Aucune facture émise dans Moduléo depuis le 09/09/2026 (30 derniers jours)."
    )


def test_un_critere_donne_supprime_la_periode_par_defaut(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"responsable": "Martin"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche.get("dateEmissionMin") is None and recherche.get("emise") is None


def test_aucune_facture_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Introuvable"})

    assert _contenu_outil(mistral_client_factice) == "Aucune facture Moduléo ne correspond à cette recherche."
    assert "cogeo/facture/multi?ids={ids}" not in faux_moduleo.routes_appelees()


# Plafond et totaux.


def _factures_de_septembre(faux_moduleo, nombre: int, emises: bool = True) -> None:
    # 100 € HT, 120 € TTC chacune, 20 € réglés sur chaque facture émise.
    for n in range(1, nombre + 1):
        faux_moduleo.ajouter_reglement(5000 + n, 20.0, "2026-09-28")
        faux_moduleo.ajouter_facture(
            1000 + n,
            f"F-2026-{n:03d}",
            "Bornage",
            DateEmission=f"2026-09-{n % 28 + 1:02d}" if emises else None,
            DateCreation=f"2026-09-{n % 28 + 1:02d}",
            IdsReglements=[5000 + n] if emises else [],
            MontantTotalHT=100.0,
            MontantTotalTTC=120.0,
        )


def test_cinq_fiches_par_defaut_les_plus_recentes_avec_le_nombre_trouve(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _factures_de_septembre(faux_moduleo, 7)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "7 factures trouvées (texte « Bornage »), total 700,00 € HT, 840,00 € TTC, reste à payer 700,00 €. "
        "Les 5 plus récentes affichées, précise la recherche."
    )
    assert contenu.count("Facture F-2026-") == 5
    assert "F-2026-007" in contenu and "F-2026-001" not in contenu


def test_nb_max_est_plafonne_a_dix(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _factures_de_septembre(faux_moduleo, 12)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage", "nb_max": 50})

    assert _contenu_outil(mistral_client_factice).count("Facture F-2026-") == 10


def test_le_reste_a_payer_total_porte_sur_les_factures_emises(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_facture(607, "F-2026-170", "Bornage", MontantTotalHT=100.0, MontantTotalTTC=120.0)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert _contenu_outil(mistral_client_factice).startswith(
        "2 factures trouvées (texte « Bornage »), total 1 300,00 € HT, 1 560,00 € TTC, "
        "reste à payer sur les émises 840,00 €."
    )


def test_un_reste_a_payer_non_deductible_retire_le_total_du_reste(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    _factures_de_septembre(faux_moduleo, 2)
    faux_moduleo.ajouter_avoir(91, 1001)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "3 factures trouvées (texte « Bornage »), total 1 400,00 € HT, 1 680,00 € TTC, "
        "reste à payer non calculé (avoir ou règlement à vérifier dans Moduléo)."
    )


def test_totaux_calcules_sur_tout_lensemble_trouve_par_lots_de_200(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _factures_de_septembre(faux_moduleo, 250, emises=False)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("250 factures trouvées (texte « Bornage »), total 25 000,00 € HT, 30 000,00 € TTC.")
    assert faux_moduleo.routes_appelees().count("cogeo/facture/multi?ids={ids}") == 2


def test_au_dela_de_50_factures_emises_le_reste_a_payer_total_nest_pas_calcule(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _factures_de_septembre(faux_moduleo, 51)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith(
        "51 factures trouvées (texte « Bornage »), total 5 100,00 € HT, 6 120,00 € TTC, "
        "reste à payer non calculé au-delà de 50 factures émises."
    )
    # Les règlements des seules fiches affichées.
    assert faux_moduleo.routes_appelees().count("cogeo/reglement/{idReglement}") == 5
    assert "Reste à payer : 100,00 €" in contenu


def test_le_statut_nomme_le_domaine(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _bornage(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    assert "Consultation Moduléo : factures" in statuts(reponse)


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
    assert references == ["factures (texte « Bornage »)", "facture F-2026-118"]


def test_un_reste_et_un_total_lus_restent_un_total_absent_est_retire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _bornage(faux_moduleo)
    faux_moduleo.ajouter_facture(607, "F-2026-170", "Bornage", MontantTotalHT=100.0, MontantTotalTTC=120.0)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"texte": "Bornage"},
        reponse=(
            "La facture F-2026-118 reste due pour 840 €. Les deux factures totalisent 1 560 € TTC.\n"
            "Soit 2 280 € en tout."
        ),
    )

    assert fin(reponse)["reponse"] == (
        "La facture F-2026-118 reste due pour 840 €. Les deux factures totalisent 1 560 € TTC.\n\n"
        "Sources : Moduléo, factures (texte « Bornage »), Moduléo, facture F-2026-118"
    )


def test_questions_couvertes_de_la_facture_et_des_totaux_ecrites_par_script(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _bornage(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Bornage"})

    questions = {q.question: q.reponse for q in db_session.query(QuestionCouverte)}
    assert questions["Quel est le montant de la facture F-2026-118 ?"] == "1 200,00 € HT, 1 440,00 € TTC"
    assert questions["La facture F-2026-118 est-elle payée ?"] == (
        "Émise le 15/09/2026 ; réglé 600,00 € TTC ; reste à payer 840,00 €"
    )
    assert questions["À quelle affaire se rattache la facture F-2026-118 ?"] == "2024-123, client SCI Les Pins"
    assert questions["Combien de factures (texte « Bornage ») ?"] == "1"
    assert questions["Quel est le montant total des factures (texte « Bornage ») ?"] == (
        "1 200,00 € HT, 1 440,00 € TTC"
    )
    assert questions["Quel est le reste à payer des factures (texte « Bornage ») ?"] == "840,00 €"
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
    assert detail["reponse_payload"]["synthese"].startswith("1 facture trouvée")
    assert any(r["route"].startswith(_RECHERCHE) for r in detail["reponse_payload"]["routes"])
