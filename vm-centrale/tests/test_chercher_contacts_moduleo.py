import json

import pytest

from flux_sse import fin, statuts

from vm_centrale.models import LectureOutil
from vm_centrale.moduleo.client import ModuleoIndisponible, ModuleoRefuse

# chercher_contacts_moduleo (spec 1.5.0, #176) : retrouver un contact
# Moduléo et ses coordonnées, avec un faux Moduléo (tests/faux_moduleo.py)
# à la place du client réel.

_OUTIL = "chercher_contacts_moduleo"
_RECHERCHE = "cogeo/contact?texte="
_TEL = "04 67 98 76 54"
_ADMIN = "cle-admin-de-test"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _chercher(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici le contact."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Coordonnées de Dupont"}, headers=_autorisation(jeton)
    )


def _recherches(faux_moduleo) -> list[dict]:
    return [parametres for route, parametres in faux_moduleo.appels if route.startswith(_RECHERCHE)]


def _dupont(faux_moduleo) -> None:
    faux_moduleo.ajouter_qualification(7, "Notaire")
    faux_moduleo.ajouter_commune(5, "Castries", "34160")
    faux_moduleo.ajouter_contact(40, "Étude Dupont", type_contact=2, qualifications=(7,))
    faux_moduleo.ajouter_telephone(1, 40, _TEL, "Bureau")
    faux_moduleo.ajouter_telephone(2, 40, "06 11 22 33 44", "Portable")
    faux_moduleo.ajouter_email(3, 40, "contact@etude-dupont.fr", "Travail")
    faux_moduleo.ajouter_adresse(4, 40, "3 rue de la Mairie", "Siège", id_commune=5)
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage du lot B")
    faux_moduleo.ajouter_affaire(102, "2023-050", "Division")
    faux_moduleo.lier_affaire(40, 101, "client")
    faux_moduleo.lier_affaire(40, 102, "intervenant")


