import pytest
from fastapi.testclient import TestClient

from poste.main import app
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AuthentificationReussie,
    JetonInvalideError,
    get_vm_centrale_client,
)


class VmCentraleClientFactice:
    def __init__(self) -> None:
        self.appels: list[tuple[str, str]] = []
        self.messages_recus: list[str] = []
        self.jetons_recus: list[str] = []
        self.jetons_verifies: list[str] = []
        self.jetons_revoques: list[str] = []
        self._authentifie = False
        self._exception: Exception | None = None
        self._jeton_rejete_par_le_relais = False
        self._reponse_message = ""
        self._jeton = "jeton-factice"
        self._prenom = "Jean"
        self._nom = "Dupont"
        self._identifiant_verifie: str | None = None
        self._exception_verification: Exception | None = None
        self._exception_revocation: Exception | None = None

    def accepter(self, prenom: str = "Jean", nom: str = "Dupont") -> None:
        self._authentifie = True
        self._exception = None
        self._prenom = prenom
        self._nom = nom

    def rejeter(self) -> None:
        self._authentifie = False
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def repondre(self, reponse: str) -> None:
        self._reponse_message = reponse
        self._exception = None
        self._jeton_rejete_par_le_relais = False

    def rejeter_le_jeton_au_relais(self) -> None:
        # Simule un 401 renvoyé par /relais (jeton révoqué côté VM entre-temps).
        self._jeton_rejete_par_le_relais = True
        self._exception = None

    def verification_reussit(self, identifiant: str) -> None:
        self._identifiant_verifie = identifiant
        self._exception_verification = None

    def verification_echoue(self) -> None:
        self._identifiant_verifie = None
        self._exception_verification = None

    def verification_indisponible(self, exception: Exception) -> None:
        self._exception_verification = exception

    def revocation_echoue(self, exception: Exception) -> None:
        self._exception_revocation = exception

    def authentifier(self, identifiant: str, mot_de_passe: str) -> AuthentificationReussie | None:
        self.appels.append((identifiant, mot_de_passe))
        if self._exception is not None:
            raise self._exception
        if not self._authentifie:
            return None
        return AuthentificationReussie(prenom=self._prenom, nom=self._nom, jeton=self._jeton)

    def envoyer_message(self, message: str, jeton: str) -> str:
        self.messages_recus.append(message)
        self.jetons_recus.append(jeton)
        if self._jeton_rejete_par_le_relais:
            raise JetonInvalideError()
        if self._exception is not None:
            raise self._exception
        return self._reponse_message

    def verifier(self, jeton: str) -> str | None:
        self.jetons_verifies.append(jeton)
        if self._exception_verification is not None:
            raise self._exception_verification
        return self._identifiant_verifie

    def revoquer(self, jeton: str) -> None:
        self.jetons_revoques.append(jeton)
        if self._exception_revocation is not None:
            raise self._exception_revocation


@pytest.fixture(autouse=True)
def keyring_factice(monkeypatch):
    # Aucun test ne doit jamais toucher le vrai gestionnaire d'identifiants
    # Windows : cette fixture le remplace par un stockage en mémoire pour
    # toute la suite.
    stockage: dict[tuple[str, str], str] = {}

    def fake_get_password(service_name: str, username: str) -> str | None:
        return stockage.get((service_name, username))

    def fake_set_password(service_name: str, username: str, password: str) -> None:
        stockage[(service_name, username)] = password

    def fake_delete_password(service_name: str, username: str) -> None:
        if (service_name, username) not in stockage:
            raise RuntimeError("Aucun mot de passe à supprimer pour ce service/utilisateur")
        del stockage[(service_name, username)]

    monkeypatch.setattr("poste.session.keyring.get_password", fake_get_password)
    monkeypatch.setattr("poste.session.keyring.set_password", fake_set_password)
    monkeypatch.setattr("poste.session.keyring.delete_password", fake_delete_password)
    return stockage


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
