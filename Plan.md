# YCTM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** realizzare una CLI Python che acquisisca incrementalmente trascrizioni YouTube, le conservi come fonti immutabili e pubblichi un manifest JSONL per il progetto LLM Wiki esterno.

**Architecture:** YCTM adotta livelli compatti: CLI, configurazione, dominio, casi d'uso e infrastruttura. Il database SQLite conserva esclusivamente stato, audit e provenienza; le trascrizioni originali risiedono nel filesystem; il manifest JSONL e' il contratto di integrazione con la LLM Wiki.

**Tech Stack:** Python 3.12+, Typer, pydantic-settings, SQLAlchemy 2.x, SQLite, httpx, youtube-transcript-api, pytest, Ruff, mypy.

## Vincoli globali

- Nessuna dipendenza LLM, prompt, trasformazione semantica o accesso diretto al database da parte della LLM Wiki.
- Nessun chunking o modifica del testo estratto.
- Configurazione solo mediante ambiente o `.env`; nessun segreto nel repository.
- Logging esclusivamente con `logging`; nessun `print()`.
- Test senza chiamate reali a YouTube.
- Nessun processo residente, server o schedulazione automatica.

## Architettura e pacchetto Python

```text
src/yctm/
  cli/
    app.py                 Applicazione Typer e comandi
  config/
    settings.py            Settings da ambiente/.env
  domain/
    models.py              Tipi di dominio, stati ed errori
  application/
    channels.py            Registrazione canali
    synchronization.py     Discovery, retry e orchestrazione
    manifest.py            Proiezione del manifest JSONL
  infrastructure/
    database/
      models.py            ORM SQLAlchemy
      session.py           Engine, sessioni e inizializzazione schema
      repositories.py      Persistenza canali, video e file
    youtube/
      data_api.py          Client HTTP della YouTube Data API v3
      transcripts.py       Client e fallback youtube-transcript-api
    filesystem/
      transcripts.py       Nomi sicuri, scrittura e hash dei file
      manifest.py          Pubblicazione atomica JSONL
tests/
  unit/
  integration/
```

Interfacce CLI pubbliche:

- `yctm init-db`
- `yctm channel add <channel-id-or-handle-or-url>`
- `yctm sync <channel-id> [--max-results N]`
- `yctm manifest rebuild`

Il comando `sync` produce un riepilogo tramite logging e codici di uscita coerenti: successo, errore di configurazione/input, errore recuperabile di sincronizzazione, limite quota.

## Modello dati e contratto di integrazione

- `Channel`: id canonico `UC...`, handle, titolo, `uploads_playlist_id`, timestamp di creazione e aggiornamento.
- `Video`: id YouTube, canale, titolo, data pubblicazione, stato (`pending`, `stored`, `retryable_error`, `terminal_error`), `attempt_count`, ultimo tentativo, ultimo errore e timestamp.
- `TranscriptFile`: id interno, video, percorso relativo, hash SHA-256, lingua, data di estrazione e timestamp. Esiste solo per una trascrizione archiviata con successo.
- `manifest.jsonl`: snapshot rigenerato atomicamente dopo una sincronizzazione o con `manifest rebuild`. Ogni riga descrive un video, il suo stato e, per `stored`, il file originale, hash, lingua e metadati di provenienza. Il consumatore LLM Wiki deve elaborare esclusivamente record `stored`.

La sincronizzazione considera noto un video in stato `stored` o `terminal_error`; per `pending` e `retryable_error` ripete l'estrazione fino a `attempt_count == 3`. Al terzo fallimento il video passa a `terminal_error`. Errori HTTP 429 interrompono il batch dopo il tracciamento del tentativo sul video corrente; errori di quota durante il discovery interrompono il batch senza creare record non identificabili.

## Dipendenze

Dipendenze applicative:

- `typer`
- `pydantic-settings`
- `sqlalchemy>=2`
- `httpx`
- `youtube-transcript-api`

Dipendenze di sviluppo:

- `pytest`
- `ruff`
- `mypy`
- `types-requests` solo se richiesto dalle annotazioni transitive

Non utilizzare `google-api-python-client`: la YouTube Data API v3 sara' invocata tramite `httpx`, gia' previsto dal progetto.

## Milestone e ordine delle attivita'

### Milestone 1: fondazioni del progetto - COMPLETATA

- [x] Creare `pyproject.toml`, pacchetto `src/yctm`, configurazione Ruff, mypy e pytest.
- [x] Implementare `Settings` per chiave YouTube, percorso SQLite, directory trascrizioni, percorso manifest e `max_results=5`.
- [x] Aggiungere `.env.example`, `.gitignore`, README iniziale e comando `init-db`.
- [x] Verificare installazione, `yctm --help` e creazione schema.

