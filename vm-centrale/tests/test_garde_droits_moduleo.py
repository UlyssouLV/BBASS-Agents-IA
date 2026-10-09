import json

import pytest
from sqlalchemy import event

from flux_sse import fin, statuts

from vm_centrale.models import DroitModuleo, GroupeModuleo, GroupeModuleoDroit
from vm_centrale.moduleo.droits import COGEO, PLANNING, chemin, charger_catalogue, rattacher
from vm_centrale.moduleo.droits import garde
from vm_centrale.moduleo.droits.catalogue import FICHIER_CATALOGUE
from vm_centrale.moduleo.routes import ROUTES_GET

# Garde des droits (spec 1.5.1, #188, ADR-0018) : point de passage unique
# du client Moduléo, fermé par défaut, avant tout envoi.

_ADMIN = "cle-admin-de-test"
_AFFAIRES = "chercher_affaires_moduleo"
_CONTACTS = "chercher_contacts_moduleo"
_RECHERCHER_CONTACTS = chemin("Contacts", "Rechercher des contacts")
_COMPTABILITE = chemin("Contacts", "Consulter et modifier le numéro de compte de comptabilité d'un contact")
_REFUS_CONTACTS = (
    "Votre compte n'a pas le droit Moduléo « Rechercher des contacts ». Aucune lecture n'a été faite. "
    "Demandez à un compte administrateur si vous en avez besoin."
)
_NON_AUTORISES = "Codes de comptabilité : non autorisés pour votre compte"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


@pytest.fixture
def compte_du_groupe(db_session):
    # Rattache j.dupont à un groupe Cogeo de test qui n'a que `chemins`.
    def _rattacher(*chemins: str) -> None:
        charger_catalogue(db_session)
        groupe = GroupeModuleo(application=COGEO, nom="Test")
        db_session.add(groupe)
        db_session.flush()
        for droit in db_session.query(DroitModuleo).filter(DroitModuleo.chemin.in_(chemins)):
            db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
        rattacher(db_session, "j.dupont", "Test", None, None)
        db_session.commit()

    return _rattacher


def _envoyer(client, mistral_client_factice, jeton: str, *appels: tuple[str, dict]):
    for outil, arguments in appels:
        mistral_client_factice.repondre_avec_appel_outil(outil, arguments)
    mistral_client_factice.repondre("Voici.", "Titre")
    return client.post("/conversations", json={"message": "Cherche Dupont"}, headers=_autorisation(jeton))


def _contenus_outils(mistral_client_factice) -> list[str]:
    return [
        m["content"] for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]


def _outils_proposes(mistral_client_factice) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[0] or []}


def _echange_outil(client, monkeypatch, jeton: str, conversation_id: int, outil: str) -> dict:
    monkeypatch.setenv("VM_ADMIN_KEY", _ADMIN)
    entetes = {**_autorisation(jeton), "X-Admin-Key": _ADMIN}
    echanges = client.get(f"/inspecteur/conversations/{conversation_id}/echanges", headers=entetes).json()
    (echange,) = [e for e in echanges if e["type_appel"] == f"outil:{outil}"]
    return client.get(f"/inspecteur/echanges/{echange['id']}", headers=entetes).json()


def _dupont(faux_moduleo) -> None:
    faux_moduleo.ajouter_contact(40, "Étude Dupont", type_contact=3, code_comptabilite="411DUP")


# Classement des routes.


def test_toutes_les_routes_get_sont_classees_et_seulement_elles():
    classement = json.loads(garde.FICHIER_CLASSEMENT.read_text(encoding="utf-8"))
    routes = [
        route
        for genre, valeur in classement.items()
        # « siens » (#191) ouvre des routes déjà classées sous leur droit.
        if genre != "siens"
        for route in (valeur if isinstance(valeur, list) else [r for routes in valeur.values() for r in routes])
    ]

    assert sorted(routes) == sorted(ROUTES_GET)
    assert len(routes) == len(set(routes)) == 207


def test_chaque_droit_exige_est_dans_le_catalogue():
    classement = json.loads(garde.FICHIER_CLASSEMENT.read_text(encoding="utf-8"))
    catalogue = json.loads(FICHIER_CATALOGUE.read_text(encoding="utf-8"))["catalogue"]

    def chemins(categorie: str, entrees: list, parents: list[str]):
        for entree in entrees:
            yield chemin(categorie, *parents, entree["libelle"])
            yield from chemins(categorie, entree.get("sous_droits", []), [*parents, entree["libelle"]])

    connus = {c for application in (COGEO, PLANNING) for cat in catalogue[application] for c in chemins(cat["categorie"], cat["droits"], [])}
    assert set(classement["droits"]) <= connus
    assert set(classement["siens"]) <= set(classement["droits"])


# Refus avant tout envoi.


def test_appel_sans_le_droit_refuse_avant_tout_envoi(
    client, faux_moduleo, compte_du_groupe, mistral_client_factice, jeton_valide, monkeypatch
):
    compte_du_groupe(_COMPTABILITE)
    _dupont(faux_moduleo)

    reponse = _envoyer(client, mistral_client_factice, jeton_valide, (_CONTACTS, {"texte": "Dupont"}))

    assert faux_moduleo.appels == []
    assert _contenus_outils(mistral_client_factice) == [_REFUS_CONTACTS]
    detail = _echange_outil(client, monkeypatch, jeton_valide, fin(reponse)["conversation"]["id"], _CONTACTS)
    assert detail["reponse_payload"]["garde_des_droits"] == (
        f"refusé, droit manquant « {_RECHERCHER_CONTACTS} » (cogeo/contact?texte=…)"
    )
    assert detail["reponse_payload"]["routes"] == []
    texte = json.dumps(detail, ensure_ascii=False)
    assert "ApiKey" not in texte and "SecurityCode" not in texte


