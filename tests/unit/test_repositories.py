from pathlib import Path

from yctm.infrastructure.database.models import Channel, TranscriptFile, Video
from yctm.infrastructure.database.repositories import (
    ChannelRepository,
    TranscriptFileRepository,
    VideoRepository,
)
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
)


def test_channel_repository_upserts_channel(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))
    channel = Channel(id="UC123", handle="@canale", title="Canale", uploads_playlist_id="UU123")

    with sessions() as session:
        repository = ChannelRepository(session)
        repository.upsert(channel)
        session.commit()

    with sessions() as session:
        stored = ChannelRepository(session).get("UC123")

    assert stored is not None
    assert stored.handle == "@canale"


def test_video_repository_returns_known_video(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale", uploads_playlist_id="UU123"))
        VideoRepository(session).add(Video(id="video-id", channel_id="UC123", title="Titolo"))
        session.commit()

    with sessions() as session:
        stored = VideoRepository(session).get("video-id")

    assert stored is not None
    assert stored.channel_id == "UC123"


def test_transcript_file_repository_stores_and_retrieves(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale", uploads_playlist_id="UU123"))
        session.add(Video(id="video-id", channel_id="UC123", title="Titolo"))
        session.commit()

    with sessions() as session:
        repo = TranscriptFileRepository(session)
        tf = TranscriptFile(
            video_id="video-id",
            storage_path="data/transcripts/video-id.md",
            sha256="abc123",
            language_code="it",
        )
        repo.add(tf)
        session.commit()

    with sessions() as session:
        stored = TranscriptFileRepository(session).get_by_video_id("video-id")

    assert stored is not None
    assert stored.storage_path == "data/transcripts/video-id.md"
    assert stored.language_code == "it"


def test_transcript_file_repository_returns_none_for_unknown_video(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"
    initialize_database(database_path)
    sessions = create_session_factory(create_engine(database_path))

    with sessions() as session:
        stored = TranscriptFileRepository(session).get_by_video_id("inesistente")

    assert stored is None
