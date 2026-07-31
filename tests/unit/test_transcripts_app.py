# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from yctm.application.transcripts import (
    VideoNotDiscoveredError,
    fetch_transcript,
    get_transcript_status,
    reset_transcripts,
)
from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Channel, Video
from yctm.infrastructure.database.repositories import VideoRepository
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from yctm.infrastructure.youtube.transcripts import (
    TranscriptExtractionError,
    TranscriptPermanentlyDisabledError,
    TranscriptUnavailableError,
)


def _setup_db(
    tmp_path: Path, video_id: str = "v1", status: str = "not_requested"
) -> Callable[[], Session]:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))
    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(Video(id=video_id, channel_id="UC123", title="Video Test", status=status))
        session.commit()
    return sessions


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_fetch_transcript_raises_if_video_not_discovered(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        with pytest.raises(VideoNotDiscoveredError) as exc_info:
            fetch_transcript(session, "unknown-id", str(tmp_path / "transcripts"))

    assert "non presente nel catalogo" in str(exc_info.value)


def test_fetch_transcript_success_stores_file_and_updates_status(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    transcripts_dir = tmp_path / "transcripts"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(Video(id="v1", channel_id="UC123", title="Test Title", status="not_requested"))
        session.commit()

    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo trascrizione", "it"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.STORED

    with sessions() as session:
        st = get_transcript_status(session, "v1")
        assert st["status"] == AcquisitionStatus.STORED
        assert st["language_code"] == "it"
        assert st["storage_path"] is not None


def test_reset_transcripts_resets_video_status(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Video(id="v1", title="V1", status="retryable_error", attempt_count=2))
        session.commit()

    with sessions() as session:
        count = reset_transcripts(session, video_id="v1")
        assert count == 1

    with sessions() as session:
        v = VideoRepository(session).get("v1")
        assert v is not None
        assert v.status == AcquisitionStatus.NOT_REQUESTED
        assert v.attempt_count == 0


# ---------------------------------------------------------------------------
# Error classification: TranscriptPermanentlyDisabledError → terminal_error immediato
# ---------------------------------------------------------------------------


def test_fetch_transcript_disabled_sets_terminal_error_immediately(tmp_path: Path) -> None:
    """Trascrizioni disabilitate: stato terminal_error al PRIMO tentativo senza incrementare a 3."""
    sessions = _setup_db(tmp_path)
    transcripts_dir = tmp_path / "transcripts"

    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptPermanentlyDisabledError("Disabilitate per v1"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.TERMINAL_ERROR
            # Il contatore NON deve essere incrementato a 3: è un errore terminale immediato
            assert v.attempt_count == 0
            assert v.last_error is not None
            assert (
                "Disabilitate" in v.last_error or "permanentemente" in (v.last_error or "").lower()
            )


# ---------------------------------------------------------------------------
# Error classification: TranscriptUnavailableError → retryable_error (1° e 2° tentativo)
# ---------------------------------------------------------------------------


def test_fetch_transcript_unavailable_first_attempt_sets_retryable(tmp_path: Path) -> None:
    """Transcript temporaneamente non disponibile: primo fallimento → retryable_error."""
    sessions = _setup_db(tmp_path)
    transcripts_dir = tmp_path / "transcripts"

    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptUnavailableError("Non disponibile"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.RETRYABLE_ERROR
            assert v.attempt_count == 1


def test_fetch_transcript_unavailable_second_attempt_remains_retryable(tmp_path: Path) -> None:
    """Secondo fallimento consecutivo: rimane retryable_error."""
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))
    with sessions() as session:
        session.add(
            Video(
                id="v1",
                title="T",
                status="retryable_error",
                attempt_count=1,
                channel_id=None,
            )
        )
        session.commit()

    transcripts_dir = tmp_path / "transcripts"
    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptUnavailableError("Non ancora disponibile"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.RETRYABLE_ERROR
            assert v.attempt_count == 2


# ---------------------------------------------------------------------------
# Error classification: terzo fallimento → terminal_error
# ---------------------------------------------------------------------------


def test_fetch_transcript_third_failure_escalates_to_terminal_error(tmp_path: Path) -> None:
    """Al terzo fallimento consecutivo (attempt_count >= 3) → terminal_error."""
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))
    with sessions() as session:
        session.add(
            Video(
                id="v1",
                title="T",
                status="retryable_error",
                attempt_count=2,
                channel_id=None,
            )
        )
        session.commit()

    transcripts_dir = tmp_path / "transcripts"
    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptExtractionError("Errore di rete"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.TERMINAL_ERROR
            assert v.attempt_count == 3


# ---------------------------------------------------------------------------
# Error classification: TranscriptExtractionError (rete/429) → retryable_error
# ---------------------------------------------------------------------------


def test_fetch_transcript_extraction_error_first_attempt_sets_retryable(tmp_path: Path) -> None:
    """Errore di rete / timeout / 429 al primo tentativo → retryable_error."""
    sessions = _setup_db(tmp_path)
    transcripts_dir = tmp_path / "transcripts"

    with patch(
        "yctm.application.transcripts.extract_transcript",
        side_effect=TranscriptExtractionError("429 Too Many Requests"),
    ):
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.RETRYABLE_ERROR
            assert v.attempt_count == 1
            assert v.last_error is not None
