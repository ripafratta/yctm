"""Client per la YouTube Data API v3 tramite httpx."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class YouTubeAPIError(Exception):
    """Errore generico durante una chiamata alla YouTube Data API."""


class QuotaExceededError(YouTubeAPIError):
    """La quota API giornaliera e' stata superata."""


class ChannelNotFoundError(YouTubeAPIError):
    """Il canale richiesto non e' stato trovato."""


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    """Informazioni sul canale restituite dalla Data API."""

    id: str
    handle: str | None
    title: str
    uploads_playlist_id: str


@dataclass(frozen=True, slots=True)
class PlaylistInfo:
    """Informazioni sulla playlist restituite dalla Data API."""

    id: str
    title: str
    channel_id: str | None


@dataclass(frozen=True, slots=True)
class VideoInfo:
    """Informazioni sul video restituite dalla Data API."""

    id: str
    channel_id: str
    title: str
    description: str = ""
    channel_title: str = ""
    published_at: datetime | None = None


_BASE_URL = "https://www.googleapis.com/youtube/v3"


def resolve_channel(api_key: str, identifier: str) -> ChannelInfo:
    """Risolve un identificativo di canale (ID, handle o URL) nelle informazioni del canale."""
    clean = _extract_identifier(identifier)
    if clean.startswith("UC"):
        return _fetch_channel_by_id(api_key, clean)
    if clean.startswith("@"):
        return _fetch_channel_by_handle(api_key, clean.lstrip("@"))
    raise ChannelNotFoundError(
        f"L'identificativo '{identifier}' non e' un ID UC... o handle @... valido."
    )


def list_recent_videos(api_key: str, uploads_playlist_id: str, max_results: int) -> list[VideoInfo]:
    """Recupera gli ultimi `max_results` video dalla playlist di caricamento."""
    params: dict[str, str | int] = {
        "part": "snippet",
        "playlistId": uploads_playlist_id,
        "maxResults": min(max_results, 50),
    }
    response = _api_get(api_key, "/playlistItems", params)
    items: list[dict[str, Any]] = response.get("items", [])
    videos: list[VideoInfo] = []
    for item in items:
        snippet = item.get("snippet", {})
        resource = snippet.get("resourceId", {})
        video_id = resource.get("videoId", "")
        if not video_id:
            continue
        published_at_raw = snippet.get("publishedAt")
        published_at = (
            datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
            if published_at_raw
            else None
        )
        videos.append(
            VideoInfo(
                id=video_id,
                channel_id=snippet.get("channelId", ""),
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                channel_title=snippet.get("channelTitle", ""),
                published_at=published_at,
            )
        )
    logger.debug("Recuperati %d video dalla playlist %s.", len(videos), uploads_playlist_id)
    return videos


def list_playlist_videos(api_key: str, playlist_id: str, max_results: int) -> list[VideoInfo]:
    """Recupera gli ultimi `max_results` video da una playlist arbitraria."""
    return list_recent_videos(api_key, playlist_id, max_results)


def resolve_playlist(api_key: str, identifier: str) -> PlaylistInfo:
    """Risolve un identificativo di playlist (ID o URL) nei metadati della playlist."""
    clean = _extract_playlist_id(identifier)
    return _fetch_playlist_by_id(api_key, clean)


def _extract_playlist_id(raw: str) -> str:
    """Estrae l'ID della playlist da un URL o da un input diretto."""
    import re

    match = re.search(r"PL[\w-]{32}", raw)
    if match:
        return match.group(0)
    return raw.strip()


def _fetch_playlist_by_id(api_key: str, playlist_id: str) -> PlaylistInfo:
    """Recupera i metadati di una playlist tramite ID."""
    params = {"part": "snippet,contentDetails", "id": playlist_id}
    response = _api_get(api_key, "/playlists", params)
    items: list[dict[str, Any]] = response.get("items", [])
    if not items:
        raise ChannelNotFoundError(f"Playlist con ID '{playlist_id}' non trovata.")
    item = items[0]
    snippet = item.get("snippet", {})
    return PlaylistInfo(
        id=item.get("id", ""),
        title=snippet.get("title", ""),
        channel_id=snippet.get("channelId"),
    )


def _extract_identifier(raw: str) -> str:
    """Estrae l'ID o l'handle da un URL o da un input diretto."""
    import re

    match = re.search(r"UC[\w-]{22}", raw)
    if match:
        return match.group(0)
    match = re.search(r"@[\w.-]+", raw)
    if match:
        return match.group(0)
    return raw.strip()


def _fetch_channel_by_id(api_key: str, channel_id: str) -> ChannelInfo:
    """Recupera le informazioni del canale tramite ID UC..."""
    params = {"part": "snippet,contentDetails", "id": channel_id}
    response = _api_get(api_key, "/channels", params)
    items: list[dict[str, Any]] = response.get("items", [])
    if not items:
        raise ChannelNotFoundError(f"Canale con ID '{channel_id}' non trovato.")
    return _parse_channel_item(items[0])


def _fetch_channel_by_handle(api_key: str, handle: str) -> ChannelInfo:
    """Recupera le informazioni del canale tramite handle (senza @)."""
    params = {"part": "snippet,contentDetails", "forHandle": handle}
    response = _api_get(api_key, "/channels", params)
    items: list[dict[str, Any]] = response.get("items", [])
    if not items:
        raise ChannelNotFoundError(f"Canale con handle '@{handle}' non trovato.")
    return _parse_channel_item(items[0])


def _parse_channel_item(item: dict[str, Any]) -> ChannelInfo:
    snippet = item.get("snippet", {})
    content_details = item.get("contentDetails", {})
    channel_id = item.get("id", "")
    uploads_playlist = content_details.get("relatedPlaylists", {}).get("uploads", "")
    if not uploads_playlist and channel_id.startswith("UC"):
        uploads_playlist = "UU" + channel_id[2:]
    return ChannelInfo(
        id=channel_id,
        handle=snippet.get("customUrl"),
        title=snippet.get("title", ""),
        uploads_playlist_id=uploads_playlist,
    )


def _api_get(api_key: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Esegue una richiesta GET alla YouTube Data API v3."""
    params["key"] = api_key
    url = f"{_BASE_URL}{path}"
    try:
        response = httpx.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            raise QuotaExceededError("Quota API YouTube superata o accesso negato.") from exc
        if exc.response.status_code == 404:
            raise ChannelNotFoundError("Risorsa YouTube non trovata.") from exc
        raise YouTubeAPIError(
            f"Errore HTTP {exc.response.status_code} dalla YouTube Data API."
        ) from exc
    except httpx.RequestError as exc:
        raise YouTubeAPIError("Errore di rete durante la chiamata alla YouTube Data API.") from exc

    if "error" in body:
        error_info = body["error"]
        code = error_info.get("code", 0)
        message = error_info.get("message", "Errore sconosciuto")
        if code == 403:
            raise QuotaExceededError(f"Quota API YouTube superata: {message}")
        raise YouTubeAPIError(f"Errore API YouTube ({code}): {message}")

    return body
