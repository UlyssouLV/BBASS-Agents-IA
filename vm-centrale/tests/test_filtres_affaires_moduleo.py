import pytest

# Filtres de chercher_affaires_moduleo (spec 1.5.0, #175) : le modèle donne
# des noms (personne, site, service, dossier de production), la VM les
# résout en ids avant cogeo/affaire?… ; faux Moduléo (tests/faux_moduleo.py).

_OUTIL = "chercher_affaires_moduleo"
_RECHERCHE = "cogeo/affaire?texte="
_FILTRES = (
    "etat",
    "date_creation_min",
    "date_creation_max",
    "date_ouverture_min",
    "date_ouverture_max",
    "date_livraison_min",
    "date_livraison_max",
    "date_cloture_min",
    "date_cloture_max",
    "site",
    "service",
    "responsable",
    "charge_affaire",
    "suivi_par",
    "dossier_production",
)


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre("Voici les affaires.", "Titre")
    return client.post(
        "/conversations", json={"message": "Quelles affaires suit Martin ?"}, headers=_autorisation(jeton)
    )


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _equipe(faux_moduleo) -> None:
    faux_moduleo.ajouter_utilisateur(1, "Jean", "Martin")
    faux_moduleo.ajouter_utilisateur(2, "Sophie", "Bernard")
    faux_moduleo.ajouter_affaire(1, "2024-001", "Bornage", IdResponsable=1, IdActeurEnCharge=2)
    faux_moduleo.ajouter_affaire(2, "2024-002", "Division", IdResponsable=2, IdActeurEnCharge=1)
    faux_moduleo.ajouter_affaire(3, "2024-003", "Copropriété", IdResponsable=2, IdActeurEnCharge=2)


def test_le_schema_decrit_chaque_filtre_en_noms_sans_id(client, faux_moduleo, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    proprietes = schema["function"]["parameters"]["properties"]
    for filtre in _FILTRES:
        assert proprietes[filtre]["description"], filtre
    assert not [nom for nom in proprietes if "id" in nom.split("_")]
    assert "identifiant" not in str(proprietes).lower()


def test_suivi_par_trouve_les_affaires_dont_la_personne_est_responsable_ou_chargee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _equipe(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"suivi_par": "Martin"})

    assert reponse.status_code == 200
    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-001" in contenu and "Affaire 2024-002" in contenu
    assert "Affaire 2024-003" not in contenu
    (_, recherche_utilisateur), = [a for a in faux_moduleo.appels if a[0].startswith("moduleo/utilisateur?")]
    assert recherche_utilisateur["nom"] == "Martin"
    assert [(p.get("idsResponsable"), p.get("idsActeurEnCharge")) for p in _recherches(faux_moduleo)] == [
        ("1", None),
        (None, "1"),
    ]


