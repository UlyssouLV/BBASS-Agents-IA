from flux_sse import fin

from vm_centrale.models import GroupeModuleo
from vm_centrale.moduleo.droits import COGEO, charger_catalogue, rattacher

# chercher_affaires_moduleo avec `avec_parcelles` (spec 1.5.1, #193) : pour
# une seule affaire, ses parcelles et leurs propriétaires, lus parcelle par
# parcelle à travers le garde. Jamais d'office. Faux Moduléo :
# tests/faux_moduleo.py.

_OUTIL = "chercher_affaires_moduleo"
_ROUTES_PARCELLES = (
    "cogeo/affaire/{idAffaire}/parcelles",
    "cogeo/parcelle/{idParcelle}",
    "cogeo/parcelle/{idParcelle}/proprietaires",
    "cogeo/proprietaire/{idProprietaire}",
)


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"]
    return message["content"]


def _schema(mistral_client_factice) -> dict:
    (outil,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    return outil["function"]


def _affaire_avec_parcelles(faux_moduleo) -> None:
    # Affaire 2024-123 à Castries : AB 123 à la SCI Les Oliviers et à Paul
    # Durand, AB 124 sans propriétaire connu.
    faux_moduleo.ajouter_commune(5, "Castries", "34160")
    faux_moduleo.ajouter_commune(6, "Vendargues", "34740")
    faux_moduleo.ajouter_contact(20, "SCI Les Oliviers")
    faux_moduleo.ajouter_contact(21, "Paul Durand")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B", IdCommune=5, IdClient=20)
    faux_moduleo.ajouter_parcelle(
        501, 101, "AB", "123", prefixe="000", id_commune=5, contenance=1234.0, lieu_dit="Les Plans"
    )
    faux_moduleo.ajouter_parcelle(502, 101, "AB", "124", id_commune=6, contenance=560.5)
    faux_moduleo.ajouter_proprietaire(801, 501, 20)
    faux_moduleo.ajouter_proprietaire(802, 501, 21)


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Les parcelles de l'affaire 2024-123 ?"}, headers=_autorisation(jeton)
    )


def _routes_parcelles(faux_moduleo) -> list[str]:
    return [route for route in faux_moduleo.routes_appelees() if route in _ROUTES_PARCELLES]


def test_sans_avec_parcelles_aucune_lecture_de_parcelle_et_fiche_inchangee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_avec_parcelles(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    assert "Parcelles" not in _contenu_outil(mistral_client_factice)
    assert _routes_parcelles(faux_moduleo) == []


def test_le_schema_decrit_avec_parcelles_pour_une_seule_affaire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _chercher(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    schema = _schema(mistral_client_factice)
    assert schema["parameters"]["properties"]["avec_parcelles"]["type"] == "boolean"
    assert "une seule affaire" in schema["parameters"]["properties"]["avec_parcelles"]["description"]
    assert "parcelles" in schema["description"]


def test_avec_parcelles_sur_plusieurs_affaires_refuse_et_demande_une_seule_affaire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_avec_parcelles(faux_moduleo)
    faux_moduleo.ajouter_affaire(102, "2024-124", "Bornage du lot C")

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "bornage", "avec_parcelles": True})

    contenu = _contenu_outil(mistral_client_factice)
    assert "une seule affaire" in contenu
    assert "2 affaires correspondent" in contenu
    assert "Affaire 2024-123" not in contenu
    assert _routes_parcelles(faux_moduleo) == []
    assert "cogeo/affaire/multi?ids={ids}" not in faux_moduleo.routes_appelees()


def test_avec_parcelles_sur_une_affaire_parcelles_et_proprietaires_dans_la_fiche(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_avec_parcelles(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"numero": "2024-123", "avec_parcelles": True})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("Affaire 2024-123")
    assert "Parcelles :" in contenu
    assert (
        "- AB 123, Castries (34160), lieu-dit Les Plans, contenance 1 234 m², "
        "propriétaires : SCI Les Oliviers, Paul Durand"
    ) in contenu
    assert "- AB 124, Vendargues (34740), contenance 560,5 m²" in contenu
    # Une parcelle, puis ses propriétaires, un par un, à travers le garde.
    routes = faux_moduleo.routes_appelees()
    assert routes.count("cogeo/parcelle/{idParcelle}") == 2
    assert routes.count("cogeo/parcelle/{idParcelle}/proprietaires") == 2
    assert routes.count("cogeo/proprietaire/{idProprietaire}") == 2
    # Les noms de l'affaire et des propriétaires en une seule lecture.
    assert routes.count("cogeo/contact/multi?ids={ids}") == 1
    assert routes.count("moduleo/commune/multi?ids={ids}") == 1


def test_avec_parcelles_texte_qui_trouve_une_seule_affaire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_avec_parcelles(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "lot B", "avec_parcelles": "true"})

    assert "- AB 124, Vendargues (34740)" in _contenu_outil(mistral_client_factice)


def test_avec_parcelles_affaire_sans_parcelle_le_dit(client, faux_moduleo, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")

    _chercher(client, mistral_client_factice, jeton_valide, {"numero": "2024-123", "avec_parcelles": True})

    assert "Parcelles : aucune dans Moduléo" in _contenu_outil(mistral_client_factice)


def test_reference_et_contenance_lues_restent_une_contenance_absente_part(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_avec_parcelles(faux_moduleo)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"numero": "2024-123", "avec_parcelles": True},
        reponse="La parcelle AB 123 fait 1 234 m². La parcelle voisine fait 9 876 m².",
    )

    visible = fin(reponse)["reponse"]
    assert "AB 123" in visible
    assert "1 234 m²" in visible
    assert "9 876" not in visible
    assert visible.endswith("Sources : Moduléo, affaire 2024-123")


def test_sans_le_droit_de_consulter_les_contacts_proprietaires_retires_avec_une_mention(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    # Groupe Cogeo sans aucun droit : les affaires et les parcelles se
    # lisent, pas les propriétaires (données personnelles, « Rechercher
    # des contacts »).
    charger_catalogue(db_session)
    db_session.add(GroupeModuleo(application=COGEO, nom="Sans droit"))
    db_session.flush()
    rattacher(db_session, "j.dupont", "Sans droit", None, None)
    db_session.commit()
    _affaire_avec_parcelles(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"numero": "2024-123", "avec_parcelles": True})

    contenu = _contenu_outil(mistral_client_factice)
    assert "- AB 123, Castries (34160), lieu-dit Les Plans, contenance 1 234 m²" in contenu
    assert "Propriétaires : non autorisés pour votre compte" in contenu
    assert "Paul Durand" not in contenu
    routes = faux_moduleo.routes_appelees()
    assert "cogeo/parcelle/{idParcelle}/proprietaires" not in routes
    assert "cogeo/proprietaire/{idProprietaire}" not in routes
