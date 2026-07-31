# YCTM Implementation Plan — YouTube Source and Transcript Catalog

**Goal:** Realizzare una CLI Python neutrale e generica per la registrazione delle fonti YouTube (canali e playlist), la scoperta incrementale dei metadati dei video e il download puntuale controllato delle trascrizioni.

**Architecture:** YCTM adotta una struttura a livelli disaccoppiata: CLI, configurazione, dominio, casi d'uso e infrastruttura. Il database SQLite conserva il catalogo di canali, playlist, video e metadati di acquisizione. Le trascrizioni originali risiedono nel filesystem sotto forma di documenti Markdown immutabili. YCTM è disaccoppiato da Knowledge Base (KB) e sistemi LLM esterni.

**Tech Stack:** Python 3.12+, Typer, pydantic-settings, SQLAlchemy 2.x, SQLite, httpx, youtube-transcript-api, pytest, Ruff, mypy.

---

## Vincoli Globali e Principi Architetturali

- Nessuna dipendenza o accoppiamento diretto con LLM, prompt, chunking o trasformazioni semantiche.
- Nessun manifest JSONL o esportatore specifico per consumer esterni.
- Nessuna estrazione automatica di transcript durante la fase di discovery dei metadati.
- Il download delle trascrizioni avvengono esclusivamente in modo puntuale ed esplicito per video catalogati.
- Configurazione solo mediante ambiente o `.env`; nessun segreto nel repository.
- Logging esclusivamente tramite il modulo standard `logging`; nessun uso di `print()`.
- Test automatici privi di chiamate reali alle API esterne di YouTube.
- Nessun processo residente, server o meccanismo di scheduling automatico.

---

## Struttura del Pacchetto

```text
src/yctm/
  cli/
    app.py                 Comandi CLI organizzati per sottogruppi (channel, playlist, discover, video, transcript, db)
  config/
    settings.py            Settings da ambiente/.env (pydantic-settings)
  domain/
    models.py              Tipi di dominio, stati ed eccezioni
  application/
    channels.py            Registrazione ed elencazione fonti canale
    playlists.py           Registrazione ed elencazione fonti playlist
    discovery.py           Discovery metadati da Data API v3 (stato not_requested)
    transcripts.py         Download puntuale, reset e gestione stati trascrizione
    catalog.py             Consultazione ed elencazione del catalogo video e statistiche
  infrastructure/
    database/
      models.py            Modelli ORM SQLAlchemy (Channel, Playlist, Video, TranscriptFile)
      session.py           Engine SQLite, sessioni e migrazioni di schema (upgrade)
      repositories.py      Persistenza e query filtrate del catalogo
    youtube/
      data_api.py          Client HTTP per YouTube Data API v3 (resolve handle/channel/playlist, list videos)
      transcripts.py       Client youtube-transcript-api e gerarchia di fallback sottotitoli
      captions.py          Supporto didascalie v3 (opzionale)
      auth.py              Flusso OAuth 2.0 (opzionale)
    filesystem/
      transcripts.py       Nomi file sicuri, scrittura Markdown e calcolo hash SHA-256
tests/
  unit/
```

---

## Interfacce CLI Pubbliche

- **Database**: `yctm init-db`, `yctm db upgrade`
- **Fonti Canale**: `yctm channel add`, `yctm channel list`, `yctm channel remove`
- **Fonti Playlist**: `yctm playlist add`, `yctm playlist list`, `yctm playlist remove`
- **Discovery Metadati**: `yctm discover channel`, `yctm discover playlist`, `yctm discover all`
- **Consultazione Catalogo**: `yctm video list`, `yctm video show`, `yctm video discover`
- **Gestione Trascrizioni**: `yctm transcript fetch`, `yctm transcript status`, `yctm transcript reset`, `yctm transcript retry`
- **Utility**: `yctm stats`, `yctm auth`

---

## Modello Dati e Macchina a Stati

### Entità

- `Channel`: ID canonico `UC...`, handle `@...`, titolo, `uploads_playlist_id`, timestamp creazione/aggiornamento.
- `Playlist`: ID canonico `PL...`, titolo, `channel_id`, timestamp creazione/aggiornamento.
- `Video`: ID YouTube, `channel_id`, titolo, descrizione, data pubblicazione, `discovered_at`, stato (`not_requested`, `stored`, `retryable_error`, `terminal_error`), `attempt_count`, ultimo errore.
- `playlist_videos`: Tabella di associazione molti-a-molti tra `Playlist` e `Video` (chiave primaria composita `playlist_id`, `video_id`).
- `TranscriptFile`: ID interno, `video_id`, percorso storage (`data/transcripts/...`), SHA-256, lingua, timestamp estrazione.


### Stati di Acquisizione

1. `not_requested`: Video scoperto ed iscritto al catalogo locale. Trascrizione non richiesta.
2. `stored`: Trascrizione estratta e salvata su filesystem (stato terminale).
3. `retryable_error`: Tentativo di estrazione fallito per errore temporaneo (es. rete, timeout).
4. `terminal_error`: Tentativo fallito definitivamente (trascrizioni disabilitate o 3 tentativi esauriti) (stato terminale).

---

## Milestone e Stato del Progetto

### Milestone 1: Fondazioni e Configurazione — COMPLETATA
- [x] Configurazione `pyproject.toml`, Ruff, mypy e pytest.
- [x] Implementazione `Settings` e variabili d'ambiente.
- [x] Gestione schema SQLite locale.

### Milestone 2: Dominio e Persistenza Catalogo — COMPLETATA
- [x] Definizione dell'enum `AcquisitionStatus` (`not_requested`, `stored`, `retryable_error`, `terminal_error`).
- [x] Modelli ORM `Channel`, `Playlist`, `Video` e `TranscriptFile`.
- [x] Query avanzate di filtraggio video (`status`, `channel`, `playlist`, `after`, `before`, `limit`, `offset`).

### Milestone 3: Discovery Metadati e Client API — COMPLETATA
- [x] Risoluzione canali/playlist tramite YouTube Data API v3.
- [x] Discovery metadati video con early exit al primo elemento noto.
- [x] Registrazione video con stato iniziale `not_requested` senza chiamate all'estrattore di transcript.

### Milestone 4: Fetch Puntuale Trascrizioni e Filesystem — COMPLETATA
- [x] Download esplicito transcript tramite `yctm transcript fetch VIDEO_ID`.
- [x] Gerarchia fallback sottotitoli (manuali it/en -> ASR it/en).
- [x] Scrittura atomica file Markdown con frontmatter YAML e hash SHA-256.

### Milestone 5: Interfaccia CLI e Documentazione — COMPLETATA
- [x] CLI Typer organizzata per sottogruppi di comandi.
- [x] Deprecazione comandi legacy `sync` e `playlist-sync`.
- [x] Allineamento documentazione (`Spec.md`, `README.md`, `YCTM.1.md`, `AGENTS.md`).
