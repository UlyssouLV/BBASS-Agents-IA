from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo.client import LecteurModuleo, ModuleoIntrouvable
from vm_centrale.moduleo.fiches import Paiements, facture_emise, fiche_facture, reste_a_payer, synthese_factures
from vm_centrale.moduleo.resolution import (
    Noms,
    NomNonResolu,
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
    chercher_avec_affaire,
    date_api,
    dates_api,
    liste_ids,
    lire_argument,
    lire_fiches,
    lire_par_lots,
    nb_max,
    propose,
    refus_du_garde,
)

_NOM = "chercher_factures_moduleo"

_ROUTE_RECHERCHE = next(route for route in ROUTES_GET if route.startswith("cogeo/facture?texte="))
_ROUTE_FACTURES = "cogeo/facture/multi?ids={ids}"
_ROUTE_FACTURES_AFFAIRE = "cogeo/affaire/{idAffaire}/factures"
_ROUTE_AFFAIRES = "cogeo/affaire/multi?ids={ids}"
_ROUTE_DESTINATAIRES = "cogeo/destinataire/multi?ids={ids}"
_ROUTE_REGLEMENT = "cogeo/reglement/{idReglement}"
_ROUTE_ECHEANCE = "cogeo/echeance/{idEcheance}"
_ROUTE_AVOIRS = "cogeo/avoir/facture?idFacture={idFacture}"

# Reste à payer total : Moduléo n'a qu'une route par règlement, lue pour
# chaque facture émise ; au-delà, pas de total du reste à payer, les fiches
# affichées gardent le leur.
_RESTE_MAX = 50
_LECTURES_PARALLELES = 16

# Sans aucun critère (spec 1.5.1) : les factures émises ces derniers jours,
# période annoncée dans le résultat.
_JOURS_DEFAUT = 30
_AUCUN = "Aucune facture Moduléo ne correspond à cette recherche."
_AUCUN_RECENT = "Aucune facture émise dans Moduléo depuis le {depuis} ({jours} derniers jours)."
_RESTE_NON_DEDUCTIBLE = "(avoir ou règlement à vérifier dans Moduléo)"
_RESTE_TROP = f"au-delà de {_RESTE_MAX} factures émises"
_SANS_LECTURE = (
    "Aucune lecture faite dans Moduléo : n'invente aucune facture, demande au collaborateur "
    "un numéro, un nom ou une période."
)
_RIEN_A_CHERCHER = f"Moduléo n'est pas configuré. {_SANS_LECTURE}"

# Filtres de dates : argument du modèle → (paramètre de cogeo/facture?…,
# libellé dans les critères).
_DATES = {
    "date_emission_min": ("dateEmissionMin", "émission depuis le"),
    "date_emission_max": ("dateEmissionMax", "émission jusqu'au"),
}
# Filtres en noms, résolus en ids par la VM, et leur libellé.
_NOMS = {"service": "service", "responsable": "responsable", "redacteur": "rédacteur", "affaire": "affaire"}

_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche des factures dans Moduléo, le logiciel de gestion du cabinet, par texte, émission, "
            "dates d'émission, service, responsable, rédacteur ou numéro d'affaire, filtres combinables "
            "donnés en noms tels que le collaborateur les dit. Renvoie en tête le nombre de factures "
            "trouvées, leurs totaux HT et TTC et leur reste à payer, calculés sur toutes les factures "
            "trouvées : cite-les tels quels, ne fais jamais d'addition ni de soustraction toi-même. Puis "
            "une fiche par facture, les plus récentes d'abord : numéro, affaire, client, dates, "
            "montants HT et TTC, échéances et règlements, reste à payer quand Moduléo permet de le "
            "déduire (sans ligne « Reste à payer », ne l'estime pas). Sans aucun critère, renvoie les "
            f"factures émises ces {_JOURS_DEFAUT} derniers jours, et le dit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texte": {"type": "string", "description": "Un mot du numéro ou de l'objet de la facture."},
                "emise": {
                    "type": "boolean",
                    "description": "true : seulement les factures émises ; false : seulement celles pas encore émises.",
                },
                **{
                    argument: {
                        "type": "string",
                        "description": (
                            f"Date d’émission {'au plus tôt' if argument.endswith('_min') else 'au plus tard'}, "
                            "au format AAAA-MM-JJ."
                        ),
                    }
                    for argument in _DATES
                },
                "service": {"type": "string", "description": "Nom du service du cabinet."},
                "responsable": {"type": "string", "description": "Nom et / ou prénom du responsable de la facture."},
                "redacteur": {"type": "string", "description": "Nom et / ou prénom du rédacteur de la facture."},
                "affaire": {
                    "type": "string",
                    "description": "Numéro exact de l'affaire de la facture (ex. « 2024-123 »).",
                },
                "nb_max": {
                    "type": "integer",
                    "description": (
                        f"Nombre de fiches voulues, {NB_DEFAUT} par défaut, {NB_PLAFOND} au plus ; "
                        "les totaux portent toujours sur toutes les factures trouvées."
                    ),
                },
            },
        },
    },
}


