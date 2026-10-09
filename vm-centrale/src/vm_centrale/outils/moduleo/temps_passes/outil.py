from datetime import date, datetime, timedelta, timezone
from typing import Any

from vm_centrale.moduleo.client import LecteurModuleo
from vm_centrale.moduleo.droits import DroitsModuleo, chemin
from vm_centrale.moduleo.fiches import NomsTempsPasses, fiche_temps_passe, synthese_temps_passes
from vm_centrale.moduleo.resolution import (
    NomNonResolu,
    chercher_code_activite,
    chercher_utilisateur,
    resoudre_codes_activite,
    resoudre_utilisateurs,
)
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import (
    NB_DEFAUT,
    NB_PLAFOND,
    Lecture,
    date_api,
    id_affaire,
    liste_ids,
    lire_argument,
    lire_fiches,
    lire_par_lots,
    nb_max,
    propose,
    refus_du_garde,
)

_NOM = "chercher_temps_passes_moduleo"

_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/tempspasse?dateMin="))
_ROUTE_TEMPS_PASSES = "cogeo/tempspasse/multi?ids={ids}"
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"

# Sans ce droit, seulement les temps de l'utilisateur Moduléo lié au compte
# (spec 1.5.1) : le garde des droits l'impose (`siens`, routes.json).
_DROIT_AUTRES = chemin(
    "Temps passés et frais des temps passés",
    "Consulter les temps passés et les frais des temps passés des autres collaborateurs",
)
_VOS_TEMPS = "vos temps seulement"

# Sans aucun critère (spec 1.5.1) : les temps passés de ces derniers jours,
# période annoncée dans le résultat.
_JOURS_DEFAUT = 7
_AUCUN = "Aucun temps passé Moduléo ne correspond à cette recherche."
_AUCUN_RECENT = "Aucun temps passé saisi dans Moduléo du {du} au {au} ({jours} derniers jours{vos})."
_SANS_LECTURE = (
    "Aucune lecture faite dans Moduléo : n'invente aucun temps passé, demande au collaborateur "
    "un nom, une affaire ou une période."
)
_RIEN_A_CHERCHER = f"Moduléo n'est pas configuré. {_SANS_LECTURE}"

# Filtres de dates : argument du modèle → (paramètre de cogeo/tempspasse?…,
# libellé dans les critères).
_DATES = {"date_min": ("dateMin", "depuis le"), "date_max": ("dateMax", "jusqu'au")}
# Filtres en noms, résolus en ids par la VM, et leur libellé.
_NOMS = {"collaborateur": "collaborateur", "code_activite": "code activité", "affaire": "affaire"}

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des temps passés dans Moduléo, le logiciel de gestion du cabinet, par période, "
            "collaborateur, code activité ou numéro d'affaire, filtres combinables donnés en noms tels "
            "que le collaborateur les dit. Renvoie en tête le nombre de lignes trouvées et le total "
            "d'heures, général, par collaborateur et par code activité, calculés sur tous les temps "
            "trouvés : cite-les tels quels, ne fais jamais d'addition toi-même. Puis le détail des "
            "lignes les plus récentes : date, collaborateur, affaire, code activité, heures. Sans aucun "
            f"critère, renvoie les temps passés des {_JOURS_DEFAUT} derniers jours, et le dit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                **{
                    argument: {
                        "type": "string",
                        "description": (
                            f"Date {'au plus tôt' if argument.endswith('_min') else 'au plus tard'}, "
                            "au format AAAA-MM-JJ."
                        ),
                    }
                    for argument in _DATES
                },
                "collaborateur": {"type": "string", "description": "Nom et / ou prénom du collaborateur."},
                "code_activite": {
                    "type": "string",
                    "description": "Nom ou code de l'activité tel qu'il est dans Moduléo.",
                },
                "affaire": {"type": "string", "description": "Numéro exact de l'affaire (ex. « 2024-123 »)."},
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de lignes de détail voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus ; "
                        "les totaux portent toujours sur tous les temps trouvés."
                    ),
                },
            },
        },
    },
}


def _date_du_jour() -> date:
    return datetime.now(timezone.utc).date()


def _siens(droits: DroitsModuleo) -> dict[str, Any] | None:
    # Sans le droit « autres » : la recherche des seuls temps du compte,
    # seule autorisée par le garde ; sans utilisateur Moduléo lié, aucune.
    if droits.id_utilisateur_moduleo is None:
        return None
    return {"idsUtilisateurs": str(droits.id_utilisateur_moduleo)}


def _declarer(contexte: ContexteTour) -> dict | None:
    # Moduléo configuré, droit « autres », ou compte lié à son utilisateur
    # Moduléo (garde des droits).
    return _SCHEMA if propose(contexte, _ROUTE_RECHERCHE, _siens(contexte.droits_moduleo)) else None


