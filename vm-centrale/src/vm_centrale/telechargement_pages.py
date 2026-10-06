import ssl
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
import truststore

from vm_centrale.config import PAGES_HTTP_TIMEOUT

# Au-delà, la page est ignorée sans être lue en entier : une page HTML
# dépasse rarement quelques centaines de kilo-octets.
_TAILLE_MAX_PAGE = 5 * 1024 * 1024

def _creer_client_http() -> httpx.Client:
    # Magasin de certificats du système plutôt que certifi : il complète la
    # chaîne d'un serveur qui n'envoie pas son intermédiaire (#129). La
    # vérification reste toujours active, jamais verify=False.
    # Suivre les redirections : une URL de résultat pointe souvent vers une
    # page déplacée (http → https, URL raccourcie).
    return httpx.Client(
        timeout=PAGES_HTTP_TIMEOUT,
        follow_redirects=True,
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    )


_http_client = _creer_client_http()


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
        # Le timeout du client vaut par opération (connexion, chaque lecture),
        # pas pour la page entière : un serveur qui envoie un octet à la fois
        # tiendrait la requête ouverte. L'échéance globale est donc vérifiée
        # à chaque morceau reçu (dépassement d'une lecture au plus).
        echeance = time.monotonic() + PAGES_HTTP_TIMEOUT
        try:
            with _http_client.stream("GET", url) as reponse:
                type_contenu = reponse.headers.get("content-type", "")
                if reponse.status_code != 200 or "html" not in type_contenu.lower():
                    # Page refusée par l'outil de toute façon : le corps
                    # (PDF, vidéo…) n'est jamais lu.
                    return PageTelechargee(statut=reponse.status_code, type_contenu=type_contenu, corps="")
                morceaux: list[bytes] = []
                taille = 0
                for morceau in reponse.iter_bytes():
                    taille += len(morceau)
                    if taille > _TAILLE_MAX_PAGE:
                        raise PageIndisponible(f"page de plus de {_TAILLE_MAX_PAGE} octets")
                    if time.monotonic() > echeance:
                        raise PageIndisponible(f"délai de {PAGES_HTTP_TIMEOUT:g} s dépassé")
                    morceaux.append(morceau)
                # Même décodage que `reponse.text` : charset de l'en-tête,
                # sinon UTF-8.
                corps = b"".join(morceaux).decode(reponse.encoding or "utf-8", errors="replace")
                return PageTelechargee(statut=reponse.status_code, type_contenu=type_contenu, corps=corps)
        except httpx.HTTPError as erreur:
            raise PageIndisponible(str(erreur) or type(erreur).__name__) from erreur


def get_telechargeur_pages() -> TelechargeurPages:
    return TelechargeurHttpx()
