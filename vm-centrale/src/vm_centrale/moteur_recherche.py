from dataclasses import dataclass
from typing import Protocol

import httpx

from vm_centrale.config import SEARXNG_HTTP_TIMEOUT, SEARXNG_URL

_http_client = httpx.Client(timeout=SEARXNG_HTTP_TIMEOUT)


@dataclass(frozen=True)
class ResultatRecherche:
    titre: str
    url: str
    # Extrait de la page tel que le moteur le renvoie (pas la page elle-même).
    extrait: str


class MoteurIndisponible(Exception):
    # Seule exception d'un MoteurRecherche : l'outil rechercher_web la
    # transforme en texte d'outil « recherche indisponible », jamais en 500.
    pass


class MoteurRecherche(Protocol):
    # Interface du moteur (spec 1.4.0, ADR-0013) : passer à un service payant
    # revient à en écrire une autre implémentation.
    def rechercher(self, requete: str) -> list[ResultatRecherche]: ...


class MoteurSearxng:
    def __init__(self, url_base: str = SEARXNG_URL) -> None:
        self._url_recherche = f"{url_base.rstrip('/')}/search"

    def rechercher(self, requete: str) -> list[ResultatRecherche]:
        try:
            reponse = _http_client.get(self._url_recherche, params={"q": requete, "format": "json"})
            reponse.raise_for_status()
            resultats = reponse.json()["results"]
            return [
                ResultatRecherche(
                    titre=resultat.get("title") or "",
                    url=resultat["url"],
                    extrait=resultat.get("content") or "",
                )
                for resultat in resultats
                if resultat.get("url")
            ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as erreur:
            raise MoteurIndisponible(str(erreur)) from erreur


def get_moteur_recherche() -> MoteurRecherche:
    return MoteurSearxng()
