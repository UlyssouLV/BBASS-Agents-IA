class SessionStore:
    # État en mémoire du processus : pas de persistance disque, pas
    # d'expiration automatique (voir CONTEXT.md, "Session"). Une seule
    # session à la fois, puisqu'un poste n'a qu'un collaborateur connecté.
    def __init__(self) -> None:
        self._identifiant: str | None = None

    @property
    def est_connecte(self) -> bool:
        return self._identifiant is not None

    @property
    def identifiant(self) -> str | None:
        return self._identifiant

    def ouvrir(self, identifiant: str) -> None:
        self._identifiant = identifiant

    def fermer(self) -> None:
        self._identifiant = None


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store
