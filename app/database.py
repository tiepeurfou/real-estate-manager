from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_PATH

engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Créé les tables à partir des modèles. Utilisé par les tests ;
    en exploitation, le schéma est géré par les migrations Alembic."""
    SQLModel.metadata.create_all(engine)
