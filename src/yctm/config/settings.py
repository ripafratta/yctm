"""Impostazioni configurabili di YCTM."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carica la configurazione da ambiente o file .env."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="YCTM_", extra="ignore")

    youtube_api_key: str = ""
    database_path: Path = Path("data/yctm.sqlite3")
    transcripts_directory: Path = Path("data/transcripts")
    manifest_path: Path = Path("data/manifest.jsonl")
    max_results: int = 3

    # OAuth 2.0 per YouTube Data API (captions.download)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    oauth_token_path: Path = Path.home() / ".yctm" / "token.json"
    oauth_localhost_port: int = 8080

    # youtube-transcript-api (scraping via innertube)
    # Percorso del file cookie in formato Netscape (esportato dal browser)
    # per autenticare le richieste ed evitare blocchi IP.
    cookies_path: Path | None = None
    # Delay in secondi tra richieste consecutive di trascrizione.
    # Default 15s per evitare rate-limiting.
    transcript_fetch_delay: int = 15
