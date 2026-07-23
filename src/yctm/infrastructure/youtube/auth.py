"""
OAuth 2.0 flow per YouTube Data API v3 (captions.download).

╔══════════════════════════════════════════════════════════════════════════════╗
║ NOTA: Implementazione basata su YouTube Data API v3 captions.download.     ║
║                                                                             ║
║ PROBLEMA: L'endpoint captions.download richiede che l'app sia verificata   ║
║ da Google OPPURE che l'account proprietario dei video abiliti il download   ║
║ di caption di terze parti. Nella pratica, restituisce 403 Forbidden per     ║
║ la quasi totalità dei video YouTube, rendendo questo approccio inutilizzabile║
║ per uno scraper generico di trascrizioni.                                   ║
║                                                                             ║
║ SOSTITUITO DA: youtube-transcript-api (scraping via innertube), che non     ║
║ necessita di OAuth e funziona per tutti i video con trascrizioni pubbliche. ║
║ Vedi transcripts.py per l'implementazione attiva.                           ║
║                                                                             ║
║ Mantenuto come riferimento per eventuale utilizzo futuro qualora Google     ║
║ dovesse approvare l'app o cambiare le policy di download.                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

from yctm.config.settings import Settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

_TOKEN_DIR = Path.home() / ".yctm"
_TOKEN_FILE = _TOKEN_DIR / "token.json"


def run_oauth_flow(
    client_id: str,
    client_secret: str,
    no_browser: bool = False,
    port: int = 8080,
) -> Credentials:
    if not client_id or not client_secret:
        raise ValueError(
            "YCTM_YOUTUBE_CLIENT_ID e YCTM_YOUTUBE_CLIENT_SECRET devono essere "
            "impostati in .env. Crea le credenziali OAuth 2.0 su "
            "https://console.cloud.google.com/apis/credentials (tipo: Desktop application)."
        )

    client_config: dict[str, Any] = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, _SCOPES)
    _TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    if no_browser:
        creds = flow.run_console()
    else:
        creds = flow.run_local_server(port=port, open_browser=True)

    _save_token(creds)
    logger.info("Token OAuth salvato in %s", _TOKEN_FILE)
    return creds  # type: ignore[no-any-return]


def load_credentials(token_path: Path | None = None) -> Credentials | None:
    path = token_path or _TOKEN_FILE
    if not path.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(path), _SCOPES)  # type: ignore[no-untyped-call]
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("File token corrotto (%s): %s", path, exc)
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            logger.info("Token OAuth refrescato automaticamente.")
        except Exception as exc:
            logger.warning("Impossibile refrescare il token OAuth: %s", exc)
            return None

    return creds  # type: ignore[no-any-return]


def get_authenticated_client(settings: Settings | None = None) -> Any:
    if settings is None:
        settings = Settings()

    creds = load_credentials(settings.oauth_token_path)
    if creds is None or not creds.valid:
        raise ValueError("Nessun token OAuth valido trovato. Esegui 'yctm auth' per autenticarti.")

    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    return build("youtube", "v3", credentials=creds)


def _save_token(creds: Credentials) -> None:
    """Salva le credenziali su disco."""
    _TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    with open(_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())  # type: ignore[no-untyped-call]
    os.chmod(_TOKEN_FILE, 0o600)
