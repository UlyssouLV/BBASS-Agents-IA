from datetime import datetime, timedelta

import pytest

from vm_centrale.models import GroupeModuleo
from vm_centrale.moduleo.droits import GROUPE_DEV, charger_catalogue, creer_groupes_dev

# Rattachements des comptes et journal des droits Moduléo administrés par
# API (spec 1.5.3, #212) : pour le seul Compte administrateur.


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


@pytest.fixture
def catalogue(db_session):
    charger_catalogue(db_session)
    db_session.commit()


@pytest.fixture
def admin(seed_compte, jeton_store, catalogue):
    seed_compte("a.martin", "secret", "Castries", ["Foncier"], "Alice", "Martin", est_admin=True)
    return _autorisation(jeton_store.emettre("a.martin"))


@pytest.fixture
def durand(seed_compte):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")


def _rattachement(client, admin, identifiant: str) -> dict:
    (rattachement,) = [
        r for r in client.get("/moduleo/rattachements", headers=admin).json() if r["identifiant"] == identifiant
    ]
    return rattachement


def test_chaque_compte_est_liste_sans_rattachement_par_defaut(client, admin, durand):
    reponse = client.get("/moduleo/rattachements", headers=admin)

    assert reponse.status_code == 200
    sans_rattachement = {"groupe_cogeo_id": None, "groupe_planning_id": None, "id_utilisateur_moduleo": None}
    assert reponse.json() == [
        {"identifiant": "a.martin", **sans_rattachement},
        {"identifiant": "n.durand", **sans_rattachement},
    ]


def _groupe(client, admin, application: str, nom: str) -> int:
    (groupe,) = [
        g
        for g in client.get("/moduleo/groupes", headers=admin).json()
        if (g["application"], g["nom"]) == (application, nom)
    ]
    return groupe["id"]


def _modifier(client, admin, identifiant: str, **champs):
    return client.patch(f"/moduleo/rattachements/{identifiant}", json=champs, headers=admin)


def test_un_compte_se_rattache_et_un_champ_absent_garde_sa_valeur(client, admin, durand):
    cogeo, planning = _groupe(client, admin, "cogeo", "Admin"), _groupe(client, admin, "planning", "Admin")

    _modifier(client, admin, "n.durand", groupe_cogeo_id=cogeo)
    reponse = _modifier(client, admin, "n.durand", groupe_planning_id=planning)

    assert reponse.status_code == 200
    assert reponse.json() == {
        "identifiant": "n.durand",
        "groupe_cogeo_id": cogeo,
        "groupe_planning_id": planning,
        "id_utilisateur_moduleo": None,
    }
    assert _rattachement(client, admin, "n.durand") == reponse.json()


def test_null_retire_le_groupe(client, admin, durand):
    cogeo, planning = _groupe(client, admin, "cogeo", "Admin"), _groupe(client, admin, "planning", "Admin")
    _modifier(client, admin, "n.durand", groupe_cogeo_id=cogeo, groupe_planning_id=planning)

    _modifier(client, admin, "n.durand", groupe_cogeo_id=None)

    assert _rattachement(client, admin, "n.durand")["groupe_cogeo_id"] is None
    assert _rattachement(client, admin, "n.durand")["groupe_planning_id"] == planning


@pytest.mark.parametrize(("champ", "application"), [("groupe_cogeo_id", "planning"), ("groupe_planning_id", "cogeo")])
def test_un_groupe_dune_autre_application_est_refuse_sans_rien_changer(champ, application, client, admin, durand):
    cogeo = _groupe(client, admin, "cogeo", "Admin")
    _modifier(client, admin, "n.durand", groupe_cogeo_id=cogeo)

    reponse = _modifier(client, admin, "n.durand", **{champ: _groupe(client, admin, application, "Admin")})

    assert reponse.status_code == 422
    assert _rattachement(client, admin, "n.durand")["groupe_cogeo_id"] == cogeo
    assert _rattachement(client, admin, "n.durand")["groupe_planning_id"] is None


def test_un_groupe_inconnu_est_refuse(client, admin, durand):
    assert _modifier(client, admin, "n.durand", groupe_cogeo_id=999).status_code == 422


def test_le_groupe_de_dev_ne_se_rattache_pas_depuis_le_panel(client, admin, durand, db_session):
    # « Tous droits (dev) » reste hors Panel (ADR-0019).
    creer_groupes_dev(db_session)
    db_session.commit()
    groupe_id = db_session.query(GroupeModuleo).filter_by(application="cogeo", nom=GROUPE_DEV).one().id

    assert _modifier(client, admin, "n.durand", groupe_cogeo_id=groupe_id).status_code == 422
    assert _rattachement(client, admin, "n.durand")["groupe_cogeo_id"] is None


def test_un_compte_inconnu_est_refuse(client, admin):
    assert _modifier(client, admin, "x.inconnu", groupe_cogeo_id=None).status_code == 404


def test_lutilisateur_moduleo_se_resout_par_son_nom_et_null_le_retire(client, faux_moduleo, admin, durand):
    faux_moduleo.ajouter_utilisateur(31, "Nadia", "Durand")

    reponse = _modifier(client, admin, "n.durand", utilisateur_moduleo="Nadia Durand")

    assert reponse.status_code == 200
    assert reponse.json()["id_utilisateur_moduleo"] == 31
    _modifier(client, admin, "n.durand", utilisateur_moduleo=None)
    assert _rattachement(client, admin, "n.durand")["id_utilisateur_moduleo"] is None


