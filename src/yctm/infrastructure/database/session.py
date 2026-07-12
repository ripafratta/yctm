"""Inizializzazione del database SQLite."""

from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import Session, sessionmaker

from yctm.infrastructure.database.models import Base


def create_engine(database_path: Path) -> Engine:
    """Crea il motore SQLite per il percorso indicato."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlalchemy_create_engine(f"sqlite:///{database_path}")


def initialize_database(database_path: Path = Path("data/yctm.sqlite3")) -> None:
    """Crea le tabelle necessarie se non sono gia' presenti."""
    Base.metadata.create_all(create_engine(database_path))


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crea sessioni SQLAlchemy per il motore indicato."""
    return sessionmaker(bind=engine)
