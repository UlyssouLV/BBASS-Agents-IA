from datetime import date, datetime, timedelta, timezone
from typing import Any

from vm_centrale.moduleo.client import LecteurModuleo
from vm_centrale.moduleo.droits import autorise
from vm_centrale.moduleo.fiches import NomsPlanning, fiche_tache, synthese_planning
from vm_centrale.moduleo.resolution import (
    NomNonResolu,
    activites,
    chercher_activite,
    chercher_participant,
    resoudre_equipements,
    resoudre_participants,
)
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import (
    NB_DEFAUT,
    NB_PLAFOND,
    Lecture,
    date_api,
    liste_ids,
    lire_argument,
    lire_fiches,
    lire_par_lots,
    nb_max,
    propose,
    refus_du_garde,
)

_NOM = "chercher_planning_moduleo"

# Aucun droit de consultation dans Moduléo pour le planning (spec 1.5.1) :
# un groupe Planning suffit (`groupe_planning`, routes.json).
_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("planning/tacheplanning?libelle="))
_ROUTE_TACHES = "planning/tacheplanning/multi?ids={ids}"
# Numéro de l'affaire liée : groupe Cogeo exigé, sinon une mention.
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"

# Sans aucun critère (spec 1.5.1) : aujourd'hui et les jours suivants,
# période annoncée dans le résultat.
_JOURS_DEFAUT = 7
_DEFAUT = f"aujourd'hui et les {_JOURS_DEFAUT} jours suivants"
_AUCUN = "Aucune tâche du planning Moduléo ne correspond à cette recherche."
_AUCUN_PROCHE = "Aucune tâche au planning Moduléo du {du} au {au} ({defaut})."
_SANS_LECTURE = (
    "Aucune lecture faite dans Moduléo : n'invente aucune tâche, demande au collaborateur "
    "un nom, une activité ou une période."
)
_RIEN_A_CHERCHER = f"Moduléo n'est pas configuré. {_SANS_LECTURE}"

# Filtres de dates : argument du modèle → (paramètre de
# planning/tacheplanning?…, libellé dans les critères).
_DATES = {"date_min": ("dateDebut", "depuis le"), "date_max": ("dateFin", "jusqu'au")}
# Filtres du modèle et leur libellé ; collaborateur et activité en noms,
# résolus en ids par la VM.
_FILTRES = {"collaborateur": "collaborateur", "activite": "activité", "mot_cle": "mot-clé"}

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des tâches du planning dans Moduléo, le logiciel de gestion du cabinet, par "
            "collaborateur (participant), période, activité ou mot-clé du libellé, filtres combinables "
            "donnés en noms tels que le collaborateur les dit. Pour un jour donné, date_min et date_max "
            "à ce jour. Renvoie en tête le nombre de tâches trouvées et les participants avec leur "
            "nombre de tâches, calculés sur toutes les tâches trouvées : cite-les tels quels. Puis les "
            "premières tâches dans l'ordre chronologique : libellé, date et heures, participants, "
            "activité, matériel, affaire liée, lieu. Sans aucun critère, renvoie les tâches "
            f"d'{_DEFAUT}, et le dit."
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
                "collaborateur": {
                    "type": "string",
                    "description": "Nom et / ou prénom d'un participant aux tâches.",
                },
                "activite": {
                    "type": "string",
                    "description": "Nom de l'activité du planning tel qu'il est dans Moduléo.",
                },
                "mot_cle": {"type": "string", "description": "Mot ou expression du libellé de la tâche."},
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de tâches voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus ; "
                        "le nombre et les participants portent toujours sur toutes les tâches trouvées."
                    ),
                },
            },
        },
    },
}


def _date_du_jour() -> date:
    return datetime.now(timezone.utc).date()


def _declarer(contexte: ContexteTour) -> dict | None:
    # Moduléo configuré et compte rattaché à un groupe Planning.
    return _SCHEMA if propose(contexte, _ROUTE_RECHERCHE) else None


def _parametres(lecteur: LecteurModuleo, dates: dict[str, str], filtres: dict[str, str]) -> dict[str, Any]:
    # Tous les noms avant la recherche : NomNonResolu l'empêche. Tâches
    # supprimées jamais lues.
    parametres: dict[str, Any] = {**dates, "recupererTachesSupprimees": "false"}
    if "collaborateur" in filtres:
        parametres["idsParticipants"] = str(chercher_participant(lecteur, filtres["collaborateur"]))
    if "activite" in filtres:
        parametres["idActivite"] = chercher_activite(lecteur, filtres["activite"])
    if "mot_cle" in filtres:
        parametres["libelle"] = filtres["mot_cle"]
    return parametres


