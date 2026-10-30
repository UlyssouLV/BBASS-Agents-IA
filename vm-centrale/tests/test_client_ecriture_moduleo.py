import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from faux_moduleo import URL_SERVEUR_DE_TEST, FauxModuleo

from vm_centrale.moduleo import client as client_module
from vm_centrale.moduleo.client import (
    ClientModuleo,
    ModuleoDonneesRefusees,
    ModuleoIndisponible,
    ModuleoIntrouvable,
    ModuleoRefuse,
    RequeteInterdite,
    TransportHttp,
)
from vm_centrale.moduleo.droits import GROUPE_DEV, DroitManquant, DroitsModuleo, chemin
from vm_centrale.moduleo.droits import garde
from vm_centrale.moduleo.routes import ROUTES_ECRITURE

# Client d'écriture Moduléo (spec 1.5.2, #202, ADR-0023) : `ecrire()`
# n'envoie que vers un serveur de test listé, `MODULEO_ECRITURE` actif,
# après le garde des droits. Aucun accès réseau.

_DOCS = Path(client_module.__file__).parent / "docs"
_SERVEUR_DU_CABINET = "https://mwa-bbass.kipaware.fr/api"
_WADL = "{http://wadl.dev.java.net/2009/02}"


def _routes_ecriture_du_wadl() -> dict[tuple[str, str], str | None]:
    # (méthode, gabarit sans « api/ ») → exemple de corps JSON, ou None.
    routes = {}
    for ressource in ET.parse(_DOCS / "wadl.xml").getroot().iter(f"{_WADL}resource"):
        for methode in ressource.findall(f"{_WADL}method"):
            if methode.get("name") == "GET":
                continue
            requete = methode.find(f"{_WADL}request")
            exemple = next(
                (
                    representation.findtext(f"{_WADL}doc")
                    for representation in (requete if requete is not None else [])
                    if representation.get("mediaType") == "application/json"
                ),
                None,
            )
            routes[(methode.get("name", ""), ressource.get("path", "").removeprefix("api/"))] = exemple
    return routes


def test_routes_ecriture_contient_exactement_les_routes_post_put_delete_du_wadl_versionne():
    du_wadl = _routes_ecriture_du_wadl()

    assert set(ROUTES_ECRITURE) == set(du_wadl)
    assert len(ROUTES_ECRITURE) == 86
    assert sorted(m for m, _ in ROUTES_ECRITURE) == sorted(["POST"] * 39 + ["PUT"] * 32 + ["DELETE"] * 15)
    for (methode, route), exemple in du_wadl.items():
        decrite = ROUTES_ECRITURE[(methode, route)]
        assert (decrite.methode, decrite.route) == (methode, route)
        assert decrite.exemple == exemple
        if exemple is not None:
            json.loads(exemple)


def test_route_ecriture_porte_ses_parametres_types_et_sa_description():
    telephone = ROUTES_ECRITURE[("PUT", "moduleo/telephone/{idTelephone}")]
    archive = ROUTES_ECRITURE[("PUT", "cogeo/archive?idArchive={idArchive}&idAffaire={idAffaire}")]

    assert telephone.parametres == {"idTelephone": "int"}
    assert archive.parametres == {"idArchive": "int", "idAffaire": "int"}
    assert ROUTES_ECRITURE[("POST", "moduleo/telephone")].description == "Crée un numéro de téléphone."
    assert ROUTES_ECRITURE[("DELETE", "moduleo/telephone/{idTelephone}")].exemple is None


# Barrière avant envoi.

_TELEPHONE = {"IdContact": 40, "Numero": "04 67 00 00 00", "Lieu": "Bureau"}
_CONTACTS = DroitsModuleo(groupe_cogeo=GROUPE_DEV, droits=frozenset({chemin("Contacts", "Rechercher des contacts")}))


@pytest.fixture
def ecriture_active(monkeypatch):
    monkeypatch.setenv("MODULEO_ECRITURE", "1")


def _rien_recu(faux: FauxModuleo) -> bool:
    return faux.appels == [] and faux.ecritures == []


