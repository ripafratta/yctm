"""Test per l'adattatore filesystem."""

from datetime import datetime
from pathlib import Path

from yctm.infrastructure.filesystem.transcripts import (
    build_filename,
    compute_sha256,
    sanitize_filename,
    write_transcript_atomically,
)


def test_sanitize_filename_removes_special_chars() -> None:
    assert sanitize_filename("Hello World!") == "Hello_World"
    assert sanitize_filename("Cosa c'e'?") == "Cosa_c_e"
    assert sanitize_filename("   spazi   ") == "spazi"
    assert sanitize_filename("a/b:c*d") == "a_b_c_d"


def test_sanitize_filename_truncates_long_titles() -> None:
    long_title = "A" * 100
    result = sanitize_filename(long_title, max_length=80)
    assert len(result) <= 80


def test_sanitize_filename_returns_untitled_for_empty() -> None:
    assert sanitize_filename("!!!") == "untitled"


def test_build_filename_includes_date_and_id() -> None:
    dt = datetime(2026, 1, 15)
    name = build_filename(dt, "abc123", "My Video Title")
    assert name.startswith("20260115_abc123_")
    assert name.endswith(".md")


def test_build_filename_without_date() -> None:
    name = build_filename(None, "abc123", "My Title")
    assert name.startswith("nodate_abc123_")
    assert name.endswith(".md")


def test_compute_sha256_is_deterministic() -> None:
    h1 = compute_sha256("test content")
    h2 = compute_sha256("test content")
    assert h1 == h2
    assert len(h1) == 64


def test_compute_sha256_differs_for_different_content() -> None:
    h1 = compute_sha256("a")
    h2 = compute_sha256("b")
    assert h1 != h2


def test_write_transcript_atomically_creates_file(tmp_path: Path) -> None:
    result = write_transcript_atomically(
        tmp_path, "20260115_abc123_title.md", "Contenuto della trascrizione."
    )
    assert Path(result.storage_path).exists()
    assert Path(result.storage_path).read_text() == "Contenuto della trascrizione."
    assert len(result.sha256) == 64


def test_write_transcript_atomically_overwrites(tmp_path: Path) -> None:
    write_transcript_atomically(tmp_path, "test.md", "Primo contenuto.")
    write_transcript_atomically(tmp_path, "test.md", "Secondo contenuto.")
    assert Path(tmp_path / "test.md").read_text() == "Secondo contenuto."
