import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flux_sse import fin

from vm_centrale.database import init_db
from vm_centrale.main import app
from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit
from vm_centrale.moduleo.droits import chemin

# Groupes et Droits Moduléo recopiés dans BBASS, rattachement des comptes
# (spec 1.5.1, #187, ADR-0018) : sans groupe, aucun outil Moduléo.

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "affecter_groupes_moduleo.py"
_OUTILS_COGEO = {"chercher_affaires_moduleo", "chercher_contacts_moduleo"}
_SANS_GROUPE = "Votre compte n'est rattaché à aucun groupe Moduléo Cogeo. Aucune lecture n'a été faite."

# Nombre de cases par catégorie Cogeo, tel qu'affiché dans les captures
# (« Catégorie: Analyse - 10 élément(s) »).
_CATEGORIES_COGEO = {
    "Affaires, groupes et archivage": 40,
    "Analyse": 10,
    "Catalogue": 11,
    "Contacts": 11,
    "Devis, factures et avoirs": 43,
    "G.E.D": 4,
    "Notes": 2,
    "Paramètres": 21,
    "Procédures qualité": 8,
    "Ressources Humaines": 17,
    "Signature électronique": 5,
    "Suivi": 14,
    "Tâches à faire": 2,
    "Temps passés et frais des temps passés": 8,
}


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _script():
    spec = importlib.util.spec_from_file_location("affecter_groupes_moduleo", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _outils_proposes(client, mistral_client_factice, jeton: str) -> set[str]:
    # Le premier appel principal du tour.
    premier = len(mistral_client_factice.tools_appels_reponse)
    mistral_client_factice.repondre("Bonjour.", "Titre")
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[premier] or []}


def _seed_durand(seed_compte, est_admin: bool = False):
    return seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand", est_admin=est_admin)


@pytest.fixture
def demarrage_reel(monkeypatch, db_session):
    # Le démarrage de la VM, sur la base de test : init_db n'est pas
    # neutralisé ici (conftest le remplace partout ailleurs).
    monkeypatch.setattr("vm_centrale.main.init_db", lambda: init_db(db_session.get_bind()))

    def demarrer() -> None:
        with TestClient(app):
            pass

    return demarrer


def _droits_du_groupe(db_session, application: str, nom: str) -> dict[str, dict | None]:
    groupe = db_session.query(GroupeModuleo).filter_by(application=application, nom=nom).one()
    return {
        droit.chemin: accord.conditions
        for accord, droit in db_session.query(GroupeModuleoDroit, DroitModuleo)
        .join(DroitModuleo, GroupeModuleoDroit.droit_id == DroitModuleo.id)
        .filter(GroupeModuleoDroit.groupe_id == groupe.id)
    }


def test_au_demarrage_le_catalogue_et_le_groupe_admin_sont_charges_sans_doublon(demarrage_reel, db_session):
    demarrage_reel()
    premier = (
        db_session.query(DroitModuleo).count(),
        db_session.query(GroupeModuleo).count(),
        db_session.query(GroupeModuleoDroit).count(),
    )
    demarrage_reel()

    assert (
        db_session.query(DroitModuleo).count(),
        db_session.query(GroupeModuleo).count(),
        db_session.query(GroupeModuleoDroit).count(),
    ) == premier
    # Seul le groupe Admin, en Cogeo et en Planning : aucun autre groupe
    # de prod, ni le groupe de dev.
    assert sorted((g.application, g.nom) for g in db_session.query(GroupeModuleo)) == [
        ("cogeo", "Admin"),
        ("planning", "Admin"),
    ]


def test_le_catalogue_cogeo_reprend_toutes_les_cases_des_captures(demarrage_reel, db_session):
    demarrage_reel()

    cogeo = db_session.query(DroitModuleo).filter_by(application="cogeo").all()
    par_categorie = {categorie: 0 for categorie in _CATEGORIES_COGEO}
    for droit in cogeo:
        par_categorie[droit.categorie] += 1
    assert par_categorie == _CATEGORIES_COGEO
    # Un sous-droit garde son parent ; un même libellé sous deux parents
    # donne deux droits.
    sous_droit = next(d for d in cogeo if d.libelle == "Voir le prix de vente des temps passés")
    assert db_session.get(DroitModuleo, sous_droit.parent_id).libelle == "Voir l'onglet prix de revient"
    assert sum(d.libelle == "Émettre à la fin du mois précédent" for d in cogeo) == 2


