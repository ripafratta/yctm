"""Client per l'estrazione delle trascrizioni tramite youtube-transcript-api."""

import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api._transcripts import Transcript, TranscriptList

from yctm.domain.models import RecoverableAcquisitionError, YctmError

logger = logging.getLogger(__name__)


class TranscriptExtractionError(YctmError):
    """Errore generico durante l'estrazione della trascrizione."""


class TranscriptUnavailableError(RecoverableAcquisitionError):
    """La trascrizione non e' ancora disponibile per questo video."""


class TranscriptPermanentlyDisabledError(YctmError):
    """Le trascrizioni sono permanentemente disabilitate per questo video."""


_LANGUAGE_FALLBACK = ["it", "en"]


def extract_transcript(video_id: str) -> tuple[str, str]:
    """Estrae la trascrizione di un video applicando il fallback linguistico.

    Restituisce (testo_completo, codice_lingua).
    """
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        raise TranscriptPermanentlyDisabledError(
            f"Trascrizioni disabilitate per il video {video_id}."
        ) from None
    except Exception as exc:
        logger.warning("Errore imprevisto durante list_transcripts per %s: %s", video_id, exc)
        raise TranscriptExtractionError(
            f"Impossibile accedere alle trascrizioni per il video {video_id}."
        ) from exc

    chosen = _find_best_transcript(transcript_list)
    if chosen is None:
        raise TranscriptUnavailableError(
            f"Nessuna trascrizione disponibile nelle lingue configurate per il video {video_id}."
        )

    try:
        fetched = chosen.fetch()
        language_code: str = chosen.language_code
    except NoTranscriptFound:
        raise TranscriptUnavailableError(
            f"Trascrizione non ancora generata per il video {video_id}."
        ) from None
    except Exception as exc:
        logger.warning("Errore durante il fetch della trascrizione per %s: %s", video_id, exc)
        raise TranscriptExtractionError(
            f"Errore durante il recupero della trascrizione per il video {video_id}."
        ) from exc

    full_text = " ".join(snippet.text for snippet in fetched)
    logger.info(
        "Trascrizione estratta per %s: lingua=%s, caratteri=%d.",
        video_id,
        language_code,
        len(full_text),
    )
    return full_text, language_code


def _find_best_transcript(transcript_list: TranscriptList) -> Transcript | None:
    """Seleziona la migliore trascrizione secondo il fallback configurato."""
    for lang in _LANGUAGE_FALLBACK:
        try:
            return transcript_list.find_transcript([lang])
        except NoTranscriptFound:
            pass
        try:
            return transcript_list.find_generated_transcript([lang])
        except NoTranscriptFound:
            pass
    return None
