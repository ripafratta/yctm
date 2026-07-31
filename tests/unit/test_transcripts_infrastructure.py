"""Test di classificazione delle eccezioni infrastrutturali per l'estrazione trascrizioni.

Verifica che ogni scenario di errore (disabilitazione permanente, indisponibilità temporanea,
errori di rete/429) venga classificato nella corretta eccezione di dominio.
"""

from unittest.mock import MagicMock, patch

import pytest
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from yctm.infrastructure.youtube.transcripts import (
    TranscriptExtractionError,
    TranscriptPermanentlyDisabledError,
    TranscriptUnavailableError,
    extract_transcript,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transcript_list(raise_on_list: Exception | None = None) -> MagicMock:
    """Crea un mock di YouTubeTranscriptApi.list() pronto all'uso."""
    mock_api = MagicMock()
    if raise_on_list is not None:
        mock_api.list.side_effect = raise_on_list
    return mock_api


# ---------------------------------------------------------------------------
# Test: TranscriptPermanentlyDisabledError
# ---------------------------------------------------------------------------


def test_transcripts_disabled_raises_permanently_disabled() -> None:
    """TranscriptsDisabled → TranscriptPermanentlyDisabledError (terminale immediato)."""
    mock_api = _make_transcript_list(TranscriptsDisabled("vid1"))
    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptPermanentlyDisabledError):
            extract_transcript("vid1")


# ---------------------------------------------------------------------------
# Test: TranscriptUnavailableError
# ---------------------------------------------------------------------------


def test_no_transcript_found_in_fallback_raises_unavailable() -> None:
    """Nessuna lingua nel fallback → TranscriptUnavailableError (ritentabile)."""
    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.side_effect = NoTranscriptFound("vid1", ["it"], [])
    mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound(
        "vid1", ["it", "en"], []
    )

    mock_api = MagicMock()
    mock_api.list.return_value = mock_transcript_list

    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptUnavailableError):
            extract_transcript("vid1")


def test_fetch_raises_no_transcript_found_raises_unavailable() -> None:
    """NoTranscriptFound durante il fetch → TranscriptUnavailableError."""
    mock_transcript = MagicMock()
    mock_transcript.language_code = "it"
    mock_transcript.fetch.side_effect = NoTranscriptFound("vid1", ["it"], [])

    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.return_value = mock_transcript
    mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound("vid1", [], [])

    mock_api = MagicMock()
    mock_api.list.return_value = mock_transcript_list

    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptUnavailableError):
            extract_transcript("vid1")


# ---------------------------------------------------------------------------
# Test: TranscriptExtractionError
# ---------------------------------------------------------------------------


def test_generic_exception_on_list_raises_extraction_error() -> None:
    """Eccezione generica su api.list() → TranscriptExtractionError (ritentabile con limite)."""
    mock_api = _make_transcript_list(RuntimeError("Connection reset"))
    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptExtractionError):
            extract_transcript("vid1")


def test_network_timeout_on_list_raises_extraction_error() -> None:
    """TimeoutError su api.list() → TranscriptExtractionError."""
    mock_api = _make_transcript_list(TimeoutError("timed out"))
    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptExtractionError):
            extract_transcript("vid1")


def test_http_429_on_list_raises_extraction_error() -> None:
    """Errore HTTP 429 (too many requests) su api.list() → TranscriptExtractionError."""
    mock_api = _make_transcript_list(Exception("429 Too Many Requests"))
    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptExtractionError):
            extract_transcript("vid1")


def test_generic_exception_on_fetch_raises_extraction_error() -> None:
    """Eccezione generica durante chosen.fetch() → TranscriptExtractionError."""
    mock_transcript = MagicMock()
    mock_transcript.language_code = "en"
    mock_transcript.fetch.side_effect = OSError("network error")

    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.return_value = mock_transcript
    mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound("vid1", [], [])

    mock_api = MagicMock()
    mock_api.list.return_value = mock_transcript_list

    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        with pytest.raises(TranscriptExtractionError):
            extract_transcript("vid1")


# ---------------------------------------------------------------------------
# Test: Happy path — fallback linguistico
# ---------------------------------------------------------------------------


def test_extract_transcript_returns_text_and_language() -> None:
    """Estrazione con successo: restituisce testo e codice lingua."""
    mock_snippet = MagicMock()
    mock_snippet.text = "Hello world"

    mock_transcript = MagicMock()
    mock_transcript.language_code = "en"
    mock_transcript.fetch.return_value = [mock_snippet]

    mock_transcript_list = MagicMock()
    # Simula IT non disponibile, EN disponibile
    mock_transcript_list.find_transcript.side_effect = [
        NoTranscriptFound("vid1", ["it"], []),
        mock_transcript,  # EN manuale
    ]
    mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound("vid1", [], [])

    mock_api = MagicMock()
    mock_api.list.return_value = mock_transcript_list

    with patch("yctm.infrastructure.youtube.transcripts._get_api", return_value=mock_api):
        text, lang = extract_transcript("vid1")

    assert text == "Hello world"
    assert lang == "en"
