# Documento di Progettazione e Piano di Implementazione: YouTube Channel Transcript Monitor (YCTM)

Il presente documento definisce le specifiche architetturali e il piano di implementazione per lo sviluppo di YCTM. Il progetto è concepito come uno strumento a riga di comando (CLI) ad esecuzione manuale (on-demand), finalizzato all'estrazione e all'archiviazione incrementale delle trascrizioni di canali YouTube. L'obiettivo primario è l'alimentazione strutturata di una base di conoscenza per modelli linguistici (LLM Wiki), con particolare riferimento a domini rigorosi (come la finanza personale) in cui l'integrità del contesto rende inapplicabili le logiche di frammentazione del testo (chunking).

## 1. Architettura Generale del Sistema

Il sistema adotta un'architettura modulare priva di demoni in background. L'esecuzione è innescata esclusivamente da comandi impartiti dall'utente tramite CLI. I macro-componenti del sistema sono:

* **Modulo di Interfaccia CLI:** Gestisce i parametri di input, il routing dei comandi e l'output a terminale (stdout).
* **Modulo di Rilevamento (Discovery):** Interroga la YouTube Data API v3 per individuare i nuovi video, limitando le chiamate agli ultimi contenuti caricati e implementando una logica di interruzione anticipata (early exit) basata sullo stato locale.
* **Modulo di Estrazione:** Utilizza la libreria `youtube-transcript-api` per il recupero anonimo dei sottotitoli, applicando una rigorosa gerarchia di fallback linguistico.
* **Livello di Persistenza e Governance:** Si affida a SQLAlchemy con motore SQLite locale per mantenere l'inventario dei canali e l'audit trail dei video elaborati, garantendo la deduplicazione.
* **Sottosistema di Archiviazione:** Salva le trascrizioni su file system (in formato testo o Markdown) preservando l'unitarietà del documento per l'ingestione nella Wiki.

## 2. Modello Dati e Livello di Persistenza

Il database relazionale locale (SQLite) funge esclusivamente da registro di governance e macchina per la deduplicazione, evitando il sovraccarico di immagazzinare testo grezzo nei record. Si richiede l'implementazione del seguente schema tramite SQLAlchemy ORM.

### Entità `Channel`

Rappresenta il canale sorgente e i parametri di configurazione associati.

