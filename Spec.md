# Specifica Architetturale: YouTube Channel Transcript Monitor (YCTM)

Il presente documento definisce le specifiche architetturali di YCTM, uno strumento a riga di comando (CLI) ad esecuzione manuale (on-demand), finalizzato all'estrazione e all'archiviazione incrementale delle trascrizioni di canali e playlist YouTube. L'obiettivo primario è l'alimentazione strutturata di una base di conoscenza per modelli linguistici (LLM Wiki), con particolare riferimento a domini rigorosi (come la finanza personale) in cui l'integrità del contesto rende inapplicabili le logiche di frammentazione del testo (chunking).

## 1. Architettura Generale del Sistema

Il sistema adotta un'architettura modulare priva di demoni in background. L'esecuzione è innescata esclusivamente da comandi impartiti dall'utente tramite CLI. I macro-componenti del sistema sono:

* **Modulo di Interfaccia CLI:** Gestisce i parametri di input, il routing dei comandi e l'output a terminale (stdout). Implementato con **Typer**.
* **Modulo di Configurazione:** Gestisce le variabili d'ambiente e il file `.env` tramite `pydantic-settings` (API key YouTube, percorsi database e trascrizioni, limite massimo risultati).
* **Modulo di Rilevamento (Discovery):** Interroga la YouTube Data API v3 tramite **httpx** per individuare i nuovi video da canali e playlist, limitando le chiamate agli ultimi N contenuti caricati e implementando una logica di interruzione anticipata (early exit) basata sullo stato locale.
* **Modulo di Estrazione:** Utilizza la libreria `youtube-transcript-api` per il recupero anonimo dei sottotitoli, applicando una rigorosa gerarchia di fallback linguistico (manuale IT → manuale EN → ASR IT → ASR EN). Include un delay di 2 secondi tra richieste consecutive per mitigare i blocchi IP.
* **Livello di Persistenza e Governance:** Si affida a SQLAlchemy 2.x con motore SQLite locale per mantenere l'inventario di canali e playlist, l'audit trail dei video elaborati e la macchina a stati di acquisizione, garantendo la deduplicazione.
* **Sottosistema di Archiviazione:** Salva le trascrizioni su file system in formato Markdown con frontmatter YAML, preservando l'unitarietà del documento per l'ingestione nella Wiki.

## 2. Modello Dati e Livello di Persistenza

Il database relazionale locale (SQLite) funge esclusivamente da registro di governance e macchina per la deduplicazione, evitando il sovraccarico di immagazzinare testo grezzo nei record. Si richiede l'implementazione del seguente schema tramite SQLAlchemy ORM.

### Entità `Channel`

Rappresenta il canale sorgente e i parametri di configurazione associati.

