"""Applicazione CLI di YCTM."""

import logging

import typer
from sqlalchemy.orm import Session

from yctm.config.settings import Settings

app = typer.Typer(help="Acquisisce incrementalmente trascrizioni YouTube.")
logger = logging.getLogger(__name__)


@app.callback()
def main() -> None:
    """Gestisce i comandi disponibili."""


@app.command("init-db")
def init_database(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Inizializza il database SQLite locale."""
    _setup_logging(verbose)
    from yctm.infrastructure.database.session import initialize_database

    settings = _get_settings()
    initialize_database(settings.database_path)
    logger.info("Database inizializzato.")


def _get_settings() -> Settings:
    """Carica le impostazioni da ambiente o file .env."""
    return Settings()


def _get_session(settings: Settings) -> Session:
    """Crea una sessione database a partire dalle impostazioni."""
    from yctm.infrastructure.database.session import create_engine, create_session_factory

    engine = create_engine(settings.database_path)
    return create_session_factory(engine)()


def _setup_logging(verbose: bool = False) -> None:
    """Configura il logging per l'applicazione."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command("channel")
def channel_add(
    identifier: str = typer.Argument(help="ID UC..., handle @... o URL del canale"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Registra un canale YouTube."""
    _setup_logging(verbose)
    settings = _get_settings()

    from yctm.application.channels import register_channel
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        channel = register_channel(settings.youtube_api_key, session, identifier)
        typer.echo(f"Canale registrato: {channel.title} ({channel.id})")
    except ChannelNotFoundError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except QuotaExceededError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    except YouTubeAPIError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    finally:
        session.close()


@app.command("sync")
def sync_channel(
    channel_id: str = typer.Argument(help="ID UC... del canale da sincronizzare"),
    max_results: int = typer.Option(
        0,
        "--max-results",
        help="Numero massimo di video da analizzare (default dalle impostazioni)",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Chiedi conferma prima di scaricare ogni trascrizione"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Sincronizza le trascrizioni degli ultimi video di un canale."""
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.manifest import rebuild_manifest
    from yctm.application.synchronization import synchronize_channel
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        result = synchronize_channel(
            settings.youtube_api_key,
            session,
            channel_id,
            str(settings.transcripts_directory),
            limit,
            interactive=interactive,
        )
        rebuild_manifest(session, settings.manifest_path)
        typer.echo(result.summary)
    except ChannelNotFoundError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except QuotaExceededError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    except YouTubeAPIError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    finally:
        session.close()


@app.command("playlist")
def playlist_add(
    identifier: str = typer.Argument(help="ID playlist (PL...) o URL della playlist"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Registra una playlist YouTube."""
    _setup_logging(verbose)
    settings = _get_settings()

    from yctm.application.playlists import register_playlist
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        playlist = register_playlist(settings.youtube_api_key, session, identifier)
        typer.echo(f"Playlist registrata: {playlist.title} ({playlist.id})")
    except ChannelNotFoundError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except QuotaExceededError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    except YouTubeAPIError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    finally:
        session.close()


@app.command("playlist-sync")
def sync_playlist_command(
    playlist_id: str = typer.Argument(help="ID della playlist (PL...) da sincronizzare"),
    max_results: int = typer.Option(
        0,
        "--max-results",
        help="Numero massimo di video da analizzare (default dalle impostazioni)",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Chiedi conferma prima di scaricare ogni trascrizione"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Sincronizza le trascrizioni dei video di una playlist."""
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.manifest import rebuild_manifest
    from yctm.application.playlists import synchronize_playlist
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        result = synchronize_playlist(
            settings.youtube_api_key,
            session,
            playlist_id,
            str(settings.transcripts_directory),
            limit,
            interactive=interactive,
        )
        rebuild_manifest(session, settings.manifest_path)
        typer.echo(result.summary)
    except ChannelNotFoundError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except QuotaExceededError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    except YouTubeAPIError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    finally:
        session.close()


@app.command("manifest")
def rebuild_manifest_command(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Rigenera il manifest JSONL dai dati presenti."""
    _setup_logging(verbose)
    settings = _get_settings()

    from yctm.application.manifest import rebuild_manifest

    session = _get_session(settings)
    try:
        count = rebuild_manifest(session, settings.manifest_path)
        typer.echo(f"Manifest generato con {count} record in {settings.manifest_path}.")
    finally:
        session.close()
