"""Test della relazione molti-a-molti Playlist ↔ Video.

Copre:
- Persistenza dell'associazione dopo discover_playlist.
- Filtro `video list --playlist` restituisce solo i video associati.
- Idempotenza dell'associazione (doppia add non duplica riga).
- Video già noto a catalogo: associazione registrata ugualmente.
- CLI `video list --playlist` end-to-end con mock API.
- Migrazione `upgrade_database` crea `playlist_videos` su DB legacy.
"""

import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect, text

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from yctm.application.discovery import discover_playlist
from yctm.cli.app import app
from yctm.infrastructure.database.models import Channel, Playlist, Video
from yctm.infrastructure.database.repositories import (
    PlaylistRepository,
    VideoRepository,
)
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
    upgrade_database,
)
from yctm.infrastructure.youtube.data_api import VideoInfo


def _setup(tmp_path: Path) -> sessionmaker[Session]:
    """DB inizializzato con un canale, una playlist e nessun video."""
    db_path = tmp_path / "yctm.sqlite3"
    initialize_database(db_path)
    engine = create_engine(db_path)
    sessions = create_session_factory(engine)
    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(Playlist(id="PL001", title="Playlist Test", channel_id="UC123"))
        session.commit()
    return sessions


def _make_video_info(video_id: str, channel_id: str = "UC123") -> VideoInfo:
    return VideoInfo(
        id=video_id,
        channel_id=channel_id,
        title=f"Titolo {video_id}",
    )


# ---------------------------------------------------------------------------
# Persistenza associazione
# ---------------------------------------------------------------------------


def test_discover_playlist_registers_association(tmp_path: Path) -> None:
    """discover_playlist deve persistere l'associazione playlist ↔ video."""
    sessions = _setup(tmp_path)
    videos_api = [_make_video_info("v1"), _make_video_info("v2")]

    with patch(
        "yctm.application.discovery.list_playlist_videos",
        return_value=videos_api,
    ):
        with sessions() as session:
            discover_playlist("fake-key", session, "PL001", max_results=10)

    with sessions() as session:
        pl_repo = PlaylistRepository(session)
        playlist = pl_repo.get("PL001")
        assert playlist is not None
        video_ids = {v.id for v in playlist.videos}
        assert "v1" in video_ids
        assert "v2" in video_ids


def test_discover_playlist_association_persists_for_known_video(tmp_path: Path) -> None:
    """Un video già noto deve ricevere l'associazione anche al secondo discovery."""
    sessions = _setup(tmp_path)

    # Prima passata: video scoperto e associato
    with patch(
        "yctm.application.discovery.list_playlist_videos",
        return_value=[_make_video_info("v1")],
    ):
        with sessions() as session:
            discover_playlist("fake-key", session, "PL001")

    # Seconda passata: stessa playlist, v1 già noto → deve registrare l'associazione
    # (path del video già catalogato)
    with patch(
        "yctm.application.discovery.list_playlist_videos",
        return_value=[_make_video_info("v1")],
    ):
        with sessions() as session:
            result = discover_playlist("fake-key", session, "PL001")
            assert result.already_known == 1

    with sessions() as session:
        playlist = PlaylistRepository(session).get("PL001")
        assert playlist is not None
        assert any(v.id == "v1" for v in playlist.videos)


# ---------------------------------------------------------------------------
# Idempotenza
# ---------------------------------------------------------------------------


def test_add_video_is_idempotent(tmp_path: Path) -> None:
    """PlaylistRepository.add_video non deve creare righe duplicate."""
    sessions = _setup(tmp_path)

    # Inserisci il video manualmente
    with sessions() as session:
        session.add(Video(id="v1", title="V", status="not_requested", channel_id="UC123"))
        session.commit()

    # Aggiungi l'associazione due volte
    with sessions() as session:
        repo = PlaylistRepository(session)
        repo.add_video("PL001", "v1")
        repo.add_video("PL001", "v1")  # idempotente
        session.commit()

    with sessions() as session:
        from sqlalchemy import func

        from yctm.infrastructure.database.models import playlist_videos

        count = session.execute(
            session.query(func.count())
            .select_from(playlist_videos)
            .filter(
                playlist_videos.c.playlist_id == "PL001",
                playlist_videos.c.video_id == "v1",
            )
            .statement
        ).scalar()
        assert count == 1, f"Devono esserci 0 duplicati, trovati: {count}"


# ---------------------------------------------------------------------------
# Filtro video list --playlist
# ---------------------------------------------------------------------------


