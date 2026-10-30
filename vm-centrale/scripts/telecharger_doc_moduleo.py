"""Retelecharge la doc de l'API Moduleo et regenere les tables des routes.

Copie le WADL (`wadl.xml`) et la page de documentation (`documentation.html`)
du serveur de MODULEO_URL dans `vm_centrale/moduleo/docs/`, puis regenere
`vm_centrale/moduleo/routes.py` (`ROUTES_GET` : toutes les routes GET du WADL,
ADR-0017 ; `ROUTES_ECRITURE` : toutes les routes POST / PUT / DELETE, avec
parametres, exemple de corps JSON et description, ADR-0023) et
`docs/index-routes.md` (une ligne par route GET : parametres, description
tiree de la page HTML). Aucune cle n'est necessaire : la doc du serveur est
publique.

Lancement : `python scripts/telecharger_doc_moduleo.py` depuis vm-centrale/.
"""

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from vm_centrale.config import MODULEO_URL
import vm_centrale.moduleo

# Le paquet, pas client.py : routes.py peut manquer avant la première génération.
DOSSIER_MODULEO = Path(vm_centrale.moduleo.__file__).parent
DOSSIER_DOCS = DOSSIER_MODULEO / "docs"

_WADL = "{http://wadl.dev.java.net/2009/02}"
_LIGNE_HTML = re.compile(
    r'<td class="api-name"><a [^>]*>(?P<api>[^<]*)</a></td>\s*'
    r'<td class="api-documentation">(?P<description>.*?)</td>',
    re.DOTALL,
)
_CATEGORIE_HTML = re.compile(r'<h2 id="[^"]*">(?P<categorie>[^<]*)</h2>')
_PARAMETRE = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class RouteGet:
    # Gabarit du WADL sans le préfixe « api/ », déjà porté par MODULEO_URL.
    route: str
    # Nom -> type (« int », « string »…) des paramètres du WADL.
    types: dict[str, str]
    categorie: str
    description: str


@dataclass(frozen=True)
class RouteEcriture:
    # Une route POST / PUT / DELETE du WADL (ADR-0023). Un même gabarit
    # peut porter plusieurs méthodes (« webhook » : POST et DELETE).
    methode: str
    route: str
    types: dict[str, str]
    # Exemple de corps JSON du WADL (représentation application/json), ou
    # None : la route ne prend pas de corps.
    exemple: str | None
    description: str


def routes_get(wadl: bytes, documentation: str) -> list[RouteGet]:
    descriptions = _descriptions(documentation)
    routes = []
    for chemin, methode in _methodes(wadl):
        if methode.get("name") != "GET":
            continue
        categorie, description = descriptions.get(("GET", chemin), ("Sans catégorie", ""))
        routes.append(RouteGet(chemin.removeprefix("api/"), _types(methode), categorie, description))
    return sorted(routes, key=lambda r: (r.categorie, r.route))


def routes_ecriture(wadl: bytes, documentation: str) -> list[RouteEcriture]:
    descriptions = _descriptions(documentation)
    routes = []
    for chemin, methode in _methodes(wadl):
        nom = methode.get("name", "")
        if nom == "GET":
            continue
        # La requête seulement : la réponse a aussi ses représentations.
        exemple = next(
            (
                representation.findtext(f"{_WADL}doc") or None
                for representation in methode.findall(f"{_WADL}request/{_WADL}representation")
                if representation.get("mediaType") == "application/json"
            ),
            None,
        )
        _, description = descriptions.get((nom, chemin), ("", ""))
        routes.append(RouteEcriture(nom, chemin.removeprefix("api/"), _types(methode), exemple, description))
    return sorted(routes, key=lambda r: (r.route, r.methode))


def _methodes(wadl: bytes) -> list[tuple[str, ET.Element]]:
    # (chemin « api/… », élément <method>) de chaque méthode du WADL.
    return [
        (ressource.get("path", ""), methode)
        for ressource in ET.fromstring(wadl).iter(f"{_WADL}resource")
        for methode in ressource.findall(f"{_WADL}method")
    ]


def _types(methode: ET.Element) -> dict[str, str]:
    # Nom -> type (« int », « string »…) des paramètres du WADL.
    return {
        param.get("name", ""): param.get("type", "").removeprefix("xs:") for param in methode.iter(f"{_WADL}param")
    }


def _descriptions(documentation: str) -> dict[tuple[str, str], tuple[str, str]]:
    # (« GET », « api/… ») -> (catégorie de la page, description en texte brut).
    resultat = {}
    reperes = [(m.start(), m.group("categorie")) for m in _CATEGORIE_HTML.finditer(documentation)]
    for ligne in _LIGNE_HTML.finditer(documentation):
        methode, _, chemin = html.unescape(ligne.group("api")).partition(" ")
        categorie = next((nom for debut, nom in reversed(reperes) if debut < ligne.start()), "")
        texte = html.unescape(re.sub(r"<[^>]+>", " ", ligne.group("description")))
        resultat[(methode, chemin)] = (html.unescape(categorie), " ".join(texte.split()))
    return resultat


