"""Modelli ORM del registro operativo."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from yctm.domain.models import AcquisitionStatus


class Base(DeclarativeBase):
    """Base dei modelli SQLAlchemy."""


# Tabella di associazione molti-a-molti Playlist ↔ Video.
# La PK composita (playlist_id, video_id) garantisce idempotenza per costruzione.
playlist_videos = Table(
    "playlist_videos",
    Base.metadata,
    Column(
        "playlist_id",
        String,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "video_id",
        String,
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("added_at", DateTime, default=datetime.now),
)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    handle: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    uploads_playlist_id: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    status: Mapped[str] = mapped_column(String, default=AcquisitionStatus.NOT_REQUESTED)
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    transcript_file: Mapped["TranscriptFile | None"] = relationship(
        back_populates="video", uselist=False
    )
    playlists: Mapped[list["Playlist"]] = relationship(
        secondary=playlist_videos,
        back_populates="videos",
    )

    def register_failure(self, message: str) -> None:
        """Registra un errore e rende terminale il terzo tentativo."""
        self.attempt_count = (self.attempt_count or 0) + 1
        self.last_attempt_at = datetime.now()
        self.last_error = message
        self.status = (
            AcquisitionStatus.TERMINAL_ERROR
            if self.attempt_count >= 3
            else AcquisitionStatus.RETRYABLE_ERROR
        )


class TranscriptFile(Base):
    __tablename__ = "transcript_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"), unique=True)
    storage_path: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    language_code: Mapped[str] = mapped_column(String)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    video: Mapped["Video"] = relationship(back_populates="transcript_file")


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    videos: Mapped[list["Video"]] = relationship(
        secondary=playlist_videos,
        back_populates="playlists",
    )
