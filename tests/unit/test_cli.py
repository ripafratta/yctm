from pathlib import Path

from typer.testing import CliRunner

from yctm.cli.app import app
from yctm.infrastructure.database.session import initialize_database


def test_help_lists_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.stdout
    assert "init-db" in result.stdout
    assert "channel" in result.stdout
    assert "playlist" in result.stdout
    assert "discover" in result.stdout
    assert "video" in result.stdout
    assert "transcript" in result.stdout
    assert "stats" in result.stdout


def test_init_db_command_succeeds(tmp_path: Path) -> None:
    db_path = tmp_path / "yctm.sqlite3"
    initialize_database(db_path)
    result = CliRunner().invoke(app, ["init-db"])
    assert result.exit_code == 0


def test_deprecated_sync_warning() -> None:
    result = CliRunner().invoke(app, ["sync", "UC123"])
    assert "ATTENZIONE: 'yctm sync' è deprecato" in result.stderr