def test_list_videos_filter_by_playlist_returns_only_associated(tmp_path: Path) -> None:
    """VideoRepository.list_videos(playlist_id=...) deve restituire solo i video associati."""
    sessions = _setup(tmp_path)

    with sessions() as session:
        session.add(Video(id="in_pl", title="In playlist", status="not_requested"))
        session.add(Video(id="out_pl", title="Non in playlist", status="not_requested"))
        session.commit()

    with sessions() as session:
        PlaylistRepository(session).add_video("PL001", "in_pl")
        session.commit()

    with sessions() as session:
        results = VideoRepository(session).list_videos(playlist_id="PL001")
        ids = {v.id for v in results}
        assert "in_pl" in ids
        assert "out_pl" not in ids


def test_list_videos_filter_by_playlist_empty_when_no_association(tmp_path: Path) -> None:
    """Se nessun video è associato alla playlist, il filtro deve restituire lista vuota."""
    sessions = _setup(tmp_path)

    with sessions() as session:
        session.add(Video(id="v1", title="V", status="not_requested"))
        session.commit()

    with sessions() as session:
        results = VideoRepository(session).list_videos(playlist_id="PL001")
        assert results == []


def test_list_videos_no_playlist_filter_returns_all(tmp_path: Path) -> None:
    """Senza filtro playlist, list_videos deve restituire tutti i video."""
    sessions = _setup(tmp_path)

    with sessions() as session:
        session.add(Video(id="v1", title="V1", status="not_requested"))
        session.add(Video(id="v2", title="V2", status="not_requested"))
        session.commit()

    with sessions() as session:
        results = VideoRepository(session).list_videos()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------------


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "YCTM_YOUTUBE_API_KEY": "fake-key",
        "YCTM_DATABASE_PATH": str(tmp_path / "yctm.sqlite3"),
        "YCTM_TRANSCRIPTS_DIRECTORY": str(tmp_path / "transcripts"),
    }


def test_cli_video_list_playlist_filter_json(tmp_path: Path) -> None:
    """CLI video list --playlist --format json deve restituire solo i video associati."""
    sessions = _setup(tmp_path)

    with sessions() as session:
        session.add(
            Video(id="in_pl", title="In playlist", status="not_requested", channel_id="UC123")
        )
        session.add(
            Video(id="out_pl", title="Non in playlist", status="not_requested", channel_id="UC123")
        )
        session.commit()

    with sessions() as session:
        PlaylistRepository(session).add_video("PL001", "in_pl")
        session.commit()

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["video", "list", "--playlist", "PL001", "--format", "json"],
        env=_env(tmp_path),
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    ids = {item["id"] for item in data}
    assert "in_pl" in ids
    assert "out_pl" not in ids


def test_cli_video_list_playlist_filter_table(tmp_path: Path) -> None:
    """CLI video list --playlist (formato tabella) deve mostrare solo i video associati."""
    sessions = _setup(tmp_path)

    with sessions() as session:
        session.add(
            Video(id="in_pl", title="In playlist", status="not_requested", channel_id="UC123")
        )
        session.add(Video(id="out_pl", title="Escluso", status="not_requested", channel_id="UC123"))
        session.commit()

    with sessions() as session:
        PlaylistRepository(session).add_video("PL001", "in_pl")
        session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["video", "list", "--playlist", "PL001"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "in_pl" in result.output
    assert "out_pl" not in result.output


# ---------------------------------------------------------------------------
# Migrazione: upgrade_database crea playlist_videos su DB legacy
# ---------------------------------------------------------------------------


def test_upgrade_database_creates_playlist_videos_table(tmp_path: Path) -> None:
    """upgrade_database deve creare la tabella playlist_videos se assente."""
    db_path = tmp_path / "legacy.sqlite3"
    # Crea DB senza playlist_videos (schema < v0.3)
    engine = create_engine(db_path)
    # Crea solo le tabelle base senza playlist_videos
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE playlists (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
                " channel_id TEXT, created_at DATETIME, updated_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE videos (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
                " status TEXT, created_at DATETIME, updated_at DATETIME)"
            )
        )

    tables_before = set(inspect(engine).get_table_names())
    assert "playlist_videos" not in tables_before

    upgrade_database(engine)

    tables_after = set(inspect(engine).get_table_names())
    assert "playlist_videos" in tables_after


def test_upgrade_database_playlist_videos_idempotent(tmp_path: Path) -> None:
    """upgrade_database è idempotente: non solleva errori su DB già aggiornato."""
    db_path = tmp_path / "current.sqlite3"
    initialize_database(db_path)
    engine = create_engine(db_path)
    # Secondo upgrade silenzioso
    upgrade_database(engine)
    assert "playlist_videos" in set(inspect(engine).get_table_names())
