"""
YouTube Data API v3 — chiamate a captions.list e captions.download.

╔══════════════════════════════════════════════════════════════════════════════╗
║ NOTA: Questa implementazione fa parte dell'approccio OAuth-based che è     ║
║ stato sostituito da youtube-transcript-api (scraping via innertube).        ║
║                                                                             ║
║ PROBLEMA: captions.download fallisce con 403 per la maggior parte dei      ║
║ video perché richiede permessi speciali (app verificata o contributor di    ║
║ terze parti abilitato dal proprietario del video).                          ║
║                                                                             ║
║ Mantenuto come riferimento per eventuale utilizzo futuro.                   ║
║ Vedi auth.py per maggiori dettagli.                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CaptionTrack:
    """Rappresenta un track di didascalie restituito da captions.list."""

    id: str
    language: str
    track_kind: str  # "standard" (manuale) o "ASR" (auto-generata)
    is_cc: bool = False


def list_caption_tracks(client: Any, video_id: str) -> list[CaptionTrack]:
    """Recupera la lista dei caption track disponibili per un video.

    Args:
        client: Resource YouTube v3 autenticata.
        video_id: ID del video YouTube.

    Returns:
        Lista di CaptionTrack ordinata per preferenza.

    Raises:
        Exception: Eventuali errori API (403, 404, etc.) propagate.
    """
    request = client.captions().list(part="snippet", videoId=video_id)

    response: dict[str, Any] = request.execute()
    items: list[dict[str, Any]] = response.get("items", [])

    tracks: list[CaptionTrack] = []
    for item in items:
        snippet = item.get("snippet", {})
        tracks.append(
            CaptionTrack(
                id=item.get("id", ""),
                language=snippet.get("language", ""),
                track_kind=snippet.get("trackKind", "ASR"),
                is_cc=snippet.get("isCC", False),
            )
        )

    logger.debug("Trovati %d caption track per video %s", len(tracks), video_id)
    return tracks


def find_best_track(
    tracks: list[CaptionTrack],
    fallback: list[str] | None = None,
) -> str | None:
    """Seleziona il miglior caption track disponibile.

    Ordine di preferenza:
    1. Manuali (track_kind == "standard") nelle lingue richieste
    2. ASR (track_kind == "ASR") nelle lingue richieste
    3. Prima lingua disponibile

    Args:
        tracks: Lista di CaptionTrack da cui selezionare.
        fallback: Ordine di preferenza lingue (default: ["it", "en"]).

    Returns:
        ID del caption track migliore, o None se nessun track disponibile.
    """
    if not tracks:
        return None

    if fallback is None:
        fallback = ["it", "en"]

    # 1. Cerca track manuali nelle lingue richieste
    for lang in fallback:
        for t in tracks:
            if t.track_kind == "standard" and t.language == lang:
                logger.debug("Selezionato track manuale %s (%s)", t.id, t.language)
                return t.id

    # 2. Cerca track ASR nelle lingue richieste
    for lang in fallback:
        for t in tracks:
            if t.track_kind == "ASR" and t.language == lang:
                logger.debug("Selezionato track ASR %s (%s)", t.id, t.language)
                return t.id

    # 3. Prima lingua disponibile (qualsiasi track)
    best = tracks[0]
    logger.debug(
        "Nessuna lingua preferita trovata, selezionato %s (%s, %s)",
        best.id,
        best.language,
        best.track_kind,
    )
    return best.id


def download_caption(client: Any, caption_id: str) -> str:
    """Scarica il contenuto SRT di un caption track.

    Args:
        client: Resource YouTube v3 autenticata.
        caption_id: ID del caption track da scaricare.

    Returns:
        Contenuto della didascalia in formato SRT.

    Raises:
        Exception: Eventuali errori API (403, 404, etc.) propagate.
    """
    request = client.captions().download(id=caption_id, tfmt="srt")

    response = request.execute()
    if isinstance(response, bytes):
        return response.decode("utf-8")
    return str(response)


def parse_srt_to_plain_text(srt_content: str) -> str:
    """Converte il contenuto SRT in testo semplice.

    Rimuove numeri di riga, timestamp e righe vuote,
    restituendo il testo continuo.

    Args:
        srt_content: Contenuto in formato SRT.

    Returns:
        Testo semplice senza marcature SRT.
    """
    if not srt_content:
        return ""

    # Rimuove marcature WebVTT (se presenti)
    text = srt_content
    if text.startswith("WEBVTT"):
        text = re.sub(r"^WEBVTT.*\n?", "", text)

    # Rimuove numeri di riga (interi da soli su una riga)
    text = re.sub(r"^\d+\n", "", text, flags=re.MULTILINE)

    # Rimuove timestamp (formato HH:MM:SS,mmm --> HH:MM:SS,mmm)
    text = re.sub(
        r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}.*\n?",
        "",
        text,
    )

    # Rimuove tag HTML (es. <c>, </c>, <00:00:01.234>)
    text = re.sub(r"<[^>]+>", "", text)

    # Rimuove righe vuote e normalizza spazi
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = " ".join(lines)

    # Normalizza spazi multipli
    text = re.sub(r"\s+", " ", text)

    return text.strip()