def generer_routes(routes: list[RouteGet], ecritures: list[RouteEcriture], telechargement: date) -> str:
    # Les gabarits du WADL ne contiennent ni guillemet ni barre oblique inverse.
    lignes = "".join(f'        "{r.route}",\n' for r in sorted(routes, key=lambda r: r.route))
    lignes_ecriture = "".join(
        f'    ("{r.methode}", "{r.route}"): RouteEcriture(\n'
        f'        methode="{r.methode}",\n'
        f'        route="{r.route}",\n'
        f"        parametres={r.types!r},\n"
        f"        exemple={r.exemple!r},\n"
        f"        description={r.description!r},\n"
        f"    ),\n"
        for r in ecritures
    )
    return (
        f"# Généré par scripts/telecharger_doc_moduleo.py depuis docs/wadl.xml\n"
        f"# (téléchargé le {telechargement.isoformat()}) : ne pas modifier à la main.\n"
        f"from dataclasses import dataclass\n"
        f"\n"
        f"# Toutes les routes GET de l'API Moduléo, et elles seules (ADR-0017) :\n"
        f"# le client refuse en lecture toute route absente de cette table.\n"
        f"\n"
        f"ROUTES_GET = frozenset(\n"
        f"    {{\n"
        f"{lignes}"
        f"    }}\n"
        f")\n"
        f"\n"
        f"\n"
        f"@dataclass(frozen=True)\n"
        f"class RouteEcriture:\n"
        f"    methode: str\n"
        f"    route: str\n"
        f"    # Nom -> type du WADL de chaque paramètre, tous obligatoires.\n"
        f"    parametres: dict[str, str]\n"
        f"    # Exemple de corps JSON du WADL, ou None : la route ne prend pas de corps.\n"
        f"    exemple: str | None\n"
        f"    description: str\n"
        f"\n"
        f"\n"
        f"# Toutes les routes POST / PUT / DELETE de l'API Moduléo (ADR-0023), par\n"
        f"# (méthode, gabarit) : ClientModuleo.ecrire refuse toute autre route.\n"
        f"ROUTES_ECRITURE = {{\n"
        f"{lignes_ecriture}"
        f"}}\n"
    )


def generer_index(routes: list[RouteGet], telechargement: date) -> str:
    sortie = [
        "# Routes GET de l'API Moduléo",
        "",
        f"Généré par `scripts/telecharger_doc_moduleo.py` depuis `wadl.xml` et "
        f"`documentation.html` (téléchargés le {telechargement.isoformat()}) : "
        f"ne pas modifier à la main. {len(routes)} routes GET, préfixées par "
        f"`MODULEO_URL`.",
    ]
    categorie_courante = None
    for route in routes:
        if route.categorie != categorie_courante:
            categorie_courante = route.categorie
            sortie += ["", f"## {categorie_courante}", "", "| Route | Paramètres | Description |", "| --- | --- | --- |"]
        parametres = ", ".join(
            f"`{nom}` ({route.types.get(nom) or '?'})" for nom in _PARAMETRE.findall(route.route)
        )
        description = (route.description or "Sans description dans la page de documentation.").replace(
            "|", "\\|"
        )
        sortie.append(f"| `{route.route}` | {parametres or '—'} | {description} |")
    return "\n".join(sortie) + "\n"


def main() -> None:
    url_doc = f"{MODULEO_URL.rstrip('/')}/documentation"
    with httpx.Client(timeout=60) as http:
        wadl = http.get(f"{url_doc}/wadl").raise_for_status().content
        page = http.get(url_doc).raise_for_status()
    aujourd_hui = date.today()
    routes = routes_get(wadl, page.text)
    ecritures = routes_ecriture(wadl, page.text)
    DOSSIER_DOCS.mkdir(exist_ok=True)
    (DOSSIER_DOCS / "wadl.xml").write_bytes(wadl)
    (DOSSIER_DOCS / "documentation.html").write_bytes(page.content)
    # Fins de ligne LF aussi sous Windows : une régénération ne doit changer
    # que le contenu.
    (DOSSIER_MODULEO / "routes.py").write_text(
        generer_routes(routes, ecritures, aujourd_hui), encoding="utf-8", newline="\n"
    )
    (DOSSIER_DOCS / "index-routes.md").write_text(
        generer_index(routes, aujourd_hui), encoding="utf-8", newline="\n"
    )
    print(f"Routes Moduléo : {len(routes)} GET, {len(ecritures)} d'écriture (doc de {url_doc})")


if __name__ == "__main__":
    main()
