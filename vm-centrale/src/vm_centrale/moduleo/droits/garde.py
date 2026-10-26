import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vm_centrale.moduleo.droits.catalogue import COGEO, FICHIER_CATALOGUE, PLANNING, chemin
from vm_centrale.moduleo.droits.compte import DroitsModuleo
from vm_centrale.moduleo.routes import ROUTES_ECRITURE

# Garde des droits (spec 1.5.1, ADR-0018) : point de passage unique, fermé
# par défaut, avant tout envoi à Moduléo. Chaque route GET, et depuis 1.5.2
# chaque route d'écriture (#202, ADR-0019), est classée dans routes.json ;
# une route non classée est refusée. Règles : moduleo/README.md.

FICHIER_CLASSEMENT = Path(__file__).parent / "routes.json"

_SANS_LECTURE = "Aucune lecture n'a été faite."
_SANS_ECRITURE = "Rien n'a été écrit."
_DEMANDER = "Demandez à un compte administrateur si vous en avez besoin."
_NOMS_APPLICATIONS = {COGEO: "Cogeo", PLANNING: "Planning"}
# Compte sans aucun groupe (#199) : la phrase que le modèle rend pour une
# donnée Moduléo, aucun outil Moduléo ne lui étant proposé.
SANS_AUCUN_GROUPE = f"Votre compte n'est rattaché à aucun groupe Moduléo. {_SANS_LECTURE} {_DEMANDER}"


@dataclass(frozen=True)
class Siens:
    # Sans le droit, une route reste lisible pour les seuls éléments de
    # l'utilisateur Moduléo lié au compte (#191) : `parametre`, celui de la
    # requête qui doit valoir son id ; ou `champ`, celui de chaque élément
    # reçu qui doit valoir son id.
    parametre: str | None = None
    champ: str | None = None


@dataclass(frozen=True)
class SiensEcriture:
    # Sans le droit, une écriture reste permise sur les seuls éléments de
    # l'utilisateur Moduléo lié au compte (#202) : `champ` du corps doit
    # valoir son id (`corps`), et l'élément existant désigné par le
    # paramètre `existant`, relu par la route `lecture`, doit être à lui.
    champ: str
    lecture: str
    corps: bool = False
    existant: str | None = None


@dataclass(frozen=True)
class Exigence:
    # Une seule des formes : libre (rien), groupe d'une application, droit
    # (son chemin), ou fermée (aucun compte). Un droit peut s'ouvrir aux
    # seuls éléments du compte (`siens` en lecture, `siens_ecriture`).
    groupe: str | None = None
    droit: str | None = None
    fermee: bool = False
    siens: Siens | None = None
    siens_ecriture: SiensEcriture | None = None


LIBRE = Exigence()
FERMEE = Exigence(fermee=True)


class DroitManquant(Exception):
    # `phrase` va au modèle, `refus` à l'inspecteur (« refusé, droit
    # manquant … »). Jamais la clé ni le SecurityCode.
    def __init__(self, phrase: str, refus: str) -> None:
        super().__init__(refus)
        self.phrase = phrase
        self.refus = refus


def _applications_des_droits() -> dict[str, str]:
    # Chemin de chaque droit du catalogue → son application.
    catalogue = json.loads(FICHIER_CATALOGUE.read_text(encoding="utf-8"))["catalogue"]
    applications: dict[str, str] = {}

    def parcourir(application: str, categorie: str, entrees: list, parents: list[str]) -> None:
        for entree in entrees:
            applications[chemin(categorie, *parents, entree["libelle"])] = application
            parcourir(application, categorie, entree.get("sous_droits", []), [*parents, entree["libelle"]])

    for application, categories in catalogue.items():
        for categorie in categories:
            parcourir(application, categorie["categorie"], categorie["droits"], [])
    return applications


_APPLICATIONS = _applications_des_droits()


def _charger_classement() -> dict[str, Exigence]:
    donnees = json.loads(FICHIER_CLASSEMENT.read_text(encoding="utf-8"))
    classement = {route: LIBRE for route in donnees["libre"]}
    classement |= {route: FERMEE for route in donnees["fermee"]}
    classement |= {route: Exigence(groupe=COGEO) for route in donnees["groupe_cogeo"]}
    classement |= {route: Exigence(groupe=PLANNING) for route in donnees["groupe_planning"]}
    for droit, routes in donnees["droits"].items():
        if droit not in _APPLICATIONS:
            raise ValueError(f"routes.json : droit absent du catalogue : {droit}")
        classement |= {route: Exigence(droit=droit) for route in routes}
    for droit, regles in donnees.get("siens", {}).items():
        sienne = [(route, Siens(parametre=p)) for route, p in regles.get("parametres", {}).items()]
        sienne += [(route, Siens(champ=c)) for route, c in regles.get("reponses", {}).items()]
        for route, siens in sienne:
            if classement.get(route) != Exigence(droit=droit):
                raise ValueError(f"routes.json : « siens » hors des routes du droit {droit} : {route}")
            classement[route] = Exigence(droit=droit, siens=siens)
    return classement


