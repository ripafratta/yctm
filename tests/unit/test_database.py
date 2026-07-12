from pathlib import Path

from sqlalchemy import inspect

from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Video
from yctm.infrastructure.database.session import create_engine, initialize_database


def test_initialize_database_creates_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "yctm.sqlite3"

    initialize_database(database_path)

    inspector = inspect(create_engine(database_path))
    assert {"channels", "videos", "transcript_files"} <= set(inspector.get_table_names())


def test_video_marks_third_failure_as_terminal() -> None:
    video = Video(id="video-id", channel_id="channel-id", title="Titolo")

    video.register_failure("Trascrizione non disponibile")
    video.register_failure("Trascrizione non disponibile")
    video.register_failure("Trascrizione non disponibile")

    assert video.attempt_count == 3
    assert video.status == AcquisitionStatus.TERMINAL_ERROR
    assert video.last_error == "Trascrizione non disponibile"
