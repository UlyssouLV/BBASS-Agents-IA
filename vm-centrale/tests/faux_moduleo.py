from typing import Any

from vm_centrale.moduleo.client import ModuleoIntrouvable
from vm_centrale.moduleo.routes import ROUTES_GET

# Faux Moduléo (spec 1.5.0) : injecté à la place de ClientModuleo
# (dependency get_client_moduleo), aucun test ne sort sur le réseau. Mêmes
# routes et même forme de JSON que les exemples du WADL local
# (vm_centrale/moduleo/docs/wadl.xml) ; une route absente de ROUTES_GET
# fait échouer le test, comme le vrai client la refuserait.

_RECHERCHE_AFFAIRES = next(route for route in ROUTES_GET if route.startswith("cogeo/affaire?texte="))


class FauxModuleo:
    def __init__(self) -> None:
        # (route, paramètres) de chaque lecture, dans l'ordre.
        self.appels: list[tuple[str, dict[str, Any]]] = []
        self._affaires: dict[int, dict] = {}
        self._intervenants: dict[int, dict] = {}
        self._utilisateurs: dict[int, dict] = {}
        self._contacts: dict[int, dict] = {}
        self._communes: dict[int, dict] = {}
        self._sites: dict[int, str] = {}
        self._services: dict[int, str] = {}
        self._dossiers_production: dict[int, str] = {}
        self._exception: Exception | None = None

    def echouer(self, exception: Exception) -> None:
        # Toute lecture suivante lève `exception` (panne, refus).
        self._exception = exception

    def ajouter_affaire(self, id_affaire: int, numero: str, objet: str = "", **champs: Any) -> None:
        # `champs` : les autres clés de l'affaire, au nom du JSON Moduléo
        # (`Etat`, `DateOuverture`, `IdResponsable`…).
        self._affaires[id_affaire] = {
            "IdAffaire": id_affaire,
            "Numero": numero,
            "Objet": objet,
            "Etat": None,
            "DateCreation": None,
            "DateOuverture": None,
            "DateCloture": None,
            "DateLivraison": None,
            "Adresse": None,
            "IdCommune": None,
            "IdClient": None,
            "QualiteClient": None,
            "IdRepresentant": None,
            "QualiteRepresentant": None,
            "IdResponsable": None,
            "IdActeurEnCharge": None,
            "IdSite": None,
            "IdService": None,
            "IdDossierProduction": None,
            **champs,
        }

    def ajouter_intervenant(
        self,
        id_intervenant: int,
        id_affaire: int,
        id_contact: int,
        qualite: str,
        id_representant: int | None = None,
        qualite_representant: str = "",
    ) -> None:
        self._intervenants[id_intervenant] = {
            "IdIntervenant": id_intervenant,
            "IdContact": id_contact,
            "IdRepresentant": id_representant,
            "IdAffaire": id_affaire,
            "QualiteIntervenant": qualite,
            "QualiteRepresentant": qualite_representant,
        }

    def ajouter_utilisateur(
        self, id_utilisateur: int, prenom: str, nom: str, tel_fixe: str = "", tel_portable: str = "", email: str = ""
    ) -> None:
        self._utilisateurs[id_utilisateur] = {
            "IdUtilisateur": id_utilisateur,
            "Nom": nom,
            "Prenom": prenom,
            "Actif": True,
            "Email": email,
            "TelFixe": tel_fixe,
            "TelPortable": tel_portable,
            "IdService": 1,
            "IdSite": 1,
        }

    def ajouter_contact(self, id_contact: int, nom: str) -> None:
        self._contacts[id_contact] = {"IdContact": id_contact, "Nom": nom, "TypeContact": 1, "Qualifications": []}

    def ajouter_commune(self, id_commune: int, nom: str, code_postal: str) -> None:
        self._communes[id_commune] = {
            "IdCommune": id_commune,
            "Nom": nom,
            "CodePostal": code_postal,
            "Insee": "",
            "Pays": "France",
        }

    def ajouter_site(self, id_site: int, nom: str) -> None:
        self._sites[id_site] = nom

    def ajouter_service(self, id_service: int, nom: str) -> None:
        self._services[id_service] = nom

    def ajouter_dossier_production(self, id_dossier: int, nom: str) -> None:
        self._dossiers_production[id_dossier] = nom

    def routes_appelees(self) -> list[str]:
        return [route for route, _ in self.appels]

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        parametres = parametres or {}
        assert route in ROUTES_GET, route
        self.appels.append((route, parametres))
        if self._exception is not None:
            raise self._exception
        if route == "cogeo/affaire/numeroAffaire?numAffaire={numAffaire}":
            for affaire in self._affaires.values():
                if affaire["Numero"] == parametres["numAffaire"]:
                    return affaire["IdAffaire"]
            raise ModuleoIntrouvable(f"404 sur {route}")
        if route == _RECHERCHE_AFFAIRES:
            ids = [i for i, affaire in self._affaires.items() if _correspond(affaire, parametres)]
            return ids[: parametres.get("nbMaxResultats") or len(ids)]
        if route == "moduleo/utilisateur?nom={nom}&prenom={prenom}&actifSeulement={actifSeulement}":
            return [
                i
                for i, utilisateur in self._utilisateurs.items()
                if _contient(utilisateur["Nom"], parametres.get("nom"))
                and _contient(utilisateur["Prenom"], parametres.get("prenom"))
            ]
        if route == "moduleo/site?nom={nom}&actifSeulement={actifSeulement}":
            return [i for i, nom in self._sites.items() if _contient(nom, parametres.get("nom"))]
        if route == "moduleo/service?nom={nom}&actifSeulement={actifSeulement}":
            return [i for i, nom in self._services.items() if _contient(nom, parametres.get("nom"))]
        if route == "fileo/dossierproduction?texteRecherche={texteRecherche}":
            return [
                i for i, nom in self._dossiers_production.items() if _contient(nom, parametres["texteRecherche"])
            ]
        if route == "fileo/dossierproduction/{idDossierProduction}":
            id_dossier = parametres["idDossierProduction"]
            if id_dossier not in self._dossiers_production:
                raise ModuleoIntrouvable(f"404 sur {route}")
            return {"IdDossierProduction": id_dossier, "Nom": self._dossiers_production[id_dossier]}
        if route == "cogeo/affaire/multi?ids={ids}":
            return [self._affaires[i] for i in _ids(parametres) if i in self._affaires]
        if route == "cogeo/affaire/{idAffaire}/intervenants":
            return [
                i for i, intervenant in self._intervenants.items() if intervenant["IdAffaire"] == parametres["idAffaire"]
            ]
        if route == "cogeo/intervenant/multi?ids={ids}":
            return [self._intervenants[i] for i in _ids(parametres) if i in self._intervenants]
        if route == "moduleo/utilisateur/{idUtilisateur}":
            if parametres["idUtilisateur"] not in self._utilisateurs:
                raise ModuleoIntrouvable(f"404 sur {route}")
            return self._utilisateurs[parametres["idUtilisateur"]]
        if route == "cogeo/contact/multi?ids={ids}":
            return [self._contacts[i] for i in _ids(parametres) if i in self._contacts]
        if route == "moduleo/commune/multi?ids={ids}":
            return [self._communes[i] for i in _ids(parametres) if i in self._communes]
        raise AssertionError(f"Route non simulée par le faux Moduléo : {route}")