# Route (gabarit de ROUTES_GET) → exigence. Lu une fois par processus.
CLASSEMENT = _charger_classement()


def _route_ecriture(cle: str) -> tuple[str, str]:
    # « POST cogeo/tempspasse » → clé de ROUTES_ECRITURE ; une route
    # inconnue du WADL fait échouer le chargement.
    methode, _, route = cle.partition(" ")
    if (methode, route) not in ROUTES_ECRITURE:
        raise ValueError(f"routes.json : route d'écriture absente du WADL : {cle}")
    return methode, route


def _charger_classement_ecriture() -> dict[tuple[str, str], Exigence]:
    donnees = json.loads(FICHIER_CLASSEMENT.read_text(encoding="utf-8"))["ecriture"]
    classement = {_route_ecriture(cle): LIBRE for cle in donnees["libre"]}
    # « fermee » : route → raison, recopiée dans le README du module.
    classement |= {_route_ecriture(cle): FERMEE for cle in donnees["fermee"]}
    classement |= {_route_ecriture(cle): Exigence(groupe=COGEO) for cle in donnees["groupe_cogeo"]}
    classement |= {_route_ecriture(cle): Exigence(groupe=PLANNING) for cle in donnees["groupe_planning"]}
    for droit, cles in donnees["droits"].items():
        if droit not in _APPLICATIONS:
            raise ValueError(f"routes.json : droit absent du catalogue : {droit}")
        classement |= {_route_ecriture(cle): Exigence(droit=droit) for cle in cles}
    for droit, regle in donnees.get("siens", {}).items():
        existants = regle.get("existant", {})
        for cle in {*regle.get("corps", []), *existants}:
            route = _route_ecriture(cle)
            if classement.get(route) != Exigence(droit=droit):
                raise ValueError(f"routes.json : « siens » hors des routes du droit {droit} : {cle}")
            siens = SiensEcriture(
                champ=regle["champ"],
                lecture=regle["lecture"],
                corps=cle in regle.get("corps", []),
                existant=existants.get(cle),
            )
            classement[route] = Exigence(droit=droit, siens_ecriture=siens)
    return classement


# (méthode, gabarit de ROUTES_ECRITURE) → exigence. Lu une fois par processus.
CLASSEMENT_ECRITURE = _charger_classement_ecriture()


def _route_courte(route: str) -> str:
    # « cogeo/contact?texte=… » : l'inspecteur n'a pas besoin du gabarit
    # entier.
    debut, separateur, _ = route.partition("=")
    return f"{debut}{separateur}…" if separateur else route


def _sans_groupe(application: str, suite: str = _SANS_LECTURE) -> DroitManquant:
    nom = _NOMS_APPLICATIONS[application]
    return DroitManquant(
        f"Votre compte n'est rattaché à aucun groupe Moduléo {nom}. {suite} {_DEMANDER}",
        f"refusé, groupe {nom} manquant",
    )


def _groupe(droits: DroitsModuleo, application: str) -> str | None:
    return droits.groupe_cogeo if application == COGEO else droits.groupe_planning


def _droit_manquant(droit: str, route: str, suite: str = _SANS_LECTURE) -> DroitManquant:
    libelle = droit.rsplit(" › ", 1)[-1]
    return DroitManquant(
        f"Votre compte n'a pas le droit Moduléo « {libelle} ». {suite} {_DEMANDER}",
        f"refusé, droit manquant « {droit} » ({_route_courte(route)})",
    )


def _ids(valeur: Any) -> set[str]:
    return {i.strip() for i in str(valeur).split(",") if i.strip()} if valeur is not None else set()


def _les_siens(siens: Siens | None, droits: DroitsModuleo, parametres: dict[str, Any] | None) -> bool:
    # Sans le droit : seulement un compte lié à son utilisateur Moduléo,
    # et un paramètre qui ne désigne que lui. Une route à `champ` passe
    # ici ; chaque élément reçu est relu par verifier_reponse.
    if siens is None or droits.id_utilisateur_moduleo is None:
        return False
    if siens.champ is not None:
        return True
    return _ids((parametres or {}).get(siens.parametre)) == {str(droits.id_utilisateur_moduleo)}


