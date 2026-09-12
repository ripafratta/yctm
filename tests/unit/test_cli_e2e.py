"""Test CLI end-to-end: database e directory temporanee reali.

Verifica i comandi principali tramite typer.testing.CliRunner con
database SQLite su tmp_path e mock delle chiamate API YouTube.
"""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from yctm.cli.app import app
from yctm.infrastructure.database.models import Channel, Video
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from yctm.infrastructure.youtube.transcripts import TranscriptExtractionError


def _env(tmp_path: Path) -> dict[str, str]:
    """Variabili d'ambiente minime per puntare al DB temporaneo."""
    return {
        "YCTM_YOUTUBE_API_KEY": "fake-key",
        "YCTM_DATABASE_PATH": str(tmp_path / "yctm.sqlite3"),
        "YCTM_TRANSCRIPTS_DIRECTORY": str(tmp_path / "transcripts"),
    }


def _seed_db(tmp_path: Path) -> None:
    """Crea DB e inserisce dati di test."""
    db_path = tmp_path / "yctm.sqlite3"
    initialize_database(db_path)
    engine = create_engine(db_path)
    sessions = create_session_factory(engine)
    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(
            Video(
                id="vid1",
                channel_id="UC123",
                title="Video Uno",
                status="not_requested",
            )
        )
        session.add(
            Video(
                id="vid2",
                channel_id="UC123",
                title="Video Due",
                status="stored",
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# init-db
# ---------------------------------------------------------------------------


def test_cli_init_db_creates_database(tmp_path: Path) -> None:
    """init-db deve creare il database e terminare con exit code 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["init-db"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "yctm.sqlite3").exists()


def test_cli_db_upgrade_succeeds(tmp_path: Path) -> None:
    """db upgrade su un DB già aggiornato deve essere idempotente e terminare con exit 0."""
    runner = CliRunner()
    runner.invoke(app, ["init-db"], env=_env(tmp_path))
    result = runner.invoke(app, ["db", "upgrade"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# video list — filtri e formati
# ---------------------------------------------------------------------------


def test_cli_video_list_table_output(tmp_path: Path) -> None:
    """video list deve stampare l'intestazione della tabella e i video presenti."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "list"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "VIDEO_ID" in result.output
    assert "vid1" in result.output
    assert "vid2" in result.output


def test_cli_video_list_filter_by_status(tmp_path: Path) -> None:
    """video list --status stored deve restituire solo i video stored."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "list", "--status", "stored"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "vid2" in result.output
    assert "vid1" not in result.output


def test_cli_video_list_filter_not_requested(tmp_path: Path) -> None:
    """video list --status not_requested deve restituire solo i video not_requested."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "list", "--status", "not_requested"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "vid1" in result.output
    assert "vid2" not in result.output


def test_cli_video_list_json_output(tmp_path: Path) -> None:
    """video list --format json deve produrre JSON valido con i campi attesi."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "list", "--format", "json"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 2
    ids = {item["id"] for item in data}
    assert "vid1" in ids
    assert "vid2" in ids
    # Verifica presenza dei campi chiave
    first = data[0]
    assert "id" in first
    assert "title" in first
    assert "status" in first
    assert "channel_id" in first


def test_cli_video_list_json_status_filter(tmp_path: Path) -> None:
    """video list --format json --status stored deve produrre lista con solo video stored."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["video", "list", "--format", "json", "--status", "stored"],
        env=_env(tmp_path),
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert all(item["status"] == "stored" for item in data)


def test_cli_video_show_existing_video(tmp_path: Path) -> None:
    """video show deve stampare i dettagli del video richiesto."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "show", "vid1"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "vid1" in result.output
    assert "Video Uno" in result.output


def test_cli_video_show_not_found_returns_exit_2(tmp_path: Path) -> None:
    """video show per un ID inesistente deve restituire exit code 2."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["video", "show", "nonexistent"], env=_env(tmp_path))
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_cli_stats_shows_catalog_counts(tmp_path: Path) -> None:
    """stats deve mostrare il conteggio corretto dei video nel catalogo."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["stats"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "Video catalogati" in result.output
    assert "2" in result.output


# ---------------------------------------------------------------------------
# transcript fetch — end-to-end con mock
# ---------------------------------------------------------------------------


def test_cli_transcript_fetch_stores_file(tmp_path: Path) -> None:
    """transcript fetch deve scaricare e salvare la trascrizione."""
    _seed_db(tmp_path)
    runner = CliRunner()
    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo video uno", "it"),
    ):
        result = runner.invoke(app, ["transcript", "fetch", "vid1"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    transcripts_dir = tmp_path / "transcripts"
    files = list(transcripts_dir.glob("*.md"))
    assert len(files) == 1


def test_cli_transcript_fetch_video_not_in_catalog_returns_exit_2(tmp_path: Path) -> None:
    """transcript fetch per un video non a catalogo deve restituire exit code 2."""
    runner = CliRunner()
    runner.invoke(app, ["init-db"], env=_env(tmp_path))
    result = runner.invoke(app, ["transcript", "fetch", "not_in_db"], env=_env(tmp_path))
    assert result.exit_code == 2


def test_cli_transcript_fetch_prints_rate_limit_warning(tmp_path: Path) -> None:
    """Verifica che in caso di errore 429 la CLI mostri l'avviso sui cookie."""
    _seed_db(tmp_path)
    runner = CliRunner()
    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptExtractionError("HTTP 429 Too Many Requests"),
    ):
        result = runner.invoke(app, ["transcript", "fetch", "vid1"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "Tip: YouTube potrebbe aver applicato un blocco IP" in result.output
    assert "--cookies data/cookies.txt" in result.output


# ---------------------------------------------------------------------------
# channel list e playlist list
# ---------------------------------------------------------------------------


def test_cli_channel_list_empty(tmp_path: Path) -> None:
    """channel list su DB vuoto deve indicare che non ci sono canali."""
    runner = CliRunner()
    runner.invoke(app, ["init-db"], env=_env(tmp_path))
    result = runner.invoke(app, ["channel", "list"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "Nessun canale" in result.output


def test_cli_channel_list_shows_registered_channel(tmp_path: Path) -> None:
    """channel list deve mostrare i canali presenti nel catalogo."""
    _seed_db(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["channel", "list"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "UC123" in result.output
    assert "Canale Test" in result.output
