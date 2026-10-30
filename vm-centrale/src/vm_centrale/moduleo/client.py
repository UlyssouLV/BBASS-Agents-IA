import json
import re
from functools import cache
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from vm_centrale.config import MODULEO_HTTP_TIMEOUT, get_environnement, get_moduleo_ecriture
from vm_centrale.moduleo.configuration import config_moduleo
from vm_centrale.moduleo.droits import DroitsModuleo, verifier, verifier_ecriture, verifier_reponse
from vm_centrale.moduleo.routes import ROUTES_ECRITURE, ROUTES_GET

_http_client = httpx.Client(timeout=MODULEO_HTTP_TIMEOUT)

_PARAMETRE = re.compile(r"\{(\w+)\}")


def _sans_barre_finale(url: str) -> str:
    return url.strip().rstrip("/").lower()


# Serveurs Moduléo de test (spec 1.5.2, ADR-0023) : liste versionnée, seconde
# barrière de l'écriture après MODULEO_ECRITURE. Lue une fois par processus.
SERVEURS_DE_TEST = frozenset(
    _sans_barre_finale(serveur["url"])
    for serveur in json.loads((Path(__file__).parent / "serveurs_test.json").read_text(encoding="utf-8"))[
        "serveurs"
    ]
)


class RequeteInterdite(Exception):
    # Levée avant tout envoi (ADR-0017, ADR-0023) : méthode autre que GET en
    # lecture, route hors de ROUTES_GET / ROUTES_ECRITURE, route mal remplie,
    # corps incohérent, écriture inactive ou serveur hors de la liste des
    # serveurs de test. Une erreur du code ou de la config de la VM, pas de
    # Moduléo. Un droit manquant est un DroitManquant (garde des droits).
    pass


class ErreurModuleo(Exception):
    pass


class ModuleoIndisponible(ErreurModuleo):
    # Panne : délai dépassé, serveur injoignable ou réponse inexploitable.
    pass


class ModuleoRefuse(ErreurModuleo):
    # Refus : clé, SecurityCode ou droit refusé par Moduléo (401 / 403).
    # `message` : le sien sur une écriture (#260), sans la clé ni le code.
    def __init__(self, detail: str, message: str | None = None) -> None:
        super().__init__(detail)
        self.message = message


class ModuleoIntrouvable(ModuleoIndisponible):
    # 404 : l'élément demandé n'existe pas (ex. un numéro d'affaire inconnu,
    # #174). Une panne pour qui ne l'attend pas ; un outil qui sait qu'une
    # recherche peut ne rien trouver l'attrape à part.
    pass


class ModuleoDonneesRefusees(ErreurModuleo):
    # 400 sur une écriture (#202) : Moduléo refuse les données envoyées ;
    # `message` est le sien, sans la clé ni le code.
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LecteurModuleo(Protocol):
    # Une lecture déjà autorisée : le transport HTTP, le faux Moduléo des
    # tests (tests/faux_moduleo.py), ou ClientModuleo lié aux droits d'un
    # compte (`pour`), ce que reçoivent la résolution des noms et les fiches.
    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any: ...


class TransportModuleo(LecteurModuleo, Protocol):
    # Ce que ClientModuleo enveloppe : le transport HTTP ou le faux Moduléo.
    # `url` : le serveur où partent les requêtes (MODULEO_URL).
    url: str

    def ecrire(self, methode: str, route: str, parametres: dict[str, Any], corps: Any) -> Any: ...


