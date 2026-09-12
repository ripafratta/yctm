"""Applicazione CLI di YCTM (YouTube Source and Transcript Catalog)."""

import json
import logging
from datetime import datetime

import typer
from sqlalchemy.orm import Session

from yctm.config.settings import Settings

app = typer.Typer(
    name="yctm",
    help="YCTM: YouTube Source and Transcript Catalog",
    no_args_is_help=True,
)

channel_app = typer.Typer(help="Gestione delle fonti canale YouTube.", no_args_is_help=True)
playlist_app = typer.Typer(help="Gestione delle fonti playlist YouTube.", no_args_is_help=True)
discover_app = typer.Typer(
    help="Discovery dei metadati dai canali e playlist.", no_args_is_help=True
)
video_app = typer.Typer(help="Consultazione e discovery del catalogo video.", no_args_is_help=True)
transcript_app = typer.Typer(
    help="Estrazione puntuale e gestione delle trascrizioni.", no_args_is_help=True
)
db_app = typer.Typer(help="Gestione del database SQLite locale.", no_args_is_help=True)

app.add_typer(channel_app, name="channel")
app.add_typer(playlist_app, name="playlist")
app.add_typer(discover_app, name="discover")
app.add_typer(video_app, name="video")
app.add_typer(transcript_app, name="transcript")
app.add_typer(db_app, name="db")

logger = logging.getLogger(__name__)


def _get_settings() -> Settings:
    return Settings()


def _get_session(settings: Settings) -> Session:
    from yctm.infrastructure.database.session import create_engine, create_session_factory

    engine = create_engine(settings.database_path)
    return create_session_factory(engine)()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            typer.echo(f"Errore formato data '{date_str}'. Usa YYYY-MM-DD.", err=True)
            raise typer.Exit(code=1) from exc


def _check_rate_limit_warning(last_error: str | None) -> None:
    """Stampa un messaggio d'avviso se l'errore indica blocchi IP o rate-limiting."""
    if not last_error:
        return
    err_msg = last_error.lower()
    keywords = ["429", "too many requests", "rate", "block", "ip", "impossibile accedere"]
    if any(kw in err_msg for kw in keywords):
        typer.echo(
            "\n💡 Tip: YouTube potrebbe aver applicato un blocco IP o un limite di "
            "richieste (HTTP 429).\n"
            "   Per superare il blocco, esporta i cookie da una sessione browser autenticata "
            "in formato Netscape\n"
            "   e passali con '--cookies data/cookies.txt' oppure imposta YCTM_COOKIES_PATH "
            "nel file .env.",
            err=True,
        )


# -----------------------------------------------------------------------------
# Database Commands
# -----------------------------------------------------------------------------


