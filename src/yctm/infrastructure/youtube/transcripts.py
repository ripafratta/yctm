"""
Estrazione trascrizioni — IMPLEMENTAZIONE ATTIVA: youtube-transcript-api.

╔══════════════════════════════════════════════════════════════════════════════╗
║ APPROCCIO ATTIVO: youtube-transcript-api (scraping via innertube).          ║
║ Non richiede OAuth, API key, né verifiche Google. Funziona per tutti i     ║
║ video con trascrizioni pubbliche. Delay di 2 secondi tra richieste per      ║
║ evitare blocchi IP.                                                         ║
║                                                                             ║
║ ALTERNATIVA SOSPESA: YouTube Data API v3 captions.download (OAuth-based).   ║
║ Sostituita perché captions.download restituisce 403 per la maggior parte    ║
║ dei video a meno che l'app non sia verificata da Google o il proprietario   ║
║ del video non abbia abilitato contributi di terze parti.                    ║
║                                                                             ║
║ I moduli auth.py e captions.py (stessa directory) contengono l'approccio    ║
║ OAuth-based, mantenuto come riferimento per futuro.                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import http.cookiejar
import logging
from pathlib import Path

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api._transcripts import Transcript, TranscriptList

from yctm.domain.models import RecoverableAcquisitionError, YctmError

logger = logging.getLogger(__name__)

# Sessione riutilizzata tra chiamate successive per sfruttare i cookie.
# Inizializzata lazy al primo extract_transcript con cookies_path.
_shared_session: requests.Session | None = None
_shared_api: YouTubeTranscriptApi | None = None


class TranscriptExtractionError(YctmError):
    """Errore generico durante l'estrazione della trascrizione."""


class TranscriptUnavailableError(RecoverableAcquisitionError):
    """La trascrizione non e' ancora disponibile per questo video (ritentabile)."""


class TranscriptPermanentlyDisabledError(YctmError):
    """Le trascrizioni sono permanentemente disabilitate per questo video."""


_LANGUAGE_FALLBACK = ["it", "en"]


def extract_transcript(
    video_id: str,
    cookies_path: Path | None = None,
) -> tuple[str, str]:
    """Estrae la trascrizione di un video applicando il fallback linguistico.

    Usa youtube-transcript-api (scraping innertube) — non richiede OAuth né API key.
    Se viene fornito un cookies_path (file in formato Netscape), viene usato per
    autenticare le richieste e ridurre il rischio di blocchi IP.

    Args:
        video_id: ID del video YouTube.
        cookies_path: Percorso a un file cookie in formato Netscape (opzionale).

    Returns:
        Tupla (testo_completo, codice_lingua).

    Raises:
        TranscriptPermanentlyDisabledError: Trascrizioni disabilitate per il video.
        TranscriptUnavailableError: Nessuna lingua disponibile nei fallback.
        TranscriptExtractionError: Errore di rete o API imprevisto.
    """
    api = _get_api(cookies_path)
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
    """Seleziona la migliore trascrizione secondo il fallback configurato.

    Ordine: manuale IT → manuale EN → generata IT → generata EN → None.
    """
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


def _get_api(cookies_path: Path | None) -> YouTubeTranscriptApi:
    """Restituisce un'istanza di YouTubeTranscriptApi, eventualmente con cookie.

    La sessione HTTP con i cookie viene riutilizzata tra chiamate successive,
    ammortizzando il costo di parsing del file cookie.
    """
    global _shared_session, _shared_api

    # Rigenera solo se il cookies_path cambia o è la prima chiamata
    current_cookies = getattr(_shared_session, "_yctm_cookies_path", None)
    if _shared_api is not None and current_cookies == cookies_path:
        return _shared_api

    session = None
    if cookies_path is not None and cookies_path.exists():
        session = requests.Session()
        cj = http.cookiejar.MozillaCookieJar()
        try:
            cj.load(str(cookies_path), ignore_expires=False)
            session.cookies.update(cj)
            logger.info("Cookie caricati da %s (%d cookie).", cookies_path, len(cj))
        except Exception as exc:
            logger.warning("Impossibile caricare i cookie da %s: %s", cookies_path, exc)
            session = None

    if session is not None:
        session._yctm_cookies_path = cookies_path  # type: ignore[attr-defined]

    _shared_session = session
    _shared_api = YouTubeTranscriptApi(http_client=session)
    return _shared_api
