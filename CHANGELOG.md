# Changelog (YCTM)

Tutti i cambiamenti di rilievo apportati a YCTM sono documentati in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [Unreleased]

---

## [0.1.0] - 2026-07-31

### Aggiunto
- **Architettura Catalogo Neutrale**: Catalogo locale disaccoppiato da Knowledge Base, dipendenze LLM o manifest specifici per consumer esterni.
- **Separazione Discovery / Fetch**: `yctm discover` per acuisire i soli metadati (YouTube Data API v3) senza scaricare i transcript; `yctm transcript fetch` per il download puntuale ed esplicito su filesystem.
- **Relazione Molti-a-Molti Playlist-Video**: Introdotta la tabella di associazione `playlist_videos` con chiave primaria composita `(playlist_id, video_id)` per unire le playlist ai video catalogati in modo idempotente.
- **Filtro CLI `--playlist`**: Abilitato il filtraggio dei video per playlist nel comando `yctm video list --playlist PLAYLIST_ID`.
- **Comando `yctm doctor`**: Comando di diagnostica per verificare l'integrità tra database e filesystem (rilevamento file orfani e record con file mancanti).
- **Compensazione Transazionale Immediata**: In `yctm transcript fetch`, qualora il commit su SQLite fallisca dopo la scrittura su disco, il file Markdown orfano viene immediatamente rimosso dal filesystem.
- **Suite di Test Completa**: 90 test unitari ed e2e coprenti CLI, migrazione SQLite, integrità file/SHA-256 e classificazione eccezioni (429/quota/500/trascrizioni disabilitate).
- **Documentazione Modulare**: Nuova struttura `docs/` (`architecture.md`, `cli-reference.md`, `database.md`, `troubleshooting.md`), registro delle decisioni architetturali `docs/adr/` (ADR 0001, 0002, 0003) ed archivio storico `docs/history/`.


---

## [0.1.1] - 2026-09-12

### Migliorato
- **Gestione Rate-Limiting**: Aggiunta la gestione dei messaggi di avviso sul rate-limiting e il relativo test unitario sono stati integrati con successo.

### Riepilogo modifiche

1. **[src/yctm/cli/app.py](file:///Users/marco/Desktop/GitHub/yctm/src/yctm/cli/app.py)**:
   - Aggiunta della funzione helper `_check_rate_limit_warning(last_error: str | None) -> None` per rilevare parole chiave di blocco o rate-limiting (`429`, `too many requests`, `rate`, `block`, `ip`, `impossibile accedere`) e stampare il suggerimento per l'uso dei cookie su `stderr`.
   - Invocazione di `_check_rate_limit_warning` nei comandi `transcript_fetch_cmd` e `transcript_retry_cmd` qualora lo stato finale del video non sia `stored`.

2. **[tests/unit/test_cli_e2e.py](file:///Users/marco/Desktop/GitHub/yctm/tests/unit/test_cli_e2e.py)**:
   - Importata l'eccezione [TranscriptExtractionError](file:///Users/marco/Desktop/GitHub/yctm/src/yctm/infrastructure/youtube/transcripts.py).
   - Aggiunto il test `test_cli_transcript_fetch_prints_rate_limit_warning` che simula un errore HTTP 429 e verifica la presenza del suggerimento e del parametro `--cookies` nell'output CLI.

### Esito verifiche di qualità

Tutti i controlli obbligatori definiti in [AGENTS.md](file:///Users/marco/Desktop/GitHub/yctm/AGENTS.md) hanno restituito esito positivo:
- `ruff check .` ✅
- `ruff format --check .` ✅
- `pytest` (91 test passati) ✅
- `mypy .` (nessun errore su 41 file sorgente) ✅