import pytest

from vm_centrale.moduleo.droits import charger_catalogue, chemin, rattacher

# API d'administration des groupes Moduléo (spec 1.5.3, #211, ADR-0019) :
# catalogue des cases en lecture seule, groupes et droits accordés, pour le
# seul Compte administrateur.


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


def _noeud(arbre: list[dict], *libelles: str) -> dict:
    # Le droit au bout de « catégorie, parent…, libellé » dans l'arborescence.
    (categorie,) = [c for c in arbre if c["categorie"] == libelles[0]]
    droits = categorie["droits"]
    for libelle in libelles[1:]:
        (noeud,) = [d for d in droits if d["libelle"] == libelle]
        droits = noeud["sous_droits"]
    return noeud


def test_le_catalogue_se_lit_en_arborescence_cogeo_et_planning(client, admin):
    reponse = client.get("/moduleo/catalogue", headers=admin)

    assert reponse.status_code == 200
    catalogue = reponse.json()
    assert set(catalogue) == {"cogeo", "planning"}
    assert [c["categorie"] for c in catalogue["cogeo"]][:2] == ["Affaires, groupes et archivage", "Analyse"]
    sous_droit = _noeud(
        catalogue["cogeo"],
        "Affaires, groupes et archivage",
        "Voir l'onglet prix de revient",
        "Voir le prix de vente des temps passés",
    )
    assert sous_droit["chemin"] == chemin(
        "Affaires, groupes et archivage",
        "Voir l'onglet prix de revient",
        "Voir le prix de vente des temps passés",
    )
    creer = _noeud(catalogue["planning"], "Planning", "Créer une tâche")
    assert set(creer["conditions"]) == {"Avec conditions de participation", "Avec conditions sur l'activité"}


def _creer(client, admin, application: str, nom: str):
    return client.post("/moduleo/groupes", json={"application": application, "nom": nom}, headers=admin)


def _groupes(client, admin) -> list[tuple[str, str]]:
    return [(g["application"], g["nom"]) for g in client.get("/moduleo/groupes", headers=admin).json()]


def test_un_groupe_cree_apparait_dans_la_liste_sans_aucun_droit(client, admin):
    reponse = _creer(client, admin, "cogeo", "Production")

    assert reponse.status_code == 201
    assert reponse.json()["nom"] == "Production"
    assert _groupes(client, admin) == [("cogeo", "Admin"), ("cogeo", "Production"), ("planning", "Admin")]
    assert client.get(f"/moduleo/groupes/{reponse.json()['id']}/droits", headers=admin).json() == []


def test_un_meme_nom_est_refuse_dans_une_application_mais_pas_dans_lautre(client, admin):
    assert _creer(client, admin, "cogeo", "Admin").status_code == 409
    assert _creer(client, admin, "planning", "Production").status_code == 201
    assert _creer(client, admin, "cogeo", "Production").status_code == 201


def test_une_application_inconnue_est_refusee(client, admin):
    assert _creer(client, admin, "fileo", "Production").status_code == 422


def _id(client, admin, application: str, nom: str) -> int:
    (groupe,) = [
        g for g in client.get("/moduleo/groupes", headers=admin).json() if (g["application"], g["nom"]) == (application, nom)
    ]
    return groupe["id"]


def test_un_groupe_renomme_garde_ses_droits(client, admin):
    groupe_id = _id(client, admin, "cogeo", "Admin")
    droits = client.get(f"/moduleo/groupes/{groupe_id}/droits", headers=admin).json()

    reponse = client.patch(f"/moduleo/groupes/{groupe_id}", json={"nom": "Direction"}, headers=admin)

    assert reponse.status_code == 200
    assert _groupes(client, admin) == [("cogeo", "Direction"), ("planning", "Admin")]
    assert client.get(f"/moduleo/groupes/{groupe_id}/droits", headers=admin).json() == droits
    assert len(droits) == 153