def test_outil_sans_le_droit_non_propose(client, faux_moduleo, compte_du_groupe, mistral_client_factice, jeton_valide):
    compte_du_groupe(_COMPTABILITE)

    _envoyer(client, mistral_client_factice, jeton_valide)

    proposes = _outils_proposes(mistral_client_factice)
    assert _AFFAIRES in proposes
    assert _CONTACTS not in proposes


def test_route_libre_acceptee_sans_aucun_droit(
    client, faux_moduleo, compte_du_groupe, mistral_client_factice, jeton_valide
):
    # Groupe Cogeo sans aucune case : affaires (groupe exigé) et référentiels
    # (libres) passent.
    compte_du_groupe()
    faux_moduleo.ajouter_site(3, "Castries")
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage", IdSite=3)

    _envoyer(client, mistral_client_factice, jeton_valide, (_AFFAIRES, {"site": "Castries"}))

    assert "moduleo/site?nom={nom}&actifSeulement={actifSeulement}" in faux_moduleo.routes_appelees()
    assert _contenus_outils(mistral_client_factice)[0].startswith("Affaire 2024-123")


def test_route_non_classee_refusee(client, faux_moduleo, mistral_client_factice, jeton_valide, monkeypatch):
    route = next(r for r in ROUTES_GET if r.startswith("cogeo/affaire?texte="))
    monkeypatch.delitem(garde.CLASSEMENT, route)
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage")

    reponse = _envoyer(client, mistral_client_factice, jeton_valide, (_AFFAIRES, {"texte": "Bornage"}))

    assert faux_moduleo.appels == []
    assert _contenus_outils(mistral_client_factice) == [
        "Cette donnée Moduléo n'est ouverte à aucun compte. Aucune lecture n'a été faite."
    ]
    assert _AFFAIRES not in _outils_proposes(mistral_client_factice)
    assert fin(reponse)["reponse"]


def test_route_refusee_en_cours_dappel_ne_part_pas(
    client, faux_moduleo, compte_du_groupe, mistral_client_factice, jeton_valide, monkeypatch
):
    # Le droit de recherche des contacts est là, une route lue ensuite est
    # refusée par le garde : elle ne part pas, phrase fixe.
    compte_du_groupe(_RECHERCHER_CONTACTS)
    _dupont(faux_moduleo)
    faux_moduleo.ajouter_telephone(1, 40, "04 67 98 76 54")
    monkeypatch.setitem(garde.CLASSEMENT, "cogeo/contact/{idContact}/telephones", garde.FERMEE)

    _envoyer(client, mistral_client_factice, jeton_valide, (_CONTACTS, {"texte": "Dupont"}))

    assert "cogeo/contact/{idContact}/telephones" not in faux_moduleo.routes_appelees()
    assert _contenus_outils(mistral_client_factice) == [
        "Cette donnée Moduléo n'est ouverte à aucun compte. Aucune lecture n'a été faite."
    ]


# Lecture des droits une fois par tour.


def test_droits_lus_une_seule_fois_par_tour(client, faux_moduleo, mistral_client_factice, jeton_valide, db_session):
    _dupont(faux_moduleo)
    faux_moduleo.ajouter_affaire(101, "2024-123", "Bornage")
    requetes: list[str] = []

    def compter(conn, cursor, statement, *args):
        if any(table in statement for table in ("rattachements_moduleo", "groupes_moduleo", "droits_moduleo")):
            requetes.append(statement)

    moteur = db_session.get_bind()
    event.listen(moteur, "before_cursor_execute", compter)
    try:
        _envoyer(
            client,
            mistral_client_factice,
            jeton_valide,
            (_CONTACTS, {"texte": "Dupont"}),
            (_AFFAIRES, {"texte": "Bornage"}),
            (_CONTACTS, {"texte": "Dupont"}),
        )
    finally:
        event.remove(moteur, "before_cursor_execute", compter)

    assert len(requetes) == 1
    assert len(_contenus_outils(mistral_client_factice)) == 3


# Vérification par champ.


def test_champ_sans_son_sous_droit_remplace_par_une_mention(
    client, faux_moduleo, compte_du_groupe, mistral_client_factice, jeton_valide
):
    compte_du_groupe(_RECHERCHER_CONTACTS)
    _dupont(faux_moduleo)

    _envoyer(client, mistral_client_factice, jeton_valide, (_CONTACTS, {"texte": "Dupont"}))

    (contenu,) = _contenus_outils(mistral_client_factice)
    assert _NON_AUTORISES in contenu
    assert "411DUP" not in contenu


def test_champ_avec_son_sous_droit_affiche(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _dupont(faux_moduleo)

    _envoyer(client, mistral_client_factice, jeton_valide, (_CONTACTS, {"texte": "Dupont"}))

    (contenu,) = _contenus_outils(mistral_client_factice)
    assert "Code de comptabilité : 411DUP" in contenu
    assert "non autorisés" not in contenu


# Statut par domaine.


@pytest.mark.parametrize(("outil", "domaine"), [(_AFFAIRES, "affaires"), (_CONTACTS, "contacts")])
def test_le_statut_nomme_le_domaine(outil, domaine, client, faux_moduleo, mistral_client_factice, jeton_valide):
    _dupont(faux_moduleo)

    reponse = _envoyer(client, mistral_client_factice, jeton_valide, (outil, {"texte": "Dupont"}))

    assert f"Consultation Moduléo : {domaine}" in statuts(reponse)
