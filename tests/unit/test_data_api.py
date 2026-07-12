"""Test per il client YouTube Data API."""

import httpx
import pytest

from yctm.infrastructure.youtube.data_api import (
    ChannelNotFoundError,
    QuotaExceededError,
    YouTubeAPIError,
    list_recent_videos,
    resolve_channel,
)


def _channel_response(channel_id: str, title: str, handle: str) -> dict:
    return {
        "items": [
            {
                "id": channel_id,
                "snippet": {"title": title, "customUrl": handle},
                "contentDetails": {"relatedPlaylists": {"uploads": f"UU{channel_id[2:]}"}},
            }
        ]
    }


def _playlist_response(video_ids: list[str]) -> dict:
    items = []
    for vid in video_ids:
        items.append(
            {
                "snippet": {
                    "channelId": "UC123",
                    "title": f"Video {vid}",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "resourceId": {"videoId": vid},
                }
            }
        )
    return {"items": items}


def test_resolve_channel_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=_channel_response("UC1234567890123456789012", "Test Channel", "@test"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    info = resolve_channel("fake-key", "UC1234567890123456789012")
    assert info.id == "UC1234567890123456789012"
    assert info.title == "Test Channel"
    assert info.handle == "@test"
    assert info.uploads_playlist_id.startswith("UU")


def test_resolve_channel_by_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=_channel_response("UC1234567890123456789012", "Test", "@handle"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    info = resolve_channel("fake-key", "@handle")
    assert info.id == "UC1234567890123456789012"


def test_resolve_channel_by_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=_channel_response("UC1234567890123456789012", "Test", "@test"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    info = resolve_channel("fake-key", "https://www.youtube.com/@test")
    assert info.id == "UC1234567890123456789012"


def test_resolve_channel_url_with_uc_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=_channel_response("UC1234567890123456789012", "Test", "@test"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    info = resolve_channel(
        "fake-key",
        "https://www.youtube.com/channel/UC1234567890123456789012",
    )
    assert info.id == "UC1234567890123456789012"


def test_resolve_channel_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(404, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", mock_get)
    with pytest.raises(ChannelNotFoundError):
        resolve_channel("fake-key", "@nonexistent")


def test_resolve_channel_quota_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            403,
            json={"error": {"code": 403, "message": "Quota exceeded"}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    with pytest.raises(QuotaExceededError):
        resolve_channel("fake-key", "@test")


def test_resolve_channel_invalid_identifier() -> None:
    with pytest.raises(ChannelNotFoundError):
        resolve_channel("fake-key", "not_a_valid_id")


def test_list_recent_videos(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json=_playlist_response(["vid1", "vid2", "vid3"]),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    videos = list_recent_videos("fake-key", "UU1234567890123456789012", max_results=5)
    assert len(videos) == 3
    assert videos[0].id == "vid1"
    assert videos[0].title == "Video vid1"


def test_list_recent_videos_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        return httpx.Response(200, json={"items": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", mock_get)
    videos = list_recent_videos("fake-key", "UU123", max_results=5)
    assert videos == []


def test_list_recent_videos_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url, params=None, timeout=None):
        raise httpx.RequestError("Connection failed")

    monkeypatch.setattr(httpx, "get", mock_get)
    with pytest.raises(YouTubeAPIError):
        list_recent_videos("fake-key", "UU123", max_results=5)
