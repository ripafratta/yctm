"""Caso d'uso: Recupero puntuale e gestione dello stato delle trascrizioni."""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from yctm.domain.models import AcquisitionStatus, YctmError
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
from yctm.infrastructure.youtube.transcripts import (
    TranscriptExtractionError,
    TranscriptPermanentlyDisabledError,
    TranscriptUnavailableError,
    extract_transcript,
)

logger = logging.getLogger(__name__)


class VideoNotDiscoveredError(YctmError):
    """Il video richiesto non è presente nel catalogo locale."""


def fetch_transcript(
    session: Session,
    video_id: str,
    transcripts_dir: str,
    cookies_path: str | None = None,
) -> Video:
    """Scarica il transcript per un video già censito nel catalogo locale.

    Raises:
        VideoNotDiscoveredError: Se il video non è a catalogo.
    """
    video_repo = VideoRepository(session)
    video = video_repo.get(video_id)
    if video is None:
        raise VideoNotDiscoveredError(
            f"Video '{video_id}' non presente nel catalogo. "
            f"Esegui prima: yctm video discover {video_id}"
        )

    channel_repo = ChannelRepository(session)
    channel = channel_repo.get(video.channel_id) if video.channel_id else None

    channel_title = channel.title if channel else ""
    channel_handle = channel.handle if channel else None

    try:
        text, language_code = extract_transcript(
            video.id,
            cookies_path=Path(cookies_path) if cookies_path else None,
        )
    except TranscriptPermanentlyDisabledError:
        logger.info("Trascrizioni disabilitate per il video %s.", video.id)
        video.status = AcquisitionStatus.TERMINAL_ERROR
        video.last_error = "Trascrizioni disabilitate permanentemente."
        video_repo.add(video)
        session.commit()
        return video
    except (TranscriptUnavailableError, TranscriptExtractionError) as exc:
        logger.warning("Errore recupero transcript per %s: %s", video.id, exc)
        video.register_failure(str(exc))
        video_repo.add(video)
        session.commit()
        return video

    filename = build_filename(video.published_at, video.id, video.title)
    content = build_transcript_markdown(
        text=text,
        video_id=video.id,
        title=video.title,
        channel_id=video.channel_id or "",
        channel_title=channel_title,
        channel_handle=channel_handle,
        published_at=video.published_at,
        language_code=language_code,
        description=video.description,
    )
    stored = write_transcript_atomically(Path(transcripts_dir), filename, content)

    transcript_repo = TranscriptFileRepository(session)
    tf = transcript_repo.get_by_video_id(video.id)
    if tf is None:
        tf = TranscriptFile(
            video_id=video.id,
            storage_path=stored.storage_path,
            sha256=stored.sha256,
            language_code=language_code,
        )
        transcript_repo.add(tf)
    else:
        tf.storage_path = stored.storage_path
        tf.sha256 = stored.sha256
        tf.language_code = language_code

    video.status = AcquisitionStatus.STORED
    video.last_error = None
    video_repo.add(video)

    try:
        session.commit()
    except Exception:
        # Compensazione immediata: rimuovi il file orfano se il DB fallisce il commit
        try:
            Path(stored.storage_path).unlink(missing_ok=True)
            logger.info("Compensazione effettuata: file orfano %s rimosso.", stored.storage_path)
        except OSError as cleanup_exc:
            logger.warning(
                "Impossibile rimuovere il file orfano %s: %s",
                stored.storage_path,
                cleanup_exc,
            )

        raise

    logger.info("Transcript per video %s archiviato con successo.", video.id)
    return video


def get_transcript_status(session: Session, video_id: str) -> dict[str, str | None | int]:
    """Restituisce lo stato tecnico del transcript di un video."""
    video_repo = VideoRepository(session)
    video = video_repo.get(video_id)
    if video is None:
        raise VideoNotDiscoveredError(f"Video '{video_id}' non presente nel catalogo.")

    tf_repo = TranscriptFileRepository(session)
    tf = tf_repo.get_by_video_id(video_id)

    return {
        "video_id": video.id,
        "title": video.title,
        "status": video.status,
        "attempt_count": video.attempt_count,
        "last_attempt_at": video.last_attempt_at.isoformat() if video.last_attempt_at else None,
        "last_error": video.last_error,
        "storage_path": tf.storage_path if tf else None,
        "language_code": tf.language_code if tf else None,
        "sha256": tf.sha256 if tf else None,
    }


def reset_transcripts(
    session: Session,
    video_id: str | None = None,
    status_filter: str | None = None,
) -> int:
    """Reimposta lo stato dei transcript a not_requested."""
    video_repo = VideoRepository(session)
    if video_id:
        success = video_repo.reset_video(video_id)
        session.commit()
        return 1 if success else 0

    if status_filter:
        count = video_repo.reset_to_pending(status_filter)
        session.commit()
        return count

    return 0