@app.command("init-db")
@db_app.command("init")
def init_database(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Inizializza il database SQLite locale."""
    _setup_logging(verbose)
    from yctm.infrastructure.database.session import initialize_database

    settings = _get_settings()
    initialize_database(settings.database_path)
    typer.echo(f"Database inizializzato/verificato in {settings.database_path}.")


@db_app.command("upgrade")
def upgrade_database_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Aggiorna lo schema del database preesistente."""
    _setup_logging(verbose)
    from yctm.infrastructure.database.session import create_engine, upgrade_database

    settings = _get_settings()
    engine = create_engine(settings.database_path)
    upgrade_database(engine)
    typer.echo("Database aggiornato con successo.")


# -----------------------------------------------------------------------------
# Channel Commands
# -----------------------------------------------------------------------------


@channel_app.command("add")
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


@channel_app.command("list")
def channel_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Elenca tutti i canali registrati."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.channels import list_channels

    session = _get_session(settings)
    try:
        channels = list_channels(session)
        if not channels:
            typer.echo("Nessun canale registrato.")
            return
        typer.echo(f"{'ID CANALE':<26} {'HANDLE':<20} {'TITOLO'}")
        typer.echo("-" * 75)
        for ch in channels:
            handle_str = ch.handle or ""
            typer.echo(f"{ch.id:<26} {handle_str:<20} {ch.title}")
    finally:
        session.close()


@channel_app.command("remove")
def channel_remove(
    channel_id: str = typer.Argument(help="ID UC... del canale da rimuovere"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Rimuove un canale registrato."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.channels import remove_channel

    session = _get_session(settings)
    try:
        if remove_channel(session, channel_id):
            typer.echo(f"Canale '{channel_id}' rimosso.")
        else:
            typer.echo(f"Canale '{channel_id}' non trovato.", err=True)
            raise typer.Exit(code=2)
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Playlist Commands
# -----------------------------------------------------------------------------


@playlist_app.command("add")
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


@playlist_app.command("list")
def playlist_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Elenca tutte le playlist registrate."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.playlists import list_playlists

    session = _get_session(settings)
    try:
        playlists = list_playlists(session)
        if not playlists:
            typer.echo("Nessuna playlist registrata.")
            return
        typer.echo(f"{'ID PLAYLIST':<36} {'CANALE ID':<26} {'TITOLO'}")
        typer.echo("-" * 80)
        for pl in playlists:
            ch_id = pl.channel_id or ""
            typer.echo(f"{pl.id:<36} {ch_id:<26} {pl.title}")
    finally:
        session.close()


@playlist_app.command("remove")
def playlist_remove(
    playlist_id: str = typer.Argument(help="ID PL... della playlist da rimuovere"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Rimuove una playlist registrata."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.playlists import remove_playlist

    session = _get_session(settings)
    try:
        if remove_playlist(session, playlist_id):
            typer.echo(f"Playlist '{playlist_id}' rimossa.")
        else:
            typer.echo(f"Playlist '{playlist_id}' non trovata.", err=True)
            raise typer.Exit(code=2)
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Discover Commands
# -----------------------------------------------------------------------------


@discover_app.command("channel")
def discover_channel_cmd(
    channel_id: str = typer.Argument(help="ID UC... del canale da analizzare"),
    max_results: int = typer.Option(
        0, "--max-results", help="Numero massimo di video (default dalle impostazioni)"
    ),
    since: str = typer.Option(
        None, "--since", help="Filtra video pubblicati da questa data (YYYY-MM-DD)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simula il discovery senza salvare nel DB"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Esegue il discovery dei metadati dei video per un canale."""
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results
    since_dt = _parse_date(since)

    from yctm.application.discovery import discover_channel
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        res = discover_channel(
            settings.youtube_api_key,
            session,
            channel_id,
            max_results=limit,
            since=since_dt,
            dry_run=dry_run,
        )
        typer.echo(res.summary)
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


@discover_app.command("playlist")
def discover_playlist_cmd(
    playlist_id: str = typer.Argument(help="ID PL... della playlist da analizzare"),
    max_results: int = typer.Option(
        0, "--max-results", help="Numero massimo di video (default dalle impostazioni)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simula il discovery senza salvare nel DB"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Esegue il discovery dei metadati dei video per una playlist."""
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.discovery import discover_playlist
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        res = discover_playlist(
            settings.youtube_api_key,
            session,
            playlist_id,
            max_results=limit,
            dry_run=dry_run,
        )
        typer.echo(res.summary)
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


@discover_app.command("all")
def discover_all_cmd(
    max_results: int = typer.Option(
        0, "--max-results", help="Numero massimo di video per fonte (default dalle impostazioni)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simula il discovery senza salvare nel DB"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Esegue il discovery per tutti i canali e playlist registrati."""
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.discovery import discover_all
    from yctm.infrastructure.youtube.data_api import QuotaExceededError, YouTubeAPIError

    session = _get_session(settings)
    try:
        results = discover_all(
            settings.youtube_api_key,
            session,
            max_results=limit,
            dry_run=dry_run,
        )
        if not results:
            typer.echo("Nessuna fonte registrata.")
            return
        for source, res in results.items():
            typer.echo(f"{source}: {res.summary}")
    except QuotaExceededError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=4) from exc
    except YouTubeAPIError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Video Commands
# -----------------------------------------------------------------------------


@video_app.command("list")
def video_list_cmd(
    status: str = typer.Option(
        None,
        "--status",
        help="Filtra per stato (not_requested, stored, retryable_error, terminal_error)",
    ),
    channel: str = typer.Option(None, "--channel", help="Filtra per ID canale"),
    playlist: str = typer.Option(None, "--playlist", help="Filtra per ID playlist"),
    after: str = typer.Option(None, "--after", help="Video pubblicati da questa data (YYYY-MM-DD)"),
    before: str = typer.Option(
        None, "--before", help="Video pubblicati fino a questa data (YYYY-MM-DD)"
    ),
    limit: int = typer.Option(50, "--limit", help="Numero massimo di risultati (default: 50)"),
    offset: int = typer.Option(0, "--offset", help="Paginazione offset (default: 0)"),
    format: str = typer.Option("table", "--format", help="Formato output: table o json"),
    order: str = typer.Option(
        "published-desc", "--order", help="Ordinamento: published-desc o published-asc"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Elenca i video catalogati."""
    _setup_logging(verbose)
    settings = _get_settings()

    after_dt = _parse_date(after)
    before_dt = _parse_date(before)

    from yctm.application.catalog import list_catalog_videos

    session = _get_session(settings)
    try:
        videos = list_catalog_videos(
            session,
            status=status,
            channel_id=channel,
            playlist_id=playlist,
            after=after_dt,
            before=before_dt,
            limit=limit,
            offset=offset,
            order=order,
        )

        if format == "json":
            typer.echo(json.dumps(videos, indent=2, ensure_ascii=False))
            return

        if not videos:
            typer.echo("Nessun video trovato.")
            return

        typer.echo(f"{'VIDEO_ID':<12} {'PUBBLICATO':<12} {'CANALE':<20} {'TITOLO':<40} {'STATO'}")
        typer.echo("-" * 95)
        for v in videos:
            v_id = v["id"]
            pub = v["published_at"][:10] if v["published_at"] else "N/A"
            ch = (v["channel_title"] or v["channel_id"] or "")[:19]
            title = (v["title"] or "")[:39]
            st = v["status"]
            typer.echo(f"{v_id:<12} {pub:<12} {ch:<20} {title:<40} {st}")
    finally:
        session.close()


@video_app.command("show")
def video_show_cmd(
    video_id: str = typer.Argument(help="ID del video YouTube"),
    format: str = typer.Option("table", "--format", help="Formato output: table o json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Mostra le informazioni dettagliate di un singolo video."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.catalog import get_video_details

    session = _get_session(settings)
    try:
        details = get_video_details(session, video_id)
        if details is None:
            typer.echo(f"Video '{video_id}' non trovato nel catalogo locale.", err=True)
            raise typer.Exit(code=2)

        if format == "json":
            typer.echo(json.dumps(details, indent=2, ensure_ascii=False))
            return

        typer.echo(f"ID Video:        {details['id']}")
        typer.echo(f"Titolo:          {details['title']}")
        typer.echo(f"Canale:          {details['channel_title']} ({details['channel_id']})")
        typer.echo(f"Pubblicato il:   {details['published_at']}")
        typer.echo(f"Scoperto il:     {details['discovered_at']}")
        typer.echo(f"Stato Transcript:{details['status']}")
        typer.echo(f"Tentativi:       {details['attempt_count']}")
        if details["last_error"]:
            typer.echo(f"Ultimo Errore:   {details['last_error']}")
        if details["transcript_file"]:
            tf = details["transcript_file"]
            typer.echo(f"File Transcript: {tf['storage_path']} ({tf['language_code']})")
            typer.echo(f"SHA-256:         {tf['sha256']}")
        if details["description"]:
            typer.echo("\nDescrizione:")
            typer.echo(details["description"])
    finally:
        session.close()


@video_app.command("discover")
def video_discover_cmd(
    video_id: str = typer.Argument(help="ID del singolo video YouTube da censire"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Esegue il discovery e la registrazione di un singolo video nel catalogo."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.discovery import discover_video
    from yctm.infrastructure.youtube.data_api import (
        ChannelNotFoundError,
        QuotaExceededError,
        YouTubeAPIError,
    )

    session = _get_session(settings)
    try:
        video = discover_video(settings.youtube_api_key, session, video_id)
        typer.echo(f"Video catalogato: {video.title} ({video.id}) [Stato: {video.status}]")
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


# -----------------------------------------------------------------------------
# Transcript Commands
# -----------------------------------------------------------------------------


@transcript_app.command("fetch")
def transcript_fetch_cmd(
    video_id: str = typer.Argument(help="ID del video già catalogato"),
    cookies: str = typer.Option(None, "--cookies", help="Percorso del file cookie Netscape"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Scarica il transcript per un video presente nel catalogo locale."""
    _setup_logging(verbose)
    settings = _get_settings()
    cookies_file = cookies or (str(settings.cookies_path) if settings.cookies_path else None)

    from yctm.application.transcripts import VideoNotDiscoveredError, fetch_transcript

    session = _get_session(settings)
    try:
        video = fetch_transcript(
            session,
            video_id,
            str(settings.transcripts_directory),
            cookies_path=cookies_file,
        )
        if video.status == "stored":
            typer.echo(f"✅ Transcript scaricato e archiviato per video {video.id}.")
        else:
            typer.echo(
                f"⚠️ Operazione completata con stato: {video.status}. Errore: {video.last_error}"
            )
            _check_rate_limit_warning(video.last_error)
    except VideoNotDiscoveredError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    finally:
        session.close()


@transcript_app.command("status")
def transcript_status_cmd(
    video_id: str = typer.Argument(help="ID del video"),
    format: str = typer.Option("table", "--format", help="Formato output: table o json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Mostra lo stato tecnico del transcript per un video."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.transcripts import VideoNotDiscoveredError, get_transcript_status

    session = _get_session(settings)
    try:
        st = get_transcript_status(session, video_id)
        if format == "json":
            typer.echo(json.dumps(st, indent=2, ensure_ascii=False))
            return

        typer.echo(f"Video ID:     {st['video_id']}")
        typer.echo(f"Titolo:       {st['title']}")
        typer.echo(f"Stato:        {st['status']}")
        typer.echo(f"Tentativi:    {st['attempt_count']}")
        if st["last_error"]:
            typer.echo(f"Ultimo Errore:{st['last_error']}")
        if st["storage_path"]:
            typer.echo(f"File Path:    {st['storage_path']}")
    except VideoNotDiscoveredError as exc:
        typer.echo(f"Errore: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    finally:
        session.close()


@transcript_app.command("reset")
def transcript_reset_cmd(
    video_id: str = typer.Argument(None, help="ID del singolo video da resettare (opzionale)"),
    status: str = typer.Option(
        None, "--status", help="Stato da resettare (retryable_error, terminal_error)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Reimposta lo stato delle trascrizioni a not_requested per consentire nuovi tentativi."""
    _setup_logging(verbose)
    if not video_id and not status:
        typer.echo(
            "Specifica un video_id oppure l'opzione --status (es. --status retryable_error).",
            err=True,
        )
        raise typer.Exit(code=1)

    settings = _get_settings()
    from yctm.application.transcripts import reset_transcripts

    session = _get_session(settings)
    try:
        count = reset_transcripts(session, video_id=video_id, status_filter=status)
        typer.echo(f"Resettati {count} video a 'not_requested'.")
    finally:
        session.close()


@transcript_app.command("retry")
def transcript_retry_cmd(
    video_id: str = typer.Argument(help="ID del video da ritentare"),
    cookies: str = typer.Option(None, "--cookies", help="Percorso del file cookie Netscape"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Resetta e forza un nuovo tentativo di fetch per un video."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.transcripts import fetch_transcript, reset_transcripts

    session = _get_session(settings)
    try:
        reset_transcripts(session, video_id=video_id)
        video = fetch_transcript(
            session,
            video_id,
            str(settings.transcripts_directory),
            cookies_path=cookies or (str(settings.cookies_path) if settings.cookies_path else None),
        )
        typer.echo(f"Retry completato per {video_id}. Nuovo stato: {video.status}")
        if video.status != "stored":
            _check_rate_limit_warning(video.last_error)
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Top level Stats & Auth & Deprecated Commands
# -----------------------------------------------------------------------------


@app.command("stats")
def stats_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Mostra le statistiche del catalogo e dell'operatività locale."""
    _setup_logging(verbose)
    settings = _get_settings()
    from yctm.application.catalog import get_catalog_stats

    session = _get_session(settings)
    try:
        stats = get_catalog_stats(session)
        typer.echo("=== Statistiche YCTM ===")
        typer.echo(f"Canali registrati:     {stats['channels']}")
        typer.echo(f"Playlist registrate:   {stats['playlists']}")
        typer.echo(f"Video catalogati:      {stats['videos']}")
        typer.echo("Stati Video:")
        for st_name, count in stats["status_counts"].items():
            typer.echo(f"  - {st_name:<16}: {count}")
        typer.echo(f"Trascrizioni su disco: {stats['transcripts_stored']}")
    finally:
        session.close()


@app.command("auth")
def auth_command(
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Modalità headless (incolla il codice su console)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """[SPERIMENTALE] Autentica YCTM con OAuth 2.0 per YouTube Data API."""
    _setup_logging(verbose)
    settings = _get_settings()

    from yctm.infrastructure.youtube.auth import run_oauth_flow

    try:
        creds = run_oauth_flow(
            client_id=settings.youtube_client_id,
            client_secret=settings.youtube_client_secret,
            no_browser=no_browser,
            port=settings.oauth_localhost_port,
        )
        typer.echo("✅ Autenticazione riuscita! Token salvato in ~/.yctm/token.json")
        typer.echo(f"   Scade il: {creds.expiry}")
    except ValueError as exc:
        typer.echo(f"❌ {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"❌ Errore durante l'autenticazione: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("doctor")
def doctor_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """Verifica l'integrità del catalogo e del filesystem (file orfani e record mancanti)."""
    _setup_logging(verbose)
    settings = _get_settings()
    session = _get_session(settings)

    try:
        from pathlib import Path

        from yctm.infrastructure.database.models import TranscriptFile

        transcripts_dir = Path(settings.transcripts_directory)
        existing_files = (
            {p.resolve() for p in transcripts_dir.glob("*.md")}
            if transcripts_dir.exists()
            else set()
        )

        db_records = session.query(TranscriptFile).all()
        db_paths = {Path(r.storage_path).resolve() for r in db_records}

        missing_on_disk = [r for r in db_records if not Path(r.storage_path).exists()]
        orphaned_files = existing_files - db_paths

        typer.echo("=== DIAGNOSTICA INTEGRITÀ CATALUTA/FILESYSTEM ===")
        typer.echo(f"Trascrizioni registrate nel DB: {len(db_records)}")
        typer.echo(f"File Markdown presenti su disco: {len(existing_files)}")
        typer.echo(f"Record DB con file mancante su disco: {len(missing_on_disk)}")
        typer.echo(f"File orfani su disco (non a DB): {len(orphaned_files)}")

        if missing_on_disk:
            typer.echo("\n⚠️  Record con file mancanti su disco:")
            for r in missing_on_disk:
                typer.echo(f"  - Video ID: {r.video_id} -> {r.storage_path}")

        if orphaned_files:
            typer.echo("\n⚠️  File orfani trovati su disco:")
            for f in sorted(orphaned_files):
                typer.echo(f"  - {f}")

        if not missing_on_disk and not orphaned_files:
            typer.echo("\n✅ Nessun problema di integrità riscontrato.")
    finally:
        session.close()


@app.command("sync")
def sync_deprecated(
    channel_id: str = typer.Argument(help="ID UC... del canale da analizzare"),
    max_results: int = typer.Option(0, "--max-results", help="Numero massimo di video"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """[DEPRECATO] Usa 'yctm discover channel'. Esegue solo il discovery metadati."""
    typer.echo(
        "⚠️  ATTENZIONE: 'yctm sync' è deprecato. Utilizzare 'yctm discover channel'.", err=True
    )
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.discovery import discover_channel

    session = _get_session(settings)
    try:
        res = discover_channel(settings.youtube_api_key, session, channel_id, max_results=limit)
        typer.echo(res.summary)
    finally:
        session.close()


@app.command("playlist-sync")
def playlist_sync_deprecated(
    playlist_id: str = typer.Argument(help="ID PL... della playlist da analizzare"),
    max_results: int = typer.Option(0, "--max-results", help="Numero massimo di video"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato"),
) -> None:
    """[DEPRECATO] Usa 'yctm discover playlist'. Esegue solo il discovery metadati."""
    typer.echo(
        "⚠️  ATTENZIONE: 'yctm playlist-sync' è deprecato. Utilizzare 'yctm discover playlist'.",
        err=True,
    )
    _setup_logging(verbose)
    settings = _get_settings()
    limit = max_results if max_results > 0 else settings.max_results

    from yctm.application.discovery import discover_playlist

    session = _get_session(settings)
    try:
        res = discover_playlist(settings.youtube_api_key, session, playlist_id, max_results=limit)
        typer.echo(res.summary)
    finally:
        session.close()