def test_responsable_prenom_et_nom_filtre_le_seul_responsable(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _equipe(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"responsable": "Jean Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-001" in contenu
    assert "Affaire 2024-002" not in contenu
    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsResponsable"] == "1"
    assert recherche.get("texte") is None


def test_charge_affaire_filtre_le_charge_daffaire(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _equipe(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"charge_affaire": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-002" in contenu
    assert "Affaire 2024-001" not in contenu
    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsActeurEnCharge"] == "1"


def test_dates_et_etat_transmis_au_format_de_lapi(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_affaire(1, "2024-001", "Bornage", Etat="Production", DateOuverture="2024-01-15T00:00:00+01:00")
    faux_moduleo.ajouter_affaire(2, "2023-050", "Bornage", Etat="Production", DateOuverture="2023-11-02T00:00:00+01:00")
    faux_moduleo.ajouter_affaire(3, "2024-002", "Bornage", Etat="Close", DateOuverture="2024-02-01T00:00:00+01:00")

    _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {
            "etat": "Production",
            "date_ouverture_min": "2024-01-01",
            "date_ouverture_max": "31/12/2024",
            "date_creation_min": "2023-06-01",
            "date_creation_max": "2024-12-31",
            "date_livraison_min": "2024-01-01",
            "date_livraison_max": "2024-12-31",
            "date_cloture_min": "2024-01-01",
            "date_cloture_max": "2024-12-31",
        },
    )

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["etatAffaire"] == "Production"
    assert recherche["dateOuvertureMin"] == "2024-01-01"
    assert recherche["dateOuvertureMax"] == "2024-12-31"
    assert recherche["dateCreationMin"] == "2023-06-01"
    assert recherche["dateCreationMax"] == "2024-12-31"
    assert recherche["dateLivraisonMin"] == "2024-01-01"
    assert recherche["dateLivraisonMax"] == "2024-12-31"
    assert recherche["dateClotureMin"] == "2024-01-01"
    assert recherche["dateClotureMax"] == "2024-12-31"


def test_affaires_ouvertes_depuis_janvier(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_affaire(1, "2024-001", "Bornage", DateOuverture="2024-01-15T00:00:00+01:00")
    faux_moduleo.ajouter_affaire(2, "2023-050", "Bornage", DateOuverture="2023-11-02T00:00:00+01:00")

    _chercher(client, mistral_client_factice, jeton_valide, {"date_ouverture_min": "2024-01-01"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-001" in contenu
    assert "Affaire 2023-050" not in contenu


def test_une_date_illisible_message_clair_sans_recherche(client, faux_moduleo, mistral_client_factice, jeton_valide):
    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"date_ouverture_min": "janvier"})

    assert reponse.status_code == 200
    contenu = _contenu_outil(mistral_client_factice)
    assert "janvier" in contenu and "AAAA-MM-JJ" in contenu
    assert _recherches(faux_moduleo) == []


def test_site_service_et_dossier_de_production_resolus_en_ids(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_site(3, "Montpellier")
    faux_moduleo.ajouter_site(4, "Nîmes")
    faux_moduleo.ajouter_service(7, "Topographie")
    faux_moduleo.ajouter_dossier_production(12, "Lotissement Les Pins")
    faux_moduleo.ajouter_affaire(1, "2024-001", "Bornage", IdSite=3, IdService=7, IdDossierProduction=12)
    faux_moduleo.ajouter_affaire(2, "2024-002", "Bornage", IdSite=4, IdService=7, IdDossierProduction=12)

    _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"site": "montpellier", "service": "Topographie", "dossier_production": "Les Pins"},
    )

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsSite"] == "3"
    assert recherche["idsService"] == "7"
    assert recherche["idDossierProduction"] == 12
    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-001" in contenu and "Affaire 2024-002" not in contenu


@pytest.mark.parametrize(
    ("arguments", "nom"),
    [
        ({"suivi_par": "Dupuis"}, "Dupuis"),
        ({"responsable": "Dupuis"}, "Dupuis"),
        ({"charge_affaire": "Dupuis"}, "Dupuis"),
        ({"site": "Lyon"}, "Lyon"),
        ({"service": "Juridique"}, "Juridique"),
        ({"dossier_production": "Zac Nord"}, "Zac Nord"),
    ],
)
def test_un_nom_introuvable_message_clair_sans_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, arguments, nom
):
    _equipe(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "bornage", **arguments})

    assert reponse.status_code == 200
    contenu = _contenu_outil(mistral_client_factice)
    assert f"« {nom} »" in contenu
    assert "Affaire" not in contenu
    assert _recherches(faux_moduleo) == []


def test_un_nom_ambigu_renvoie_les_candidats_sans_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _equipe(faux_moduleo)
    faux_moduleo.ajouter_utilisateur(5, "Paul", "Martin")

    _chercher(client, mistral_client_factice, jeton_valide, {"suivi_par": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "« Martin »" in contenu
    assert "Jean Martin" in contenu and "Paul Martin" in contenu
    assert "Sophie Bernard" not in contenu
    assert _recherches(faux_moduleo) == []


def test_un_dossier_de_production_ambigu_renvoie_les_candidats(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_dossier_production(12, "Lotissement Les Pins")
    faux_moduleo.ajouter_dossier_production(13, "Lotissement Les Chênes")

    _chercher(client, mistral_client_factice, jeton_valide, {"dossier_production": "Lotissement"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Lotissement Les Pins" in contenu and "Lotissement Les Chênes" in contenu
    assert _recherches(faux_moduleo) == []


def test_prenom_seul_trouve_la_personne(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _equipe(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"responsable": "Sophie"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsResponsable"] == "2"


def test_un_filtre_avec_texte_combine_les_deux(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _equipe(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "division", "suivi_par": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-002" in contenu
    assert "Affaire 2024-001" not in contenu
    assert {p["texte"] for p in _recherches(faux_moduleo)} == {"division"}