def _date_du_jour() -> date:
    return datetime.now(timezone.utc).date()


def _declarer(contexte: ContexteTour) -> dict | None:
    # Moduléo configuré, droit « Consulter les factures et les avoirs »
    # (garde des droits).
    return _SCHEMA if propose(contexte, _ROUTE_RECHERCHE) else None



def _lire_factures(lecteur: LecteurModuleo, ids: list[int]) -> list[dict]:
    # Toutes les factures trouvées, plus récentes d'abord : date d'émission
    # (de création pour une facture non émise), puis id.
    return sorted(
        lire_par_lots(lecteur, _ROUTE_FACTURES, ids),
        key=lambda f: (str(f.get("DateEmission") or f.get("DateCreation") or "")[:10], f.get("IdFacture") or 0),
        reverse=True,
    )


def _lire_si_present(lecteur: LecteurModuleo, route: str, parametres: dict) -> dict | None:
    # Un règlement ou une échéance supprimé (404) n'est pas une panne : le
    # reste à payer n'est alors plus déductible.
    try:
        return lecteur.lire(route, parametres)
    except ModuleoIntrouvable:
        return None


def _paiements(lecteur: LecteurModuleo, facture: dict, avec_echeances: bool) -> Paiements:
    # Règlements (`IdsReglements` de la facture), avec leurs échéances pour
    # une fiche affichée. Complets seulement si tous sont lus, sans avoir
    # sur la facture, sans pénalités ni type de règlement autre que 0 : sens
    # non relevé, à confirmer à l'essai réel.
    avoirs = lecteur.lire(_ROUTE_AVOIRS, {"idFacture": facture["IdFacture"]})
    lus = [_lire_si_present(lecteur, _ROUTE_REGLEMENT, {"idReglement": i}) for i in facture.get("IdsReglements") or []]
    reglements = tuple(r for r in lus if r is not None)
    complets = (
        not avoirs
        and len(reglements) == len(lus)
        and all(not r.get("MontantReglementPenalitesTTC") and r.get("TypeReglement") in (None, 0) for r in reglements)
    )
    echeances: dict[int, dict] = {}
    if avec_echeances:
        for id_echeance in dict.fromkeys(r["IdEcheance"] for r in reglements if r.get("IdEcheance")):
            if (echeance := _lire_si_present(lecteur, _ROUTE_ECHEANCE, {"idEcheance": id_echeance})) is not None:
                echeances[id_echeance] = echeance
    return Paiements(reglements, echeances, complets)


def _tous_les_paiements(lecteur: LecteurModuleo, factures: list[dict], affichees: int) -> dict[int, Paiements]:
    # Ceux des factures émises : toutes jusqu'à _RESTE_MAX, sinon les seules
    # affichées. Une facture non émise n'a ni reste à payer ni règlement lu.
    emises = [f for f in factures if facture_emise(f)]
    a_lire = emises if len(emises) <= _RESTE_MAX else [f for f in factures[:affichees] if facture_emise(f)]
    ids_affiches = {f["IdFacture"] for f in factures[:affichees]}
    taches = [(f, f["IdFacture"] in ids_affiches) for f in a_lire]
    # Une panne dans un thread remonte ici, à la lecture de son résultat.
    with ThreadPoolExecutor(max_workers=min(len(taches), _LECTURES_PARALLELES) or 1) as executeur:
        lus = list(executeur.map(lambda tache: _paiements(lecteur, *tache), taches))
    return {facture["IdFacture"]: paiements for (facture, _), paiements in zip(taches, lus)}


def _reste_total(factures: list[dict], paiements: dict[int, Paiements]) -> tuple[float | None, str]:
    # Reste à payer de toutes les factures émises, ou `None` et sa raison ;
    # aucune facture émise : `None` et "", sans mention.
    emises = [f for f in factures if facture_emise(f)]
    if not emises:
        return None, ""
    if len(emises) > _RESTE_MAX:
        return None, _RESTE_TROP
    restes = [reste_a_payer(f, paiements.get(f["IdFacture"])) for f in emises]
    connus = [reste for reste in restes if reste is not None]
    if len(connus) < len(restes):
        return None, _RESTE_NON_DEDUCTIBLE
    return round(sum(connus), 2), ""