def _parametres(lecteur: LecteurModuleo, dates: dict[str, str], noms: dict[str, str], droits: DroitsModuleo) -> dict:
    # Tous les noms avant la recherche : NomNonResolu l'empêche. Sans le
    # droit « autres », un autre collaborateur part tel quel : le garde le
    # refuse, avec sa phrase fixe.
    parametres: dict[str, Any] = dict(dates)
    if "collaborateur" in noms:
        parametres["idsUtilisateurs"] = str(chercher_utilisateur(lecteur, noms["collaborateur"]))
    elif not droits.a(_DROIT_AUTRES):
        parametres |= _siens(droits) or {}
    if "code_activite" in noms:
        parametres["idCodeActivite"] = chercher_code_activite(lecteur, noms["code_activite"])
    if "affaire" in noms:
        parametres["idAffaire"] = id_affaire(lecteur, noms["affaire"])
    return parametres


def _lire_temps(lecteur: LecteurModuleo, ids: list[int]) -> list[dict]:
    # Tous les temps trouvés, plus récents d'abord : date, puis id.
    return sorted(
        lire_par_lots(lecteur, _ROUTE_TEMPS_PASSES, ids),
        key=lambda t: (str(t.get("Date") or "")[:10], t.get("IdTempsPasse") or 0),
        reverse=True,
    )


def _noms(lecteur: LecteurModuleo, temps: list[dict], affiches: list[dict]) -> NomsTempsPasses:
    # Collaborateurs et codes activité de tous les temps (totaux), numéros
    # d'affaire des seules lignes affichées.
    ids_affaires = [t["IdAffaire"] for t in affiches if t.get("IdAffaire")]
    affaires = (
        {a["IdAffaire"]: str(a.get("Numero") or "") for a in lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(ids_affaires)})}
        if ids_affaires
        else {}
    )
    return NomsTempsPasses(
        utilisateurs=resoudre_utilisateurs(lecteur, [t.get("IdUtilisateur") for t in temps]),
        affaires=affaires,
        codes_activite=resoudre_codes_activite(lecteur, [t.get("IdCodeActivite") for t in temps]),
    )


def _criteres(arguments: dict, noms: dict[str, str], restreint: bool) -> str:
    # « affaire 2024-123, vos temps seulement » : la portée des totaux,
    # dans le résultat et la référence de leur lecture.
    criteres = [
        f"{libelle} {date.fromisoformat(date_api(valeur)).strftime('%d/%m/%Y')}"
        for argument, (_, libelle) in _DATES.items()
        if (valeur := lire_argument(arguments, argument))
    ]
    criteres.extend(f"{_NOMS[nom]} {valeur}" for nom, valeur in noms.items())
    if restreint and "collaborateur" not in noms:
        criteres.append(_VOS_TEMPS)
    return ", ".join(criteres)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    droits = contexte.droits_moduleo
    if (refus := refus_du_garde(contexte, _ROUTE_RECHERCHE, _siens(droits))) is not None:
        return refus
    restreint = not droits.a(_DROIT_AUTRES)
    noms = {nom: valeur for nom in _NOMS if (valeur := lire_argument(arguments, nom))}
    try:
        dates = {
            parametre: date_api(valeur)
            for argument, (parametre, _) in _DATES.items()
            if (valeur := lire_argument(arguments, argument))
        }
    except NomNonResolu as erreur:
        return ResultatOutil(f"{erreur} {_SANS_LECTURE}", trace={"routes": [], "non_resolu": str(erreur)})
    if contexte.client_moduleo is None:
        return ResultatOutil(_RIEN_A_CHERCHER)

    if dates or noms:
        criteres = _criteres(arguments, noms, restreint)
        reference, aucun = f"temps passés ({criteres})", _AUCUN

        def portee(nombre: int) -> str:
            return f"{'trouvé' if nombre == 1 else 'trouvés'} ({criteres})"
    else:
        aujourdhui = _date_du_jour()
        depuis = aujourdhui - timedelta(days=_JOURS_DEFAUT)
        dates = {"dateMin": depuis.isoformat(), "dateMax": aujourdhui.isoformat()}
        du, au = depuis.strftime("%d/%m/%Y"), aujourdhui.strftime("%d/%m/%Y")
        vos = f", {_VOS_TEMPS}" if restreint else ""
        reference = f"temps passés du {du} au {au}" + (f" ({_VOS_TEMPS})" if restreint else "")
        aucun = _AUCUN_RECENT.format(du=du, au=au, jours=_JOURS_DEFAUT, vos=vos)

        def portee(nombre: int) -> str:
            return f"{'saisi' if nombre == 1 else 'saisis'} du {du} au {au} ({_JOURS_DEFAUT} derniers jours{vos})"

    def lire(lecteur: LecteurModuleo) -> Lecture:
        ids = [int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, _parametres(lecteur, dates, noms, droits))]
        if not ids:
            return Lecture([], [])
        temps = _lire_temps(lecteur, ids)
        affiches = temps[: nb_max(arguments.get("nb_max"))]
        noms_temps = _noms(lecteur, temps, affiches)
        fiches = [fiche_temps_passe(t, noms_temps, droits) for t in affiches]
        synthese = synthese_temps_passes(temps, noms_temps, len(fiches), portee(len(temps)), reference)
        return Lecture([t["IdTempsPasse"] for t in temps], fiches, synthese)

    return lire_fiches(contexte, contexte.client_moduleo, "temps passés", lire, aucun, "", _SANS_LECTURE)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
