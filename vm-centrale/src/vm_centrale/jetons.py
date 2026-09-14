import secrets


class JetonStore:
    # État en mémoire du processus : pas de persistance disque, pas
    # d'expiration automatique — un jeton reste valide jusqu'au redémarrage
    # du processus de la VM centrale (voir ADR sur le relais protégé).
    def __init__(self) -> None:
        self._jetons: set[str] = set()

    def emettre(self) -> str:
        jeton = secrets.token_urlsafe(32)
        self._jetons.add(jeton)
        return jeton

    def est_valide(self, jeton: str) -> bool:
        return jeton in self._jetons


_jeton_store = JetonStore()


def get_jeton_store() -> JetonStore:
    return _jeton_store
