"""Test di migrazione dello schema SQLite da versioni precedenti.

Verifica che upgrade_database aggiunga correttamente le colonne
'description' e 'discovered_at' a database creati senza di esse.
"""

from pathlib import Path

from sqlalchemy import inspect, text

from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
    upgrade_database,
)


def _create_legacy_database(db_path: Path) -> None:
    """Crea un database con schema v1 (senza description e discovered_at)."""
    engine = create_engine(db_path)
    # Crea la tabella videos senza le colonne aggiunte in v0.2
    with engine.begin() as conn:
        conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY,
                    handle TEXT,
                    title TEXT NOT NULL,
                    uploads_playlist_id TEXT UNIQUE NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
        )
        conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    channel_id TEXT REFERENCES channels(id),
                    title TEXT NOT NULL,
                    published_at DATETIME,
                    status TEXT NOT NULL DEFAULT 'not_requested',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at DATETIME,
                    last_error TEXT,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
        )
        conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS transcript_files (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT UNIQUE REFERENCES videos(id),
                    storage_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    extracted_at DATETIME
                )
            """)
        )
        conn.execute(
            text("""
                INSERT INTO videos (id, title, status, created_at, updated_at)
                VALUES ('v_legacy', 'Legacy Video', 'not_requested',
                        '2024-01-01 00:00:00', '2024-01-01 00:00:00')
            """)
        )
    engine.dispose()


def test_upgrade_adds_description_column(tmp_path: Path) -> None:
    """upgrade_database deve aggiungere la colonna 'description' allo schema legacy."""
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(db_path)
    engine = create_engine(db_path)

    columns_before = {c["name"] for c in inspect(engine).get_columns("videos")}
    assert "description" not in columns_before

    upgrade_database(engine)

    columns_after = {c["name"] for c in inspect(engine).get_columns("videos")}
    assert "description" in columns_after


def test_upgrade_adds_discovered_at_column(tmp_path: Path) -> None:
    """upgrade_database deve aggiungere la colonna 'discovered_at' allo schema legacy."""
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(db_path)
    engine = create_engine(db_path)

    columns_before = {c["name"] for c in inspect(engine).get_columns("videos")}
    assert "discovered_at" not in columns_before

    upgrade_database(engine)

    columns_after = {c["name"] for c in inspect(engine).get_columns("videos")}
    assert "discovered_at" in columns_after


def test_upgrade_backfills_discovered_at_from_created_at(tmp_path: Path) -> None:
    """upgrade_database deve copiare created_at in discovered_at per le righe esistenti."""
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(db_path)
    engine = create_engine(db_path)

    upgrade_database(engine)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT discovered_at, created_at FROM videos WHERE id='v_legacy'")
        ).fetchone()

    assert row is not None
    assert row[0] is not None, "discovered_at deve essere valorizzato dopo la migrazione"
    assert row[0] == row[1], "discovered_at deve avere lo stesso valore di created_at"


def test_upgrade_is_idempotent_on_current_schema(tmp_path: Path) -> None:
    """upgrade_database su uno schema già aggiornato non deve sollevare eccezioni."""
    db_path = tmp_path / "current.sqlite3"
    initialize_database(db_path)
    engine = create_engine(db_path)

    # Secondo upgrade: deve essere un no-op silenzioso
    upgrade_database(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("videos")}
    assert "description" in columns
    assert "discovered_at" in columns


def test_upgrade_preserves_existing_data(tmp_path: Path) -> None:
    """I record preesistenti non devono essere alterati dopo la migrazione."""
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_database(db_path)
    engine = create_engine(db_path)

    upgrade_database(engine)

    sessions = create_session_factory(engine)
    with sessions() as session:
        from yctm.infrastructure.database.repositories import VideoRepository

        video = VideoRepository(session).get("v_legacy")
        assert video is not None
        assert video.title == "Legacy Video"
        assert video.status == "not_requested"
