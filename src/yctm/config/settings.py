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
    max_results: int = 5
