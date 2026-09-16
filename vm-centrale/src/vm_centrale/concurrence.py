import threading
import time

# VM centrale tourne en un seul process uvicorn (vm_centrale.main.run, pas de
# workers multiples) : les requêtes FastAPI synchrones s'exécutent malgré
# tout dans de vrais threads système du même process (threadpool de
# Starlette), donc un verrou en mémoire par compte suffit à sérialiser les
# écritures concurrentes (Conversation.resume_contexte, ProfilTravail) sans
# recourir à un verrou distribué (ex. advisory lock Postgres) — inutile tant
# qu'il n'y a qu'un seul process VM centrale.


class VerrousParCompte:
    def __init__(self) -> None:
        self._verrou_global = threading.Lock()
        self._verrous: dict[str, threading.Lock] = {}

    def pour(self, identifiant_compte: str) -> threading.Lock:
        with self._verrou_global:
            return self._verrous.setdefault(identifiant_compte, threading.Lock())


verrous_comptes = VerrousParCompte()


_DUREE_CONSERVATION_SECONDES = 300.0


class CacheIdempotence:
    # Déduplique une requête rejouée (relance réseau bas niveau, cf. clé
    # d'idempotence fournie par l'appelant) : la première exécution pour une
    # clé donnée est mémorisée, toute requête suivante avec la même clé
    # (même compte) reçoit la même réponse sans rejouer l'appel Mistral ni
    # ré-écrire en base. Entrées expirées après _DUREE_CONSERVATION_SECONDES
    # (purgées paresseusement, pas de tâche de fond) : une clé n'a besoin de
    # vivre que le temps d'une relance proche dans le temps.
    def __init__(self) -> None:
        self._verrou = threading.Lock()
        self._entrees: dict[tuple[str, str], tuple[float, object]] = {}

    def recuperer(self, identifiant_compte: str, cle: str) -> object | None:
        with self._verrou:
            self._purger()
            entree = self._entrees.get((identifiant_compte, cle))
            return entree[1] if entree is not None else None

    def enregistrer(self, identifiant_compte: str, cle: str, reponse: object) -> None:
        with self._verrou:
            self._entrees[(identifiant_compte, cle)] = (time.monotonic(), reponse)

    def _purger(self) -> None:
        limite = time.monotonic() - _DUREE_CONSERVATION_SECONDES
        perimees = [cle for cle, (horodatage, _) in self._entrees.items() if horodatage < limite]
        for cle in perimees:
            del self._entrees[cle]


cache_idempotence = CacheIdempotence()