* `id` (String, Primary Key): Identificativo canonico del canale (Prefisso `UC...`).
* `handle` (String): Nome utente pubblico (es. `@NomeCanale`).
* `title` (String): Titolo descrittivo fornito dalle API.
* `uploads_playlist_id` (String): Identificativo della playlist automatica dei caricamenti (derivato dall'ID del canale sostituendo il prefisso `UC` con `UU`).

### Entità `Video`

Traccia i contenuti analizzati e collega le entità al file system locale.

* `id` (String, Primary Key): Identificativo canonico del video di YouTube.
* `channel_id` (String, Foreign Key): Collegamento all'entità `Channel`.
* `title` (String): Titolo del video.
* `published_at` (DateTime): Data e ora di pubblicazione.
* `extraction_date` (DateTime): Timestamp dell'avvenuta archiviazione locale.
* `storage_path` (String): Percorso assoluto o relativo del file contenente la trascrizione integrale.
* `language_code` (String): Lingua effettiva della trascrizione estratta (es. `it`, `en`).

## 3. Flussi Operativi e Logica di Sincronizzazione

Il sistema deve implementare due flussi di esecuzione principali.

### A. Registrazione Iniziale del Canale

Comando deputato all'aggiunta di una nuova fonte. L'agente dovrà implementare le seguenti operazioni:

1. Ricezione dell'identificativo o dell'URL del canale.
2. Invocazione della YouTube Data API v3 per ottenere il `Channel ID` univoco.
3. Calcolo algoritmico del `uploads_playlist_id`.
4. Inserimento del record nella tabella `Channel` (se non preesistente).

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


5. **Archiviazione Documentale:** Il testo acquisito non deve subire alcun processo di chunking. Deve essere unificato in un unico blocco testuale, corredato da frontmatter YAML con i metadati del video, e salvato su disco in formato Markdown in una directory predefinita. Il nome del file deve essere normalizzato (es. `{published_at}_{video_id}_{title}.md`).
6. **Commit dello Stato:** Inserimento del record in `Video` con il corrispondente `storage_path`. Le operazioni di salvataggio file e commit su DB devono essere gestite in un contesto transazionale per evitare disallineamenti in caso di errore I/O.

## 4. Gestione delle Eccezioni

L'agente implementatore deve prevedere blocchi `try/except` specifici per isolare e gestire le seguenti casistiche senza interrompere l'esecuzione complessiva del batch:

* `TranscriptsDisabled`: Il video non permette le trascrizioni. Il sistema deve generare un avviso a terminale e opzionalmente salvare un record con `storage_path` nullo o flag di salto.
* `NoTranscriptFound`: Trascrizione non ancora generata dai server di Google. Il video deve essere scartato nella run corrente, senza essere inserito in SQLite; verrà naturalmente rielaborato alla successiva sincronizzazione.
* Errori di Rete e Limiti di Quota HTTP 429: Implementazione di un blocco dell'esecuzione con messaggistica chiara verso l'utente, suggerendo l'uso opzionale di proxy tramite variabili d'ambiente.

## 5. Stack Tecnologico e Linee Guida per il Codice

L'agente dovrà generare il codice basandosi sulle seguenti librerie standard di settore, garantendo un approccio "clean code":

* **Interfaccia CLI:** `Typer` (fortemente consigliato per il parsing dei parametri basato su annotazioni di tipo) o `Click`.
* **Database e ORM:** `SQLAlchemy` 2.x (configurato per connettore `sqlite:///`).
* **Integrazione YouTube API:** `google-api-python-client` per l'interazione con gli endpoint ufficiali (lettura metadati).
* **Estrazione Testo:** `youtube-transcript-api`.
* **Gestione Configurazione:** `pydantic-settings` o `python-dotenv` per il caricamento delle credenziali API e dei percorsi di base delle directory.

Il codice dovrà presentare una chiara separazione degli strati di responsabilità (es. `cli.py` per l'interfaccia, `youtube_client.py` per le integrazioni esterne, `database.py` per i modelli SQLAlchemy, `core.py` per la logica di orchestrazione). Tutto il codice dovrà essere compatibile con le convenzioni moderne di Python (versione >= 3.10) e utilizzare rigorosamente la tipizzazione statica (type hints).



# YouTube Channel Transcript Monitor (YCTM) - Implementazione e Stack Tecnologico

Per l'implementazione del progetto YouTube Channel Transcript Monitor (YCTM) secondo i requisiti architetturali definiti (esecuzione on-demand, interfaccia a riga di comando, archiviazione incrementale su database relazionale e mantenimento dell'unitarietà del documento), è possibile riutilizzare un ecosistema specifico di librerie Python e trarre pattern di design da alcuni progetti open source esistenti.

Di seguito si individuano gli strumenti e i software da impiegare, suddivisi per livello architetturale.

### Librerie Python (Stack Tecnologico)

Queste librerie costituiscono le fondamenta del codice da sviluppare e devono essere integrate direttamente come dipendenze del progetto:

* **youtube-transcript-api**: Libreria fondamentale (manutenuta da *jdepoix*) per l'estrazione del payload testuale. Interagisce con gli endpoint interni del riproduttore web, bypassando i protocolli di autenticazione dell'API ufficiale di Google. Integra i metodi necessari per implementare la gerarchia di fallback linguistico (es. distinzione tra sottotitoli manuali e autogenerati).
* **google-api-python-client**: Client ufficiale necessario esclusivamente per il modulo di rilevamento (discovery). Verrà impiegato per interrogare la YouTube Data API v3, risolvere l'identificativo canonico del canale e recuperare la lista ordinata degli ultimi *N* video caricati tramite la playlist automatica "Uploads".
* **SQLAlchemy (versione 2.x)**: Strumento ORM (Object-Relational Mapping) per la gestione del livello di persistenza. Astre le query SQL e gestisce il database locale (SQLite), garantendo l'integrità referenziale tra i canali e i video scaricati e operando come motore di deduplicazione.
* **Typer**: Framework per la costruzione dell'interfaccia a riga di comando (CLI). Basato su Pydantic, sfrutta la tipizzazione statica di Python (type hints) per validare automaticamente i parametri di input e generare la documentazione di aiuto a terminale, risultando più moderno e conciso rispetto al tradizionale `argparse` o a `Click`.
* **pydantic-settings** (o in alternativa **python-dotenv**): Modulo per la gestione rigorosa delle configurazioni. Necessario per isolare le credenziali sensibili (chiavi API di Google) e i parametri di sistema (percorsi delle directory di archiviazione locale) all'interno di file `.env`.

### Progetti Open Source di Riferimento (Pattern e Logiche)

Sebbene il codice di YCTM debba essere scritto ex novo per garantire aderenza ai requisiti specifici, i seguenti progetti open source offrono logiche implementative e pattern architetturali da cui prelevare specifiche porzioni di codice:

* **ytfetcher**: Modello di riferimento primario per l'implementazione della CLI. Il progetto dimostra come strutturare in modo efficiente il passaggio dei parametri a riga di comando (incluso il parametro `max_results` per limitare il raggio d'azione agli ultimi caricamenti) e come esportare il testo preservandone l'unitarietà, senza forzare processi di chunking.
* **youtube-transcripts-get**: Costituisce il riferimento algoritmico per l'implementazione della sincronizzazione incrementale. La logica di questo progetto illustra l'interruzione anticipata (early exit) del ciclo di interrogazione: quando l'algoritmo incontra un identificativo già presente nel tracciamento locale, arresta immediatamente le chiamate di rete, ottimizzando i tempi di esecuzione e azzerando gli sprechi di quota API.
* **youtube-channel-transcript-downloader**: Utile come riferimento per le procedure di normalizzazione e archiviazione su file system. Mostra metodologie efficaci per la pulizia delle stringhe testuali (title sanitization) destinate ai nomi dei file e per il salvataggio dei documenti in formato "plain text" grezzo, essenziale per una successiva elaborazione (ingestion) pulita all'interno della LLM Wiki.