def _ids(parametres: dict[str, Any]) -> list[int]:
    # Séparateur entre les ids : la virgule (doc Moduléo, routes `multi`).
    return [int(i) for i in str(parametres["ids"]).split(",") if i]


def _contient(valeur: str, recherche: str | None) -> bool:
    # Recherche par nom du faux : sans casse, sur une partie du nom.
    return not recherche or recherche.lower() in valeur.lower()


# Filtres de cogeo/affaire?… (#175) : paramètre → champ de l'affaire.
_FILTRES_IDS = {
    "idsSite": "IdSite",
    "idsService": "IdService",
    "idsResponsable": "IdResponsable",
    "idsActeurEnCharge": "IdActeurEnCharge",
}
_FILTRES_DATES = {
    "Creation": "DateCreation",
    "Ouverture": "DateOuverture",
    "Livraison": "DateLivraison",
    "Cloture": "DateCloture",
}


def _correspond(affaire: dict, parametres: dict[str, Any]) -> bool:
    texte = parametres.get("texte")
    if texte and not _contient(f"{affaire['Numero']} {affaire['Objet']} {affaire['Adresse'] or ''}", texte):
        return False
    if parametres.get("etatAffaire") is not None and str(affaire["Etat"]) != parametres["etatAffaire"]:
        return False
    dossier = parametres.get("idDossierProduction")
    if dossier is not None and affaire["IdDossierProduction"] != dossier:
        return False
    for parametre, champ in _FILTRES_IDS.items():
        if parametres.get(parametre) is not None and affaire[champ] not in _ids({"ids": parametres[parametre]}):
            return False
    for suffixe, champ in _FILTRES_DATES.items():
        jour = (affaire[champ] or "")[:10]
        minimum, maximum = parametres.get(f"date{suffixe}Min"), parametres.get(f"date{suffixe}Max")
        if minimum is not None and not (jour and jour >= minimum):
            return False
        if maximum is not None and not (jour and jour <= maximum):
            return False
    return True
