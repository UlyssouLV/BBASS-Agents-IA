import pytest
from fastapi.testclient import TestClient

from poste.main import app
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AuthentificationReussie,
    CompteAdmin,
    CompteCree,
    JetonInvalideError,
    VerificationReussie,
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
        self._agence = "Castries"
        self._poles: list[str] = ["Foncier"]
        self._est_admin = False
        self._doit_changer_mot_de_passe = False
        self._identifiant_verifie: str | None = None
        self._est_admin_verifie = False
        self._exception_verification: Exception | None = None
        self._exception_revocation: Exception | None = None
        self._comptes: list[CompteAdmin] = []
        self._exception_liste_comptes: Exception | None = None
        self._jetons_liste_comptes: list[str] = []
        self._compte_cree: CompteCree | None = None
        self._exception_creation_compte: Exception | None = None
        self._requetes_creation_compte: list[dict] = []
        self._jetons_creation_compte: list[str] = []

    def accepter(
        self,
        prenom: str = "Jean",
        nom: str = "Dupont",
        agence: str = "Castries",
        poles: list[str] | None = None,
        est_admin: bool = False,
        doit_changer_mot_de_passe: bool = False,
    ) -> None:
        self._authentifie = True
        self._exception = None
        self._prenom = prenom
        self._nom = nom
        self._agence = agence
        self._poles = poles if poles is not None else ["Foncier"]
        self._est_admin = est_admin
        self._doit_changer_mot_de_passe = doit_changer_mot_de_passe

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

    def verification_reussit(self, identifiant: str, est_admin: bool = False) -> None:
        self._identifiant_verifie = identifiant
        self._est_admin_verifie = est_admin
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
        return AuthentificationReussie(
            prenom=self._prenom,
            nom=self._nom,
            jeton=self._jeton,
            agence=self._agence,
            poles=self._poles,
            est_admin=self._est_admin,
            doit_changer_mot_de_passe=self._doit_changer_mot_de_passe,
        )

    def envoyer_message(self, message: str, jeton: str) -> str:
        self.messages_recus.append(message)
        self.jetons_recus.append(jeton)
        if self._jeton_rejete_par_le_relais:
            raise JetonInvalideError()
        if self._exception is not None:
            raise self._exception
        return self._reponse_message

    def verifier(self, jeton: str) -> VerificationReussie | None:
        self.jetons_verifies.append(jeton)
        if self._exception_verification is not None:
            raise self._exception_verification
        if self._identifiant_verifie is None:
            return None
        return VerificationReussie(identifiant=self._identifiant_verifie, est_admin=self._est_admin_verifie)

    def revoquer(self, jeton: str) -> None:
        self.jetons_revoques.append(jeton)
        if self._exception_revocation is not None:
            raise self._exception_revocation

    def liste_comptes_retourne(self, comptes: list[CompteAdmin]) -> None:
        self._comptes = comptes
        self._exception_liste_comptes = None

    def liste_comptes_echoue(self, exception: Exception) -> None:
        # Couvre aussi bien JetonInvalideError / AccesAdminRequisError
        # (erreurs métier attendues, voir vm_centrale_client) qu'une panne
        # quelconque de la VM centrale.
        self._exception_liste_comptes = exception

    def lister_comptes(self, jeton: str) -> list[CompteAdmin]:
        self._jetons_liste_comptes.append(jeton)
        if self._exception_liste_comptes is not None:
            raise self._exception_liste_comptes
        return self._comptes

    def creation_compte_reussit(self, compte: CompteCree) -> None:
        self._compte_cree = compte
        self._exception_creation_compte = None

    def creation_compte_echoue(self, exception: Exception) -> None:
        self._exception_creation_compte = exception

    def creer_compte(
        self,
        jeton: str,
        identifiant: str,
        prenom: str,
        nom: str,
        agence: str,
        poles: list[str],
        email: str | None = None,
    ) -> CompteCree:
        self._jetons_creation_compte.append(jeton)
        self._requetes_creation_compte.append(
            {
                "identifiant": identifiant,
                "prenom": prenom,
                "nom": nom,
                "email": email,
                "agence": agence,
                "poles": poles,
            }
        )
        if self._exception_creation_compte is not None:
            raise self._exception_creation_compte
        assert self._compte_cree is not None
        return self._compte_cree


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
