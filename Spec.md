# Specifica Architetturale: YouTube Channel Transcript Monitor (YCTM)

Il presente documento definisce le specifiche architetturali di YCTM, uno strumento a riga di comando (CLI) ad esecuzione manuale (on-demand), finalizzato al discovery dei metadati da canali e playlist YouTube e all'estrazione puntuale delle trascrizioni.

YCTM è un **servizio locale, generico e neutrale di catalogazione delle fonti YouTube e di recupero controllato dei transcript**. Non conosce utilizzi editoriali, criteri di rilevanza né pubblica artefatti o manifest per i consumer esterni.

## 1. Architettura Generale del Sistema

Il sistema adotta un'architettura modulare priva di demoni in background. L'esecuzione è innescata esclusivamente da comandi impartiti dall'utente tramite CLI. I macro-componenti del sistema sono:

* **Modulo di Interfaccia CLI:** Gestisce i parametri di input, il routing dei comandi e l'output a terminale (stdout/stderr) in formato tabellare o JSON. Implementato con **Typer**.
* **Modulo di Configurazione:** Gestisce le variabili d'ambiente e il file `.env` tramite `pydantic-settings` (API key YouTube, percorsi database e trascrizioni, limite massimo risultati, delay).
* **Modulo di Rilevamento (Discovery):** Interroga la YouTube Data API v3 per individuare nuovi video da canali, playlist o video singoli. Salva e aggiorna i metadati (`title`, `description`, `published_at`, `discovered_at`) ponendo lo stato a `not_requested`. Non scarica mai i transcript.
* **Modulo di Estrazione (Transcript Fetch):** Scarica puntualmente su richiesta esplicita (`yctm transcript fetch VIDEO_ID`) il transcript per un video già censito nel catalogo locale, applicando una gerarchia di fallback linguistico (manuale IT → manuale EN → ASR IT → ASR EN).
* **Livello di Persistenza e Governance:** Si affida a SQLAlchemy 2.x con motore SQLite locale per mantenere l'inventario di canali, playlist, video catalogati e transcript scaricati.
* **Sottosistema di Archiviazione:** Salva le trascrizioni su filesystem in formato Markdown con frontmatter YAML, preservando l'unitarietà del documento.

## 2. Modello Dati e Livello di Persistenza

Il database relazionale locale (SQLite) funge da registro delle fonti e catalogo dei video scoperti.

### Entità `Channel`

* `id` (String, Primary Key): Identificativo canonico del canale (Prefisso `UC...`).
* `handle` (String, nullable): Nome utente pubblico (es. `@NomeCanale`).
* `title` (String): Titolo del canale.
* `uploads_playlist_id` (String, UNIQUE): Identificativo della playlist dei caricamenti del canale.
* `created_at`, `updated_at` (DateTime).

### Entità `Playlist`

* `id` (String, Primary Key): Identificativo canonico della playlist (prefisso `PL...`).
* `title` (String): Titolo della playlist.
* `channel_id` (String, Foreign Key, nullable): Collegamento al canale proprietario.
* `created_at`, `updated_at` (DateTime).

### Entità `Video`

* `id` (String, Primary Key): Identificativo del video YouTube.
* `channel_id` (String, Foreign Key, nullable): Canale associato.
* `title` (String): Titolo del video.
* `description` (String, nullable): Descrizione completa del video.
* `published_at` (DateTime, nullable): Data di pubblicazione su YouTube.
* `discovered_at` (DateTime): Timestamp di inserimento nel catalogo YCTM.
* `status` (String, default `not_requested`): Stato di acquisizione (`not_requested`, `stored`, `retryable_error`, `terminal_error`).
* `attempt_count` (Integer, default 0): Numero di tentativi di download effettuati.
* `last_attempt_at` (DateTime, nullable): Timestamp dell'ultimo tentativo.
* `last_error` (String, nullable): Messaggio dell'ultimo errore tecnico.
* `created_at`, `updated_at` (DateTime).

### Tabella di Associazione `playlist_videos`

* `playlist_id` (String, Foreign Key, Primary Key): Riferimento alla playlist.
* `video_id` (String, Foreign Key, Primary Key): Riferimento al video.
* `added_at` (DateTime): Timestamp di associazione.

### Entità `TranscriptFile`


* `id` (Integer, Primary Key).
* `video_id` (String, Foreign Key, UNIQUE): Relazione 1:1 con `Video`.
* `storage_path` (String): Percorso del file `.md`.
* `sha256` (String): Hash SHA-256 del file.
* `language_code` (String): Lingua del transcript (es. `it`, `en`).
* `extracted_at` (DateTime).

## 3. Macchina a Stati dei Video

Gli stati riguardano esclusivamente l'acquisizione tecnica del transcript:

* `not_requested`: Video scoperto nel catalogo, trascrizione non ancora richiesta.
* `stored`: Transcript estratto e archiviato con successo nel filesystem (terminale).
* `retryable_error`: Download richiesto ma fallito per errore temporaneo (es. rete).
* `terminal_error`: Download richiesto ma fallito definitivamente (trascrizioni disabilitate o tentativi esauriti) (terminale).

## 4. Flussi Operativi e CLI

### Discovery Metadati

I comandi `yctm discover channel`, `yctm discover playlist`, `yctm discover all` e `yctm video discover VIDEO_ID` chiamano la YouTube Data API v3 per censire i video con stato `not_requested`. Non effettuano alcuna chiamata all'estrattore di sottotitoli.

### Consultazione Catalogo

`yctm video list` mostra i video presenti nel catalogo con filtri (`--status`, `--channel`, `--playlist`, `--after`, `--before`, `--limit`, `--format table|json`).
`yctm video show VIDEO_ID` restituisce le informazioni dettagliate di un singolo video.

### Download Puntuale

`yctm transcript fetch VIDEO_ID` richiede l'estrazione del transcript per un video già presente nel catalogo locale. Se il video non è a catalogo, l'operazione viene rifiutata indicando di eseguire prima `yctm video discover VIDEO_ID`.

