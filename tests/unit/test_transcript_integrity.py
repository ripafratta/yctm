"""Test di integrità del transcript: hash, file su disco e TranscriptFile in DB.

Verifica che dopo un fetch riuscito:
- il file Markdown esista su disco;
- l'hash SHA-256 nel DB corrisponda al contenuto del file su disco;
- il record TranscriptFile sia correttamente associato al Video;
- un secondo fetch sullo stesso video (già stored) sia idempotente.
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from yctm.application.transcripts import fetch_transcript
from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.models import Channel, Video
from yctm.infrastructure.database.repositories import TranscriptFileRepository, VideoRepository
from yctm.infrastructure.database.session import (
    create_engine,
    create_session_factory,
    initialize_database,
)


def _setup(tmp_path: Path) -> tuple[sessionmaker[Session], Path]:
    """Inizializza DB e directory trascrizioni, inserisce un video di test."""
    db_path = tmp_path / "yctm.sqlite3"
    transcripts_dir = tmp_path / "transcripts"
    initialize_database(db_path)
    engine = create_engine(db_path)
    sessions = create_session_factory(engine)
    with sessions() as session:
        session.add(Channel(id="UC123", title="Canale Test", uploads_playlist_id="UU123"))
        session.add(
            Video(
                id="v1",
                channel_id="UC123",
                title="Titolo Video Test",
                status="not_requested",
            )
        )
        session.commit()
    return sessions, transcripts_dir


# ---------------------------------------------------------------------------
# Integrità post-fetch: file su disco, hash SHA-256 e TranscriptFile
# ---------------------------------------------------------------------------


def test_fetch_creates_markdown_file_on_disk(tmp_path: Path) -> None:
    """fetch_transcript deve creare almeno un file .md nella directory transcript."""
    sessions, transcripts_dir = _setup(tmp_path)
    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Contenuto della trascrizione.", "it"),
    ):
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))

    files = list(transcripts_dir.glob("*.md"))
    assert len(files) == 1, "Deve esistere esattamente un file .md"


def test_fetch_sha256_matches_file_content(tmp_path: Path) -> None:
    """L'hash SHA-256 nel DB deve corrispondere all'hash del file su disco."""
    sessions, transcripts_dir = _setup(tmp_path)
    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo coerente.", "it"),
    ):
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))

    # Leggi il TranscriptFile dal DB
    with sessions() as session:
        tf = TranscriptFileRepository(session).get_by_video_id("v1")
        assert tf is not None
        stored_sha256 = tf.sha256
        storage_path = tf.storage_path

    # Calcola l'hash del file su disco
    content = Path(storage_path).read_text(encoding="utf-8")
    disk_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    assert stored_sha256 == disk_sha256, (
        f"SHA-256 nel DB ({stored_sha256}) diverso dall'hash del file su disco ({disk_sha256})"
    )


def test_fetch_creates_transcript_file_record_in_db(tmp_path: Path) -> None:
    """Dopo un fetch riuscito deve esistere un record TranscriptFile nel DB."""
    sessions, transcripts_dir = _setup(tmp_path)
    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo.", "en"),
    ):
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))

    with sessions() as session:
        tf = TranscriptFileRepository(session).get_by_video_id("v1")
        assert tf is not None
        assert tf.video_id == "v1"
        assert tf.language_code == "en"
        assert tf.storage_path
        assert tf.sha256


def test_fetch_transcript_file_record_points_to_existing_file(tmp_path: Path) -> None:
    """Il percorso storage_path nel DB deve puntare a un file realmente esistente."""
    sessions, transcripts_dir = _setup(tmp_path)
    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo esistente.", "it"),
    ):
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))

    with sessions() as session:
        tf = TranscriptFileRepository(session).get_by_video_id("v1")
        assert tf is not None
        assert Path(tf.storage_path).exists(), f"Il file {tf.storage_path} non esiste su disco"


# ---------------------------------------------------------------------------
# Idempotenza: secondo fetch su video già stored
# ---------------------------------------------------------------------------


def test_fetch_idempotent_when_video_already_stored(tmp_path: Path) -> None:
    """Un secondo fetch su un video già stored deve aggiornarsi senza duplicare il file."""
    sessions, transcripts_dir = _setup(tmp_path)
    transcript_text = "Testo idempotente."

    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=(transcript_text, "it"),
    ):
        # Primo fetch
        with sessions() as session:
            v = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v.status == AcquisitionStatus.STORED

        # Secondo fetch (stesso video, già stored)
        with sessions() as session:
            v2 = fetch_transcript(session, "v1", str(transcripts_dir))
            assert v2.status == AcquisitionStatus.STORED

    # Deve esistere un solo file .md (non duplicati)
    files = list(transcripts_dir.glob("*.md"))
    assert len(files) == 1, f"Non devono esserci file duplicati, trovati: {files}"


def test_fetch_idempotent_transcript_file_record_not_duplicated(tmp_path: Path) -> None:
    """Due fetch successivi non devono creare due record TranscriptFile per lo stesso video."""
    sessions, transcripts_dir = _setup(tmp_path)

    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo.", "it"),
    ):
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))
        with sessions() as session:
            fetch_transcript(session, "v1", str(transcripts_dir))

    with sessions() as session:
        from sqlalchemy import func

        from yctm.infrastructure.database.models import TranscriptFile

        count = (
            session.query(func.count(TranscriptFile.id))
            .filter(TranscriptFile.video_id == "v1")
            .scalar()
        )
        assert count == 1, f"Deve esistere un solo record TranscriptFile, trovati: {count}"


# ---------------------------------------------------------------------------
# Rollback/compensazione: DB commit fallisce dopo scrittura del file
# ---------------------------------------------------------------------------


def test_fetch_rolls_back_status_on_db_commit_failure(tmp_path: Path) -> None:
    """Se il commit DB fallisce dopo la scrittura del file, la funzione deve propagare l'errore."""
    sessions, transcripts_dir = _setup(tmp_path)

    with patch(
        "yctm.application.transcripts.extract_transcript",
        return_value=("Testo.", "it"),
    ):
        with sessions() as session:
            with patch.object(session, "commit", side_effect=RuntimeError("DB error")):
                with pytest.raises(RuntimeError, match="DB error"):
                    fetch_transcript(session, "v1", str(transcripts_dir))

    # Lo stato nel DB deve rimanere not_requested (la sessione era in errore)
    with sessions() as session:
        v = VideoRepository(session).get("v1")
        assert v is not None
        # La sessione ha fatto rollback: lo stato non deve essere stored
        assert v.status == AcquisitionStatus.NOT_REQUESTED

    # Compensazione verificata: il file scritto deve essere stato rimosso dal filesystem
    files = list(transcripts_dir.glob("*.md"))
    assert len(files) == 0, f"Il file orfano deve essere stato rimosso, trovati: {files}"
