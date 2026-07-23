"""Inizializzazione del database SQLite."""

from pathlib import Path

from sqlalchemy import Engine, inspect, text
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import Session, sessionmaker

from yctm.infrastructure.database.models import Base


def create_engine(database_path: Path) -> Engine:
    """Crea il motore SQLite per il percorso indicato."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlalchemy_create_engine(f"sqlite:///{database_path}")


def upgrade_database(engine: Engine) -> None:
    """Esegue migrazioni leggere per aggiornare lo schema del database preesistente."""
    inspector = inspect(engine)
    if "videos" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("videos")}
        with engine.begin() as conn:
            if "description" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN description TEXT"))
            if "discovered_at" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN discovered_at DATETIME"))
                conn.execute(
                    text("UPDATE videos SET discovered_at = created_at WHERE discovered_at IS NULL")
                )


def initialize_database(database_path: Path = Path("data/yctm.sqlite3")) -> None:
    """Crea le tabelle e applica eventuali migrazioni leggere di schema."""
    engine = create_engine(database_path)
    Base.metadata.create_all(engine)
    upgrade_database(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crea sessioni SQLAlchemy per il motore indicato."""
    return sessionmaker(bind=engine)