def test_renommer_vers_un_nom_deja_pris_est_refuse(client, admin):
    groupe_id = _creer(client, admin, "cogeo", "Production").json()["id"]

    reponse = client.patch(f"/moduleo/groupes/{groupe_id}", json={"nom": "Admin"}, headers=admin)

    assert reponse.status_code == 409
    assert _groupes(client, admin) == [("cogeo", "Admin"), ("cogeo", "Production"), ("planning", "Admin")]


def test_renommer_un_groupe_inconnu_est_refuse(client, admin):
    assert client.patch("/moduleo/groupes/999", json={"nom": "X"}, headers=admin).status_code == 404


def test_le_nom_du_groupe_de_dev_est_reserve(client, admin):
    # « Tous droits (dev) » reste hors Panel (ADR-0019).
    groupe_id = _creer(client, admin, "cogeo", "Production").json()["id"]

    assert _creer(client, admin, "cogeo", "Tous droits (dev)").status_code == 422
    assert client.patch(f"/moduleo/groupes/{groupe_id}", json={"nom": "Tous droits (dev)"}, headers=admin).status_code == 422


_CONSULTER_DEVIS = chemin("Devis, factures et avoirs", "Consulter les devis")
_RECHERCHER_CONTACTS = chemin("Contacts", "Rechercher des contacts")
_CREER_TACHE = chemin("Planning", "Créer une tâche")
_CONDITIONS_ACTIVITE = {
    "Avec conditions sur l'activité": {
        "L'activité doit toujours être indiquée": True,
        "L'activité … des activités suivantes": {"operateur": "Fait partie", "activites": ["CHANTIER"]},
    }
}


def _remplacer(client, admin, groupe_id: int, droits: list[dict]):
    return client.put(f"/moduleo/groupes/{groupe_id}/droits", json=droits, headers=admin)


def _droits(client, admin, groupe_id: int) -> list[dict]:
    return client.get(f"/moduleo/groupes/{groupe_id}/droits", headers=admin).json()


def test_les_droits_dun_groupe_sont_remplaces_par_les_cases_cochees(client, admin):
    groupe_id = _id(client, admin, "cogeo", "Admin")

    reponse = _remplacer(client, admin, groupe_id, [{"chemin": _RECHERCHER_CONTACTS}, {"chemin": _CONSULTER_DEVIS}])

    assert reponse.status_code == 200
    assert _droits(client, admin, groupe_id) == [
        {"chemin": _RECHERCHER_CONTACTS, "conditions": None},
        {"chemin": _CONSULTER_DEVIS, "conditions": None},
    ]


def test_un_groupe_planning_recoit_ses_conditions(client, admin):
    groupe_id = _creer(client, admin, "planning", "Prod").json()["id"]

    assert _remplacer(client, admin, groupe_id, [{"chemin": _CREER_TACHE, "conditions": _CONDITIONS_ACTIVITE}]).status_code == 200

    assert _droits(client, admin, groupe_id) == [{"chemin": _CREER_TACHE, "conditions": _CONDITIONS_ACTIVITE}]


@pytest.mark.parametrize(
    ("application", "droit"),
    [
        # Une case absente du catalogue en base : le Panel n'en crée pas.
        ("cogeo", {"chemin": chemin("Contacts", "Droit inventé")}),
        # Une case de l'autre application.
        ("cogeo", {"chemin": _CREER_TACHE}),
        # Une condition que Moduléo ne propose pas sur cette action.
        ("planning", {"chemin": _CREER_TACHE, "conditions": {"Avec conditions sur le créateur": {}}}),
        ("planning", {"chemin": _CREER_TACHE, "conditions": {"Avec conditions sur l'activité": {"Champ inventé": True}}}),
        # Des conditions sur une case Cogeo.
        ("cogeo", {"chemin": _CONSULTER_DEVIS, "conditions": _CONDITIONS_ACTIVITE}),
    ],
)
def test_un_droit_hors_catalogue_est_refuse_sans_rien_changer(application, droit, client, admin):
    groupe_id = _id(client, admin, application, "Admin")
    avant = _droits(client, admin, groupe_id)

    reponse = _remplacer(client, admin, groupe_id, [droit])

    assert reponse.status_code == 422
    assert _droits(client, admin, groupe_id) == avant


