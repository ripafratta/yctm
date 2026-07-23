YCTM(1)                     YCTM Manual                    YCTM(1)



NOME
       yctm — YouTube Source and Transcript Catalog

SINTASSI
       yctm init-db [--verbose]
       yctm db upgrade [--verbose]

       yctm channel add <identificativo>
       yctm channel list
       yctm channel remove <channel-id>

       yctm playlist add <identificativo>
       yctm playlist list
       yctm playlist remove <playlist-id>

       yctm discover channel <channel-id> [--max-results N] [--since YYYY-MM-DD] [--dry-run]
       yctm discover playlist <playlist-id> [--max-results N] [--dry-run]
       yctm discover all [--max-results N] [--dry-run]

       yctm video list [--status S] [--channel C] [--playlist P] [--after YYYY-MM-DD] [--before YYYY-MM-DD] [--limit N] [--offset N] [--format table|json] [--order published-desc|published-asc]
       yctm video show <video-id> [--format table|json]
       yctm video discover <video-id>

       yctm transcript fetch <video-id> [--cookies PATH]
       yctm transcript status <video-id> [--format table|json]
       yctm transcript reset [<video-id>] [--status S]
       yctm transcript retry <video-id> [--cookies PATH]

       yctm stats
       yctm auth [--no-browser]   [SPERIMENTALE]

DESCRIZIONE
       YCTM e' uno strumento a riga di comando (CLI) per la registrazione delle
       fonti YouTube (canali e playlist), il discovery dei metadati dei video e
       il recupero puntuale delle trascrizioni.

       YCTM e' un servizio locale, generico e neutrale: non gestisce concetti di
       Knowledge Base (KB), rilevanza editoriale o pubblicazione di manifest per
       consumer esterni.

       Il programma e' progettato per esecuzione on-demand e non introduce
       processi residenti, server o meccanismi di scheduling automatico.



COMANDI

   DATABASE
       init-db, db init
           Inizializza il database SQLite creando lo schema delle tabelle.

       db upgrade
           Esegue migrazioni leggere di schema su database SQLite preesistenti.

   FONTI CANALE
       channel add <identificativo>
           Registra un canale YouTube nel database locale (da ID UC..., handle @...
           o URL).

       channel list
           Elenca i canali registrati nel database.

       channel remove <channel-id>
           Rimuove un canale dal database.

   FONTI PLAYLIST
       playlist add <identificativo>
           Registra una playlist YouTube (da ID PL... o URL).

       playlist list
           Elenca le playlist registrate nel database.

       playlist remove <playlist-id>
           Rimuove una playlist dal database.

   DISCOVERY METADATI
       discover channel <channel-id>
           Interroga la YouTube Data API v3 ed esegue il discovery dei metadati
           video per un canale. Registra i nuovi video a catalogo con stato
           not_requested. Non effettua alcuna estrazione di transcript.

           Opzioni:
               --max-results N     Numero massimo di video (default da config)
               --since YYYY-MM-DD  Limita a video pubblicati da questa data
               --dry-run           Simula il discovery senza salvare a DB

       discover playlist <playlist-id>
           Esegue il discovery dei metadati per una playlist registrata.

       discover all
           Esegue il discovery sequenziale per tutti i canali e le playlist registrati.

   CONSULTAZIONE CATALOGO
       video list
           Elenca i video catalogati con filtri opzionali (--status, --channel,
           --playlist, --after, --before, --limit, --offset, --format table|json, --order).

       video show <video-id>
           Mostra le informazioni dettagliate di un singolo video (metadati, stato,
           dettagli file transcript se presente).

       video discover <video-id>
           Esegue il discovery puntuale di un singolo video da YouTube.

   TRASCRIZIONI
       transcript fetch <video-id>
           Scarica puntualmente il transcript per un video gia' presente nel catalogo
           locale. Se il video non e' a catalogo, rifiuta l'operazione richiedendo
           prima 'yctm video discover VIDEO_ID'.

       transcript status <video-id>
           Mostra lo stato tecnico dell'acquisizione per un video.

       transcript reset [<video-id>] [--status S]
           Reimposta a not_requested lo stato di un video o di tutti i video con lo
           stato specificato.

       transcript retry <video-id>
           Resetta e forza un nuovo tentativo di fetch per un video.

   UTILITY E MANUTENZIONE
       stats
           Mostra le statistiche aggregate sul catalogo e sull'operativita'.

       auth [SPERIMENTALE]
           Esegue l'autenticazione OAuth 2.0 per YouTube Data API.
           Nota: L'implementazione attiva delle trascrizioni usa youtube-transcript-api
           (scraping via innertube) e non necessita di OAuth. Auth e' mantenuto come
           riferimento sperimentale per eventuale uso futuro di captions.download.



STATO DI ACQUISIZIONE
       Ogni video nel database si trova in uno dei seguenti stati tecnici:

       not_requested       Video catalogato, nessun download del transcript richiesto
       stored              Transcript estratto e archiviato con successo (terminale)
       retryable_error     Download richiesto ma fallito per errore temporaneo
       terminal_error      Download richiesto ma fallito definitivamente (disabilitato/tentativi esauriti) (terminale)



FILE
       .env
           File di configurazione delle variabili d'ambiente.

       data/yctm.sqlite3
           Database SQLite contentente il catalogo di canali, playlist, video
           e file di trascrizione.

       data/transcripts/
           Directory contenente le trascrizioni in formato Markdown (.md). Ogni
           file include frontmatter YAML con i metadati del video.



VARIABILI D'AMBIENTE
       YCTM_YOUTUBE_API_KEY          (obbligatoria) Chiave API YouTube Data API v3
       YCTM_DATABASE_PATH            Percorso del database SQLite (default: data/yctm.sqlite3)
       YCTM_TRANSCRIPTS_DIRECTORY    Directory destinazione trascrizioni (default: data/transcripts)
       YCTM_MAX_RESULTS              Numero massimo di risultati per discovery (default: 5)
       YCTM_TRANSCRIPT_FETCH_DELAY   Delay in secondi tra tentativi transcript (default: 15)
       YCTM_COOKIES_PATH             Percorso opzionale del file cookie Netscape



CODICI DI USCITA
       0   Successo
       1   Errore nei parametri di input o generico
       2   Risorsa (canale/playlist/video) non trovata o non presente a catalogo
       3   Errore generico API YouTube o di rete
       4   Quota API YouTube superata



VEDERE ANCHE
       SPEC.md
       AGENTS.md
       README.md



YCTM 0.2.0                      2026-07-22                      YCTM(1)

