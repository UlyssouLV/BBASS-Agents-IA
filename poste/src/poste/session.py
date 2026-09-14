class SessionStore:
    # État en mémoire du processus : pas de persistance disque, pas
    # d'expiration automatique (voir CONTEXT.md, "Session"). Une seule
    # session à la fois, puisqu'un poste n'a qu'un collaborateur connecté.
    # Le jeton de la VM centrale vit ici, jamais persisté, effacé avec le
    # reste de la session à la déconnexion.
    def __init__(self) -> None:
        self._identifiant: str | None = None
        self._jeton: str | None = None

    @property
    def est_connecte(self) -> bool:
        return self._identifiant is not None

    @property
    def identifiant(self) -> str | None:
        return self._identifiant

    @property
    def jeton(self) -> str | None:
        return self._jeton

    def ouvrir(self, identifiant: str, jeton: str) -> None:
        self._identifiant = identifiant
        self._jeton = jeton

    def fermer(self) -> None:
        self._identifiant = None
        self._jeton = None


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store
