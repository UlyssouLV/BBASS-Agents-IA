from dataclasses import dataclass
from typing import Protocol

import httpx

from vm_centrale.config import PAGES_HTTP_TIMEOUT

# Suivre les redirections : une URL de résultat pointe souvent vers une page
# déplacée (http → https, URL raccourcie).
_http_client = httpx.Client(timeout=PAGES_HTTP_TIMEOUT, follow_redirects=True)


@dataclass(frozen=True)
class PageTelechargee:
    statut: int
    # En-tête Content-Type tel que le serveur le renvoie (vide s'il manque).
    type_contenu: str
    corps: str


class PageIndisponible(Exception):
    # Seule exception d'un TelechargeurPages (délai dépassé, serveur
    # injoignable) : rechercher_web ignore alors la page et garde l'extrait
    # du moteur, jamais une erreur.
    pass


class TelechargeurPages(Protocol):
    # Téléchargement d'une page trouvée par le moteur (spec 1.4.0, étape 2).
    # Statut HTTP et type de contenu sont jugés par l'outil, pas ici.
    def telecharger(self, url: str) -> PageTelechargee: ...


class TelechargeurHttpx:
    def telecharger(self, url: str) -> PageTelechargee:
        try:
            reponse = _http_client.get(url)
            return PageTelechargee(
                statut=reponse.status_code,
                type_contenu=reponse.headers.get("content-type", ""),
                corps=reponse.text,
            )
        except httpx.HTTPError as erreur:
            raise PageIndisponible(str(erreur) or type(erreur).__name__) from erreur


def get_telechargeur_pages() -> TelechargeurPages:
    return TelechargeurHttpx()
