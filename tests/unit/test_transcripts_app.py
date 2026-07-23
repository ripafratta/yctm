from pathlib import Path
from unittest.mock import patch

import pytest

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
