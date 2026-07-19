"""Caso d'uso: registrazione e sincronizzazione di playlist."""

import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from yctm.application.synchronization import SyncResult, _confirm_video
from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Playlist, TranscriptFile, Video
from yctm.infrastructure.database.repositories import (
    PlaylistRepository,
    TranscriptFileRepository,
    VideoRepository,
)
from yctm.infrastructure.filesystem.transcripts import (
    build_filename,
    build_transcript_markdown,
    write_transcript_atomically,
)
from yctm.infrastructure.youtube.data_api import (
    ChannelNotFoundError,
    QuotaExceededError,
    YouTubeAPIError,
    list_playlist_videos,
    resolve_playlist,
)
from yctm.infrastructure.youtube.transcripts import (
    TranscriptExtractionError,
    TranscriptPermanentlyDisabledError,
    TranscriptUnavailableError,
    extract_transcript,
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


def synchronize_playlist(
    api_key: str,
    session: Session,
    playlist_id: str,
    transcripts_dir: str,
    max_results: int = 5,
    interactive: bool = False,
    transcript_fetch_delay: int = 15,
    cookies_path: str | None = None,
) -> SyncResult:
    """Sincronizza le trascrizioni dei video di una playlist."""
    result = SyncResult()
    repo = PlaylistRepository(session)
    playlist = repo.get(playlist_id)
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
    logger.info("Discovery completato: %d video per la playlist '%s'.", len(videos), playlist_id)

    video_repo = VideoRepository(session)
    transcript_repo = TranscriptFileRepository(session)

    for video_info in videos:
        existing = video_repo.get(video_info.id)
        if existing is not None and AcquisitionStatus(existing.status).is_terminal:
            logger.debug("Video %s gia' terminale. Interruzione anticipata.", video_info.id)
            result.already_known += 1
            break

        video = existing or Video(
            id=video_info.id,
            channel_id=video_info.channel_id,
            title=video_info.title,
            published_at=video_info.published_at,
        )

        channel_label = video_info.channel_title or playlist.title or playlist_id
        if interactive and not _confirm_video(video_info, channel_label):
            result.skipped_interactive += 1
            continue

        try:
            text, language_code = extract_transcript(
                video_info.id,
                cookies_path=Path(cookies_path) if cookies_path else None,
            )
        except TranscriptPermanentlyDisabledError:
            logger.info("Trascrizioni disabilitate per il video %s.", video_info.id)
            video.status = AcquisitionStatus.TERMINAL_ERROR
            video.last_error = "Trascrizioni disabilitate permanentemente."
            video_repo.add(video)
            session.commit()
            result.skipped_disabled += 1
        except TranscriptUnavailableError as exc:
            logger.info("Trascrizione non disponibile per %s: %s", video_info.id, exc)
            video.register_failure(str(exc))
            video_repo.add(video)
            session.commit()
            result.skipped_unavailable += 1
        except TranscriptExtractionError as exc:
            logger.warning("Errore di estrazione per %s: %s", video_info.id, exc)
            video.register_failure(str(exc))
            video_repo.add(video)
            session.commit()
            result.errors += 1
        else:
            filename = build_filename(video_info.published_at, video_info.id, video_info.title)
            content = build_transcript_markdown(
                text=text,
                video_id=video_info.id,
                title=video_info.title,
                channel_id=video_info.channel_id,
                channel_title=video_info.channel_title,
                published_at=video_info.published_at,
                language_code=language_code,
                description=video_info.description,
            )
            stored = write_transcript_atomically(Path(transcripts_dir), filename, content)

            tf = TranscriptFile(
                video_id=video_info.id,
                storage_path=stored.storage_path,
                sha256=stored.sha256,
                language_code=language_code,
            )
            transcript_repo.add(tf)
            video.status = AcquisitionStatus.STORED
            video_repo.add(video)
            session.commit()
            result.stored += 1
        finally:
            time.sleep(transcript_fetch_delay)

    logger.info("Sincronizzazione playlist completata: %s", result.summary)
    return result
