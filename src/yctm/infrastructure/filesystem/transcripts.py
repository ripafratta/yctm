"""Scrittura su filesystem delle trascrizioni."""

import hashlib
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class FilesystemError(Exception):
    """Errore durante le operazioni su filesystem."""


@dataclass(frozen=True, slots=True)
class StoredTranscript:
    """Metadati di una trascrizione archiviata su disco."""

    storage_path: str
    sha256: str
    language_code: str


def sanitize_filename(title: str, max_length: int = 80) -> str:
    """Produce un nome di file sicuro da un titolo video."""
    safe = re.sub(r"[^\w\s-]", "_", title)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("_")
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip("_")
    return safe or "untitled"


def build_filename(published_at: datetime | None, video_id: str, title: str) -> str:
    """Costruisce un nome file deterministico per una trascrizione."""
    date_part = published_at.strftime("%Y%m%d") if published_at else "nodate"
    safe_title = sanitize_filename(title)
    return f"{date_part}_{video_id}_{safe_title}.md"


def compute_sha256(content: str) -> str:
    """Calcola l'hash SHA-256 di una stringa."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _yaml_scalar(value: str | None) -> str:
    """Serializza un valore scalare YAML in modo sicuro."""
    if value is None:
        return "~"
    if not value:
        return '""'
    special = (":", "#", "{", "}", "[", "]", ">", "|", "!", "%", "@", "`", '"', "'", "\\", "\n")
    if any(c in value for c in special):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _yaml_multiline(value: str) -> str:
    """Serializza una stringa multilinea come blocco YAML (|)."""
    if not value:
        return '""'
    return "|\n" + "\n".join(f"  {line}" for line in value.splitlines())


def build_transcript_markdown(
    text: str,
    video_id: str,
    title: str,
    channel_id: str,
    channel_title: str = "",
    channel_handle: str | None = None,
    published_at: datetime | None = None,
    language_code: str = "",
    description: str | None = None,
) -> str:
    """Costruisce il contenuto Markdown con frontmatter YAML per una trascrizione."""
    now = datetime.now().isoformat()
    source = f"https://www.youtube.com/watch?v={video_id}"
    pub = published_at.isoformat() if published_at else None

    lines = ["---"]
    lines.append(f"title: {_yaml_scalar(title)}")
    lines.append(f"video_id: {_yaml_scalar(video_id)}")
    lines.append(f"channel_id: {_yaml_scalar(channel_id)}")
    if channel_title:
        lines.append(f"channel_title: {_yaml_scalar(channel_title)}")
    if channel_handle:
        lines.append(f"channel_handle: {_yaml_scalar(channel_handle)}")
    if pub:
        lines.append(f"published_at: {pub}")
    lines.append(f"extracted_at: {now}")
    if language_code:
        lines.append(f"language: {_yaml_scalar(language_code)}")
    lines.append(f"source: {_yaml_scalar(source)}")
    if description:
        lines.append("description: " + _yaml_multiline(description))
    lines.append("---")
    lines.append("")
    lines.append(text.rstrip("\n"))
    lines.append("")

    return "\n".join(lines)


def write_transcript_atomically(
    directory: Path,
    filename: str,
    content: str,
) -> StoredTranscript:
    """Scrive una trascrizione su disco in modo atomico."""
    sha256 = compute_sha256(content)
    target = directory / filename

    directory.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix=f".{filename}.", dir=str(directory))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise FilesystemError(f"Impossibile scrivere la trascrizione in {target}: {exc}") from exc

    logger.info("Trascrizione salvata in %s (SHA-256: %s).", target, sha256)
    return StoredTranscript(storage_path=str(target), sha256=sha256, language_code="")
