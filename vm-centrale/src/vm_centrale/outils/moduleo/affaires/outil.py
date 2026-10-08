from datetime import datetime
from typing import Any

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo.client import LecteurModuleo, ModuleoIntrouvable
from vm_centrale.moduleo.fiches import fiche_affaire, reference_affaire
from vm_centrale.moduleo.resolution import (
    Noms,
    NomNonResolu,
    chercher_dossier_production,
    chercher_services,
    chercher_sites,
    chercher_utilisateur,
    resoudre_communes,
    resoudre_contacts,
    resoudre_utilisateurs,
)
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import (
    IDS_MAX,
    NB_DEFAUT,
    NB_PLAFOND,
    liste_ids,
    lire_argument,
    lire_fiches,
    nb_max,
)

_NOM = "chercher_affaires_moduleo"

_ROUTE_NUMERO = "cogeo/affaire/numeroAffaire?numAffaire={numAffaire}"
_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/affaire?texte="))
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"
_ROUTE_INTERVENANTS_AFFAIRE = "cogeo/affaire/{idAffaire}/intervenants"
_ROUTE_INTERVENANTS = "cogeo/intervenant/multi?ids={ids}"

_AUCUNE_AFFAIRE = "Aucune affaire Moduléo ne correspond à cette recherche."
_TROUVEES = "{n} affaires trouvées, {m} affichées"
_RIEN_A_CHERCHER = "Donne un numéro d'affaire, un texte ou un filtre à chercher dans Moduléo."

# Filtres de dates (#175) : argument du modèle → paramètre de cogeo/affaire?…
_EVENEMENTS = {
    "creation": ("Creation", "de création"),
    "ouverture": ("Ouverture", "d'ouverture"),
    "livraison": ("Livraison", "de livraison"),
    "cloture": ("Cloture", "de clôture"),
}
_DATES = {
    f"date_{evenement}_{borne}": f"date{api}{borne.capitalize()}"
    for evenement, (api, _) in _EVENEMENTS.items()
    for borne in ("min", "max")
}
# Formats de date acceptés du modèle ; l'API reçoit AAAA-MM-JJ.
_FORMATS_DATE = ("%Y-%m-%d", "%d/%m/%Y")
# Filtres en noms, résolus en ids par la VM.
_NOMS = ("site", "service", "suivi_par", "responsable", "charge_affaire", "dossier_production")

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des affaires dans Moduléo, le logiciel de gestion du cabinet, "
            "par numéro, par texte ou par filtres combinables (état, dates, site, service, "
            "collaborateur qui suit l'affaire, dossier de production), donnés en noms tels "
            "que le collaborateur les dit. Renvoie une fiche par affaire : numéro, objet, "
            "état, dates, adresse, commune, client, représentant, responsable, "
            "chargé d'affaire et intervenants avec leur qualité. À utiliser pour "
            "toute question sur une affaire du cabinet : ces données ne sont pas "
            "sur Internet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {
                    "type": "string",
                    "description": (
                        "Le numéro exact de l'affaire (ex. « 2024-123 »), s'il est connu ; "
                        "les autres paramètres sont alors ignorés."
                    ),
                },
                "texte": {
                    "type": "string",
                    "description": (
                        "Sans numéro : un mot de l'objet, de l'adresse ou du client de l'affaire, "
                        "facultatif avec des filtres."
                    ),
                },
                "etat": {
                    "type": "string",
                    "description": "État de l'affaire tel que Moduléo le nomme (ex. « Production »).",
                },
                **{
                    argument: {
                        "type": "string",
                        "description": (
                            f"Date {_EVENEMENTS[argument.split('_')[1]][1]} "
                            f"{'au plus tôt' if argument.endswith('_min') else 'au plus tard'}, "
                            "au format AAAA-MM-JJ."
                        ),
                    }
                    for argument in _DATES
                },
                "site": {"type": "string", "description": "Nom du site (agence) du cabinet."},
                "service": {"type": "string", "description": "Nom du service du cabinet."},
                "suivi_par": {
                    "type": "string",
                    "description": (
                        "Nom et / ou prénom d'un collaborateur : les affaires dont il est "
                        "responsable ou chargé d'affaire (« quelles affaires suit Martin ? »). "
                        "Remplace responsable et charge_affaire."
                    ),
                },
                "responsable": {
                    "type": "string",
                    "description": "Nom et / ou prénom du responsable de l'affaire, seulement.",
                },
                "charge_affaire": {
                    "type": "string",
                    "description": "Nom et / ou prénom du chargé d'affaire, seulement.",
                },
                "dossier_production": {
                    "type": "string",
                    "description": "Nom du dossier de production de l'affaire.",
                },
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de fiches voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus."
                    ),
                },
            },
        },
    },
}


def _declarer(contexte: ContexteTour) -> dict | None:
    # Pour tous les comptes, dès que Moduléo est configuré (spec 1.5.0).
    return _SCHEMA if contexte.client_moduleo is not None else None


