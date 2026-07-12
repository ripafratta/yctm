from pathlib import Path

from yctm.config.settings import Settings


def test_settings_use_project_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_path == Path("data/yctm.sqlite3")
    assert settings.transcripts_directory == Path("data/transcripts")
    assert settings.manifest_path == Path("data/manifest.jsonl")
    assert settings.max_results == 5
    assert settings.youtube_api_key == ""
