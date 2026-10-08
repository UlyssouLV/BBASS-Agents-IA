import json

import httpx
import pytest
from cryptography.fernet import Fernet

from flux_sse import fin, statuts

from vm_centrale.main import app
from vm_centrale.models import EchangeInspecteur, LectureOutil, Message
from vm_centrale.moduleo import client as client_module
from vm_centrale.moduleo.client import ModuleoIndisponible, ModuleoRefuse, get_client_moduleo

# chercher_affaires_moduleo (spec 1.5.0, #174) : retrouver une affaire
# Moduléo par numéro ou par texte, avec un faux Moduléo
# (tests/faux_moduleo.py) à la place du client réel.

_OUTIL = "chercher_affaires_moduleo"
_TEL_RESPONSABLE = "04 67 12 34 56"
_ADMIN = "cle-admin-de-test"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _noms_outils(tools) -> list[str]:
    return [outil["function"]["name"] for outil in tools or []]


def _contenu_outil(mistral_client_factice, appel: int = -2) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[appel] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _affaire_2024_123(faux_moduleo) -> None:
    faux_moduleo.ajouter_commune(5, "Castries", "34160")
    faux_moduleo.ajouter_contact(20, "SCI Les Oliviers")
    faux_moduleo.ajouter_contact(21, "Paul Durand")
    faux_moduleo.ajouter_contact(30, "Office notarial Rives")
    faux_moduleo.ajouter_contact(31, "Claire Rives")
    faux_moduleo.ajouter_utilisateur(1, "Jean", "Martin", tel_fixe=_TEL_RESPONSABLE, email="j.martin@bbass.fr")
    faux_moduleo.ajouter_utilisateur(2, "Sophie", "Bernard")
    faux_moduleo.ajouter_affaire(
        101,
        "2024-123",
        "Bornage du lot B",
        Etat=2,
        DateCreation="2024-03-04T09:30:00+01:00",
        DateOuverture="2024-03-11T00:00:00+01:00",
        Adresse="12 chemin des Oliviers",
        IdCommune=5,
        IdClient=20,
        QualiteClient="Propriétaire",
        IdRepresentant=21,
        QualiteRepresentant="Gérant",
        IdResponsable=1,
        IdActeurEnCharge=2,
    )
    faux_moduleo.ajouter_intervenant(
        900, 101, 30, "Notaire", id_representant=31, qualite_representant="Clerc"
    )


def _retrouver(client, mistral_client_factice, jeton: str, arguments: dict, reponse: str = "Voici l'affaire."):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, arguments)
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Retrouve l'affaire 2024-123"}, headers=_autorisation(jeton)
    )


def _echange_outil(client, conversation_id: int, jeton: str, monkeypatch) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton), "X-Admin-Key": _ADMIN}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (outil,) = [e for e in echanges if e["type_appel"] == f"outil:{_OUTIL}"]
    return client.get(f"/inspecteur/echanges/{outil['id']}", headers=entetes).json()


