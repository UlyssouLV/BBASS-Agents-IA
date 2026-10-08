import re
from functools import cache
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from vm_centrale.config import MODULEO_HTTP_TIMEOUT
from vm_centrale.moduleo.configuration import config_moduleo
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


class ModuleoIntrouvable(ModuleoIndisponible):
    # 404 : l'élément demandé n'existe pas (ex. un numéro d'affaire inconnu,
    # #174). Une panne pour qui ne l'attend pas ; un outil qui sait qu'une
    # recherche peut ne rien trouver l'attrape à part.
    pass


class LecteurModuleo(Protocol):
    # Ce que les outils connaissent de Moduléo : ClientModuleo, ou le faux
    # Moduléo des tests (tests/faux_moduleo.py).
    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any: ...


class ClientModuleo:
    # Client générique en lecture seule (spec 1.5.0, ADR-0017) : seconde
    # barrière après la clé Moduléo réglée en lecture, pour qu'aucune
    # écriture ne parte même avec une clé mal réglée.
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
        if reponse.status_code == 404:
            raise ModuleoIntrouvable(f"404 sur {route}")
        if reponse.is_error:
            raise ModuleoIndisponible(f"{reponse.status_code} sur {route}")
        try:
            return reponse.json()
        except ValueError as erreur:
            raise ModuleoIndisponible(f"Réponse non JSON sur {route}") from erreur


@cache
def get_client_moduleo() -> LecteurModuleo | None:
    # Dépendance des envois de message (spec 1.5.0, #174) : None sans config
    # Moduléo complète et déchiffrable, et les outils Moduléo ne sont pas
    # proposés. Lue une fois par processus, comme le reste de la config.
    config = config_moduleo()
    if config is None:
        return None
    return ClientModuleo(config.url, config.api_key, config.security_code)


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