def _lire_taches(lecteur: LecteurModuleo, ids: list[int]) -> list[dict]:
    # Toutes les tâches trouvées, dans l'ordre chronologique : début, puis id.
    return sorted(
        lire_par_lots(lecteur, _ROUTE_TACHES, ids),
        key=lambda t: (str(t.get("DateHeureDebut") or ""), t.get("IdTache") or 0),
    )


def _noms(lecteur: LecteurModuleo, contexte: ContexteTour, taches: list[dict], affichees: list[dict]) -> NomsPlanning:
    # Participants de toutes les tâches (synthèse) ; activités, matériel et
    # affaires des seules tâches affichées.
    ids_affaires = [t["IdAffaire"] for t in affichees if t.get("IdAffaire")]
    affaires: dict[int, str] | None = {}
    if not autorise(_ROUTE_AFFAIRES, contexte.droits_moduleo):
        affaires = None
    elif ids_affaires:
        affaires = {
            a["IdAffaire"]: str(a.get("Numero") or "")
            for a in lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(ids_affaires)})
        }
    return NomsPlanning(
        participants=resoudre_participants(lecteur, [i for t in taches for i in t.get("Participants") or []]),
        activites=activites(lecteur) if any(t.get("IdActivite") for t in affichees) else {},
        equipements=resoudre_equipements(lecteur, [i for t in affichees for i in t.get("Equipements") or []]),
        affaires=affaires,
    )


def _criteres(arguments: dict, filtres: dict[str, str]) -> str:
    # « collaborateur Jean Martin, activité Terrain » : la portée du
    # résultat et la référence de sa lecture.
    criteres = [
        f"{libelle} {date.fromisoformat(date_api(valeur)).strftime('%d/%m/%Y')}"
        for argument, (_, libelle) in _DATES.items()
        if (valeur := lire_argument(arguments, argument))
    ]
    criteres.extend(f"{_FILTRES[nom]} {valeur}" for nom, valeur in filtres.items())
    return ", ".join(criteres)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    if (refus := refus_du_garde(contexte, _ROUTE_RECHERCHE)) is not None:
        return refus
    filtres = {nom: valeur for nom in _FILTRES if (valeur := lire_argument(arguments, nom))}
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

    if dates or filtres:
        criteres = _criteres(arguments, filtres)
        reference, aucun = f"planning ({criteres})", _AUCUN

        def entete(nombre: int) -> str:
            trouvees = "tâche trouvée" if nombre == 1 else "tâches trouvées"
            return f"{nombre} {trouvees} au planning ({criteres})"
    else:
        aujourdhui = _date_du_jour()
        jusqua = aujourdhui + timedelta(days=_JOURS_DEFAUT)
        dates = {"dateDebut": aujourdhui.isoformat(), "dateFin": jusqua.isoformat()}
        du, au = aujourdhui.strftime("%d/%m/%Y"), jusqua.strftime("%d/%m/%Y")
        reference = f"planning du {du} au {au}"
        aucun = _AUCUN_PROCHE.format(du=du, au=au, defaut=_DEFAUT)

        def entete(nombre: int) -> str:
            return f"{nombre} {'tâche' if nombre == 1 else 'tâches'} au planning du {du} au {au} ({_DEFAUT})"

    def lire(lecteur: LecteurModuleo) -> Lecture:
        ids = [int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, _parametres(lecteur, dates, filtres))]
        if not ids:
            return Lecture([], [])
        taches = _lire_taches(lecteur, ids)
        affichees = taches[: nb_max(arguments.get("nb_max"))]
        noms = _noms(lecteur, contexte, taches, affichees)
        fiches = [fiche_tache(t, noms) for t in affichees]
        synthese = synthese_planning(taches, noms.participants, len(fiches), entete(len(taches)), reference)
        return Lecture([t["IdTache"] for t in taches], fiches, synthese)

    return lire_fiches(contexte, contexte.client_moduleo, "planning", lire, aucun, "", _SANS_LECTURE)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