def _fiches(lecteur: LecteurModuleo, factures: list[dict], paiements: dict[int, Paiements]) -> list[Fiche]:
    ids_affaires = [f["IdAffaire"] for f in factures if f.get("IdAffaire")]
    affaires = (
        {a["IdAffaire"]: a for a in lecteur.lire(_ROUTE_AFFAIRES, {"ids": liste_ids(ids_affaires)})}
        if ids_affaires
        else {}
    )
    ids_destinataires = [f["IdDestinataire"] for f in factures if f.get("IdDestinataire")]
    destinataires = (
        {d["IdDestinataire"]: d for d in lecteur.lire(_ROUTE_DESTINATAIRES, {"ids": liste_ids(ids_destinataires)})}
        if ids_destinataires
        else {}
    )
    noms = Noms(
        utilisateurs=resoudre_utilisateurs(
            lecteur, [f.get(champ) for f in factures for champ in ("IdResponsable", "IdRedacteur")]
        ),
        contacts=resoudre_contacts(
            lecteur,
            [d.get("IdContact") for d in destinataires.values()] + [a.get("IdClient") for a in affaires.values()],
        ),
        communes={},
    )
    return [
        fiche_facture(
            f,
            affaires.get(f.get("IdAffaire")),
            destinataires.get(f.get("IdDestinataire")),
            paiements.get(f["IdFacture"]),
            noms,
        )
        for f in factures
    ]


def _criteres(texte: str, emise: bool | None, arguments: dict, noms: dict[str, str]) -> str:
    # « texte « Bornage », émise, responsable Martin » : la portée des
    # totaux, dans le résultat et la référence de leur lecture.
    criteres = [f"texte « {texte} »"] if texte else []
    if emise is not None:
        criteres.append("émise" if emise else "non émise")
    for argument, (_, libelle) in _DATES.items():
        if valeur := lire_argument(arguments, argument):
            criteres.append(f"{libelle} {date.fromisoformat(date_api(valeur)).strftime('%d/%m/%Y')}")
    criteres.extend(f"{_NOMS[nom]} {valeur}" for nom, valeur in noms.items())
    return ", ".join(criteres)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    if (refus := refus_du_garde(contexte, _ROUTE_RECHERCHE)) is not None:
        return refus
    texte = lire_argument(arguments, "texte")
    emise = booleen(arguments.get("emise"))
    noms = {nom: valeur for nom in _NOMS if (valeur := lire_argument(arguments, nom))}
    try:
        dates = dates_api(arguments, _DATES)
    except NomNonResolu as erreur:
        return ResultatOutil(f"{erreur} {_SANS_LECTURE}", trace={"routes": [], "non_resolu": str(erreur)})
    if contexte.client_moduleo is None:
        return ResultatOutil(_RIEN_A_CHERCHER)

    if texte or emise is not None or dates or noms:
        criteres = _criteres(texte, emise, arguments, noms)
        reference, aucun = f"factures ({criteres})", _AUCUN

        def portee(nombre: int) -> str:
            return f"{'trouvée' if nombre == 1 else 'trouvées'} ({criteres})"
    else:
        aujourdhui = _date_du_jour()
        depuis = aujourdhui - timedelta(days=_JOURS_DEFAUT)
        emise, dates = True, {"dateEmissionMin": depuis.isoformat()}
        du, au = depuis.strftime("%d/%m/%Y"), aujourdhui.strftime("%d/%m/%Y")
        reference = f"factures émises du {du} au {au}"
        aucun = _AUCUN_RECENT.format(depuis=du, jours=_JOURS_DEFAUT)

        def portee(nombre: int) -> str:
            return f"{'émise' if nombre == 1 else 'émises'} depuis le {du} ({_JOURS_DEFAUT} derniers jours)"

    filtres = {"texte": texte or None, "emise": None if emise is None else str(emise).lower(), **dates}

    def lire(lecteur: LecteurModuleo) -> Lecture:
        ids = chercher_avec_affaire(lecteur, _ROUTE_RECHERCHE, _ROUTE_FACTURES_AFFAIRE, filtres, noms)
        if not ids:
            return Lecture([], [])
        factures = _lire_factures(lecteur, ids)
        affichees = nb_max(arguments.get("nb_max"))
        paiements = _tous_les_paiements(lecteur, factures, affichees)
        fiches = _fiches(lecteur, factures[:affichees], paiements)
        reste, sans_reste = _reste_total(factures, paiements)
        synthese = synthese_factures(factures, reste, sans_reste, len(fiches), portee(len(factures)), reference)
        return Lecture([f["IdFacture"] for f in factures], fiches, synthese)

    return lire_fiches(contexte, contexte.client_moduleo, "factures", lire, aucun, "", _SANS_LECTURE)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