def test_sans_config_moduleo_loutil_nest_pas_propose(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _OUTIL not in _noms_outils(mistral_client_factice.tools_appels_reponse[0])


def test_avec_config_moduleo_loutil_est_propose_sur_chaque_appel_principal(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    reponse = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    mistral_client_factice.repondre("Encore.", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{fin(reponse)['conversation']['id']}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    # Le titrage, entre les deux, part sans `tools`.
    tools_reponses = mistral_client_factice.tools_appels_reponse
    assert _OUTIL in _noms_outils(tools_reponses[0])
    assert _OUTIL in _noms_outils(tools_reponses[-1])


def test_par_numero_la_fiche_donne_les_noms_resolus_et_les_intervenants_avec_leur_qualite(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    assert reponse.status_code == 200
    fiche = _contenu_outil(mistral_client_factice)
    assert "Affaire 2024-123" in fiche
    assert "Objet : Bornage du lot B" in fiche
    assert "État : 2" in fiche
    assert "Date de création : 04/03/2024" in fiche
    assert "Date d'ouverture : 11/03/2024" in fiche
    assert "Adresse : 12 chemin des Oliviers" in fiche
    assert "Commune : Castries (34160)" in fiche
    assert "Client : SCI Les Oliviers (Propriétaire)" in fiche
    assert "Représentant : Paul Durand (Gérant)" in fiche
    assert f"Responsable : Jean Martin (tél. {_TEL_RESPONSABLE}, email j.martin@bbass.fr)" in fiche
    assert "Chargé d'affaire : Sophie Bernard" in fiche
    assert "- Office notarial Rives (Notaire), représenté par Claire Rives (Clerc)" in fiche
    # Jamais un id Moduléo dans la fiche.
    assert "IdClient" not in fiche and "101" not in fiche


def test_les_noms_sont_resolus_une_seule_fois_par_appel(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _affaire_2024_123(faux_moduleo)
    faux_moduleo.ajouter_affaire(102, "2024-124", "Bornage du lot C", IdResponsable=1, IdActeurEnCharge=1, IdClient=20)

    _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "bornage"})

    routes = faux_moduleo.routes_appelees()
    assert routes.count("moduleo/utilisateur/{idUtilisateur}") == 2
    assert routes.count("cogeo/contact/multi?ids={ids}") == 1
    assert routes.count("moduleo/commune/multi?ids={ids}") == 1
    assert routes.count("cogeo/affaire/{idAffaire}/intervenants") == 2


def test_un_numero_inconnu_dit_quaucune_affaire_ne_correspond(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"numero": "1999-001"})

    assert reponse.status_code == 200
    assert _contenu_outil(mistral_client_factice) == "Aucune affaire Moduléo ne correspond à cette recherche."


def test_par_texte_plusieurs_fiches_cinq_au_plus_par_defaut_avec_le_nombre_trouve(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    for numero in range(1, 8):
        faux_moduleo.ajouter_affaire(numero, f"2024-00{numero}", f"Bornage numéro {numero}")

    _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "bornage"})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("7 affaires trouvées, 5 affichées, précise la recherche.")
    assert [f"Affaire 2024-00{n}" in contenu for n in range(1, 8)] == [True] * 5 + [False] * 2
    (_, parametres), = [a for a in faux_moduleo.appels if a[0].startswith("cogeo/affaire?texte=")]
    assert parametres["texte"] == "bornage"


def test_par_texte_nb_max_est_plafonne_a_dix(client, faux_moduleo, mistral_client_factice, jeton_valide):
    for numero in range(10, 22):
        faux_moduleo.ajouter_affaire(numero, f"2024-0{numero}", "Division")

    _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "division", "nb_max": 50})

    contenu = _contenu_outil(mistral_client_factice)
    assert contenu.startswith("12 affaires trouvées, 10 affichées, précise la recherche.")
    assert contenu.count("Affaire 2024-0") == 10


def test_par_texte_toutes_les_fiches_trouvees_sans_message_de_plafond(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    faux_moduleo.ajouter_affaire(1, "2024-001", "Division Castries")
    faux_moduleo.ajouter_affaire(2, "2024-002", "Bornage Castries")

    _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "castries"})

    contenu = _contenu_outil(mistral_client_factice)
    assert "trouvées" not in contenu
    assert "Affaire 2024-001" in contenu and "Affaire 2024-002" in contenu


def test_par_texte_aucune_affaire_message_clair(client, faux_moduleo, mistral_client_factice, jeton_valide):
    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "introuvable"})

    assert reponse.status_code == 200
    assert _contenu_outil(mistral_client_factice) == "Aucune affaire Moduléo ne correspond à cette recherche."
    assert "cogeo/affaire/multi?ids={ids}" not in faux_moduleo.routes_appelees()


def test_sans_numero_ni_texte_rien_nest_lu(client, faux_moduleo, mistral_client_factice, jeton_valide):
    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {})

    assert reponse.status_code == 200
    assert "numéro" in _contenu_outil(mistral_client_factice)
    assert faux_moduleo.appels == []


