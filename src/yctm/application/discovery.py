"""Caso d'uso: Discovery dei metadati da canali, playlist e singoli video."""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Video
from yctm.infrastructure.database.repositories import (
    ChannelRepository,
    PlaylistRepository,
    VideoRepository,
)
from yctm.infrastructure.youtube.data_api import (
    ChannelNotFoundError,
    QuotaExceededError,
    YouTubeAPIError,
    fetch_video_by_id,
    list_playlist_videos,
    list_recent_videos,
)

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Esito di un'operazione di discovery."""

    discovered: int = 0
    already_known: int = 0
    new_added: int = 0

    @property
    def summary(self) -> str:
        return (
            f"Analizzati: {self.discovered}, Già noti: {self.already_known}, "
            f"Nuovi registrati: {self.new_added}"
        )


def discover_channel(
    api_key: str,
    session: Session,
    channel_id: str,
    max_results: int = 25,
    since: datetime | None = None,
    dry_run: bool = False,
) -> DiscoveryResult:
    """Esegue il discovery dei metadati dei video per un canale registrato.

    Non effettua alcuna estrazione di transcript.
    """
    result = DiscoveryResult()
    channel_repo = ChannelRepository(session)
    channel = channel_repo.get(channel_id)
    if channel is None:
        logger.error("Canale '%s' non presente nel database.", channel_id)
        raise ChannelNotFoundError(f"Canale '{channel_id}' non registrato.")

    try:
        videos = list_recent_videos(api_key, channel.uploads_playlist_id, max_results)
    except QuotaExceededError:
        logger.error("Quota API superata durante il discovery per il canale '%s'.", channel_id)
        raise
    except YouTubeAPIError:
        logger.exception("Errore API durante il discovery per il canale '%s'.", channel_id)
        raise

    result.discovered = len(videos)
    video_repo = VideoRepository(session)

    for video_info in videos:
        if since and video_info.published_at and video_info.published_at < since:
            logger.debug("Video %s precedente a %s, interruzione.", video_info.id, since)
            break

        existing = video_repo.get(video_info.id)
        if existing is not None:
            logger.debug("Video %s già catalogato. Interruzione anticipata.", video_info.id)
            result.already_known += 1
            break

        result.new_added += 1
        if not dry_run:
            video = Video(
                id=video_info.id,
                channel_id=channel_id,
                title=video_info.title,
                description=video_info.description,
                published_at=video_info.published_at,
                status=AcquisitionStatus.NOT_REQUESTED,
            )
            video_repo.add(video)

    if not dry_run:
        session.commit()

    logger.info("Discovery canale '%s' completato: %s", channel_id, result.summary)
    return result


def discover_playlist(
    api_key: str,
    session: Session,
    playlist_id: str,
    max_results: int = 25,
    dry_run: bool = False,
) -> DiscoveryResult:
    """Esegue il discovery dei metadati dei video per una playlist registrata.

    Non effettua alcuna estrazione di transcript.
    """
    result = DiscoveryResult()
    playlist_repo = PlaylistRepository(session)
    playlist = playlist_repo.get(playlist_id)
    if playlist is None:
        logger.error("Playlist '%s' non presente nel database.", playlist_id)
        raise ChannelNotFoundError(f"Playlist '{playlist_id}' non registrata.")

    try:
        videos = list_playlist_videos(api_key, playlist.id, max_results)
    except QuotaExceededError:
        logger.error("Quota API superata durante il discovery per la playlist '%s'.", playlist_id)
        raise
    except YouTubeAPIError:
        logger.exception("Errore API durante il discovery per la playlist '%s'.", playlist_id)
        raise

    result.discovered = len(videos)
    video_repo = VideoRepository(session)

    for video_info in videos:
        existing = video_repo.get(video_info.id)
        if existing is not None:
            logger.debug("Video %s già catalogato. Interruzione anticipata.", video_info.id)
            result.already_known += 1
            break

        result.new_added += 1
        if not dry_run:
            video = Video(
                id=video_info.id,
                channel_id=video_info.channel_id,
                title=video_info.title,
                description=video_info.description,
                published_at=video_info.published_at,
                status=AcquisitionStatus.NOT_REQUESTED,
            )
            video_repo.add(video)

    if not dry_run:
        session.commit()

    logger.info("Discovery playlist '%s' completato: %s", playlist_id, result.summary)
    return result


def discover_video(api_key: str, session: Session, video_id: str) -> Video:
    """Registra nel catalogo un singolo video tramite il suo ID YouTube."""
    video_repo = VideoRepository(session)
    existing = video_repo.get(video_id)
    if existing is not None:
        logger.info("Video %s già presente nel catalogo.", video_id)
        return existing

    try:
        video_info = fetch_video_by_id(api_key, video_id)
    except QuotaExceededError:
        logger.error("Quota API superata durante il discovery del video '%s'.", video_id)
        raise
    except YouTubeAPIError:
        logger.exception("Errore API durante il discovery del video '%s'.", video_id)
        raise

    video = Video(
        id=video_info.id,
        channel_id=video_info.channel_id,
        title=video_info.title,
        description=video_info.description,
        published_at=video_info.published_at,
        status=AcquisitionStatus.NOT_REQUESTED,
    )
    video_repo.add(video)
    session.commit()
    logger.info("Video %s registrato nel catalogo.", video_id)
    return video


def discover_all(
    api_key: str,
    session: Session,
    max_results: int = 20,
    dry_run: bool = False,
) -> dict[str, DiscoveryResult]:
    """Esegue il discovery per tutti i canali e le playlist registrati."""
    results: dict[str, DiscoveryResult] = {}
    channel_repo = ChannelRepository(session)
    playlist_repo = PlaylistRepository(session)

    for ch in channel_repo.all():
        results[f"channel:{ch.id}"] = discover_channel(
            api_key, session, ch.id, max_results=max_results, dry_run=dry_run
        )

    for pl in playlist_repo.all():
        results[f"playlist:{pl.id}"] = discover_playlist(
            api_key, session, pl.id, max_results=max_results, dry_run=dry_run
        )

    return results
