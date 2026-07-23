"""Caso d'uso: registrazione idempotente di un canale."""

import logging

from sqlalchemy.orm import Session

from yctm.infrastructure.database.models import Channel
from yctm.infrastructure.database.repositories import ChannelRepository
from yctm.infrastructure.youtube.data_api import (
    ChannelNotFoundError,
    QuotaExceededError,
    YouTubeAPIError,
    resolve_channel,
)

logger = logging.getLogger(__name__)


def register_channel(api_key: str, session: Session, identifier: str) -> Channel:
    """Registra un canale nel database locale, risolvendolo tramite YouTube Data API."""
    try:
        info = resolve_channel(api_key, identifier)
    except ChannelNotFoundError:
        logger.error("Canale non trovato: '%s'.", identifier)
        raise
    except QuotaExceededError:
        logger.error("Quota API YouTube superata durante la registrazione del canale.")
        raise
    except YouTubeAPIError:
        logger.exception("Errore API YouTube durante la registrazione del canale '%s'.", identifier)
        raise

    repo = ChannelRepository(session)
    channel = Channel(
        id=info.id,
        handle=info.handle,
        title=info.title,
        uploads_playlist_id=info.uploads_playlist_id,
    )
    result = repo.upsert(channel)
    session.commit()
    logger.info("Canale registrato: %s (%s).", result.title, result.id)
    return result


def list_channels(session: Session) -> list[Channel]:
    """Elenca tutti i canali registrati."""
    repo = ChannelRepository(session)
    return repo.all()


def remove_channel(session: Session, channel_id: str) -> bool:
    """Rimuove un canale dal database."""
    repo = ChannelRepository(session)
    success = repo.delete(channel_id)
    if success:
        session.commit()
        logger.info("Canale '%s' rimosso.", channel_id)
    return success
