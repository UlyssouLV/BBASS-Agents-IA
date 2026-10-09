import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vm_centrale.moduleo.droits.catalogue import COGEO, FICHIER_CATALOGUE, PLANNING, chemin
from vm_centrale.moduleo.droits.compte import DroitsModuleo

# Garde des droits (spec 1.5.1, ADR-0018) : point de passage unique, fermé
# par défaut, avant tout envoi à Moduléo. Chaque route GET est classée dans
# routes.json ; une route non classée est refusée. Règles :
# moduleo/README.md.

FICHIER_CLASSEMENT = Path(__file__).parent / "routes.json"

_SANS_LECTURE = "Aucune lecture n'a été faite."
_DEMANDER = "Demandez à un compte administrateur si vous en avez besoin."
_NOMS_APPLICATIONS = {COGEO: "Cogeo", PLANNING: "Planning"}


@dataclass(frozen=True)
class Siens:
    # Sans le droit, une route reste lisible pour les seuls éléments de
    # l'utilisateur Moduléo lié au compte (#191) : `parametre`, celui de la
    # requête qui doit valoir son id ; ou `champ`, celui de chaque élément
    # reçu qui doit valoir son id.
    parametre: str | None = None
    champ: str | None = None


@dataclass(frozen=True)
class Exigence:
    # Une seule des formes : libre (rien), groupe d'une application, droit
    # (son chemin), ou fermée (aucun compte). Un droit peut s'ouvrir aux
    # seuls éléments du compte (`siens`).
    groupe: str | None = None
    droit: str | None = None
    fermee: bool = False
    siens: Siens | None = None


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


def _route_courte(route: str) -> str:
    # « cogeo/contact?texte=… » : l'inspecteur n'a pas besoin du gabarit
    # entier.
    debut, separateur, _ = route.partition("=")
    return f"{debut}{separateur}…" if separateur else route


def _sans_groupe(application: str) -> DroitManquant:
    nom = _NOMS_APPLICATIONS[application]
    return DroitManquant(
        f"Votre compte n'est rattaché à aucun groupe Moduléo {nom}. {_SANS_LECTURE} {_DEMANDER}",
        f"refusé, groupe {nom} manquant",
    )


def _groupe(droits: DroitsModuleo, application: str) -> str | None:
    return droits.groupe_cogeo if application == COGEO else droits.groupe_planning


def _droit_manquant(droit: str, route: str) -> DroitManquant:
    libelle = droit.rsplit(" › ", 1)[-1]
    return DroitManquant(
        f"Votre compte n'a pas le droit Moduléo « {libelle} ». {_SANS_LECTURE} {_DEMANDER}",
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


def autorise(route: str, droits: DroitsModuleo, parametres: dict[str, Any] | None = None) -> bool:
    try:
        verifier(route, droits, parametres)
    except DroitManquant:
        return False
    return True