* `id` (String, Primary Key): Identificativo canonico del canale (Prefisso `UC...`).
* `handle` (String): Nome utente pubblico (es. `@NomeCanale`).
* `title` (String): Titolo descrittivo fornito dalle API.
* `uploads_playlist_id` (String): Identificativo della playlist automatica dei caricamenti (derivato dall'ID del canale sostituendo il prefisso `UC` con `UU`).

### Entità `Video`

Traccia i contenuti analizzati e il loro stato di acquisizione.

* `id` (String, Primary Key): Identificativo canonico del video di YouTube.
* `channel_id` (String, Foreign Key): Collegamento all'entità `Channel` (nullable per video da playlist di canali non registrati).
* `title` (String): Titolo del video.
* `published_at` (DateTime, nullable): Data e ora di pubblicazione.
* `status` (String, default `pending`): Stato di acquisizione (`pending`, `stored`, `retryable_error`, `terminal_error`).
* `attempt_count` (Integer, default 0): Numero di tentativi di estrazione effettuati.
* `last_attempt_at` (DateTime, nullable): Timestamp dell'ultimo tentativo.
* `last_error` (String, nullable): Messaggio di errore dell'ultimo tentativo fallito.

### Entità `TranscriptFile`

Memorizza la referenza al file di trascrizione archiviato su disco.

* `id` (Integer, Primary Key): Identificativo interno autoincrementale.
* `video_id` (String, Foreign Key, UNIQUE): Collegamento 1:1 all'entità `Video`.
* `storage_path` (String): Percorso del file `.md` contenente la trascrizione.
* `sha256` (String): Hash SHA-256 del file per verifica d'integrità.
* `language_code` (String): Lingua effettiva della trascrizione (es. `it`, `en`).
* `extracted_at` (DateTime): Timestamp di creazione del file.

### Entità `Playlist`

Rappresenta una playlist YouTube registrata per la sincronizzazione.

* `id` (String, Primary Key): Identificativo canonico della playlist (prefisso `PL...`).
* `title` (String): Titolo descrittivo della playlist.
* `channel_id` (String, Foreign Key, nullable): Collegamento opzionale all'entità `Channel` proprietario.

## 3. Macchina a Stati dei Video

Ogni video attraversa i seguenti stati durante il suo ciclo di vita:

```
        ┌──────────────────────────────────────────┐
        │                                          │
        ▼                                          │
    ┌─────────┐     tentativo (max 3)          ┌──────────────────┐
    │ pending ├────────────────────────────────►│ retryable_error  │
    └────┬────┘    fallimento                   └────────┬─────────┘
         │                                               │
         │ successo                           3 fallimenti│
         ▼                                               ▼
    ┌────────┐                                   ┌────────────────┐
    │ stored │ (terminale)                       │ terminal_error │ (terminale)
    └────────┘                                   └────────────────┘
```

* `pending`: In attesa di elaborazione.
* `stored`: Trascrizione acquisita con successo (**terminale**: attiva early exit).
* `retryable_error`: Errore temporaneo (blocco IP, trascrizione non ancora disponibile). Ritentato fino a 3 volte.
* `terminal_error`: Fallimento permanente dopo 3 tentativi, o trascrizioni disabilitate (**terminale**: attiva early exit).

## 4. Flussi Operativi e Logica di Sincronizzazione

Il sistema deve implementare i seguenti flussi di esecuzione.

### A. Registrazione Iniziale del Canale / Playlist

Comando deputato all'aggiunta di una nuova fonte. L'agente dovrà implementare le seguenti operazioni:

1. Ricezione dell'identificativo o dell'URL del canale.
2. Invocazione della YouTube Data API v3 per ottenere il `Channel ID` univoco.
3. Calcolo algoritmico del `uploads_playlist_id`.
4. Inserimento del record nella tabella `Channel` (se non preesistente).

La registrazione di una playlist segue lo stesso pattern: risoluzione dell'ID playlist da URL o input diretto, recupero dei metadati tramite YouTube Data API v3 (`/playlists`), inserimento nella tabella `Playlist`.

### B. Sincronizzazione Incrementale (Discovery e Download)

Comando di aggiornamento eseguito on-demand. L'algoritmo deve seguire rigorosamente questa sequenza per garantire l'elusione del rate-limiting e l'ottimizzazione del traffico:

1. **Inizializzazione:** Caricamento del limite di analisi `N` (parametro `max_results`, default raccomandato: 5).
2. **Rilevamento:** Interrogazione dell'endpoint `playlistItems` della YouTube Data API v3, puntando alla `uploads_playlist_id` del canale, recuperando al massimo `N` elementi ordinati per data di pubblicazione decrescente.
3. **Deduplicazione (Early Exit):** Iterazione sequenziale sui video recuperati. Se il `video_id` in esame è già presente nella tabella `Video`, il ciclo di rilevamento si interrompe immediatamente, assumendo che tutti i video storici successivi siano già stati analizzati (comportamento incrementale puro).
4. **Estrazione Trascrizione:** Per ogni nuovo `video_id` validato, invocazione di `youtube-transcript-api`. Il recupero deve seguire questa precisa gerarchia linguistica (fallback):
* Sottotitolo manuale primario (es. Italiano).
* Sottotitolo manuale secondario (es. Inglese).
* Sottotitolo generato automaticamente (ASR) primario.
* Sottotitolo generato automaticamente (ASR) secondario.


5. **Delay tra richieste:** Per mitigare i blocchi IP da parte di YouTube (l'endpoint `youtube-transcript-api` non è ufficiale), viene applicato un delay di **2 secondi** tra una richiesta di estrazione e la successiva, tramite struttura `try/except/else/finally` che garantisce l'esecuzione sia in caso di successo che di errore.
6. **Archiviazione Documentale:** Il testo acquisito non deve subire alcun processo di chunking. Deve essere unificato in un unico blocco testuale, corredato da frontmatter YAML con i metadati del video (canale, titolo, lingua, data, descrizione, URL sorgente), e salvato su disco in formato **Markdown** (`.md`) in una directory predefinita. Il nome del file segue la convenzione `{YYYYMMDD}_{video_id}_{titolo_sanificato}.md`.
7. **Commit dello Stato:** Inserimento del record in `Video` e `TranscriptFile`. Le operazioni di salvataggio file e commit su DB devono essere gestite in un contesto transazionale per evitare disallineamenti in caso di errore I/O (scrittura su file temporaneo, rinomina atomica, rollback compensativo in caso di fallimento DB).

### C. Sincronizzazione Playlist

Il comando `playlist-sync` segue la medesima logica di `sync`, operando sulla playlist specificata invece che sulla playlist Uploads del canale. I video scoperti condividono la tabella `videos` globale: se uno stesso video è già stato acquisito tramite un canale, non viene rielaborato.

### D. Modalità Interattiva

I comandi `sync` e `playlist-sync` supportano il flag `--interactive` (`-i`) che, dopo il discovery, mostra ogni video con autore, titolo e data e chiede conferma all'utente prima di scaricare la trascrizione. I video non confermati vengono saltati senza essere registrati nel database; ricompariranno alla prossima sincronizzazione.

### E. Reset dello Stato

Il comando `yctm reset` permette di reimpostare a `pending` i video in stato di errore:

* `yctm reset retryable` → resetta i video in `retryable_error`
* `yctm reset terminal` → resetta i video in `terminal_error`
* `yctm reset all` → resetta entrambi

## 5. Gestione delle Eccezioni

I blocchi `try/except` devono isolare e gestire le seguenti casistiche senza interrompere l'esecuzione complessiva del batch:

* `TranscriptsDisabled` (`youtube-transcript-api`): Trascrizioni permanentemente disabilitate. Il video viene marcato come `terminal_error` immediatamente.
* `NoTranscriptFound` (`youtube-transcript-api`): Trascrizione non ancora generata o blocco IP. Il video viene marcato come `retryable_error` e ritentato fino a 3 tentativi. Al terzo fallimento diventa `terminal_error`.
* Fallback linguistico assente: Nessuna trascrizione trovata in italiano o inglese. Marcato come `retryable_error`.
* Blocco IP: YouTube può bloccare l'IP per troppe richieste all'endpoint `youtube-transcript-api`. Il sistema applica un delay di 2 secondi tra le richieste. Se il blocco persiste, l'errore viene mappato come `retryable_error`. È possibile configurare un proxy via variabili d'ambiente `HTTP_PROXY` / `HTTPS_PROXY`.
* Quota API YouTube: La YouTube Data API v3 ha una quota giornaliera (default 10.000 unità). Il superamento durante il discovery interrompe immediatamente il batch senza creare record orfani.
* Errori di rete generici: Catturati come `TranscriptExtractionError`, vengono registrati e il video passa a `retryable_error`.

## 6. Stack Tecnologico e Linee Guida per il Codice

Il codice si basa sulle seguenti librerie standard di settore, con approccio "clean code":

* **Interfaccia CLI:** `Typer` (parsing dei parametri basato su annotazioni di tipo).
* **Database e ORM:** `SQLAlchemy` 2.x (connettore `sqlite:///`).
* **YouTube Data API v3:** `httpx` per le chiamate REST agli endpoint ufficiali Google (risoluzione canali/playlist, discovery playlistItems).
* **Estrazione Trascrizioni:** `youtube-transcript-api`.
* **Configurazione:** `pydantic-settings` per il caricamento di credenziali API e percorsi da ambiente o `.env`.

### Struttura del Pacchetto

```
src/yctm/
  cli/
    app.py                 Applicazione Typer e comandi
  config/
    settings.py            Settings da ambiente/.env
  domain/
    models.py              Tipi di dominio, stati ed errori
  application/
    channels.py            Registrazione canali
    playlists.py           Registrazione e sincronizzazione playlist
    synchronization.py     Discovery, retry e orchestrazione
    manifest.py            Proiezione del manifest JSONL
    reset.py               Reset stati di errore
  infrastructure/
    database/
      models.py            ORM SQLAlchemy
      session.py           Engine, sessioni e inizializzazione schema
      repositories.py      Persistenza canali, video, file e playlist
    youtube/
      data_api.py          Client HTTP YouTube Data API v3
      transcripts.py       Client e fallback youtube-transcript-api
    filesystem/
      transcripts.py       Nomi sicuri, scrittura atomica e hash SHA-256
tests/
  unit/                    Test con mock delle API esterne
```

### Comandi CLI Pubblici

| Comando | Descrizione |
|---------|------------|
| `init-db` | Inizializza il database SQLite |
| `channel` | Registra un canale YouTube |
| `sync` | Sincronizza le trascrizioni di un canale |
| `playlist` | Registra una playlist YouTube |
| `playlist-sync` | Sincronizza le trascrizioni di una playlist |
| `reset` | Reimposta a pending i video in errore |
| `manifest` | Rigenera il manifest JSONL |
