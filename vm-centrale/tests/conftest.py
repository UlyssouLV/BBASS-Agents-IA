import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from vm_centrale.database import Base, get_db
from vm_centrale.main import app
from vm_centrale.mistral_client import get_mistral_client
from vm_centrale.models import Compte, ComptePole
from vm_centrale.security import hash_password
from vm_centrale.jetons import JetonStore, get_jeton_store


@pytest.fixture(autouse=True)
def _concurrence_reinitialisee():
    # cache_idempotence et verrous_comptes sont des singletons module-level
    # (partagés par toutes les requêtes d'un même process VM centrale, voir
    # vm_centrale.concurrence), donc aussi partagés par tous les tests d'une
    # même session pytest sans ce reset : une clé d'idempotence réutilisée
    # par deux tests différents renverrait sinon la réponse mise en cache par
    # le premier test au second.
    from vm_centrale.concurrence import cache_idempotence, verrous_comptes

    cache_idempotence._entrees.clear()
    verrous_comptes._verrous.clear()
    yield


@pytest.fixture(autouse=True)
def _sans_init_db_reel(monkeypatch):
    # Le lifespan de l'app appelle `init_db()` sur l'engine réel (lié à
    # VM_CENTRALE_DATABASE_URL), en dehors du système de dependency_overrides
    # utilisé pour `get_db`. Sans ce patch, tout `TestClient(app)` exigerait
    # un PostgreSQL local démarré, alors que les tests tournent sur SQLite en
    # mémoire (fixture `db_session`) et ne doivent dépendre d'aucun service
    # externe.
    monkeypatch.setattr("vm_centrale.main.init_db", lambda: None)


class ClientMistralFactice:
    # Le routeur envoyer_message lance désormais l'appel de réponse et
    # l'appel résumé+profil en parallèle (vrais threads, cf.
    # vm_centrale.routers.conversations.envoyer_message) : ce double doit
    # donc être thread-safe (verrou) et distinguer les deux types d'appel
    # par response_format plutôt que par ordre d'arrivée, qui n'est plus
    # déterministe entre deux appels concurrents.
    def __init__(self) -> None:
        self.messages_recus: list = []
        self.response_formats_recus: list = []
        # Prompts reçus par type d'appel, dans l'ordre — utiliser ces listes
        # plutôt que messages_recus/response_formats_recus pour retrouver
        # « le dernier appel de réponse de chat » ou « le dernier appel
        # résumé+profil », dont l'ordre d'arrivée relatif n'est pas garanti.
        self.appels_reponse: list = []
        self.appels_structures: list = []
        self._verrou = threading.Lock()
        self._reponses: list[str] = []
        self._reponse_structuree: str | None = None
        self._exception: Exception | None = None

    def repondre(self, *reponses: str, resume_et_profil: str | None = None) -> None:
        # `reponses` : file pour les appels sans response_format (réponse de
        # chat, titrage) — un appel consomme la réponse suivante, sauf s'il
        # n'en reste qu'une, alors répétée indéfiniment (cas d'usage
        # historique à un seul `client.chat` par requête, ex. `/relais`).
        # `resume_et_profil` : réponse dédiée à l'appel structuré
        # (response_format non None), indépendante de cette file puisque cet
        # appel peut s'exécuter en parallèle du premier.
        self._reponses = list(reponses)
        self._reponse_structuree = resume_et_profil
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def chat(self, messages, response_format=None) -> str:
        with self._verrou:
            self.messages_recus.append(messages)
            self.response_formats_recus.append(response_format)
            if response_format is not None:
                self.appels_structures.append(messages)
            else:
                self.appels_reponse.append(messages)

            if self._exception is not None:
                raise self._exception

            if response_format is not None:
                assert self._reponse_structuree is not None, (
                    "Aucune réponse structurée configurée : passer resume_et_profil= à repondre()"
                )
                return self._reponse_structuree

            assert self._reponses, "Aucune réponse configurée : appeler repondre() d'abord"
            if len(self._reponses) > 1:
                return self._reponses.pop(0)
            return self._reponses[0]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def mistral_client_factice():
    return ClientMistralFactice()


@pytest.fixture()
def jeton_store(db_session):
    return JetonStore(db_session)


@pytest.fixture()
def client(db_session, mistral_client_factice, jeton_store):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mistral_client] = lambda: mistral_client_factice
    app.dependency_overrides[get_jeton_store] = lambda: jeton_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def jeton_valide(jeton_store):
    return jeton_store.emettre("j.dupont")


@pytest.fixture()
def seed_compte(db_session):
    def _seed(
        identifiant: str,
        mot_de_passe: str,
        agence: str,
        poles: list[str],
        prenom: str,
        nom: str,
        email: str | None = None,
        est_admin: bool = False,
        doit_changer_mot_de_passe: bool = False,
    ) -> Compte:
        compte = Compte(
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            prenom=prenom,
            nom=nom,
            email=email,
            agence=agence,
            est_admin=est_admin,
            doit_changer_mot_de_passe=doit_changer_mot_de_passe,
            poles=[ComptePole(pole=p) for p in poles],
        )
        db_session.add(compte)
        db_session.commit()
        db_session.refresh(compte)
        return compte

    return _seed
