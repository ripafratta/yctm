"""Caso d'uso: generazione del manifest JSONL."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from yctm.infrastructure.database.models import Video

logger = logging.getLogger(__name__)


@dataclass
class ManifestEntry:
    """Riga del manifest JSONL."""

    video_id: str
    channel_id: str | None
    title: str
    published_at: str | None
    status: str
    attempt_count: int
    last_error: str | None
    storage_path: str | None
    sha256: str | None
    language_code: str | None
    extracted_at: str | None


def _serialize_entry(entry: ManifestEntry) -> dict[str, Any]:
    """Serializza un ManifestEntry in un dizionario JSON-safe."""
    d = asdict(entry)
    d.pop("attempt_count", None)
    return d


def rebuild_manifest(session: Session, manifest_path: Path) -> int:
    """Rigenera il manifest JSONL dai dati presenti nel database e filesystem.

    Scrive atomicamente il file di destinazione e restituisce il numero di record.
    """
    stmt = (
        select(Video).options(joinedload(Video.transcript_file)).order_by(Video.published_at.desc())
    )
    videos = session.execute(stmt).scalars().all()

    entries: list[ManifestEntry] = []
    for video in videos:
        tf = video.transcript_file
        entry = ManifestEntry(
            video_id=video.id,
            channel_id=video.channel_id,
            title=video.title,
            published_at=video.published_at.isoformat() if video.published_at else None,
            status=video.status,
            attempt_count=video.attempt_count,
            last_error=video.last_error,
            storage_path=tf.storage_path if tf else None,
            sha256=tf.sha256 if tf else None,
            language_code=tf.language_code if tf else None,
            extracted_at=tf.extracted_at.isoformat() if tf and tf.extracted_at else None,
        )
        entries.append(entry)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=".manifest.", dir=str(manifest_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(_serialize_entry(entry), ensure_ascii=False) + "\n")
        os.replace(tmp_path, manifest_path)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info("Manifest generato con %d record in %s.", len(entries), manifest_path)
    return len(entries)