def _chercher(
    lecteur: LecteurModuleo, numero: str, texte: str, filtres: dict[str, str], noms: dict[str, str]
) -> list[int]:
    # Ids des affaires trouvées, dans l'ordre de Moduléo.
    if numero:
        try:
            id_affaire = lecteur.lire(_ROUTE_NUMERO, {"numAffaire": numero})
        except ModuleoIntrouvable:
            return []
        return [int(id_affaire)] if id_affaire else []
    parametres = {"texte": texte or None, **filtres, **_resoudre(lecteur, noms), "nbMaxResultats": IDS_MAX}
    # « Suivie par » : responsable ou chargé d'affaire. L'API combine ses
    # filtres en « et » : deux recherches, ids réunis sans doublon.
    suivi = parametres.pop("suivi_par", None)
    variantes = [{}] if suivi is None else [{"idsResponsable": suivi}, {"idsActeurEnCharge": suivi}]
    ids = [int(i) for variante in variantes for i in lecteur.lire(_ROUTE_RECHERCHE, {**parametres, **variante})]
    return list(dict.fromkeys(ids))


def _resoudre(lecteur: LecteurModuleo, noms: dict[str, str]) -> dict[str, Any]:
    # Tous les noms avant la recherche : NomNonResolu l'empêche.
    parametres: dict[str, Any] = {}
    if "site" in noms:
        parametres["idsSite"] = chercher_sites(lecteur, noms["site"])
    if "service" in noms:
        parametres["idsService"] = chercher_services(lecteur, noms["service"])
    if "suivi_par" in noms:
        parametres["suivi_par"] = str(chercher_utilisateur(lecteur, noms["suivi_par"]))
    else:
        if "responsable" in noms:
            parametres["idsResponsable"] = str(chercher_utilisateur(lecteur, noms["responsable"]))
        if "charge_affaire" in noms:
            parametres["idsActeurEnCharge"] = str(chercher_utilisateur(lecteur, noms["charge_affaire"]))
    if "dossier_production" in noms:
        parametres["idDossierProduction"] = chercher_dossier_production(lecteur, noms["dossier_production"])
    return parametres


def _filtres(arguments: dict) -> dict[str, str]:
    # État et dates, au format de l'API. Une date illisible lève
    # NomNonResolu : jamais une recherche sans le filtre demandé.
    filtres = {}
    if etat := lire_argument(arguments, "etat"):
        filtres["etatAffaire"] = etat
    for argument, parametre in _DATES.items():
        if valeur := lire_argument(arguments, argument):
            filtres[parametre] = _date_api(valeur)
    return filtres


def _date_api(valeur: str) -> str:
    for format_date in _FORMATS_DATE:
        try:
            return datetime.strptime(valeur, format_date).date().isoformat()
        except ValueError:
            continue
    raise NomNonResolu(f"Date « {valeur} » illisible : donne-la au format AAAA-MM-JJ. Recherche non lancée.")


def _fiches(lecteur: LecteurModuleo, ids: list[int]) -> list[Fiche]:
    affaires = {affaire["IdAffaire"]: affaire for affaire in lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(ids)})}
    ids_intervenants = [
        id_intervenant
        for id_affaire in ids
        if id_affaire in affaires
        for id_intervenant in lecteur.lire(_ROUTE_INTERVENANTS_AFFAIRE, {"idAffaire": id_affaire})
    ]
    intervenants = lecteur.lire(_ROUTE_INTERVENANTS, {"ids": liste_ids(ids_intervenants)}) if ids_intervenants else []
    # Tous les noms de l'appel d'un coup, dédoublonnés.
    noms = Noms(
        utilisateurs=resoudre_utilisateurs(
            lecteur, [a.get(champ) for a in affaires.values() for champ in ("IdResponsable", "IdActeurEnCharge")]
        ),
        contacts=resoudre_contacts(
            lecteur,
            [a.get(champ) for a in affaires.values() for champ in ("IdClient", "IdRepresentant")]
            + [i.get(champ) for i in intervenants for champ in ("IdContact", "IdRepresentant")],
        ),
        communes=resoudre_communes(lecteur, [a.get("IdCommune") for a in affaires.values()]),
    )
    return [
        Fiche(
            reference_affaire(affaires[id_affaire]),
            fiche_affaire(
                affaires[id_affaire],
                [intervenant for intervenant in intervenants if intervenant.get("IdAffaire") == id_affaire],
                noms,
            ),
        )
        for id_affaire in ids
        if id_affaire in affaires
    ]



def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    numero = lire_argument(arguments, "numero")
    texte = lire_argument(arguments, "texte")
    noms = {nom: valeur for nom in _NOMS if (valeur := lire_argument(arguments, nom))}
    try:
        filtres = _filtres(arguments)
    except NomNonResolu as erreur:
        return ResultatOutil(str(erreur), trace={"routes": [], "non_resolu": str(erreur)})
    if contexte.client_moduleo is None or not (numero or texte or filtres or noms):
        return ResultatOutil(_RIEN_A_CHERCHER)

    def lire(lecteur: LecteurModuleo) -> tuple[list[int], list[Fiche]]:
        ids = _chercher(lecteur, numero, texte, filtres, noms)
        return ids, _fiches(lecteur, ids[: nb_max(arguments.get("nb_max"))]) if ids else []

    return lire_fiches(contexte, contexte.client_moduleo, lire, _AUCUNE_AFFAIRE, _TROUVEES)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