class ClientModuleo:
    # Client générique (spec 1.5.0, ADR-0017) : `lire()` en GET seul, seconde
    # barrière après la clé Moduléo réglée en lecture. Depuis 1.5.1 (#188,
    # ADR-0018), il exige les droits du compte : le garde des droits passe
    # avant tout envoi, quel que soit le transport. Depuis 1.5.2 (#202,
    # ADR-0023), `ecrire()` envoie POST / PUT / DELETE, seulement vers un
    # serveur de test listé, MODULEO_ECRITURE actif.
    def __init__(self, transport: TransportModuleo) -> None:
        self._transport = transport

    def lire(self, route: str, parametres: dict[str, Any] | None, droits: DroitsModuleo) -> Any:
        return self.envoyer("GET", route, parametres, droits)

    def ecriture_ouverte(self) -> bool:
        # Les deux barrières de l'écriture, sans la route ni les droits.
        return get_moduleo_ecriture() and _sans_barre_finale(self._transport.url) in SERVEURS_DE_TEST

    def ecrire(
        self, methode: str, route: str, parametres: dict[str, Any] | None, corps: Any, droits: DroitsModuleo
    ) -> Any:
        # Une seule requête, aucune nouvelle tentative, après verifier_ecriture.
        parametres = parametres or {}
        self.verifier_ecriture(methode, route, parametres, corps, droits)
        return self._transport.ecrire(methode, route, parametres, corps)

    def verifier_ecriture(
        self, methode: str, route: str, parametres: dict[str, Any] | None, corps: Any, droits: DroitsModuleo
    ) -> None:
        # Tout ce que vérifie ecrire(), sans rien envoyer (ecrire_moduleo
        # propose avec, #204) : route, paramètres et corps
        # (RequeteInterdite), barrière serveur de test (RequeteInterdite),
        # puis garde des droits (DroitManquant).
        parametres = parametres or {}
        _remplir_ecriture(methode, route, parametres)
        _verifier_corps(methode, route, corps)
        if get_environnement() == "prod":
            raise RequeteInterdite("Écriture Moduléo refusée : la prod n'écrit jamais dans Moduléo.")
        if not get_moduleo_ecriture():
            raise RequeteInterdite("Écriture Moduléo inactive : MODULEO_ECRITURE n'est pas actif.")
        if _sans_barre_finale(self._transport.url) not in SERVEURS_DE_TEST:
            raise RequeteInterdite("Écriture Moduléo refusée : MODULEO_URL n'est pas un serveur de test listé.")
        verifier_ecriture(
            methode, route, droits, parametres, corps, lambda lecture, p: self.lire(lecture, p, droits)
        )

    def envoyer(self, methode: str, route: str, parametres: dict[str, Any] | None, droits: DroitsModuleo) -> Any:
        if methode != "GET":
            raise RequeteInterdite(f"Méthode {methode!r} refusée : Moduléo est en lecture seule.")
        _remplir(route, parametres or {})
        verifier(route, droits, parametres)
        reponse = self._transport.lire(route, parametres)
        # Une route ouverte aux seuls éléments du compte (#191) : chaque
        # élément reçu est relu avant d'être rendu.
        verifier_reponse(route, droits, reponse)
        return reponse

    def pour(self, droits: DroitsModuleo) -> LecteurModuleo:
        # Le client lié aux droits d'un compte, pour le temps d'un appel.
        return _LecteurDuCompte(self, droits)


class _LecteurDuCompte:
    def __init__(self, client: ClientModuleo, droits: DroitsModuleo) -> None:
        self._client = client
        self._droits = droits

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        return self._client.lire(route, parametres, self._droits)


class TransportHttp:
    # Requêtes sur MODULEO_URL avec les en-têtes ApiKey et SecurityCode : la
    # clé et le code ne sortent jamais d'ici.
    def __init__(self, url_base: str, api_key: str, security_code: str) -> None:
        self.url = url_base
        self._url_base = url_base.rstrip("/")
        self._en_tetes = {"ApiKey": api_key, "SecurityCode": security_code}

    def lire(self, route: str, parametres: dict[str, Any] | None = None) -> Any:
        url, params = _remplir(route, parametres or {})
        reponse = self._requete("GET", route, url, params, None)
        try:
            return reponse.json()
        except ValueError as erreur:
            raise ModuleoIndisponible(f"Réponse non JSON sur {route}") from erreur

    def ecrire(self, methode: str, route: str, parametres: dict[str, Any], corps: Any) -> Any:
        url, params = _remplir_ecriture(methode, route, parametres)
        reponse = self._requete(methode, route, url, params, corps)
        # L'écriture a eu lieu : une réponse vide ou non JSON n'est pas une
        # panne.
        if not reponse.content:
            return None
        try:
            return reponse.json()
        except ValueError:
            return reponse.text

    def _requete(self, methode: str, route: str, url: str, params: dict[str, Any], corps: Any) -> httpx.Response:
        try:
            reponse = _http_client.request(
                methode, f"{self._url_base}/{url}", params=params, json=corps, headers=self._en_tetes
            )
        except httpx.HTTPError as erreur:
            raise ModuleoIndisponible(str(erreur)) from erreur
        if reponse.status_code == 400 and methode != "GET":
            raise ModuleoDonneesRefusees(self._sans_secrets(_message_moduleo(reponse)))
        if reponse.status_code in (401, 403):
            message = self._sans_secrets(_message_moduleo(reponse)) if methode != "GET" else None
            raise ModuleoRefuse(f"{reponse.status_code} sur {route}", message or None)
        if reponse.status_code == 404:
            raise ModuleoIntrouvable(f"404 sur {route}")
        if reponse.is_error:
            raise ModuleoIndisponible(f"{reponse.status_code} sur {route}")
        return reponse

    def _sans_secrets(self, texte: str) -> str:
        # Un message de Moduléo qui répéterait la clé ou le code.
        for secret in self._en_tetes.values():
            if secret:
                texte = texte.replace(secret, "…")
        return texte