def test_les_droits_remplaces_valent_au_tour_suivant(
    client, admin, faux_moduleo, mistral_client_factice, jeton_store, seed_compte, db_session
):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")
    groupe_id = _creer(client, admin, "cogeo", "Production").json()["id"]
    rattacher(db_session, "n.durand", "Production", None, None)
    db_session.commit()
    jeton = jeton_store.emettre("n.durand")
    assert "chercher_contacts_moduleo" not in _outils_proposes(client, mistral_client_factice, jeton)

    _remplacer(client, admin, groupe_id, [{"chemin": _RECHERCHER_CONTACTS}])

    assert "chercher_contacts_moduleo" in _outils_proposes(client, mistral_client_factice, jeton)


def _outils_proposes(client, mistral_client_factice, jeton: str) -> set[str]:
    premier = len(mistral_client_factice.tools_appels_reponse)
    mistral_client_factice.repondre("Bonjour.", "Titre")
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[premier] or []}


def test_un_groupe_sans_rattachement_se_supprime(client, admin):
    groupe_id = _creer(client, admin, "cogeo", "Production").json()["id"]
    _remplacer(client, admin, groupe_id, [{"chemin": _CONSULTER_DEVIS}])

    reponse = client.delete(f"/moduleo/groupes/{groupe_id}", headers=admin)

    assert reponse.status_code == 204
    assert _groupes(client, admin) == [("cogeo", "Admin"), ("planning", "Admin")]
    assert client.get(f"/moduleo/groupes/{groupe_id}/droits", headers=admin).status_code == 404


@pytest.mark.parametrize(("cogeo", "planning", "application"), [("Admin", None, "cogeo"), (None, "Admin", "planning")])
def test_un_groupe_encore_rattache_ne_se_supprime_pas(cogeo, planning, application, client, admin, seed_compte, db_session):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")
    rattacher(db_session, "n.durand", cogeo, planning, None)
    db_session.commit()
    groupe_id = _id(client, admin, application, "Admin")

    reponse = client.delete(f"/moduleo/groupes/{groupe_id}", headers=admin)

    assert reponse.status_code == 409
    assert "n.durand" in reponse.json()["detail"]
    assert (application, "Admin") in _groupes(client, admin)
    assert len(_droits(client, admin, groupe_id)) > 0


def test_supprimer_un_groupe_inconnu_est_refuse(client, admin):
    assert client.delete("/moduleo/groupes/999", headers=admin).status_code == 404


@pytest.mark.parametrize("methode", ["post", "put", "patch", "delete"])
def test_aucune_route_necrit_le_catalogue(methode, client, admin):
    assert client.request(methode, "/moduleo/catalogue", json={}, headers=admin).status_code == 405


_ROUTES = [
    ("get", "/moduleo/catalogue", None),
    ("get", "/moduleo/groupes", None),
    ("post", "/moduleo/groupes", {"application": "cogeo", "nom": "Production"}),
    ("patch", "/moduleo/groupes/1", {"nom": "Production"}),
    ("delete", "/moduleo/groupes/1", None),
    ("get", "/moduleo/groupes/1/droits", None),
    ("put", "/moduleo/groupes/1/droits", []),
]


@pytest.mark.parametrize(("methode", "url", "corps"), _ROUTES)
def test_sans_jeton_refuse(methode, url, corps, client, catalogue):
    assert client.request(methode, url, json=corps).status_code == 401


@pytest.mark.parametrize(("methode", "url", "corps"), _ROUTES)
def test_compte_non_admin_refuse(methode, url, corps, client, catalogue, seed_compte, jeton_store):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")

    reponse = client.request(methode, url, json=corps, headers=_autorisation(jeton_store.emettre("n.durand")))

    assert reponse.status_code == 403
    assert len(client.get("/moduleo/groupes", headers=_autorisation(_admin_jeton(seed_compte, jeton_store))).json()) == 2


def _admin_jeton(seed_compte, jeton_store) -> str:
    seed_compte("a.martin", "secret", "Castries", ["Foncier"], "Alice", "Martin", est_admin=True)
    return jeton_store.emettre("a.martin")
