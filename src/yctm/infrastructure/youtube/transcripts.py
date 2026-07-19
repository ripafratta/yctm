"""Estrazione trascrizioni tramite YouTube Data API v3 (captions.download).

Rimpiazza il vecchio modulo basato su youtube-transcript-api (scraping).
Mantiene la stessa firma extract_transcript(video_id) e le stesse eccezioni
per compatibilità con synchronization.py e playlists.py.
"""

from __future__ import annotations

import logging

from yctm.config.settings import Settings
from yctm.infrastructure.youtube.auth import get_authenticated_client
from yctm.infrastructure.youtube.captions import (
    CaptionTrack,
    download_caption,
    find_best_track,
    list_caption_tracks,
    parse_srt_to_plain_text,
)

logger = logging.getLogger(__name__)


class TranscriptExtractionError(Exception):
    """Errore generico durante l'estrazione della trascrizione."""


class TranscriptUnavailableError(Exception):
    """La trascrizione non e' disponibile per questo video (ritentabile)."""


class TranscriptPermanentlyDisabledError(Exception):
    """Le trascrizioni sono permanentemente disabilitate per questo video."""


def extract_transcript(video_id: str) -> tuple[str, str]:
    """Estrae la trascrizione di un video tramite YouTube Data API v3.

    Usa captions.list per trovare il miglior track disponibile,
    poi captions.download per scaricare il contenuto SRT.

    Args:
        video_id: ID del video YouTube.

    Returns:
        Tupla (testo_completo, codice_lingua).

    Raises:
        TranscriptPermanentlyDisabledError: Nessun caption track disponibile.
        TranscriptUnavailableError: Nessuna lingua nei fallback, o download vuoto.
        TranscriptExtractionError: Errore API, di rete, o OAuth non configurato.
    """
    try:
        client = get_authenticated_client()
    except Exception as exc:
        raise TranscriptExtractionError(
            f"Impossibile autenticarsi alla YouTube API: {exc}. "
            "Esegui 'yctm auth' per configurare OAuth 2.0."
        ) from exc

    # 1. Recupera i caption track disponibili
    try:
        tracks: list[CaptionTrack] = list_caption_tracks(client, video_id)
    except Exception as exc:
        raise TranscriptExtractionError(
            f"Errore durante il recupero dei caption track per {video_id}: {exc}"
        ) from exc

    if not tracks:
        raise TranscriptPermanentlyDisabledError(
            f"Nessun caption track disponibile per il video {video_id}. "
            "Le trascrizioni potrebbero essere disabilitate."
        )

    # 2. Seleziona il miglior track
    caption_id = find_best_track(tracks)
    if caption_id is None:
        raise TranscriptUnavailableError(
            f"Nessun caption track nelle lingue configurate per il video {video_id}."
        )

    best_language = ""
    for t in tracks:
        if t.id == caption_id:
            best_language = t.language
            break

    # 3. Scarica il contenuto
    try:
        srt_content = download_caption(client, caption_id)
    except Exception as exc:
        raise TranscriptExtractionError(
            f"Errore durante il download della trascrizione per {video_id}: {exc}"
        ) from exc

    if not srt_content.strip():
        raise TranscriptUnavailableError(
            f"La trascrizione scaricata per il video {video_id} e' vuota."
        )

    # 4. Converti SRT in testo semplice
    plain_text = parse_srt_to_plain_text(srt_content)

    logger.info(
        "Trascrizione estratta per %s: lingua=%s, caratteri=%d.",
        video_id,
        best_language,
        len(plain_text),
    )
    return plain_text, best_language
