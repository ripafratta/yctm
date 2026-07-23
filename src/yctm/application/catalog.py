"""Caso d'uso: Consultazione catalogo e statistiche."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from yctm.infrastructure.database.models import TranscriptFile, Video
from yctm.infrastructure.database.repositories import (
    ChannelRepository,
    PlaylistRepository,
    TranscriptFileRepository,
    VideoRepository,
)

logger = logging.getLogger(__name__)


def list_catalog_videos(
    session: Session,
    status: str | None = None,
    channel_id: str | None = None,
    playlist_id: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "published-desc",
) -> list[dict[str, Any]]:
    """Restituisce l'elenco dei video catalogati applicando i filtri."""
    repo = VideoRepository(session)
    videos = repo.list_videos(
        status=status,
        channel_id=channel_id,
        playlist_id=playlist_id,
        after=after,
        before=before,
        limit=limit,
        offset=offset,
        order=order,
    )
    channel_repo = ChannelRepository(session)
    channels_map = {c.id: c.title for c in channel_repo.all()}

    res: list[dict[str, Any]] = []
    for v in videos:
        ch_title = channels_map.get(v.channel_id or "", "")
        res.append(
            {
                "id": v.id,
                "title": v.title,
                "channel_id": v.channel_id,
                "channel_title": ch_title,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "discovered_at": v.discovered_at.isoformat() if v.discovered_at else None,
                "status": v.status,
            }
        )
    return res


def get_video_details(session: Session, video_id: str) -> dict[str, Any] | None:
    """Restituisce le informazioni dettagliate di un singolo video."""
    repo = VideoRepository(session)
    v = repo.get(video_id)
    if v is None:
        return None

    ch_repo = ChannelRepository(session)
    ch = ch_repo.get(v.channel_id) if v.channel_id else None

    tf_repo = TranscriptFileRepository(session)
    tf = tf_repo.get_by_video_id(video_id)

    return {
        "id": v.id,
        "title": v.title,
        "description": v.description,
        "channel_id": v.channel_id,
        "channel_title": ch.title if ch else None,
        "channel_handle": ch.handle if ch else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "discovered_at": v.discovered_at.isoformat() if v.discovered_at else None,
        "status": v.status,
        "attempt_count": v.attempt_count,
        "last_attempt_at": v.last_attempt_at.isoformat() if v.last_attempt_at else None,
        "last_error": v.last_error,
        "transcript_file": (
            {
                "storage_path": tf.storage_path,
                "sha256": tf.sha256,
                "language_code": tf.language_code,
                "extracted_at": tf.extracted_at.isoformat() if tf.extracted_at else None,
            }
            if tf
            else None
        ),
    }


def get_catalog_stats(session: Session) -> dict[str, Any]:
    """Restituisce statistiche aggregate sul catalogo YCTM."""
    ch_repo = ChannelRepository(session)
    pl_repo = PlaylistRepository(session)

    total_channels = len(ch_repo.all())
    total_playlists = len(pl_repo.all())

    total_videos = session.query(Video).count()
    status_counts = {
        "not_requested": session.query(Video).filter(Video.status == "not_requested").count(),
        "stored": session.query(Video).filter(Video.status == "stored").count(),
        "retryable_error": session.query(Video).filter(Video.status == "retryable_error").count(),
        "terminal_error": session.query(Video).filter(Video.status == "terminal_error").count(),
        "pending": session.query(Video).filter(Video.status == "pending").count(),
    }
    total_transcripts = session.query(TranscriptFile).count()

    return {
        "channels": total_channels,
        "playlists": total_playlists,
        "videos": total_videos,
        "status_counts": status_counts,
        "transcripts_stored": total_transcripts,
    }
