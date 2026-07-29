from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.infrastructure.db import (
    models,  # noqa: F401 — registers tables on SQLModel.metadata
)
from app.infrastructure.db.migrations import run_migrations
from app.settings import get_settings

settings = get_settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{settings.database_path}", connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    # create_all never alters existing tables, so databases predating a model change are brought
    # up to date here.
    run_migrations(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
