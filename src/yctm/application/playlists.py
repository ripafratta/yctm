"""Caso d'uso: registrazione e gestione delle playlist."""

import logging

from sqlalchemy.orm import Session

from yctm.infrastructure.database.models import Playlist
from yctm.infrastructure.database.repositories import PlaylistRepository
from yctm.infrastructure.youtube.data_api import (
    ChannelNotFoundError,
    QuotaExceededError,
    YouTubeAPIError,
    resolve_playlist,
)

logger = logging.getLogger(__name__)


def register_playlist(api_key: str, session: Session, identifier: str) -> Playlist:
    """Registra una playlist nel database locale, risolvendola tramite YouTube Data API."""
    try:
        info = resolve_playlist(api_key, identifier)
    except ChannelNotFoundError:
        logger.error("Playlist non trovata: '%s'.", identifier)
        raise
    except QuotaExceededError:
        logger.error("Quota API YouTube superata durante la registrazione della playlist.")
        raise
    except YouTubeAPIError:
        logger.exception(
            "Errore API YouTube durante la registrazione della playlist '%s'.", identifier
        )
        raise

    repo = PlaylistRepository(session)
    playlist = Playlist(
        id=info.id,
        title=info.title,
        channel_id=info.channel_id,
    )
    result = repo.upsert(playlist)
    session.commit()
    logger.info("Playlist registrata: %s (%s).", result.title, result.id)
    return result


def list_playlists(session: Session) -> list[Playlist]:
    """Elenca tutte le playlist registrate."""
    repo = PlaylistRepository(session)
    return repo.all()


def remove_playlist(session: Session, playlist_id: str) -> bool:
    """Rimuove una playlist dal database."""
    repo = PlaylistRepository(session)
    success = repo.delete(playlist_id)
    if success:
        session.commit()
        logger.info("Playlist '%s' rimossa.", playlist_id)
    return success
