import re
from typing import Any
from urllib.parse import quote

import httpx

from vm_centrale.config import MODULEO_HTTP_TIMEOUT
from vm_centrale.moduleo.routes import ROUTES_GET

_http_client = httpx.Client(timeout=MODULEO_HTTP_TIMEOUT)

_PARAMETRE = re.compile(r"\{(\w+)\}")


class RequeteInterdite(Exception):
    # Levée avant tout envoi (ADR-0017) : méthode autre que GET, route hors
    # de ROUTES_GET, ou route mal remplie. Une erreur du code de la VM, pas
    # de Moduléo.
    pass


class ErreurModuleo(Exception):
    pass


class ModuleoIndisponible(ErreurModuleo):
    # Panne : délai dépassé, serveur injoignable ou réponse inexploitable.
    pass


class ModuleoRefuse(ErreurModuleo):
    # Refus : clé, SecurityCode ou droit refusé par Moduléo (401 / 403).
    pass


class ClientModuleo:
    # Client générique en lecture seule (spec 1.5.0, ADR-0017) : les droits
    # d'une clé Moduléo se règlent par catégorie, pas en lecture / écriture,
    # donc seule la VM garantit qu'aucune écriture ne part.
    def __init__(self, url_base: str, api_key: str, security_code: str) -> None:
        self._url_base = url_base.rstrip("/")
        self._en_tetes = {"ApiKey": api_key, "SecurityCode": security_code}

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        return self.envoyer("GET", route, parametres)

    def envoyer(self, methode: str, route: str, parametres: dict[str, Any] | None = None) -> Any:
        if methode != "GET":
            raise RequeteInterdite(f"Méthode {methode!r} refusée : Moduléo est en lecture seule.")
        url, params = _remplir(route, parametres or {})
        try:
            reponse = _http_client.get(f"{self._url_base}/{url}", params=params, headers=self._en_tetes)
        except httpx.HTTPError as erreur:
            raise ModuleoIndisponible(str(erreur)) from erreur
        if reponse.status_code in (401, 403):
            raise ModuleoRefuse(f"{reponse.status_code} sur {route}")
        if reponse.is_error:
            raise ModuleoIndisponible(f"{reponse.status_code} sur {route}")
        try:
            return reponse.json()
        except ValueError as erreur:
            raise ModuleoIndisponible(f"Réponse non JSON sur {route}") from erreur


def _remplir(route: str, parametres: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # Une route est un gabarit du WADL (« cogeo/affaire/{idAffaire} »,
    # « cogeo/affaire?texte={texte}&… ») : les paramètres du chemin sont
    # obligatoires, ceux de la requête facultatifs (None = absent).
    if route not in ROUTES_GET:
        raise RequeteInterdite(f"Route {route!r} absente de la table des routes GET.")
    chemin, _, requete = route.partition("?")
    noms_chemin = _PARAMETRE.findall(chemin)
    noms_requete = _PARAMETRE.findall(requete)
    inconnus = set(parametres) - set(noms_chemin) - set(noms_requete)
    if inconnus:
        raise RequeteInterdite(f"Paramètres {sorted(inconnus)} absents de la route {route!r}.")
    manquants = [nom for nom in noms_chemin if parametres.get(nom) is None]
    if manquants:
        raise RequeteInterdite(f"Paramètres de chemin {manquants} manquants pour {route!r}.")
    url = _PARAMETRE.sub(lambda m: quote(str(parametres[m.group(1)]), safe=""), chemin)
    params = {nom: parametres[nom] for nom in noms_requete if parametres.get(nom) is not None}
    return url, params