def verifier(route: str, droits: DroitsModuleo, parametres: dict[str, Any] | None = None) -> None:
    # Lève DroitManquant si le compte ne peut pas lire `route` avec
    # `parametres`. Recherche en mémoire seulement, sans base ni réseau.
    exigence = CLASSEMENT.get(route)
    if exigence is None or exigence.fermee:
        raise DroitManquant(
            f"Cette donnée Moduléo n'est ouverte à aucun compte. {_SANS_LECTURE}",
            f"refusé, route {'non classée' if exigence is None else 'fermée'} ({_route_courte(route)})",
        )
    if exigence.groupe is not None and _groupe(droits, exigence.groupe) is None:
        raise _sans_groupe(exigence.groupe)
    if exigence.droit is not None and not droits.a(exigence.droit):
        application = _APPLICATIONS[exigence.droit]
        if _groupe(droits, application) is None:
            raise _sans_groupe(application)
        if not _les_siens(exigence.siens, droits, parametres):
            raise _droit_manquant(exigence.droit, route)


def verifier_reponse(route: str, droits: DroitsModuleo, reponse: Any) -> None:
    # Après la lecture d'une route ouverte aux seuls éléments du compte
    # (`Siens.champ`), sans le droit : chaque élément reçu doit être à son
    # utilisateur Moduléo, sinon DroitManquant et rien n'est rendu.
    exigence = CLASSEMENT.get(route)
    if exigence is None or exigence.siens is None or exigence.siens.champ is None or droits.a(exigence.droit):
        return
    champ = exigence.siens.champ
    elements = reponse if isinstance(reponse, list) else [reponse]
    if any(not isinstance(e, dict) or e.get(champ) != droits.id_utilisateur_moduleo for e in elements):
        raise _droit_manquant(exigence.droit, route)


def verifier_ecriture(
    methode: str,
    route: str,
    droits: DroitsModuleo,
    parametres: dict[str, Any],
    corps: Any,
    lire: Callable[[str, dict[str, Any]], Any],
) -> None:
    # Lève DroitManquant si le compte ne peut pas écrire (#202). En mémoire,
    # sauf pour un élément existant de `siens_ecriture` sans le droit :
    # `lire` (la lecture du compte, elle-même gardée) le relit.
    exigence = CLASSEMENT_ECRITURE.get((methode, route))
    nom = f"{methode} {route}"
    if exigence is None or exigence.fermee:
        raise DroitManquant(
            f"Cette écriture Moduléo n'est ouverte à aucun compte. {_SANS_ECRITURE}",
            f"refusé, route {'non classée' if exigence is None else 'fermée'} ({_route_courte(nom)})",
        )
    if exigence.groupe is not None and _groupe(droits, exigence.groupe) is None:
        raise _sans_groupe(exigence.groupe, _SANS_ECRITURE)
    if exigence.droit is not None and not droits.a(exigence.droit):
        application = _APPLICATIONS[exigence.droit]
        if _groupe(droits, application) is None:
            raise _sans_groupe(application, _SANS_ECRITURE)
        if not _les_siens_en_ecriture(exigence.siens_ecriture, droits, parametres, corps, lire):
            raise _droit_manquant(exigence.droit, nom, _SANS_ECRITURE)


def _les_siens_en_ecriture(
    siens: SiensEcriture | None,
    droits: DroitsModuleo,
    parametres: dict[str, Any],
    corps: Any,
    lire: Callable[[str, dict[str, Any]], Any],
) -> bool:
    if siens is None or droits.id_utilisateur_moduleo is None:
        return False
    moi = str(droits.id_utilisateur_moduleo)
    if siens.corps and (not isinstance(corps, dict) or str(corps.get(siens.champ)) != moi):
        return False
    if siens.existant is None:
        return True
    try:
        elements = lire(siens.lecture, {"ids": parametres[siens.existant]})
    except DroitManquant:
        # La lecture refuse un élément d'un autre collaborateur.
        return False
    # Élément introuvable : refusé aussi, rien ne prouve qu'il est au compte.
    return (
        isinstance(elements, list)
        and bool(elements)
        and all(isinstance(e, dict) and str(e.get(siens.champ)) == moi for e in elements)
    )


def autorise(route: str, droits: DroitsModuleo, parametres: dict[str, Any] | None = None) -> bool:
    try:
        verifier(route, droits, parametres)
    except DroitManquant:
        return False
    return True