@pytest.mark.parametrize(
    ("methode", "route", "parametres", "corps"),
    [
        # Route inconnue, ou route de lecture.
        ("POST", "moduleo/inconnue", {}, _TELEPHONE),
        ("POST", "api/moduleo/telephone", {}, _TELEPHONE),
        ("GET", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, None),
        # Méthode qui ne correspond pas à la route.
        ("PATCH", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE),
        ("POST", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE),
        ("DELETE", "moduleo/telephone", {}, None),
        # Paramètre manquant (de chemin ou de requête) ou inconnu.
        ("PUT", "moduleo/telephone/{idTelephone}", {}, _TELEPHONE),
        ("PUT", "moduleo/telephone/{idTelephone}", {"idTelephone": None}, _TELEPHONE),
        ("PUT", "cogeo/archive?idArchive={idArchive}&idAffaire={idAffaire}", {"idArchive": 3}, None),
        ("DELETE", "moduleo/telephone/{idTelephone}", {"idTelephone": 7, "autre": 1}, None),
        # Corps absent d'une route qui en attend un, ou corps sur une route sans corps.
        ("POST", "moduleo/telephone", {}, None),
        ("DELETE", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE),
    ],
)
def test_route_methode_parametres_ou_corps_incoherents_refuses_sans_rien_envoyer(
    ecriture_active, methode, route, parametres, corps
):
    faux = FauxModuleo()

    with pytest.raises(RequeteInterdite):
        ClientModuleo(faux).ecrire(methode, route, parametres, corps, _CONTACTS)

    assert _rien_recu(faux)


@pytest.mark.parametrize("valeur", [None, "", "0", "non", "false"])
def test_ecriture_inactive_refusee_sans_rien_envoyer(monkeypatch, valeur):
    if valeur is not None:
        monkeypatch.setenv("MODULEO_ECRITURE", valeur)
    faux = FauxModuleo()

    with pytest.raises(RequeteInterdite, match="MODULEO_ECRITURE"):
        ClientModuleo(faux).ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _CONTACTS)

    assert _rien_recu(faux)


@pytest.mark.parametrize("url", [_SERVEUR_DU_CABINET, f"{_SERVEUR_DU_CABINET}/", "https://autre.exemple/api"])
def test_serveur_hors_de_la_liste_des_serveurs_de_test_refuse_sans_rien_envoyer(ecriture_active, url):
    # Le serveur du cabinet n'est pas un serveur de test : aucune écriture,
    # même MODULEO_ECRITURE actif.
    faux = FauxModuleo(url=url)

    with pytest.raises(RequeteInterdite, match="serveur"):
        ClientModuleo(faux).ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _CONTACTS)

    assert _rien_recu(faux)


def test_ecriture_autorisee_envoyee_une_fois_au_serveur_de_test(ecriture_active):
    faux = FauxModuleo()
    faux.reponse_ecriture = 812

    resultat = ClientModuleo(faux).ecrire(
        "PUT", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE, _CONTACTS
    )

    assert resultat == 812
    assert faux.ecritures == [("PUT", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE)]
    assert faux.appels == []


# Classement des routes d'écriture.


def _classement_ecriture() -> dict:
    return json.loads(garde.FICHIER_CLASSEMENT.read_text(encoding="utf-8"))["ecriture"]


def test_toutes_les_routes_ecriture_sont_classees_une_fois_et_seulement_elles():
    classement = _classement_ecriture()
    cles = [
        *classement["libre"],
        *classement["groupe_cogeo"],
        *classement["groupe_planning"],
        *(cle for cles in classement["droits"].values() for cle in cles),
        *classement["fermee"],
    ]

    assert sorted(cles) == sorted(f"{methode} {route}" for methode, route in ROUTES_ECRITURE)
    assert len(cles) == len(set(cles)) == 86


def test_routes_fermees_portent_leur_raison_dont_webhook_envoi_de_fichier_et_procedures():
    fermees = _classement_ecriture()["fermee"]

    assert {"POST webhook", "DELETE webhook", "POST fileo/fichier/upload", "POST cogeo/procedureapplication"} <= set(
        fermees
    )
    assert all(raison.strip() for raison in fermees.values())


