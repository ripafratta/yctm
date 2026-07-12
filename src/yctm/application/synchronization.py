"""Caso d'uso: sincronizzazione incrementale delle trascrizioni."""

import logging
import sys
import time
from pathlib import Path

from sqlalchemy.orm import Session

from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import TranscriptFile, Video
from yctm.infrastructure.database.repositories import (
    ChannelRepository,
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
    VideoInfo,
    YouTubeAPIError,
    list_recent_videos,
)
from yctm.infrastructure.youtube.transcripts import (
    TranscriptExtractionError,
    TranscriptPermanentlyDisabledError,
    TranscriptUnavailableError,
    extract_transcript,
)

logger = logging.getLogger(__name__)

# Delay in secondi tra richieste consecutive a youtube-transcript-api
# per evitare blocchi IP da parte di YouTube.
TRANSCRIPT_FETCH_DELAY = 2


class SyncResult:
    """Esito di una sincronizzazione."""

    def __init__(self) -> None:
        self.discovered: int = 0
        self.already_known: int = 0
        self.stored: int = 0
        self.skipped_disabled: int = 0
        self.skipped_unavailable: int = 0
        self.skipped_interactive: int = 0
        self.errors: int = 0

    @property
    def summary(self) -> str:
        return (
            f"Rilevati: {self.discovered}, Gia' noti: {self.already_known}, "
            f"Archiviati: {self.stored}, "
            f"Saltati (interattivo): {self.skipped_interactive}, "
            f"Saltati (disabilitati): {self.skipped_disabled}, "
            f"Saltati (non disponibili): {self.skipped_unavailable}, Errori: {self.errors}"
        )


def _confirm_video(video_info: VideoInfo, channel_title: str) -> bool:
    """Chiede all'utente conferma per scaricare la trascrizione di un video."""
    if video_info.published_at:
        date_str = video_info.published_at.strftime("%Y-%m-%d")
    else:
        date_str = "data sconosciuta"
    label = f'{channel_title} — "{video_info.title}" ({date_str})'
    print(f"\n{label}", file=sys.stderr)
    answer = input("  Scaricare la trascrizione? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        return True
    logger.info("Video saltato dall'utente: %s — %s", video_info.id, video_info.title)
    return False


def synchronize_channel(
    api_key: str,
    session: Session,
    channel_id: str,
    transcripts_dir: str,
    max_results: int = 5,
    interactive: bool = False,
) -> SyncResult:
    """Sincronizza le trascrizioni degli ultimi video di un canale."""
    result = SyncResult()
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
    logger.info("Discovery completato: %d video per il canale '%s'.", len(videos), channel_id)

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
            channel_id=channel_id,
            title=video_info.title,
            published_at=video_info.published_at,
        )

        channel_label = channel.title or channel.handle or channel_id
        if interactive and not _confirm_video(video_info, channel_label):
            result.skipped_interactive += 1
            continue

        try:
            text, language_code = extract_transcript(video_info.id)
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
                channel_id=channel_id,
                channel_title=channel.title,
                channel_handle=channel.handle,
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
            time.sleep(TRANSCRIPT_FETCH_DELAY)

    logger.info("Sincronizzazione completata: %s", result.summary)
    return result
