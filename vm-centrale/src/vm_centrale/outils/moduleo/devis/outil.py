from datetime import date, datetime, timedelta, timezone
from typing import Any

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo.client import LecteurModuleo
from vm_centrale.moduleo.fiches import fiche_devis, synthese_devis
from vm_centrale.moduleo.resolution import (
    Noms,
    NomNonResolu,
    chercher_services,
    chercher_utilisateur,
    resoudre_contacts,
    resoudre_utilisateurs,
)
from vm_centrale.moduleo.routes import ROUTES_GET
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import (
    NB_DEFAUT,
    NB_PLAFOND,
    Lecture,
    booleen,
    date_api,
    id_affaire,
    liste_ids,
    lire_argument,
    lire_par_lots,
    lire_fiches,
    nb_max,
    propose,
    refus_du_garde,
)

_NOM = "chercher_devis_moduleo"

_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/devis?texte="))
_ROUTE_DEVIS = "cogeo/devis/multi?ids={ids}"
_ROUTE_DEVIS_AFFAIRE = "cogeo/affaire/{idAffaire}/devis"
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"

# Sans aucun critère (spec 1.5.1) : les devis émis ces derniers jours,
# période annoncée dans le résultat.
_JOURS_DEFAUT = 30
_AUCUN = "Aucun devis Moduléo ne correspond à cette recherche."
_AUCUN_RECENT = "Aucun devis émis dans Moduléo depuis le {depuis} ({jours} derniers jours)."
_SANS_LECTURE = (
    "Aucune lecture faite dans Moduléo : n'invente aucun devis, demande au collaborateur "
    "un numéro, un nom ou une période."
)
_RIEN_A_CHERCHER = f"Moduléo n'est pas configuré. {_SANS_LECTURE}"

# Filtres de dates : argument du modèle → (paramètre de cogeo/devis?…,
# libellé dans les critères).
_DATES = {
    "date_emission_min": ("dateEmissionMin", "émission depuis le"),
    "date_emission_max": ("dateEmissionMax", "émission jusqu'au"),
    "date_reponse_min": ("dateReponseMin", "réponse depuis le"),
    "date_reponse_max": ("dateReponseMax", "réponse jusqu'au"),
}
# Filtres en noms, résolus en ids par la VM, et leur libellé.
_NOMS = {"service": "service", "responsable": "responsable", "redacteur": "rédacteur", "affaire": "affaire"}

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des devis dans Moduléo, le logiciel de gestion du cabinet, par texte, émission, "
            "dates d'émission ou de réponse, service, responsable, rédacteur ou numéro d'affaire, "
            "filtres combinables donnés en noms tels que le collaborateur les dit. Renvoie en tête "
            "le nombre de devis trouvés et leurs totaux HT et TTC, calculés sur tous les devis "
            "trouvés : cite-les tels quels, ne fais jamais d'addition toi-même. Puis une fiche "
            "par devis, les plus récents d'abord : numéro, objet, affaire, client, dates, état, "
            "responsable, rédacteur, montants HT et TTC. Sans aucun critère, renvoie les devis "
            f"émis ces {_JOURS_DEFAUT} derniers jours, et le dit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texte": {"type": "string", "description": "Un mot du numéro ou de l'objet du devis."},
                "emis": {
                    "type": "boolean",
                    "description": "true : seulement les devis émis ; false : seulement ceux pas encore émis.",
                },
                **{
                    argument: {
                        "type": "string",
                        "description": (
                            f"Date {'d’émission' if 'emission' in argument else 'de réponse'} "
                            f"{'au plus tôt' if argument.endswith('_min') else 'au plus tard'}, "
                            "au format AAAA-MM-JJ."
                        ),
                    }
                    for argument in _DATES
                },
                "service": {"type": "string", "description": "Nom du service du cabinet."},
                "responsable": {"type": "string", "description": "Nom et / ou prénom du responsable du devis."},
                "redacteur": {"type": "string", "description": "Nom et / ou prénom du rédacteur du devis."},
                "affaire": {
                    "type": "string",
                    "description": "Numéro exact de l'affaire du devis (ex. « 2024-123 »).",
                },
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de fiches voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus ; "
                        "les totaux portent toujours sur tous les devis trouvés."
                    ),
                },
            },
        },
    },
}


def _date_du_jour() -> date:
    return datetime.now(timezone.utc).date()


def _declarer(contexte: ContexteTour) -> dict | None:
    # Moduléo configuré, droit « Consulter les devis » (garde des droits).
    return _SCHEMA if propose(contexte, _ROUTE_RECHERCHE) else None


def _resoudre(lecteur: LecteurModuleo, noms: dict[str, str]) -> dict[str, Any]:
    # Tous les noms avant la recherche : NomNonResolu l'empêche.
    parametres: dict[str, Any] = {}
    if "service" in noms:
        parametres["idsService"] = chercher_services(lecteur, noms["service"])
    if "responsable" in noms:
        parametres["idsResponsable"] = str(chercher_utilisateur(lecteur, noms["responsable"]))
    if "redacteur" in noms:
        parametres["idsRedacteur"] = str(chercher_utilisateur(lecteur, noms["redacteur"]))
    if "affaire" in noms:
        parametres["affaire"] = id_affaire(lecteur, noms["affaire"])
    return parametres


