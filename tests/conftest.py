import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models import Utilisateur
from app.security import hash_password


@pytest.fixture()
def engine():
    # StaticPool : une base SQLite en mémoire n'existe que pour une connexion
    # donnée ; sans lui, chaque nouvelle connexion ouvrirait une base vide.
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(engine):
    def get_session_de_test():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = get_session_de_test
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def utilisateur_test(engine):
    with Session(engine) as s:
        utilisateur = Utilisateur(
            email="test@exemple.fr",
            mot_de_passe_hash=hash_password("motdepasse123"),
        )
        s.add(utilisateur)
        s.commit()
        s.refresh(utilisateur)
        return utilisateur


@pytest.fixture()
def client_connecte(client, utilisateur_test):
    client.post("/login", data={"email": "test@exemple.fr", "password": "motdepasse123"})
    return client