@pytest.mark.parametrize(
    ("nom", "message"),
    [
        ("Inconnu", "Aucun utilisateur Moduléo ne correspond à « Inconnu »"),
        ("Durand", "Plusieurs utilisateurs Moduléo correspondent à « Durand » : Nadia Durand, Paul Durand"),
    ],
)
def test_un_nom_inconnu_ou_ambigu_est_refuse_sans_rien_changer(nom, message, client, faux_moduleo, admin, durand):
    faux_moduleo.ajouter_utilisateur(31, "Nadia", "Durand")
    faux_moduleo.ajouter_utilisateur(32, "Paul", "Durand")
    cogeo = _groupe(client, admin, "cogeo", "Admin")
    _modifier(client, admin, "n.durand", utilisateur_moduleo="Nadia Durand")

    reponse = _modifier(client, admin, "n.durand", groupe_cogeo_id=cogeo, utilisateur_moduleo=nom)

    assert reponse.status_code == 422
    assert message in reponse.json()["detail"]
    assert _rattachement(client, admin, "n.durand")["groupe_cogeo_id"] is None
    assert _rattachement(client, admin, "n.durand")["id_utilisateur_moduleo"] == 31


def test_sans_moduleo_configure_le_nom_ne_se_resout_pas(client, admin, durand):
    reponse = _modifier(client, admin, "n.durand", utilisateur_moduleo="Nadia Durand")

    assert reponse.status_code == 503
    assert _rattachement(client, admin, "n.durand")["id_utilisateur_moduleo"] is None


def _journal(client, admin) -> list[tuple[str, str, str]]:
    return [(e["admin"], e["action"], e["cible"]) for e in client.get("/moduleo/journal", headers=admin).json()]


def test_le_journal_liste_les_actions_admin_les_plus_recentes_dabord(client, faux_moduleo, admin, durand):
    faux_moduleo.ajouter_utilisateur(31, "Nadia", "Durand")
    groupe = client.post("/moduleo/groupes", json={"application": "cogeo", "nom": "Prod"}, headers=admin).json()["id"]
    client.patch(f"/moduleo/groupes/{groupe}", json={"nom": "Production"}, headers=admin)
    client.put(f"/moduleo/groupes/{groupe}/droits", json=[], headers=admin)
    _modifier(client, admin, "n.durand", groupe_cogeo_id=groupe, utilisateur_moduleo="Nadia Durand")
    _modifier(client, admin, "n.durand", groupe_cogeo_id=None)
    client.delete(f"/moduleo/groupes/{groupe}", headers=admin)

    assert _journal(client, admin) == [
        ("a.martin", "Groupe supprimé", "cogeo « Production »"),
        ("a.martin", "Rattachement modifié", "n.durand : groupe Cogeo aucun"),
        ("a.martin", "Rattachement modifié", "n.durand : groupe Cogeo Production, utilisateur Moduléo 31"),
        ("a.martin", "Droits remplacés", "cogeo « Production » : 0 droit"),
        ("a.martin", "Groupe renommé", "cogeo « Prod » → « Production »"),
        ("a.martin", "Groupe créé", "cogeo « Prod »"),
    ]
    entree = client.get("/moduleo/journal", headers=admin).json()[0]
    # En UTC explicite : le Panel l'affiche à l'heure locale.
    assert datetime.fromisoformat(entree["date"]).utcoffset() == timedelta(0)


def test_une_action_refusee_nest_pas_journalisee(client, admin, durand):
    client.post("/moduleo/groupes", json={"application": "cogeo", "nom": "Admin"}, headers=admin)
    _modifier(client, admin, "n.durand", groupe_cogeo_id=999)
    # Rien à changer : rien à journaliser.
    _modifier(client, admin, "n.durand")

    assert _journal(client, admin) == []


_ROUTES = [
    ("get", "/moduleo/rattachements", None),
    ("patch", "/moduleo/rattachements/n.durand", {"groupe_cogeo_id": None}),
    ("get", "/moduleo/journal", None),
]


@pytest.mark.parametrize(("methode", "url", "corps"), _ROUTES)
def test_sans_jeton_refuse(methode, url, corps, client, durand):
    assert client.request(methode, url, json=corps).status_code == 401


@pytest.mark.parametrize(("methode", "url", "corps"), _ROUTES)
def test_compte_non_admin_refuse(methode, url, corps, client, durand, jeton_store, admin):
    reponse = client.request(methode, url, json=corps, headers=_autorisation(jeton_store.emettre("n.durand")))

    assert reponse.status_code == 403
    assert _journal(client, admin) == []


def _outils_proposes(client, mistral_client_factice, jeton: str) -> set[str]:
    # Le premier appel principal du tour.
    premier = len(mistral_client_factice.tools_appels_reponse)
    mistral_client_factice.repondre("Bonjour.", "Titre")
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[premier] or []}


def test_un_rattachement_par_api_vaut_au_tour_suivant(
    client, faux_moduleo, mistral_client_factice, jeton_store, admin, durand
):
    jeton = jeton_store.emettre("n.durand")
    assert "chercher_affaires_moduleo" not in _outils_proposes(client, mistral_client_factice, jeton)

    _modifier(client, admin, "n.durand", groupe_cogeo_id=_groupe(client, admin, "cogeo", "Admin"))
    assert "chercher_affaires_moduleo" in _outils_proposes(client, mistral_client_factice, jeton)

    _modifier(client, admin, "n.durand", groupe_cogeo_id=None)
    assert "chercher_affaires_moduleo" not in _outils_proposes(client, mistral_client_factice, jeton)
