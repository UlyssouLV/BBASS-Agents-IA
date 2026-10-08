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
            texte = parametres["texte"].lower()
            ids = [
                affaire["IdAffaire"]
                for affaire in self._affaires.values()
                if texte in f"{affaire['Numero']} {affaire['Objet']} {affaire['Adresse'] or ''}".lower()
            ]
            return ids[: parametres.get("nbMaxResultats") or len(ids)]
        if route == "cogeo/affaire/multi?ids={ids}":
            return [self._affaires[i] for i in _ids(parametres) if i in self._affaires]
        if route == "cogeo/affaire/{idAffaire}/intervenants":
            return [i for i, intervenant in self._intervenants.items() if intervenant["IdAffaire"] == parametres["idAffaire"]]
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
