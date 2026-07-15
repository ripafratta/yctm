"""Repository per lo stato operativo di YCTM."""

from datetime import datetime

from sqlalchemy.orm import Session

from yctm.infrastructure.database.models import Channel, Playlist, TranscriptFile, Video


class ChannelRepository:
    """Gestisce la persistenza idempotente dei canali."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, channel_id: str) -> Channel | None:
        """Restituisce il canale identificato, se presente."""
        return self._session.get(Channel, channel_id)

    def upsert(self, channel: Channel) -> Channel:
        """Inserisce o aggiorna il canale senza duplicarlo."""
        existing = self.get(channel.id)
        if existing is None:
            self._session.add(channel)
            return channel

        existing.handle = channel.handle
        existing.title = channel.title
        existing.uploads_playlist_id = channel.uploads_playlist_id
        return existing


class VideoRepository:
    """Gestisce la persistenza e la deduplicazione dei video."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, video_id: str) -> Video | None:
        """Restituisce il video identificato, se presente."""
        return self._session.get(Video, video_id)

    def add(self, video: Video) -> Video:
        """Registra un video non ancora presente."""
        self._session.add(video)
        return video

    def find_by_status(self, status: str) -> list[Video]:
        """Restituisce tutti i video con lo stato specificato."""
        return list(self._session.query(Video).filter(Video.status == status).all())

    def reset_to_pending(self, status_filter: str) -> int:
        """Reimposta a pending tutti i video con lo stato indicato.

        Resetta anche attempt_count, last_attempt_at e last_error.
        Restituisce il numero di video modificati.
        """
        now = datetime.now()
        videos = self.find_by_status(status_filter)
        for video in videos:
            video.status = "pending"
            video.attempt_count = 0
            video.last_attempt_at = None
            video.last_error = None
            video.updated_at = now
        return len(videos)


class TranscriptFileRepository:
    """Gestisce la persistenza dei file di trascrizione."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_video_id(self, video_id: str) -> TranscriptFile | None:
        """Restituisce il file di trascrizione associato al video, se presente."""
        return (
            self._session.query(TranscriptFile).filter(TranscriptFile.video_id == video_id).first()
        )

    def add(self, transcript_file: TranscriptFile) -> TranscriptFile:
        """Registra un nuovo file di trascrizione."""
        self._session.add(transcript_file)
        return transcript_file


class PlaylistRepository:
    """Gestisce la persistenza idempotente delle playlist."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, playlist_id: str) -> Playlist | None:
        """Restituisce la playlist identificata, se presente."""
        return self._session.get(Playlist, playlist_id)

    def upsert(self, playlist: Playlist) -> Playlist:
        """Inserisce o aggiorna la playlist senza duplicarla."""
        existing = self.get(playlist.id)
        if existing is None:
            self._session.add(playlist)
            return playlist

        existing.title = playlist.title
        existing.channel_id = playlist.channel_id
        return existing
