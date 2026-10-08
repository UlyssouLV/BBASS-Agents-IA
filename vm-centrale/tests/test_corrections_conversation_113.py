import json

import pytest

from flux_sse import fin

# Corrections du test humain 1.5.0 (conversation 113, « Affaire 25_862-17 »,
# #180) : téléphones à points, ligne « Sources : » sans doublon, état et
# type de contact en noms, champs sur une ligne, adresse sans la commune.

_TITRE_MEMOIRE = "Mémoire de la conversation :"
_AFFAIRES = "chercher_affaires_moduleo"
_CONTACTS = "chercher_contacts_moduleo"
_SOURCE_AKERYS = "Moduléo, contact AKERYS PROMOTION"
_SOURCE_AFFAIRE = "Moduléo, affaire 25_862-17"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _appeler(client, mistral_client_factice, jeton: str, outil: str, arguments: dict, reponse: str = "Voici."):
    mistral_client_factice.repondre_avec_appel_outil(outil, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post("/conversations", json={"message": "Affaire 25_862-17"}, headers=_autorisation(jeton))


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _recherches_affaires(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith("cogeo/affaire?texte=")]


def _akerys(faux_moduleo, telephone: str = "05.61.12.92.00") -> None:
    faux_moduleo.ajouter_contact(50, "AKERYS PROMOTION", type_contact=3)
    faux_moduleo.ajouter_telephone(1, 50, telephone, "Standard")


def _affaire_25_862_17(faux_moduleo, **champs) -> None:
    faux_moduleo.ajouter_commune(9, "Saint-Mathieu-de-Tréviers", "34270")
    faux_moduleo.ajouter_affaire(
        862,
        "25_862-17",
        "Bornage ALCARAZ\r\nZac Le Solan",
        **{"Etat": 7, "Adresse": "34270 SAINT-MATHIEU-DE-TRÉVIERS", "IdCommune": 9, **champs},
    )


def _memoire_apres_suivi(client, mistral_client_factice, jeton: str, reponse) -> str:
    mistral_client_factice.repondre("Suite", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{fin(reponse)['conversation']['id']}/messages",
        json={"message": "Et alors ?"},
        headers=_autorisation(jeton),
    )
    (memoire,) = [
        m["content"]
        for m in mistral_client_factice.appels_reponse[-1]
        if m["role"] == "system" and m["content"].startswith(_TITRE_MEMOIRE)
    ]
    return memoire


# 1. Téléphones : le séparateur ne compte pas.


@pytest.mark.parametrize(
    ("dans_moduleo", "ecrit"),
    [
        ("05.61.12.92.00", "05 61 12 92 00"),
        ("05 61 12 92 00", "05.61.12.92.00"),
        ("05.61.12.92.00", "05-61-12-92-00"),
    ],
)
def test_un_telephone_garde_quel_que_soit_le_separateur(
    client, faux_moduleo, mistral_client_factice, jeton_valide, dans_moduleo, ecrit
):
    _akerys(faux_moduleo, dans_moduleo)

    reponse = _appeler(
        client, mistral_client_factice, jeton_valide, _CONTACTS, {"texte": "AKERYS"}, f"Téléphone : {ecrit}"
    )

    assert fin(reponse)["reponse"] == f"Téléphone : {ecrit}\n\nSources : {_SOURCE_AKERYS}"


def test_un_decimal_absent_des_sources_est_toujours_retire(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _akerys(faux_moduleo)

    reponse = _appeler(
        client,
        mistral_client_factice,
        jeton_valide,
        _CONTACTS,
        {"texte": "AKERYS"},
        "Téléphone : 05 61 12 92 00. Le taux est de 12.92 points.",
    )

    visible = fin(reponse)["reponse"]
    assert "05 61 12 92 00" in visible
    assert "12.92 points" not in visible


# 2. Ligne « Sources : » sans doublon.


def test_une_citation_deja_ecrite_par_le_modele_nest_pas_repetee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _akerys(faux_moduleo)

    reponse = _appeler(
        client,
        mistral_client_factice,
        jeton_valide,
        _CONTACTS,
        {"texte": "AKERYS"},
        f"Téléphone : 05 61 12 92 00\n\nSources : {_SOURCE_AKERYS}",
    )

    assert fin(reponse)["reponse"] == f"Téléphone : 05 61 12 92 00\n\nSources : {_SOURCE_AKERYS}"


@pytest.mark.parametrize(
    ("bloc", "attendu"),
    [
        ("Sources : Moduléo", f"Sources : {_SOURCE_AKERYS}"),
        ("**Source :** Moduléo", f"**Sources :** {_SOURCE_AKERYS}"),
        ("Sources :\n- Moduléo", f"Sources :\n- {_SOURCE_AKERYS}"),
    ],
)
def test_moduleo_seul_est_remplace_par_la_citation_complete(
    client, faux_moduleo, mistral_client_factice, jeton_valide, bloc, attendu
):
    _akerys(faux_moduleo)

    reponse = _appeler(
        client,
        mistral_client_factice,
        jeton_valide,
        _CONTACTS,
        {"texte": "AKERYS"},
        f"Téléphone : 05 61 12 92 00\n\n{bloc}",
    )

    assert fin(reponse)["reponse"] == f"Téléphone : 05 61 12 92 00\n\n{attendu}"


# 3. État d'affaire en nom.


def test_la_fiche_et_la_memoire_donnent_le_nom_de_letat(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _affaire_25_862_17(faux_moduleo)

    reponse = _appeler(client, mistral_client_factice, jeton_valide, _AFFAIRES, {"numero": "25_862-17"})

    assert "État : Acceptée" in _contenu_outil(mistral_client_factice)
    memoire = _memoire_apres_suivi(client, mistral_client_factice, jeton_valide, reponse)
    assert f"  • Quel est l'état de l'affaire 25_862-17 ? → Acceptée ({_SOURCE_AFFAIRE})" in memoire.splitlines()


def test_un_etat_inconnu_reste_en_chiffre(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _affaire_25_862_17(faux_moduleo, Etat=42)

    _appeler(client, mistral_client_factice, jeton_valide, _AFFAIRES, {"numero": "25_862-17"})

    assert "État : 42" in _contenu_outil(mistral_client_factice)


@pytest.mark.parametrize(
    ("etat", "parametre"),
    [
        ("Acceptée", "Acceptee"),
        ("acceptee", "Acceptee"),
        ("En attente", "EnAttente"),
        ("Prod. terminée", "Terminee"),
        ("Clôturée", "Cloturee"),
        ("Créée", "Creee"),
    ],
)
def test_le_filtre_etat_accepte_les_noms_affiches(
    client, faux_moduleo, mistral_client_factice, jeton_valide, etat, parametre
):
    _affaire_25_862_17(faux_moduleo)

    _appeler(client, mistral_client_factice, jeton_valide, _AFFAIRES, {"etat": etat})

    (recherche,) = _recherches_affaires(faux_moduleo)
    assert recherche["etatAffaire"] == parametre


def test_un_etat_qui_nexiste_pas_dans_moduleo_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    # Tour 10 : « est-ce qu'il y en a qui ont l'état en retard ? ». Moduléo
    # ignore un nom d'état inconnu et renverrait toutes les affaires.
    _affaire_25_862_17(faux_moduleo)

    _appeler(client, mistral_client_factice, jeton_valide, _AFFAIRES, {"etat": "en retard"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "« en retard »" in contenu
    assert "Acceptée" in contenu and "Prod. terminée" in contenu
    assert "Affaire 25_862-17" not in contenu
    assert _recherches_affaires(faux_moduleo) == []


# 4. Type de contact.


def test_akerys_trouve_comme_societe_est_affiche_societe(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _akerys(faux_moduleo)
    faux_moduleo.ajouter_contact(51, "AKERYS Mairie", type_contact=4)

    _appeler(
        client, mistral_client_factice, jeton_valide, _CONTACTS, {"texte": "AKERYS", "type_contact": "société"}
    )

    fiche = _contenu_outil(mistral_client_factice)
    assert fiche.startswith("Contact AKERYS PROMOTION\nType : Société")
    assert "AKERYS Mairie" not in fiche


# 5. Champs sur une ligne, adresse sans la commune.


def test_un_champ_sur_plusieurs_lignes_tient_sur_une_ligne_et_ladresse_ne_repete_pas_la_commune(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_25_862_17(faux_moduleo)

    reponse = _appeler(client, mistral_client_factice, jeton_valide, _AFFAIRES, {"numero": "25_862-17"})

    fiche = _contenu_outil(mistral_client_factice)
    assert "Objet : Bornage ALCARAZ Zac Le Solan\n" in fiche
    assert "Adresse" not in fiche
    assert "Commune : Saint-Mathieu-de-Tréviers (34270)" in fiche
    lignes = _memoire_apres_suivi(client, mistral_client_factice, jeton_valide, reponse).splitlines()
    assert f"  • Quel est l'objet de l'affaire 25_862-17 ? → Bornage ALCARAZ Zac Le Solan ({_SOURCE_AFFAIRE})" in lignes
    assert (
        f"  • Où se trouve l'affaire 25_862-17 ? → Saint-Mathieu-de-Tréviers (34270) ({_SOURCE_AFFAIRE})"
    ) in lignes
