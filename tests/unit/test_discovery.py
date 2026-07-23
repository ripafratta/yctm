from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from yctm.application.discovery import (
    discover_channel,
    discover_video,
)
from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Channel, Video
from yctm.infrastructure.database.repositories import VideoRepository
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
)
from yctm.infrastructure.youtube.data_api import VideoInfo


def test_discover_channel_registers_videos_without_fetching_transcripts(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.commit()

    sample_videos = [
        VideoInfo(
            id="v1",
            channel_id="UC123",
            title="Video 1",
            description="Descrizione 1",
            published_at=datetime(2026, 7, 10),
        ),
        VideoInfo(
            id="v2",
            channel_id="UC123",
            title="Video 2",
            description="Descrizione 2",
            published_at=datetime(2026, 7, 9),
        ),
    ]

    with (
        patch(
            "yctm.application.discovery.list_recent_videos", return_value=sample_videos
        ) as mock_list,
        patch("yctm.infrastructure.youtube.transcripts.extract_transcript") as mock_extract,
    ):
        with sessions() as session:
            res = discover_channel("api-key", session, "UC123", max_results=5)

        mock_list.assert_called_once_with("api-key", "UU123", 5)
        mock_extract.assert_not_called()
        assert res.discovered == 2
        assert res.new_added == 2

    with sessions() as session:
        repo = VideoRepository(session)
        v1 = repo.get("v1")
        assert v1 is not None
        assert v1.title == "Video 1"
        assert v1.description == "Descrizione 1"
        assert v1.status == AcquisitionStatus.NOT_REQUESTED


def test_discover_channel_early_exit_on_known_video(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(Video(id="v1", channel_id="UC123", title="Gia Notato", status="not_requested"))
        session.commit()

    sample_videos = [
        VideoInfo(id="v1", channel_id="UC123", title="Gia Notato"),
        VideoInfo(id="v2", channel_id="UC123", title="Ignorato per early exit"),
    ]

    with patch("yctm.application.discovery.list_recent_videos", return_value=sample_videos):
        with sessions() as session:
            res = discover_channel("api-key", session, "UC123")

    assert res.discovered == 2
    assert res.already_known == 1
    assert res.new_added == 0


def test_discover_single_video(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    v_info = VideoInfo(id="vsingle", channel_id="UC999", title="Single Video", description="Desc")

    with patch("yctm.application.discovery.fetch_video_by_id", return_value=v_info):
        with sessions() as session:
            video = discover_video("api-key", session, "vsingle")
            assert video.id == "vsingle"
            assert video.status == AcquisitionStatus.NOT_REQUESTED
