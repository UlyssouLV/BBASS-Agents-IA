import json
from dataclasses import dataclass
from pathlib import Path

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
class Exigence:
    # Une seule des formes : libre (rien), groupe d'une application, droit
    # (son chemin), ou fermée (aucun compte).
    groupe: str | None = None
    droit: str | None = None
    fermee: bool = False


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


def verifier(route: str, droits: DroitsModuleo) -> None:
    # Lève DroitManquant si le compte ne peut pas lire `route`. Recherche en
    # mémoire seulement, sans base ni réseau.
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
        libelle = exigence.droit.rsplit(" › ", 1)[-1]
        raise DroitManquant(
            f"Votre compte n'a pas le droit Moduléo « {libelle} ». {_SANS_LECTURE} {_DEMANDER}",
            f"refusé, droit manquant « {exigence.droit} » ({_route_courte(route)})",
        )


def autorise(route: str, droits: DroitsModuleo) -> bool:
    try:
        verifier(route, droits)
    except DroitManquant:
        return False
    return True
