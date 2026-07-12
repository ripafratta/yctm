from typer.testing import CliRunner

from yctm.cli.app import app
from yctm.infrastructure.database.session import initialize_database


def test_help_lists_init_db_command() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.stdout
    assert "init-db" in result.stdout
    assert "channel" in result.stdout
    assert "sync" in result.stdout
    assert "manifest" in result.stdout


def test_init_db_command_succeeds(tmp_path) -> None:

    db_path = tmp_path / "yctm.sqlite3"
    # Create the database first to avoid .env dependency
    initialize_database(db_path)
    # Just verify the CLI command exists and runs
    result = CliRunner().invoke(app, ["init-db"])
    assert result.exit_code == 0