def test_route_ecriture_non_classee_refusee_sans_rien_envoyer(ecriture_active, monkeypatch):
    # Une route ajoutée au WADL par telecharger_doc_moduleo.py, pas encore classée.
    non_classee = {k: v for k, v in garde.CLASSEMENT_ECRITURE.items() if k != ("POST", "moduleo/telephone")}
    monkeypatch.setattr(garde, "CLASSEMENT_ECRITURE", non_classee)
    faux = FauxModuleo()

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _TOUS_DROITS)

    assert refus.value.refus == "refusé, route non classée (POST moduleo/telephone)"
    assert _rien_recu(faux)


# Garde des droits.

# Tous les droits exigés par une route d'écriture.
_TOUS_DROITS = DroitsModuleo(
    groupe_cogeo=GROUPE_DEV, groupe_planning=GROUPE_DEV, droits=frozenset(_classement_ecriture()["droits"])
)
_TEMPS_PASSES_DES_AUTRES = chemin(
    "Temps passés et frais des temps passés",
    "Consulter les temps passés et les frais des temps passés des autres collaborateurs",
    "Créer, modifier et supprimer les temps passés et les frais des temps passés des autres collaborateurs",
)
_TEMPS_PASSE = {"Date": "2026-10-26T00:00:00", "NombreHeure": 3.5, "IdAffaire": 12, "IdCodeActivite": 4}
# Jean Martin, utilisateur Moduléo 7, lié au compte ; 8 est un autre collaborateur.
_SANS_LES_AUTRES = DroitsModuleo(groupe_cogeo=GROUPE_DEV, id_utilisateur_moduleo=7)


def test_ecriture_sans_le_droit_refusee_avant_envoi_avec_la_phrase_fixe(ecriture_active):
    faux = FauxModuleo()

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire(
            "PUT", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _TELEPHONE,
            DroitsModuleo(groupe_cogeo=GROUPE_DEV),
        )

    assert refus.value.phrase == (
        "Votre compte n'a pas le droit Moduléo « Rechercher des contacts ». Rien n'a été écrit. "
        "Demandez à un compte administrateur si vous en avez besoin."
    )
    assert refus.value.refus == (
        "refusé, droit manquant « Contacts › Rechercher des contacts » (PUT moduleo/telephone/{idTelephone})"
    )
    assert _rien_recu(faux)


def test_tache_du_planning_sans_groupe_planning_refusee_avant_envoi(ecriture_active):
    faux = FauxModuleo()

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire(
            "DELETE", "planning/tacheplanning/{idTachePlanning}", {"idTachePlanning": 3}, None,
            DroitsModuleo(groupe_cogeo=GROUPE_DEV),
        )

    assert refus.value.refus == "refusé, groupe Planning manquant"
    assert _rien_recu(faux)


@pytest.mark.parametrize(
    ("methode", "route", "parametres", "corps"),
    [
        ("POST", "webhook", {}, {"Adresse": "https://bbass.local/", "CleSecurite": "x", "EvenementsEcoutes": [10]}),
        ("DELETE", "webhook", {}, None),
        ("POST", "fileo/fichier/upload", {}, None),
        ("POST", "cogeo/procedureapplication", {}, {}),
    ],
)
def test_route_fermee_refusee_meme_avec_tous_les_droits(ecriture_active, methode, route, parametres, corps):
    faux = FauxModuleo()

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire(methode, route, parametres, corps, _TOUS_DROITS)

    assert refus.value.phrase == "Cette écriture Moduléo n'est ouverte à aucun compte. Rien n'a été écrit."
    assert refus.value.refus.startswith("refusé, route fermée")
    assert _rien_recu(faux)


def test_son_propre_temps_passe_accepte_sans_le_droit_des_autres(ecriture_active):
    faux = FauxModuleo()
    corps = {**_TEMPS_PASSE, "IdUtilisateur": 7}

    ClientModuleo(faux).ecrire("POST", "cogeo/tempspasse", {}, corps, _SANS_LES_AUTRES)

    assert faux.ecritures == [("POST", "cogeo/tempspasse", {}, corps)]


