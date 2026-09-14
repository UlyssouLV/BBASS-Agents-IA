import pytest
from fastapi.testclient import TestClient

from poste.main import app
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import get_vm_centrale_client


class VmCentraleClientFactice:
    def __init__(self) -> None:
        self.appels: list[tuple[str, str]] = []
        self.messages_recus: list[str] = []
        self.jetons_recus: list[str] = []
        self._authentifie = False
        self._exception: Exception | None = None
        self._reponse_message = ""
        self._jeton = "jeton-factice"

    def accepter(self) -> None:
        self._authentifie = True
        self._exception = None

    def rejeter(self) -> None:
        self._authentifie = False
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def repondre(self, reponse: str) -> None:
        self._reponse_message = reponse
        self._exception = None

    def authentifier(self, identifiant: str, mot_de_passe: str) -> str | None:
        self.appels.append((identifiant, mot_de_passe))
        if self._exception is not None:
            raise self._exception
        return self._jeton if self._authentifie else None

    def envoyer_message(self, message: str, jeton: str) -> str:
        self.messages_recus.append(message)
        self.jetons_recus.append(jeton)
        if self._exception is not None:
            raise self._exception
        return self._reponse_message


@pytest.fixture()
def vm_centrale_client_factice():
    return VmCentraleClientFactice()


@pytest.fixture()
def session_store():
    return SessionStore()


@pytest.fixture()
def client(vm_centrale_client_factice, session_store):
    app.dependency_overrides[get_vm_centrale_client] = lambda: vm_centrale_client_factice
    app.dependency_overrides[get_session_store] = lambda: session_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