def test_le_catalogue_planning_reprend_les_actions_et_leurs_conditions(demarrage_reel, db_session):
    demarrage_reel()

    planning = {d.libelle: d for d in db_session.query(DroitModuleo).filter_by(application="planning")}
    assert {"Créer une tâche", "Modifier une tâche", "Supprimer une tâche"} <= set(planning)
    assert set(planning["Créer une tâche"].conditions) == {
        "Avec conditions de participation",
        "Avec conditions sur l'activité",
    }
    assert set(planning["Modifier une tâche"].conditions) == {
        "Avec conditions de participation",
        "Avec conditions sur l'activité",
        "Avec conditions sur le créateur",
    }


def test_le_groupe_admin_a_les_droits_des_captures(demarrage_reel, db_session):
    demarrage_reel()

    cogeo = _droits_du_groupe(db_session, "cogeo", "Admin")
    assert chemin("Devis, factures et avoirs", "Consulter les factures et les avoirs") in cogeo
    assert chemin("Affaires, groupes et archivage", "Voir l'avancement financier d'une affaire") in cogeo
    assert (
        chemin("Temps passés et frais des temps passés", "Consulter les temps passés et les frais des temps passés des autres collaborateurs")
        in cogeo
    )
    # Cases décochées dans les captures du groupe Admin.
    assert chemin("Affaires, groupes et archivage", "Changer la date libre d'une affaire") not in cogeo
    assert chemin("Ressources Humaines", "Consulter les informations RH des collaborateurs") not in cogeo
    assert chemin("Paramètres", "Gérer les groupes d'utilisateurs") not in cogeo
    assert len(cogeo) == 153

    planning = _droits_du_groupe(db_session, "planning", "Admin")
    activite = planning[chemin("Planning", "Créer une tâche")]["Avec conditions sur l'activité"]
    assert activite["L'activité doit toujours être indiquée"] is True
    assert activite["L'activité … des activités suivantes"] == {
        "operateur": "Ne fait pas partie",
        "activites": ["ABSENCE"],
    }
    suppression = planning[chemin("Planning", "Supprimer une tâche")]["Avec conditions sur l'activité"]
    assert suppression["L'activité doit toujours être indiquée"] is False


def test_compte_sans_groupe_aucun_outil_moduleo(client, faux_moduleo, mistral_client_factice, jeton_store):
    assert not _OUTILS_COGEO & _outils_proposes(client, mistral_client_factice, jeton_store.emettre("n.durand"))


def test_etre_compte_administrateur_ne_donne_aucun_groupe(
    client, faux_moduleo, mistral_client_factice, jeton_store, seed_compte
):
    _seed_durand(seed_compte, est_admin=True)

    assert not _OUTILS_COGEO & _outils_proposes(client, mistral_client_factice, jeton_store.emettre("n.durand"))


def test_compte_du_groupe_admin_affaires_et_contacts_proposes(
    client, faux_moduleo, mistral_client_factice, jeton_store, seed_compte, db_session
):
    _seed_durand(seed_compte)
    _script().affecter(db_session, faux_moduleo, "n.durand", cogeo="Admin", planning="Admin")

    assert _OUTILS_COGEO <= _outils_proposes(client, mistral_client_factice, jeton_store.emettre("n.durand"))


def test_compte_du_seul_groupe_planning_aucun_outil_cogeo(
    client, faux_moduleo, mistral_client_factice, jeton_store, seed_compte, db_session
):
    _seed_durand(seed_compte)
    _script().affecter(db_session, faux_moduleo, "n.durand", planning="Admin")

    assert not _OUTILS_COGEO & _outils_proposes(client, mistral_client_factice, jeton_store.emettre("n.durand"))