@cache
def get_client_moduleo() -> ClientModuleo | None:
    # Dépendance des envois de message (spec 1.5.0, #174) : None sans config
    # Moduléo complète et déchiffrable, et les outils Moduléo ne sont pas
    # proposés. Lue une fois par processus, comme le reste de la config.
    config = config_moduleo()
    if config is None:
        return None
    return ClientModuleo(TransportHttp(config.url, config.api_key, config.security_code))


def _remplir(route: str, parametres: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # Une route est un gabarit du WADL (« cogeo/affaire/{idAffaire} »,
    # « cogeo/affaire?texte={texte}&… ») : les paramètres du chemin sont
    # obligatoires, ceux de la requête facultatifs (None = absent).
    if route not in ROUTES_GET:
        raise RequeteInterdite(f"Route {route!r} absente de la table des routes GET.")
    return _gabarit(route, parametres, obligatoires_en_requete=False)


def _remplir_ecriture(methode: str, route: str, parametres: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # Une route d'écriture : tous ses paramètres sont obligatoires, ceux de
    # la requête aussi (« cogeo/archive?idArchive={idArchive}&… »).
    if (methode, route) not in ROUTES_ECRITURE:
        if any(r == route for _, r in ROUTES_ECRITURE):
            raise RequeteInterdite(f"Méthode {methode!r} sans rapport avec la route d'écriture {route!r}.")
        raise RequeteInterdite(f"Route {route!r} absente de la table des routes d'écriture.")
    return _gabarit(route, parametres, obligatoires_en_requete=True)


def _verifier_corps(methode: str, route: str, corps: Any) -> None:
    # Le WADL donne un exemple de corps à chaque route qui en prend un.
    attendu = ROUTES_ECRITURE[(methode, route)].exemple is not None
    if attendu and not isinstance(corps, (dict, list)):
        raise RequeteInterdite(f"Corps JSON attendu pour {methode} {route}.")
    if not attendu and corps is not None:
        raise RequeteInterdite(f"{methode} {route} ne prend pas de corps.")


def _message_moduleo(reponse: httpx.Response) -> str:
    # Le message d'un 400, 401 ou 403 de Moduléo (« Message » de l'API,
    # sinon le texte).
    try:
        donnees = reponse.json()
    except ValueError:
        return reponse.text.strip()
    if isinstance(donnees, dict) and isinstance(donnees.get("Message"), str):
        return donnees["Message"]
    return reponse.text.strip()


def _gabarit(route: str, parametres: dict[str, Any], obligatoires_en_requete: bool) -> tuple[str, dict[str, Any]]:
    chemin, _, requete = route.partition("?")
    noms_chemin = _PARAMETRE.findall(chemin)
    noms_requete = _PARAMETRE.findall(requete)
    inconnus = set(parametres) - set(noms_chemin) - set(noms_requete)
    if inconnus:
        raise RequeteInterdite(f"Paramètres {sorted(inconnus)} absents de la route {route!r}.")
    obligatoires = noms_chemin + (noms_requete if obligatoires_en_requete else [])
    manquants = [nom for nom in obligatoires if parametres.get(nom) is None]
    if manquants:
        raise RequeteInterdite(f"Paramètres {manquants} manquants pour {route!r}.")
    url = _PARAMETRE.sub(lambda m: quote(str(parametres[m.group(1)]), safe=""), chemin)
    params = {nom: parametres[nom] for nom in noms_requete if parametres.get(nom) is not None}
    return url, params
