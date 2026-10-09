from typing import Any

from vm_centrale.moduleo.client import ModuleoIntrouvable
from vm_centrale.moduleo.routes import ROUTES_GET

# Faux Moduléo (spec 1.5.0) : injecté à la place de ClientModuleo
# (dependency get_client_moduleo), aucun test ne sort sur le réseau. Mêmes
# routes et même forme de JSON que les exemples du WADL local
# (vm_centrale/moduleo/docs/wadl.xml) ; une route absente de ROUTES_GET
# fait échouer le test, comme le vrai client la refuserait.

_RECHERCHE_AFFAIRES = next(route for route in ROUTES_GET if route.startswith("cogeo/affaire?texte="))
_RECHERCHE_CONTACTS = next(route for route in ROUTES_GET if route.startswith("cogeo/contact?texte="))
_RECHERCHE_DEVIS = next(route for route in ROUTES_GET if route.startswith("cogeo/devis?texte="))
# Limite des routes `multi` (doc Moduléo).
_MULTI_MAX = 200
# Coordonnées d'un contact (#176) : route des ids → (route de la fiche,
# paramètre de chemin, clé du faux).
_COORDONNEES = {
    "cogeo/contact/{idContact}/telephones": ("moduleo/telephone/{idTelephone}", "idTelephone", "telephones"),
    "cogeo/contact/{idContact}/emails": ("cogeo/email/{idEmail}", "idEmail", "emails"),
    "cogeo/contact/{idContact}/adresses": ("moduleo/adresse/{idAdresse}", "idAdresse", "adresses"),
}
_FICHES_COORDONNEES = {fiche: (parametre, cle) for fiche, parametre, cle in _COORDONNEES.values()}


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
        self._qualifications: dict[int, str] = {}
        # Fiches de coordonnées par clé (`telephones`…) et par id ; ids de
        # chaque contact par clé.
        self._coordonnees: dict[str, dict[int, dict]] = {cle: {} for _, _, cle in _COORDONNEES.values()}
        self._coordonnees_contact: dict[int, dict[str, list[int]]] = {}
        self._affaires_contact: dict[int, dict[str, list[int]]] = {}
        self._devis: dict[int, dict] = {}
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

    def ajouter_devis(self, id_devis: int, numero: str, objet: str = "", **champs: Any) -> None:
        # `champs` : les autres clés du devis, au nom du JSON Moduléo
        # (`DateEmission`, `MontantTotalHT`, `IdAffaire`…). Émis : une date
        # d'émission (#189, à confirmer à l'essai réel).
        self._devis[id_devis] = {
            "IdDevis": id_devis,
            "Numero": numero,
            "Objet": objet,
            "Etat": 0,
            "DateCreation": None,
            "DateEmission": None,
            "DateReponse": None,
            "DateExpiration": None,
            "IdAffaire": None,
            "IdResponsable": None,
            "IdRedacteur": None,
            "IdSite": None,
            "IdService": None,
            "MontantTotalHT": 0.0,
            "MontantTotalTVA": 0.0,
            "MontantTotalTTC": 0.0,
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

    def ajouter_contact(
        self,
        id_contact: int,
        nom: str,
        type_contact: int = 1,
        type_donneur_ordre: int = 0,
        qualifications: tuple[int, ...] = (),
        code_comptabilite: str = "",
    ) -> None:
        self._contacts[id_contact] = {
            "IdContact": id_contact,
            "Nom": nom,
            "TypeContact": type_contact,
            "TypeDonneurOrdre": type_donneur_ordre,
            "Qualifications": list(qualifications),
            "MotsCles": "",
            "Commentaire": "",
            "CodeComptabilite": code_comptabilite,
        }

    def ajouter_qualification(self, id_qualification: int, libelle: str) -> None:
        self._qualifications[id_qualification] = libelle

    def ajouter_telephone(self, id_telephone: int, id_contact: int, numero: str, lieu: str = "") -> None:
        fiche = {"IdTelephone": id_telephone, "Numero": numero, "Lieu": lieu}
        self._ajouter_coordonnee("telephones", id_telephone, id_contact, fiche)

    def ajouter_email(self, id_email: int, id_contact: int, adresse: str, lieu: str = "") -> None:
        fiche = {"IdEmail": id_email, "Adresse": adresse, "Lieu": lieu}
        self._ajouter_coordonnee("emails", id_email, id_contact, fiche)

    def ajouter_adresse(
        self, id_adresse: int, id_contact: int, rue: str, lieu: str = "", id_commune: int | None = None
    ) -> None:
        fiche = {"IdAdresse": id_adresse, "Rue": rue, "Lieu": lieu, "IdCommune": id_commune}
        self._ajouter_coordonnee("adresses", id_adresse, id_contact, fiche)

    def lier_affaire(self, id_contact: int, id_affaire: int, role: str = "client") -> None:
        # `role` : « client » (cogeo/contact/{id}/affaires) ou
        # « intervenant » (cogeo/contact/{id}/affaireintervenant).
        self._affaires_contact.setdefault(id_contact, {}).setdefault(role, []).append(id_affaire)

    def _ajouter_coordonnee(self, cle: str, id_coordonnee: int, id_contact: int, fiche: dict) -> None:
        self._coordonnees[cle][id_coordonnee] = fiche
        self._coordonnees_contact.setdefault(id_contact, {}).setdefault(cle, []).append(id_coordonnee)

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
        if route == _RECHERCHE_CONTACTS:
            ids = [i for i, contact in self._contacts.items() if _contact_correspond(contact, parametres)]
            return ids[: parametres.get("nbMaxResultat") or len(ids)]
        if route == "cogeo/qualification/all":
            return [
                {"IdQualification": i, "Libelle": libelle, "Actif": True}
                for i, libelle in self._qualifications.items()
            ]
        if route in _COORDONNEES:
            cle = _COORDONNEES[route][2]
            return self._coordonnees_contact.get(parametres["idContact"], {}).get(cle, [])
        if route in _FICHES_COORDONNEES:
            parametre, cle = _FICHES_COORDONNEES[route]
            if parametres[parametre] not in self._coordonnees[cle]:
                raise ModuleoIntrouvable(f"404 sur {route}")
            return self._coordonnees[cle][parametres[parametre]]
        if route == "cogeo/contact/{idContact}/affaires":
            return self._affaires_contact.get(parametres["idContact"], {}).get("client", [])
        if route == "cogeo/contact/{idContact}/affaireintervenant":
            return self._affaires_contact.get(parametres["idContact"], {}).get("intervenant", [])
        if route == _RECHERCHE_DEVIS:
            return [i for i, devis in self._devis.items() if _devis_correspond(devis, parametres)]
        if route == "cogeo/devis/multi?ids={ids}":
            ids = _ids(parametres)
            assert len(ids) <= _MULTI_MAX, len(ids)
            return [self._devis[i] for i in ids if i in self._devis]
        if route == "cogeo/affaire/{idAffaire}/devis":
            return [i for i, devis in self._devis.items() if devis["IdAffaire"] == parametres["idAffaire"]]
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
    # Comme le vrai serveur (#180) : un nom d'état inconnu est ignoré, sans
    # erreur.
    etat = parametres.get("etatAffaire")
    if etat in _ETATS.values() and _ETATS.get(affaire["Etat"]) != etat:
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


# Filtres de cogeo/devis?… (#189) : paramètre → champ du devis.
_FILTRES_IDS_DEVIS = {"idsService": "IdService", "idsResponsable": "IdResponsable", "idsRedacteur": "IdRedacteur"}
_FILTRES_DATES_DEVIS = {"Emission": "DateEmission", "Reponse": "DateReponse"}


def _devis_correspond(devis: dict, parametres: dict[str, Any]) -> bool:
    if not _contient(f"{devis['Numero']} {devis['Objet']}", parametres.get("texte")):
        return False
    emis = parametres.get("emis")
    if emis is not None and (emis == "true") != bool(devis["DateEmission"]):
        return False
    for parametre, champ in _FILTRES_IDS_DEVIS.items():
        if parametres.get(parametre) is not None and devis[champ] not in _ids({"ids": parametres[parametre]}):
            return False
    for suffixe, champ in _FILTRES_DATES_DEVIS.items():
        jour = (devis[champ] or "")[:10]
        minimum, maximum = parametres.get(f"date{suffixe}Min"), parametres.get(f"date{suffixe}Max")
        if minimum is not None and not (jour and jour >= minimum):
            return False
        if maximum is not None and not (jour and jour <= maximum):
            return False
    return True


def _contact_correspond(contact: dict, parametres: dict[str, Any]) -> bool:
    # Type de contact par nom de l'énumération (« Societe ») ; type de
    # donneur d'ordre comparé tel quel ; une qualification au moins.
    if not _contient(contact["Nom"], parametres.get("texte")):
        return False
    type_contact = parametres.get("typeContact")
    if type_contact in _TYPES_CONTACT.values() and _TYPES_CONTACT.get(contact["TypeContact"]) != type_contact:
        return False
    donneur = parametres.get("typeDonneurOrdreGE")
    if donneur is not None and str(contact["TypeDonneurOrdre"]) != donneur:
        return False
    qualifications = parametres.get("idsQualifications")
    if qualifications is not None and not set(contact["Qualifications"]) & set(_ids({"ids": qualifications})):
        return False
    return True


# Entier du JSON → nom de l'énumération en filtre, relevés sur le serveur
# du cabinet (scripts/relever_enumerations_moduleo.py, #180).
_TYPES_CONTACT = {1: "Personne", 3: "Societe", 4: "Collectivite", 5: "GroupeContacts"}
_ETATS = {
    1: "Production",
    2: "Cloturee",
    4: "Creee",
    5: "Terminee",
    6: "Annulee",
    7: "Acceptee",
    8: "EnAttente",
    9: "Suspendue",
}