def test_sans_config_moduleo_loutil_nest_pas_propose(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    noms = [outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []]
    assert _OUTIL not in noms


def test_avec_config_moduleo_le_schema_decrit_les_filtres_en_noms(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _OUTIL]
    proprietes = schema["function"]["parameters"]["properties"]
    assert set(proprietes) == {"texte", "type_contact", "type_donneur_ordre", "qualifications", "nb_max"}
    assert proprietes["qualifications"]["type"] == "array"


def test_coordonnees_dun_contact_fiche_avec_telephones_emails_adresses_et_affaires(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _dupont(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont"})

    assert reponse.status_code == 200
    fiche = _contenu_outil(mistral_client_factice)
    assert fiche.startswith("Contact Étude Dupont")
    assert "Type : Société" in fiche
    assert f"- {_TEL} (Bureau)" in fiche
    assert "- 06 11 22 33 44 (Portable)" in fiche
    assert "- contact@etude-dupont.fr (Travail)" in fiche
    assert "- 3 rue de la Mairie, Castries (34160) (Siège)" in fiche
    assert "Client des affaires : 2024-123" in fiche
    assert "Intervenant dans les affaires : 2023-050" in fiche
    # Jamais un id Moduléo dans la fiche.
    assert "40" not in fiche and "101" not in fiche


def test_chaque_coordonnee_est_lue_ids_puis_fiche_et_les_affaires_en_une_lecture_multi(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _dupont(faux_moduleo)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont"})

    routes = faux_moduleo.routes_appelees()
    assert routes.count("moduleo/telephone/{idTelephone}") == 2
    assert routes.count("cogeo/email/{idEmail}") == 1
    assert routes.count("moduleo/adresse/{idAdresse}") == 1
    assert routes.count("moduleo/commune/multi?ids={ids}") == 1
    (ids_affaires,) = [p["ids"] for r, p in faux_moduleo.appels if r == "cogeo/affaire/multi?ids={ids}"]
    assert sorted(ids_affaires.split(",")) == ["101", "102"]
    (_, recherche), = [a for a in faux_moduleo.appels if a[0].startswith(_RECHERCHE)]
    assert recherche == {"texte": "Dupont", "nbMaxResultat": 200}


def test_un_contact_sans_coordonnees_na_que_son_type_et_son_nom(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_contact(41, "Paul Durand", type_contact=1)

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Durand"})

    assert _contenu_outil(mistral_client_factice) == "Contact Paul Durand\nType : Personne"


def test_filtre_par_qualification_resolu_en_noms(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _dupont(faux_moduleo)
    faux_moduleo.ajouter_qualification(8, "Géomètre-expert")
    faux_moduleo.ajouter_contact(42, "Cabinet Géo", qualifications=(8,))

    _chercher(client, mistral_client_factice, jeton_valide, {"qualifications": ["notaire"]})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsQualifications"] == "7"
    contenu = _contenu_outil(mistral_client_factice)
    assert "Étude Dupont" in contenu and "Cabinet Géo" not in contenu


def test_une_qualification_exacte_lemporte_sur_celles_qui_la_contiennent(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_qualification(7, "Notaire")
    faux_moduleo.ajouter_qualification(9, "Clerc de notaire")

    _chercher(client, mistral_client_factice, jeton_valide, {"qualifications": ["Notaire", "Clerc"]})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["idsQualifications"] == "7,9"


@pytest.mark.parametrize(
    ("qualification", "debut"),
    [
        ("Huissier", "Aucune qualification Moduléo ne correspond à « Huissier »"),
        ("Expert", "Plusieurs qualifications Moduléo correspondent à « Expert » : Expert foncier, Géomètre-expert."),
    ],
)
def test_une_qualification_inconnue_ou_ambigue_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session, qualification, debut
):
    faux_moduleo.ajouter_qualification(8, "Géomètre-expert")
    faux_moduleo.ajouter_qualification(10, "Expert foncier")

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont", "qualifications": [qualification]})

    assert _contenu_outil(mistral_client_factice).startswith(debut)
    assert _recherches(faux_moduleo) == []
    assert db_session.query(LectureOutil).count() == 0


@pytest.mark.parametrize(
    ("type_contact", "attendu"),
    [
        ("société", "Societe"),
        ("Personne", "Personne"),
        ("collectivite", "Collectivite"),
        ("groupe de contacts", "GroupeContacts"),
    ],
)
def test_le_type_de_contact_est_transmis_par_son_nom_moduleo(
    client, faux_moduleo, mistral_client_factice, jeton_valide, type_contact, attendu
):
    _chercher(client, mistral_client_factice, jeton_valide, {"type_contact": type_contact})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["typeContact"] == attendu


def test_un_type_de_contact_inconnu_ne_lance_pas_la_recherche(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont", "type_contact": "association"})

    assert "association" in _contenu_outil(mistral_client_factice)
    assert faux_moduleo.appels == []


def test_le_type_de_donneur_dordre_est_transmis_tel_quel(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _chercher(client, mistral_client_factice, jeton_valide, {"type_donneur_ordre": "Public"})

    (recherche,) = _recherches(faux_moduleo)
    assert recherche["typeDonneurOrdreGE"] == "Public"


def test_cinq_fiches_au_plus_par_defaut_avec_le_nombre_trouve(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    for numero in range(1, 8):
        faux_moduleo.ajouter_contact(numero, f"Martin {numero}")

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Martin"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("7 contacts trouvés, 5 affichés, précise la recherche.")
    assert [f"Contact Martin {n}" in contenu for n in range(1, 8)] == [True] * 5 + [False] * 2


def test_nb_max_est_plafonne_a_dix(client, faux_moduleo, mistral_client_factice, jeton_valide):
    for numero in range(10, 22):
        faux_moduleo.ajouter_contact(numero, f"Martin {numero}")

    _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Martin", "nb_max": 50})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("12 contacts trouvés, 10 affichés, précise la recherche.")
    assert contenu.count("Contact Martin") == 10


def test_aucun_contact_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Introuvable"})

    assert reponse.status_code == 200
    assert _contenu_outil(mistral_client_factice) == "Aucun contact Moduléo ne correspond à cette recherche."
    assert "cogeo/contact/multi?ids={ids}" not in faux_moduleo.routes_appelees()


def test_sans_texte_ni_filtre_rien_nest_lu(client, faux_moduleo, mistral_client_factice, jeton_valide):
    reponse = _chercher(client, mistral_client_factice, jeton_valide, {})

    assert reponse.status_code == 200
    assert "texte" in _contenu_outil(mistral_client_factice)
    assert faux_moduleo.appels == []


def test_une_ligne_lectures_outils_par_fiche_avec_la_reference_du_contact(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _dupont(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont"})

    conversation_id = fin(reponse)["conversation"]["id"]
    (lecture,) = db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).all()
    assert (lecture.outil, lecture.reference) == ("moduleo", "contact Étude Dupont")
    assert lecture.texte == _contenu_outil(mistral_client_factice)


def test_un_telephone_de_la_fiche_reste_et_cite_le_contact_au_tour_et_au_suivant(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _dupont(faux_moduleo)

    reponse = _chercher(
        client,
        mistral_client_factice,
        jeton_valide,
        {"texte": "Dupont"},
        reponse=f"L'étude Dupont est joignable au {_TEL}.",
    )

    assert fin(reponse)["reponse"] == (
        f"L'étude Dupont est joignable au {_TEL}.\n\nSources : Moduléo, contact Étude Dupont"
    )

    mistral_client_factice.repondre(f"Rappel : {_TEL}.", resume_et_profil=_resume_et_profil())
    suivante = client.post(
        f"/conversations/{fin(reponse)['conversation']['id']}/messages",
        json={"message": "Redonne-moi son téléphone"},
        headers=_autorisation(jeton_valide),
    )

    assert fin(suivante)["reponse"] == f"Rappel : {_TEL}.\n\nSources : Moduléo, contact Étude Dupont"


def test_le_flux_publie_consultation_moduleo(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _dupont(faux_moduleo)

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont"})

    assert "Consultation Moduléo" in statuts(reponse)


@pytest.mark.parametrize(
    ("exception", "phrase"),
    [
        (ModuleoIndisponible("ReadTimeout sur cogeo/contact"), "Moduléo est indisponible pour le moment."),
        (ModuleoRefuse("403 sur cogeo/contact"), "Moduléo refuse l'accès à cette donnée."),
    ],
)
def test_panne_ou_refus_phrase_fixe_au_modele_detail_dans_linspecteur(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch, db_session, exception, phrase
):
    faux_moduleo.echouer(exception)

    reponse = _chercher(
        client, mistral_client_factice, jeton_valide, {"texte": "Dupont"}, reponse="Moduléo ne répond pas."
    )

    assert fin(reponse)["reponse"] == "Moduléo ne répond pas."
    assert _contenu_outil(mistral_client_factice) == phrase
    conversation_id = fin(reponse)["conversation"]["id"]
    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton_valide), "X-Admin-Key": _ADMIN}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (outil,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    detail = client.get(f"/inspecteur/echanges/{outil['id']}", headers=entetes).json()
    assert detail["reponse_payload"]["erreur"] == str(exception)
    assert detail["reponse_payload"]["contenu"] == phrase
    assert db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).count() == 0


def test_une_panne_pendant_les_lectures_paralleles_reste_une_phrase_fixe(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _dupont(faux_moduleo)
    lire = faux_moduleo.lire

    def lire_puis_tomber(route, parametres=None):
        if route == "cogeo/email/{idEmail}":
            raise ModuleoIndisponible("ReadTimeout sur cogeo/email")
        return lire(route, parametres)

    faux_moduleo.lire = lire_puis_tomber

    reponse = _chercher(client, mistral_client_factice, jeton_valide, {"texte": "Dupont"})

    assert reponse.status_code == 200
    assert _contenu_outil(mistral_client_factice) == "Moduléo est indisponible pour le moment."