def test_une_ligne_lectures_outils_par_fiche_rattachee_au_tour_puis_supprimee_avec_la_conversation(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    faux_moduleo.ajouter_affaire(1, "2024-001", "Division Castries")
    faux_moduleo.ajouter_affaire(2, "2024-002", "Bornage Castries")

    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"texte": "castries"})
    conversation_id = fin(reponse)["conversation"]["id"]

    lectures = db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).order_by(LectureOutil.id).all()
    assert [(lecture.outil, lecture.reference) for lecture in lectures] == [
        ("moduleo", "affaire 2024-001"),
        ("moduleo", "affaire 2024-002"),
    ]
    assert lectures[0].texte in _contenu_outil(mistral_client_factice)
    (assistant,) = db_session.query(Message).filter_by(conversation_id=conversation_id, role="assistant").all()
    assert {lecture.message_id for lecture in lectures} == {assistant.id}

    client.delete(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide))
    assert db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).count() == 0


def test_un_chiffre_de_la_fiche_reste_au_tour_et_au_suivant_un_chiffre_absent_part(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(
        client,
        mistral_client_factice,
        jeton_valide,
        {"numero": "2024-123"},
        reponse=f"Jean Martin suit l'affaire, tél. {_TEL_RESPONSABLE}. Elle a été ouverte le 11/03/2024. "
        "Elle coûte 4 800 €.",
    )

    visible = fin(reponse)["reponse"]
    assert _TEL_RESPONSABLE in visible
    assert "11/03/2024" in visible
    assert "4 800" not in visible

    mistral_client_factice.repondre(
        f"Rappel : tél. {_TEL_RESPONSABLE}. Ouverte le 11/03/2024. Elle coûte 9 900 €.",
        resume_et_profil=_resume_et_profil(),
    )
    suivante = client.post(
        f"/conversations/{fin(reponse)['conversation']['id']}/messages",
        json={"message": "Redonne-moi son téléphone"},
        headers=_autorisation(jeton_valide),
    )

    visible = fin(suivante)["reponse"]
    assert _TEL_RESPONSABLE in visible
    assert "11/03/2024" in visible
    assert "9 900" not in visible


def test_un_chiffre_garde_venu_de_moduleo_cite_laffaire_sans_lien(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(
        client,
        mistral_client_factice,
        jeton_valide,
        {"numero": "2024-123"},
        reponse=f"Jean Martin suit l'affaire, tél. {_TEL_RESPONSABLE}.",
    )

    assert fin(reponse)["reponse"] == (
        f"Jean Martin suit l'affaire, tél. {_TEL_RESPONSABLE}.\n\nSources : Moduléo, affaire 2024-123"
    )


def test_un_chiffre_apporte_par_le_compte_ne_cite_pas_moduleo(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(
        client, mistral_client_factice, jeton_valide, {"numero": "2024-123"}, reponse="L'affaire 2024-123 existe."
    )

    assert fin(reponse)["reponse"] == "L'affaire 2024-123 existe."


def test_le_flux_publie_consultation_moduleo_avant_la_lecture(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    assert statuts(reponse) == [
        "Réflexion…",
        "Consultation Moduléo",
        "Réflexion…",
        "Vérification de la réponse…",
        "Titre de la conversation…",
    ]


@pytest.mark.parametrize(
    ("exception", "phrase"),
    [
        (ModuleoIndisponible("ReadTimeout sur cogeo/affaire/numeroAffaire"), "Moduléo est indisponible pour le moment."),
        (ModuleoRefuse("403 sur cogeo/affaire/numeroAffaire"), "Moduléo refuse l'accès à cette donnée."),
    ],
)
def test_panne_ou_refus_phrase_fixe_au_modele_reponse_normale_detail_dans_linspecteur(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch, db_session, exception, phrase
):
    faux_moduleo.echouer(exception)

    reponse = _retrouver(
        client, mistral_client_factice, jeton_valide, {"numero": "2024-123"}, reponse="Moduléo ne répond pas."
    )

    assert fin(reponse)["reponse"] == "Moduléo ne répond pas."
    assert _contenu_outil(mistral_client_factice) == phrase
    assert len(faux_moduleo.appels) == 1
    conversation_id = fin(reponse)["conversation"]["id"]
    detail = _echange_outil(client, conversation_id, jeton_valide, monkeypatch)
    assert detail["reponse_payload"]["erreur"] == str(exception)
    assert detail["reponse_payload"]["contenu"] == phrase
    assert db_session.query(LectureOutil).filter_by(conversation_id=conversation_id).count() == 0


def test_linspecteur_trace_les_arguments_les_fiches_et_les_routes_appelees(
    client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch
):
    _affaire_2024_123(faux_moduleo)

    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    detail = _echange_outil(client, fin(reponse)["conversation"]["id"], jeton_valide, monkeypatch)
    assert detail["requete_payload"]["arguments"] == {"numero": "2024-123"}
    (fiche,) = detail["reponse_payload"]["fiches"]
    assert fiche.startswith("Affaire 2024-123")
    assert detail["reponse_payload"]["routes"][:2] == [
        {"route": "cogeo/affaire/numeroAffaire?numAffaire={numAffaire}", "parametres": {"numAffaire": "2024-123"}},
        {"route": "cogeo/affaire/multi?ids={ids}", "parametres": {"ids": "101"}},
    ]


@pytest.fixture
def moduleo_reel_configure(client, monkeypatch, tmp_path):
    # Vraie config chiffrée et vrai ClientModuleo, transport HTTP simulé :
    # la clé et le SecurityCode réels existent, et ne doivent fuiter nulle
    # part.
    cle_maitre = tmp_path / "cle_maitre.key"
    cle = Fernet.generate_key()
    cle_maitre.write_bytes(cle)
    monkeypatch.setenv("MODULEO_URL", "https://moduleo.local/api")
    monkeypatch.setenv("MODULEO_API_KEY_CHIFFREE", Fernet(cle).encrypt(b"cle-api-secrete-42").decode())
    monkeypatch.setenv("MODULEO_SECURITY_CODE_CHIFFRE", Fernet(cle).encrypt(b"code-secret-77").decode())
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(cle_maitre))
    del app.dependency_overrides[get_client_moduleo]
    get_client_moduleo.cache_clear()
    requetes: list[httpx.Request] = []

    def installer(gestionnaire):
        def enregistrer(requete: httpx.Request) -> httpx.Response:
            requetes.append(requete)
            return gestionnaire(requete)

        monkeypatch.setattr(client_module, "_http_client", httpx.Client(transport=httpx.MockTransport(enregistrer)))

    yield installer, requetes
    get_client_moduleo.cache_clear()


def _servir_une_affaire(requete: httpx.Request) -> httpx.Response:
    chemin = requete.url.path
    if chemin == "/api/cogeo/affaire/numeroAffaire":
        return httpx.Response(200, json=7)
    if chemin == "/api/cogeo/affaire/multi":
        return httpx.Response(200, json=[{"IdAffaire": 7, "Numero": "2024-123", "Objet": "Bornage", "Etat": 1}])
    if chemin == "/api/cogeo/affaire/7/intervenants":
        return httpx.Response(200, json=[])
    return httpx.Response(404)


@pytest.mark.parametrize("gestionnaire", [_servir_une_affaire, lambda requete: httpx.Response(401)])
def test_ni_la_cle_ni_le_security_code_dans_linspecteur_ni_dans_lectures_outils(
    moduleo_reel_configure, client, mistral_client_factice, jeton_valide, db_session, gestionnaire
):
    installer, requetes = moduleo_reel_configure
    installer(gestionnaire)

    reponse = _retrouver(client, mistral_client_factice, jeton_valide, {"numero": "2024-123"})

    assert reponse.status_code == 200
    assert requetes and requetes[0].headers["ApiKey"] == "cle-api-secrete-42"
    conversation_id = fin(reponse)["conversation"]["id"]
    traces = json.dumps(
        [
            (echange.requete_payload, echange.reponse_payload, echange.erreur)
            for echange in db_session.query(EchangeInspecteur).filter_by(conversation_id=conversation_id)
        ],
        ensure_ascii=False,
    )
    lectures = " ".join(lecture.texte for lecture in db_session.query(LectureOutil).all())
    for secret in ("cle-api-secrete-42", "code-secret-77"):
        assert secret not in traces
        assert secret not in lectures