def test_un_groupe_retire_vaut_au_tour_suivant(
    client, faux_moduleo, mistral_client_factice, jeton_store, seed_compte, db_session
):
    _seed_durand(seed_compte)
    script = _script()
    script.affecter(db_session, faux_moduleo, "n.durand", cogeo="Admin")
    jeton = jeton_store.emettre("n.durand")
    assert _OUTILS_COGEO <= _outils_proposes(client, mistral_client_factice, jeton)

    script.affecter(db_session, faux_moduleo, "n.durand", cogeo="aucun")

    assert not _OUTILS_COGEO & _outils_proposes(client, mistral_client_factice, jeton)


@pytest.mark.parametrize("outil", sorted(_OUTILS_COGEO))
def test_un_outil_appele_sans_groupe_ne_lit_rien(
    outil, client, faux_moduleo, mistral_client_factice, jeton_store
):
    # Le modèle appelle un outil qui ne lui a pas été proposé.
    mistral_client_factice.repondre_avec_appel_outil(outil, {"texte": "Dupont"})
    mistral_client_factice.repondre("Je ne peux pas.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Cherche Dupont"}, headers=_autorisation(jeton_store.emettre("n.durand"))
    )

    assert reponse.status_code == 200
    fin(reponse)
    assert faux_moduleo.appels == []
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    assert message["content"].startswith(_SANS_GROUPE)


def test_le_script_resout_lutilisateur_moduleo_et_garde_les_options_absentes(
    client, faux_moduleo, seed_compte, db_session
):
    _seed_durand(seed_compte)
    faux_moduleo.ajouter_utilisateur(31, "Nadia", "Durand")
    script = _script()

    script.affecter(db_session, faux_moduleo, "n.durand", cogeo="Admin", planning="Admin")
    resultat = script.affecter(db_session, faux_moduleo, "n.durand", utilisateur="Nadia Durand")

    assert resultat == "n.durand : groupe Cogeo Admin, groupe Planning Admin, utilisateur Moduléo 31"
    assert script.affecter(db_session, None, "n.durand", utilisateur="aucun") == (
        "n.durand : groupe Cogeo Admin, groupe Planning Admin, utilisateur Moduléo aucun"
    )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"cogeo": "Production"}, "Aucun groupe cogeo « Production ». Groupes connus : Admin, Tous droits (dev)."),
        ({"utilisateur": "Inconnu"}, "Aucun utilisateur Moduléo ne correspond à « Inconnu »"),
    ],
)
def test_le_script_refuse_un_groupe_ou_un_utilisateur_inconnu_sans_rien_changer(
    options, message, client, faux_moduleo, seed_compte, db_session
):
    _seed_durand(seed_compte)
    script = _script()
    script.affecter(db_session, faux_moduleo, "n.durand", cogeo="Admin")

    with pytest.raises(script.AffectationImpossible, match=message.replace("(", r"\(").replace(")", r"\)")):
        script.affecter(db_session, faux_moduleo, "n.durand", **options)

    assert script.decrire(db_session, "n.durand").startswith("n.durand : groupe Cogeo Admin,")


def test_le_script_refuse_un_compte_inconnu(client, faux_moduleo, db_session):
    script = _script()

    with pytest.raises(script.AffectationImpossible, match="Aucun compte « x.inconnu »"):
        script.affecter(db_session, faux_moduleo, "x.inconnu", cogeo="Admin")


def test_le_groupe_de_dev_a_tous_les_droits_et_nest_cree_qua_la_demande(demarrage_reel, seed_compte, db_session):
    demarrage_reel()
    _seed_durand(seed_compte)

    _script().affecter(db_session, None, "n.durand", cogeo="Tous droits (dev)", groupe_dev=True)
    demarrage_reel()

    assert len(_droits_du_groupe(db_session, "cogeo", "Tous droits (dev)")) == sum(_CATEGORIES_COGEO.values())
    assert set(_droits_du_groupe(db_session, "planning", "Tous droits (dev)")) == {
        d.chemin for d in db_session.query(DroitModuleo).filter_by(application="planning")
    }
    assert sorted(g.nom for g in db_session.query(GroupeModuleo)) == [
        "Admin",
        "Admin",
        "Tous droits (dev)",
        "Tous droits (dev)",
    ]
