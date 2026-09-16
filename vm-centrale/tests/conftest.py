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
def _sans_init_db_reel(monkeypatch):
    # Le lifespan de l'app appelle `init_db()` sur l'engine réel (lié à
    # VM_CENTRALE_DATABASE_URL), en dehors du système de dependency_overrides
    # utilisé pour `get_db`. Sans ce patch, tout `TestClient(app)` exigerait
    # un PostgreSQL local démarré, alors que les tests tournent sur SQLite en
    # mémoire (fixture `db_session`) et ne doivent dépendre d'aucun service
    # externe.
    monkeypatch.setattr("vm_centrale.main.init_db", lambda: None)


class ClientMistralFactice:
    def __init__(self) -> None:
        self.messages_recus: list[str] = []
        self._reponse: str | None = None
        self._exception: Exception | None = None

    def repondre(self, reponse: str) -> None:
        self._reponse = reponse
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def chat(self, message: str) -> str:
        self.messages_recus.append(message)
        if self._exception is not None:
            raise self._exception
        assert self._reponse is not None
        return self._reponse


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
