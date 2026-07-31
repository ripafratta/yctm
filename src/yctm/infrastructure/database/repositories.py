"""Repository per lo stato operativo di YCTM."""

from datetime import datetime

from sqlalchemy.orm import Session

from yctm.infrastructure.database.models import (
    Channel,
    Playlist,
    TranscriptFile,
    Video,
    playlist_videos,
)


class ChannelRepository:
    """Gestisce la persistenza idempotente dei canali."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, channel_id: str) -> Channel | None:
        """Restituisce il canale identificato, se presente."""
        return self._session.get(Channel, channel_id)

    def all(self) -> list[Channel]:
        """Restituisce tutti i canali registrati."""
        return list(self._session.query(Channel).order_by(Channel.created_at.desc()).all())

    def delete(self, channel_id: str) -> bool:
        """Rimuove il canale specificato."""
        channel = self.get(channel_id)
        if channel:
            self._session.delete(channel)
            return True
        return False

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

    def list_videos(
        self,
        status: str | None = None,
        channel_id: str | None = None,
        playlist_id: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        order: str = "published-desc",
    ) -> list[Video]:
        """Elenca i video catalogati applicando i filtri specificati."""
        query = self._session.query(Video)
        if status:
            query = query.filter(Video.status == status)
        if channel_id:
            query = query.filter(Video.channel_id == channel_id)
        if playlist_id:
            query = query.join(
                playlist_videos,
                Video.id == playlist_videos.c.video_id,
            ).filter(playlist_videos.c.playlist_id == playlist_id)
        if after:
            query = query.filter(Video.published_at >= after)
        if before:
            query = query.filter(Video.published_at <= before)

        if order == "published-asc":
            query = query.order_by(Video.published_at.asc())
        else:
            query = query.order_by(Video.published_at.desc())

        if limit > 0:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)

        return list(query.all())

    def reset_to_pending(self, status_filter: str) -> int:
        """Reimposta a not_requested tutti i video con lo stato indicato.

        Resetta anche attempt_count, last_attempt_at e last_error.
        Restituisce il numero di video modificati.
        """
        now = datetime.now()
        videos = self.find_by_status(status_filter)
        for video in videos:
            video.status = "not_requested"
            video.attempt_count = 0
            video.last_attempt_at = None
            video.last_error = None
            video.updated_at = now
        return len(videos)

    def reset_video(self, video_id: str) -> bool:
        """Reimposta a not_requested un singolo video."""
        video = self.get(video_id)
        if video:
            video.status = "not_requested"
            video.attempt_count = 0
            video.last_attempt_at = None
            video.last_error = None
            video.updated_at = datetime.now()
            return True
        return False


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

    def all(self) -> list[Playlist]:
        """Restituisce tutte le playlist registrate."""
        return list(self._session.query(Playlist).order_by(Playlist.created_at.desc()).all())

    def delete(self, playlist_id: str) -> bool:
        """Rimuove la playlist specificata."""
        playlist = self.get(playlist_id)
        if playlist:
            self._session.delete(playlist)
            return True
        return False

    def upsert(self, playlist: Playlist) -> Playlist:
        """Inserisce o aggiorna la playlist senza duplicarla."""
        existing = self.get(playlist.id)
        if existing is None:
            self._session.add(playlist)
            return playlist

        existing.title = playlist.title
        existing.channel_id = playlist.channel_id
        return existing

    def add_video(self, playlist_id: str, video_id: str) -> None:
        """Registra l'associazione playlist ↔ video in modo idempotente.

        Non solleva eccezioni se la coppia esiste già (PK composita garantisce unicità).
        """
        from sqlalchemy.dialects.sqlite import insert

        stmt = (
            insert(playlist_videos)
            .values(
                playlist_id=playlist_id,
                video_id=video_id,
                added_at=datetime.now(),
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(stmt)
