YCTM(1)                     YCTM Manual                    YCTM(1)



NOME
       yctm — YouTube Channel Transcript Monitor

SINTASSI
       yctm init-db [--verbose]
       yctm channel [--verbose] <identificativo>
       yctm sync [--verbose] [--max-results N] [--interactive] <channel-id>
       yctm playlist [--verbose] <identificativo>
       yctm playlist-sync [--verbose] [--max-results N] [--interactive] <playlist-id>
       yctm manifest [--verbose]

DESCRIZIONE
       YCTM e' uno strumento a riga di comando per l'acquisizione incrementale
       di trascrizioni da canali e playlist YouTube. Le trascrizioni vengono
       archiviate come documenti unitari su filesystem, senza subire processi
       di chunking o modifica del contenuto originale. Un database SQLite
       mantiene il registro di audit, la deduplicazione e la provenienza dei
       dati. Un manifest JSONL viene pubblicato per l'ingestione da parte di
       sistemi esterni (LLM Wiki).

       Il programma e' progettato per esecuzione on-demand e non introduce
       processi residenti, server o meccanismi di scheduling automatico.



COMANDI

   init-db
       Inizializza il database SQLite creando lo schema delle tabelle
       (channels, videos, transcript_files, playlists). Puo' essere eseguito
       piu' volte senza effetti collaterali.

       Opzioni:
           -v, --verbose   Output di logging dettagliato

   channel
       Registra un canale YouTube nel database locale. L'identificativo puo'
       essere:

           un ID canonico       UC...
           un handle            @nomecanale
           un URL completo      https://www.youtube.com/@nomecanale
                                https://www.youtube.com/channel/UC...

       Il comando interroga la YouTube Data API v3 per risolvere
       l'identificativo e recuperare i metadati del canale. Se il canale e'
       gia' presente, i metadati vengono aggiornati.

       Opzioni:
           -v, --verbose   Output di logging dettagliato

       Codici di uscita:
           0   Canale registrato correttamente
           2   Canale non trovato
           3   Errore API YouTube
           4   Quota API superata

   sync
       Sincronizza le trascrizioni degli ultimi video pubblicati da un canale
       gia' registrato. Il comando esegue il discovery sulla playlist
       automatica "Uploads" del canale, estrae le trascrizioni per ogni nuovo
       video e aggiorna il database. Al termine rigenera automaticamente il
       manifest JSONL.

       La sincronizzazione e' incrementale: se un video risulta gia' in stato
       terminale (stored o terminal_error), la scansione si interrompe
       anticipatamente assumendo che tutti i video precedenti siano gia' noti.

       La gerarchia di fallback per l'estrazione delle trascrizioni e':
           1. Sottotitoli manuali in italiano
           2. Sottotitoli manuali in inglese
           3. Sottotitoli ASR (automatici) in italiano
           4. Sottotitoli ASR (automatici) in inglese

       I video con trascrizioni disabilitate vengono marcati come
       terminal_error. I video con trascrizione non ancora disponibile vengono
       riprovati fino a 3 tentativi, dopodiche' passano a terminal_error.

       Argomenti:
           channel-id          ID del canale (UC...)

       Opzioni:
           --max-results N     Numero massimo di video da analizzare
           -i, --interactive   Chiede conferma prima di scaricare ogni
                               trascrizione (utile per selezionare solo
                               i video di interesse)
                               (default: valore da configurazione)
           -v, --verbose       Output di logging dettagliato

       Codici di uscita:
           0   Sincronizzazione completata
           2   Canale non registrato
           3   Errore API YouTube
           4   Quota API superata

   playlist
       Registra una playlist YouTube nel database locale. L'identificativo
       puo' essere:

           un ID playlist       PL...
           un URL completo      https://www.youtube.com/playlist?list=PL...

       Il comando interroga la YouTube Data API v3 per risolvere
       l'identificativo e recuperare i metadati della playlist.

       Opzioni:
           -v, --verbose   Output di logging dettagliato

       Codici di uscita:
           0   Playlist registrata correttamente
           2   Playlist non trovata
           3   Errore API YouTube
           4   Quota API superata

   playlist-sync
       Sincronizza le trascrizioni dei video appartenenti a una playlist gia'
       registrata. La logica di sincronizzazione e' identica a sync: discovery
       sulla playlist, estrazione delle trascrizioni con fallback linguistico,
       deduplicazione globale ed early exit. Al termine rigenera il manifest
       JSONL.

       I video scoperti da una playlist condividono la stessa tabella videos
       dei canali: se uno stesso video e' gia' stato acquisito tramite un
       canale, non viene rielaborato.

       Argomenti:
           playlist-id         ID della playlist (PL...)

       Opzioni:
           --max-results N     Numero massimo di video da analizzare
           -i, --interactive   Chiede conferma prima di scaricare ogni
                               trascrizione (utile per selezionare solo
                               i video di interesse)
                               (default: valore da configurazione)
           -v, --verbose       Output di logging dettagliato

       Codici di uscita:
           0   Sincronizzazione completata
           2   Playlist non registrata
           3   Errore API YouTube
           4   Quota API superata

   manifest
       Rigenera il file manifest.jsonl a partire dallo stato corrente del
       database e del filesystem. La scrittura e' atomica: il file viene
       creato come temporaneo nella stessa directory e poi rinominato.

       Opzioni:
           -v, --verbose   Output di logging dettagliato