### Milestone 2: dominio e persistenza - COMPLETATA

- [x] Definire stati, eccezioni dedicate e tipi per risultato di discovery ed estrazione.
- [x] Implementare modelli ORM, vincoli di unicita', timestamp, session factory, repository e TranscriptFileRepository.
- [x] Testare deduplicazione canali/video, incrementi del contatore tentativi, transizioni di stato e assenza del testo nel database.
- [x] Eseguire commit: `feat: add domain and persistence layer`.

### Milestone 3: integrazioni YouTube e filesystem - COMPLETATA

- [x] Implementare risoluzione di ID canale e handle, calcolo dell'upload playlist e lettura degli ultimi N elementi tramite YouTube Data API.
- [x] Implementare fallback trascrizioni: manuale italiano, manuale inglese, ASR italiano, ASR inglese.
- [x] Mappare `TranscriptsDisabled`, `NoTranscriptFound`, errori HTTP e rete in eccezioni di dominio.
- [x] Implementare sanitizzazione del nome, scrittura temporanea, rinomina atomica e hash SHA-256.
- [x] Testare ogni client con `httpx.MockTransport` e sostituti di `youtube-transcript-api`.
- [x] Eseguire commit: `feat: add youtube and filesystem adapters`.

### Milestone 4: casi d'uso di registrazione e sincronizzazione - COMPLETATA

- [x] Implementare registrazione idempotente del canale.
- [x] Implementare discovery limitato, ordinato e con early exit al primo video terminale noto.
- [x] Applicare retry fino a tre tentativi per tutte le indisponibilita' o errori recuperabili su video identificati.
- [x] Coordinare file e database con compensazione: scrittura temporanea, persistenza, rinomina e rimozione del file in caso di rollback.
- [x] Testare batch con successi, video gia' noto, assenza trascrizione, trascrizioni disabilitate, errore di rete, terzo fallimento e HTTP 429.
- [x] Eseguire commit: `feat: implement incremental synchronization`.

### Milestone 5: manifest e CLI - COMPLETATA

- [x] Generare il manifest da SQLite e filesystem, in ordine deterministico, scrivendo un file temporaneo e sostituendo quello precedente atomicamente.
- [x] Collegare i casi d'uso ai comandi Typer e convertire eccezioni in logging e codici di uscita.
- [x] Documentare installazione, configurazione, comandi, struttura dei file, contratto JSONL e troubleshooting.
- [x] Testare CLI con filesystem temporaneo e manifest corretto per record `stored` e `terminal_error`.
- [x] Eseguire commit: `feat: publish manifest and cli commands`.

### Milestone 6: verifica finale - COMPLETATA

- [x] Eseguire `ruff check .`.
- [x] Eseguire `ruff format .`.
- [x] Eseguire `pytest`.
- [x] Eseguire `mypy .`.
- [x] Verificare manualmente `yctm init-db`, `yctm channel add`, `yctm sync` e `yctm manifest rebuild` con client simulati.
- [x] Eseguire commit: `docs: complete setup and usage guide`.

## Rischi tecnici e mitigazioni

- YouTube puo' modificare endpoint, quote o comportamento dei sottotitoli: isolare i client, usare timeout espliciti e test contrattuali simulati.
- `youtube-transcript-api` puo' subire limitazioni o blocchi: registrare esiti, consentire retry limitati e documentare le variabili proxy senza includere proxy nel codice.
- Database e filesystem non condividono una transazione atomica: usare file temporanei, rinomina atomica, rollback compensativo e registrare gli errori di pulizia.
- L'early exit presume ordine cronologico coerente della playlist Uploads: limitare la logica alla playlist ufficiale e testare l'ordinamento.
- Il manifest puo' essere letto durante una sincronizzazione: pubblicarlo soltanto tramite sostituzione atomica.
- I nomi video possono generare percorsi non validi: sanitizzare il titolo e rendere sempre univoco il nome con data e `video_id`.

## Assunzioni

- La LLM Wiki e' un progetto distinto e legge i record `stored` del manifest JSONL.
- Il testo delle trascrizioni e' una fonte originale immutabile; l'estrazione semantica e' esterna a YCTM.
- Gli URL supportati per l'aggiunta del canale sono ID `UC...`, handle `@...` e URL YouTube che li contengono.
- Non viene introdotto un sistema di migrazione database nella prima versione; lo schema viene creato da SQLAlchemy.