@pytest.mark.parametrize(
    "droits",
    [
        _SANS_LES_AUTRES,
        # Sans utilisateur Moduléo lié, aucun temps passé n'est « le sien ».
        DroitsModuleo(groupe_cogeo=GROUPE_DEV),
    ],
)
def test_temps_passe_d_un_autre_refuse_sans_le_droit_des_autres(ecriture_active, droits):
    faux = FauxModuleo()

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire("POST", "cogeo/tempspasse", {}, {**_TEMPS_PASSE, "IdUtilisateur": 8}, droits)

    assert refus.value.refus.startswith(f"refusé, droit manquant « {_TEMPS_PASSES_DES_AUTRES} »")
    assert _rien_recu(faux)


def test_temps_passe_d_un_autre_accepte_avec_le_droit_des_autres(ecriture_active):
    faux = FauxModuleo()
    droits = DroitsModuleo(groupe_cogeo=GROUPE_DEV, droits=frozenset({_TEMPS_PASSES_DES_AUTRES}))

    ClientModuleo(faux).ecrire("POST", "cogeo/tempspasse", {}, {**_TEMPS_PASSE, "IdUtilisateur": 8}, droits)

    assert len(faux.ecritures) == 1


def test_modifier_ou_supprimer_son_temps_passe_relit_l_existant_puis_ecrit(ecriture_active):
    faux = FauxModuleo()
    faux.ajouter_temps_passe(31, "2026-10-26T00:00:00", 3.5, 7)
    client = ClientModuleo(faux)

    client.ecrire(
        "PUT", "cogeo/tempspasse/{idTempsPasse}", {"idTempsPasse": 31}, {**_TEMPS_PASSE, "IdUtilisateur": 7},
        _SANS_LES_AUTRES,
    )
    client.ecrire("DELETE", "cogeo/tempspasse/{idTempsPasse}", {"idTempsPasse": 31}, None, _SANS_LES_AUTRES)

    assert [(m, p) for m, _, p, _ in faux.ecritures] == [("PUT", {"idTempsPasse": 31}), ("DELETE", {"idTempsPasse": 31})]


@pytest.mark.parametrize(
    ("methode", "corps"),
    [
        ("PUT", {**_TEMPS_PASSE, "IdUtilisateur": 7}),
        ("DELETE", None),
    ],
)
def test_modifier_ou_supprimer_le_temps_passe_d_un_autre_refuse_sans_rien_ecrire(ecriture_active, methode, corps):
    faux = FauxModuleo()
    faux.ajouter_temps_passe(32, "2026-10-26T00:00:00", 2.0, 8)

    with pytest.raises(DroitManquant) as refus:
        ClientModuleo(faux).ecrire(
            methode, "cogeo/tempspasse/{idTempsPasse}", {"idTempsPasse": 32}, corps, _SANS_LES_AUTRES
        )

    assert refus.value.refus.startswith(f"refusé, droit manquant « {_TEMPS_PASSES_DES_AUTRES} »")
    assert faux.ecritures == []


def test_supprimer_un_temps_passe_introuvable_refuse_sans_rien_ecrire(ecriture_active):
    faux = FauxModuleo()

    with pytest.raises(DroitManquant):
        ClientModuleo(faux).ecrire(
            "DELETE", "cogeo/tempspasse/{idTempsPasse}", {"idTempsPasse": 99}, None, _SANS_LES_AUTRES
        )

    assert faux.ecritures == []


# Requête HTTP vers le serveur de test.


def _client_http(monkeypatch, gestionnaire, url: str = URL_SERVEUR_DE_TEST) -> ClientModuleo:
    monkeypatch.setattr(
        client_module, "_http_client", httpx.Client(transport=httpx.MockTransport(gestionnaire))
    )
    return ClientModuleo(TransportHttp(url, "cle-api", "code-securite"))


def _enregistreur(requetes: list[httpx.Request], reponse: httpx.Response):
    def _gestionnaire(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        return reponse

    return _gestionnaire


def test_ecriture_envoie_methode_route_et_corps_avec_les_en_tetes(ecriture_active, monkeypatch):
    requetes: list[httpx.Request] = []
    client = _client_http(monkeypatch, _enregistreur(requetes, httpx.Response(200, json=812)))

    resultat = client.ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _CONTACTS)

    assert resultat == 812
    (requete,) = requetes
    assert requete.method == "POST"
    assert str(requete.url) == "https://mwa-kpw-api.kipaware.fr/api/moduleo/telephone"
    assert json.loads(requete.content) == _TELEPHONE
    assert requete.headers["ApiKey"] == "cle-api"
    assert requete.headers["SecurityCode"] == "code-securite"


