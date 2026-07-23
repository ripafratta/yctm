from pathlib import Path

import pytest

from yctm.config.settings import Settings


def test_settings_use_project_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YCTM_MAX_RESULTS", raising=False)
    monkeypatch.delenv("YCTM_YOUTUBE_API_KEY", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_path == Path("data/yctm.sqlite3")
    assert settings.transcripts_directory == Path("data/transcripts")
    assert settings.max_results == 5
    assert settings.youtube_api_key == ""