def _chercher(lecteur: LecteurModuleo, filtres: dict[str, Any], noms: dict[str, str]) -> list[int]:
    # La recherche de devis n'a pas de filtre d'affaire : les devis de
    # l'affaire, croisés avec la recherche s'il y a d'autres filtres.
    parametres = {cle: valeur for cle, valeur in {**filtres, **_resoudre(lecteur, noms)}.items() if valeur is not None}
    id_affaire = parametres.pop("affaire", None)
    if id_affaire is None:
        return [int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, parametres)]
    ids = [int(i) for i in lecteur.lire(_ROUTE_DEVIS_AFFAIRE, {"idAffaire": id_affaire})]
    if not parametres or not ids:
        return ids
    trouves = {int(i) for i in lecteur.lire(_ROUTE_RECHERCHE, parametres)}
    return [i for i in ids if i in trouves]


def _lire_devis(lecteur: LecteurModuleo, ids: list[int]) -> list[dict]:
    # Tous les devis trouvés, plus récents d'abord : date d'émission (de
    # création pour un devis non émis), puis id.
    return sorted(
        lire_par_lots(lecteur, _ROUTE_DEVIS, ids),
        key=lambda d: (str(d.get("DateEmission") or d.get("DateCreation") or "")[:10], d.get("IdDevis") or 0),
        reverse=True,
    )


def _fiches(lecteur: LecteurModuleo, devis: list[dict]) -> list[Fiche]:
    ids_affaires = [d["IdAffaire"] for d in devis if d.get("IdAffaire")]
    affaires = (
        {a["IdAffaire"]: a for a in lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(ids_affaires)})}
        if ids_affaires
        else {}
    )
    noms = Noms(
        utilisateurs=resoudre_utilisateurs(
            lecteur, [d.get(champ) for d in devis for champ in ("IdResponsable", "IdRedacteur")]
        ),
        contacts=resoudre_contacts(lecteur, [a.get("IdClient") for a in affaires.values()]),
        communes={},
    )
    return [fiche_devis(d, affaires.get(d.get("IdAffaire")), noms) for d in devis]


def _criteres(texte: str, emis: bool | None, arguments: dict, noms: dict[str, str]) -> str:
    # « texte « Bornage », émis, responsable Martin » : la portée des
    # totaux, dans le résultat et la référence de leur lecture.
    criteres = [f"texte « {texte} »"] if texte else []
    if emis is not None:
        criteres.append("émis" if emis else "non émis")
    for argument, (_, libelle) in _DATES.items():
        if valeur := lire_argument(arguments, argument):
            criteres.append(f"{libelle} {date.fromisoformat(date_api(valeur)).strftime('%d/%m/%Y')}")
    criteres.extend(f"{_NOMS[nom]} {valeur}" for nom, valeur in noms.items())
    return ", ".join(criteres)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    if (refus := refus_du_garde(contexte, _ROUTE_RECHERCHE)) is not None:
        return refus
    texte = lire_argument(arguments, "texte")
    emis = booleen(arguments.get("emis"))
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

    if texte or emis is not None or dates or noms:
        criteres = _criteres(texte, emis, arguments, noms)
        reference, aucun = f"devis ({criteres})", _AUCUN

        def portee(nombre: int) -> str:
            return f"{'trouvé' if nombre == 1 else 'trouvés'} ({criteres})"
    else:
        aujourdhui = _date_du_jour()
        depuis = aujourdhui - timedelta(days=_JOURS_DEFAUT)
        emis, dates = True, {"dateEmissionMin": depuis.isoformat()}
        du, au = depuis.strftime("%d/%m/%Y"), aujourdhui.strftime("%d/%m/%Y")
        reference = f"devis émis du {du} au {au}"
        aucun = _AUCUN_RECENT.format(depuis=du, jours=_JOURS_DEFAUT)

        def portee(nombre: int) -> str:
            return f"émis depuis le {du} ({_JOURS_DEFAUT} derniers jours)"

    filtres = {"texte": texte or None, "emis": None if emis is None else str(emis).lower(), **dates}

    def lire(lecteur: LecteurModuleo) -> Lecture:
        ids = _chercher(lecteur, filtres, noms)
        if not ids:
            return Lecture([], [])
        devis = _lire_devis(lecteur, ids)
        fiches = _fiches(lecteur, devis[: nb_max(arguments.get("nb_max"))])
        synthese = synthese_devis(devis, len(fiches), portee(len(devis)), reference)
        return Lecture([d["IdDevis"] for d in devis], fiches, synthese)

    return lire_fiches(contexte, contexte.client_moduleo, "devis", lire, aucun, "", _SANS_LECTURE)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