def test_ecriture_sans_corps_envoie_les_parametres_de_chemin_et_de_requete(ecriture_active, monkeypatch):
    requetes: list[httpx.Request] = []
    client = _client_http(monkeypatch, _enregistreur(requetes, httpx.Response(204)))
    droits = DroitsModuleo(
        groupe_cogeo=GROUPE_DEV,
        droits=frozenset({chemin("Affaires, groupes et archivage", "Changer l'archive d'une affaire")}),
    )

    resultat = client.ecrire(
        "PUT", "cogeo/archive?idArchive={idArchive}&idAffaire={idAffaire}", {"idArchive": 3, "idAffaire": 12}, None, droits
    )

    assert resultat is None
    (requete,) = requetes
    assert requete.method == "PUT"
    assert requete.url.path == "/api/cogeo/archive"
    assert dict(requete.url.params) == {"idArchive": "3", "idAffaire": "12"}
    assert requete.content == b""


def test_ecriture_vers_le_serveur_du_cabinet_refusee_sans_requete(ecriture_active, monkeypatch):
    requetes: list[httpx.Request] = []
    client = _client_http(monkeypatch, _enregistreur(requetes, httpx.Response(200)), url=_SERVEUR_DU_CABINET)

    with pytest.raises(RequeteInterdite):
        client.ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _CONTACTS)

    assert requetes == []
    assert not client.ecriture_ouverte()


def test_donnees_refusees_par_moduleo_levent_son_message(ecriture_active, monkeypatch):
    client = _client_http(
        monkeypatch, lambda _: httpx.Response(400, json={"Message": "Le numéro de téléphone est obligatoire."})
    )

    with pytest.raises(ModuleoDonneesRefusees) as erreur:
        client.ecrire("POST", "moduleo/telephone", {}, {"IdContact": 40}, _CONTACTS)

    assert erreur.value.message == "Le numéro de téléphone est obligatoire."


@pytest.mark.parametrize("statut", [401, 403])
def test_refus_de_moduleo_sur_une_ecriture_levent_son_message_sans_cle_ni_code(ecriture_active, monkeypatch, statut):
    # #260 : la carte dit pourquoi Moduléo refuse ; la clé et le code, s'il
    # les répétait, n'en sortent pas.
    message = "Id ne peut pas être null ou égal à 0 (clé cle-api, code code-securite)"
    client = _client_http(monkeypatch, lambda _: httpx.Response(statut, json={"Message": message}))

    with pytest.raises(ModuleoRefuse) as erreur:
        client.ecrire("POST", "moduleo/telephone", {}, _TELEPHONE, _CONTACTS)

    assert erreur.value.message == "Id ne peut pas être null ou égal à 0 (clé …, code …)"


def _delai_depasse(requete: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("délai dépassé", request=requete)


@pytest.mark.parametrize(
    ("gestionnaire", "erreur"),
    [
        (lambda _: httpx.Response(401, text="Clé refusée"), ModuleoRefuse),
        (lambda _: httpx.Response(403, text="Accès refusé"), ModuleoRefuse),
        (lambda _: httpx.Response(404, text="Introuvable"), ModuleoIntrouvable),
        (lambda _: httpx.Response(500, text="Erreur serveur"), ModuleoIndisponible),
        (_delai_depasse, ModuleoIndisponible),
    ],
)
def test_erreurs_moduleo_traduites_comme_en_lecture_sans_nouvelle_tentative(
    ecriture_active, monkeypatch, gestionnaire, erreur
):
    requetes: list[httpx.Request] = []

    def _compter(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        return gestionnaire(requete)

    client = _client_http(monkeypatch, _compter)

    with pytest.raises(erreur):
        client.ecrire("DELETE", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, None, _CONTACTS)

    assert len(requetes) == 1


def test_lire_refuse_toujours_toute_methode_autre_que_get(ecriture_active):
    faux = FauxModuleo()

    with pytest.raises(RequeteInterdite):
        ClientModuleo(faux).envoyer("PUT", "moduleo/telephone/{idTelephone}", {"idTelephone": 7}, _CONTACTS)

    assert _rien_recu(faux)