STATO DI ACQUISIZIONE
       Ogni video nel database si trova in uno dei seguenti stati:

       pending             In attesa di elaborazione
       stored              Trascrizione acquisita e archiviata
       retryable_error     Errore temporaneo, sara' riprovato
       terminal_error      Errore permanente, non verra' riesaminato

       Un video in stato stored o terminal_error e' considerato terminale e
       interrompe la scansione incrementale (early exit).



FILE
       .env
           File di configurazione delle variabili d'ambiente.

       data/yctm.sqlite3
           Database SQLite contentente il registro di canali, playlist, video
           e file di trascrizione.

       data/transcripts/
           Directory contenente le trascrizioni in formato Markdown (.md). Ogni
           file include frontmatter YAML con i metadati del video. Il nome di
           ogni file e' composto da data, ID video e titolo sanificato.

       data/manifest.jsonl
           Manifest JSONL per l'integrazione con la LLM Wiki. Ogni riga e'
           un oggetto JSON con i campi: video_id, channel_id, title,
           published_at, status, last_error, storage_path, sha256,
           language_code, extracted_at.



VARIABILI D'AMBIENTE
       YCTM_YOUTUBE_API_KEY      (obbligatoria) Chiave API YouTube
       YCTM_DATABASE_PATH        Percorso del database SQLite
                                 (default: data/yctm.sqlite3)
       YCTM_TRANSCRIPTS_DIRECTORY Directory di destinazione trascrizioni
                                 (default: data/transcripts)
       YCTM_MANIFEST_PATH        Percorso del file manifest JSONL
                                 (default: data/manifest.jsonl)
       YCTM_MAX_RESULTS          Numero massimo di video per sincronizzazione
                                 (default: 5)



CODICI DI USCITA
       0   Successo
       2   Risorsa (canale/playlist) non trovata
       3   Errore generico API YouTube o di rete
       4   Quota API YouTube superata



NOTE
       Le chiamate alla YouTube Data API v3 consumano quote giornaliere.
       Si consiglia di mantenere il valore di max_results basso (5-10) e di
       eseguire la sincronizzazione periodicamente per distribuire il carico.

       Il progetto e' descritto in SPEC.md. Le regole operative per lo
       sviluppo sono definite in AGENTS.md.



VEDERE ANCHE
       SPEC.md
       AGENTS.md
       README.md



YCTM 0.1.0                      2026-07-12                      YCTM(1)
