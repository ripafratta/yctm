# Livello di Persistenza e Database (YCTM)

## Scopo

Questo documento è la fonte primaria per: lo schema del database SQLite, la descrizione delle entità relazionali, la gestione della relazione molti-a-molti, la macchina a stati ed i meccanismi di migrazione ed integrità.

Non contiene: la guida ai comandi CLI per il database (vedi [docs/cli-reference.md](cli-reference.md)) o le decisioni architetturali di alto livello (vedi [docs/architecture.md](architecture.md)).

Documenti correlati:
* [SPEC.md](../SPEC.md) — Requisiti funzionali normativi.
* [docs/architecture.md](architecture.md) — Architettura del software.
* [docs/adr/0003-playlist-video-many-to-many.md](adr/0003-playlist-video-many-to-many.md) — ADR sulla relazione N:M.

---

## 1. Modello Dati Relazionale

YCTM utilizza **SQLAlchemy 2.x** ed un database locale **SQLite** per la persistenza del catalogo. Il testo integrale dei transcript **non è memorizzato nel DB**, ma salvato su filesystem.

```text
┌─────────┐             ┌─────────────────┐             ┌──────────┐
│ Channel │─ ── ── ── ──│ playlist_videos │── ── ── ── ─│ Playlist │
└─────────┘             └─────────────────┘             └──────────┘
     │                           │                           │
     │ 1:N                       │ N:M                       │ 1:N
     ▼                           ▼                           │
┌──────────────────────────────────────────────────┐         │
│                      Video                       │◄────────┘
└──────────────────────────────────────────────────┘
                         │
                         │ 1:1
                         ▼
               ┌───────────────────┐
               │  TranscriptFile   │
               └───────────────────┘
```

---

## 2. Definizione delle Entità

### `Channel` (Tabella `channels`)
Rappresenta un canale YouTube registrato come fonte.
* `id` (String, Primary Key): Identificativo canonico (prefisso `UC...`).
* `handle` (String, nullable): Nome utente pubblico (es. `@NomeCanale`).
* `title` (String): Titolo del canale.
* `uploads_playlist_id` (String, Unique): ID della playlist dei caricamenti del canale (`UU...`).
* `created_at`, `updated_at` (DateTime).

### `Playlist` (Tabella `playlists`)
Rappresenta una playlist YouTube registrata come fonte.
* `id` (String, Primary Key): Identificativo canonico (prefisso `PL...`).
* `title` (String): Titolo della playlist.
* `channel_id` (String, Foreign Key, nullable): Canale proprietario, se identificabile.
* `created_at`, `updated_at` (DateTime).

### `Video` (Tabella `videos`)
Rappresenta un video scoperto o censito nel catalogo YCTM.
* `id` (String, Primary Key): ID del video YouTube (11 caratteri).
* `channel_id` (String, Foreign Key, nullable): Canale associato.
* `title` (String): Titolo del video.
* `description` (String, nullable): Descrizione completa.
* `published_at` (DateTime, nullable): Data di pubblicazione originale su YouTube.
* `discovered_at` (DateTime): Timestamp di iscrizione nel catalogo YCTM.
* `status` (String): Stato di acquisizione transcript (`not_requested`, `stored`, `retryable_error`, `terminal_error`).
* `attempt_count` (Integer): Numero di tentativi di fetch effettuati.
* `last_attempt_at` (DateTime, nullable): Timestamp dell'ultimo tentativo.
* `last_error` (String, nullable): Messaggio dell'ultimo errore tecnico registrato.
* `created_at`, `updated_at` (DateTime).

### `playlist_videos` (Tabella di Associazione N:M)
Gestisce la relazione molti-a-molti tra `Playlist` e `Video`.
* `playlist_id` (String, Foreign Key, Primary Key): ID della playlist (`PL...`).
* `video_id` (String, Foreign Key, Primary Key): ID del video.
* `added_at` (DateTime): Timestamp di associazione.

### `TranscriptFile` (Tabella `transcript_files`)
Mantiene il riferimento al file Markdown archiviato nel filesystem.
* `id` (Integer, Primary Key).
* `video_id` (String, Foreign Key, Unique): Relazione 1:1 con `Video`.
* `storage_path` (String): Percorso relativo o assoluto del file `.md`.
* `sha256` (String): Hash SHA-256 del contenuto del file Markdown.
* `language_code` (String): Codice lingua del transcript estratto (es. `it`, `en`).
* `extracted_at` (DateTime): Timestamp dell'avvenuta estrazione.

---

## 3. Macchina a Stati Tecnica del Transcript

Lo stato dell'entità `Video` traccia unicamente la gestione tecnica dell'acquisizione:

* `not_requested`: Stato iniziale. Video a catalogo, transcript non ancora richiesto.
* `stored`: Transcript salvato con successo su disco e registrato in DB.
* `retryable_error`: Fallimento temporaneo (rete/quota/timeout). Incrementa `attempt_count`.
* `terminal_error`: Fallimento permanente (sottotitoli disabilitati, non presenti o 3 tentativi falliti).

---

## 4. Migrazioni ed Upgrade dello Schema

Le migrazioni vengono gestite in modo leggero all'interno di `infrastructure/database/session.py` tramite la funzione `upgrade_database(engine)`. Ad ogni avvio o via `yctm db upgrade`, il sistema ispeziona lo schema SQLite ed applica le modifiche mancanti (es. creazione tabella `playlist_videos`, aggiunta colonne `description` o `discovered_at`).

---

## 5. Controllo di Integrità e Recovery

Per rilevare disallineamenti tra database e filesystem (ad esempio file cancellati manualmente o rimasti orfani), è disponibile il comando:

```bash
yctm doctor
```

Inoltre, durante l'esecuzione di `yctm transcript fetch`, se il salvataggio sul DB fallisce dopo la scrittura del file su disco, il sistema esegue una **compensazione immediata** cancellando il file orfano dal filesystem.
