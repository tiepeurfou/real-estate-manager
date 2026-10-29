import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.services.mail as mail_module
import app.services.releves as releves_module
from app.config import BASE_DIR
from app.database import get_session
from app.main import app
from app.models import Utilisateur
from app.security import hash_password


@pytest.fixture(autouse=True)
def _boite_mail_non_configuree_par_defaut(monkeypatch):
    """Le vrai .env du développeur peut contenir de vrais identifiants Gmail
    (nécessaires pour l'usage réel de l'appli) — les tests ne doivent jamais
    s'y connecter ni dépendre de sa présence/absence. Patché au niveau de
    app.services.mail (plutôt que du router) : c'est là que boite_mail_configuree()/
    nouveau_client_imap() lisent ces constantes, et c'est aussi ce que lit le
    scheduler (app/services/scheduler.py) — sans ce patch au bon endroit, le
    scan automatique pourrait se connecter à la vraie boîte pendant les tests.
    Un test qui veut simuler une boîte configurée repointe explicitement ces
    attributs (voir tests/test_routers/test_ingestion_mail.py)."""
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_ADRESSE", "")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_MOT_DE_PASSE", "")


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


@pytest.fixture()
def dossier_documents_temporaire(monkeypatch):
    """Les tests qui enregistrent un document ne doivent pas écrire dans le
    vrai data/documents du dépôt : on redirige vers un sous-dossier jetable."""
    dossier = BASE_DIR / "data" / "documents_test_tmp"
    monkeypatch.setattr(releves_module, "DOSSIER_DOCUMENTS", dossier)
    yield dossier
    shutil.rmtree(dossier, ignore_errors=True)
