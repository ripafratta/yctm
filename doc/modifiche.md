
# Ottimo, ho solo alcune osservazioni:

1) A mio avviso yctm deve rimanere disaccoppiato dalle kb,  lui deve solo gestire le fonti e non i loro utilizzi, ogni kb avrà a disposizione i comandi per registrare le proprie fonti di interesse su yctm. Di conseguenza yctm non deve 'pubblicare' niente. Quindi non è necessario registrare il campo scope.
2) Per lo stesso motivo eviterei di salvare il campo review status, se la kb chiede la traduzione yctm la scaricherà, altrimenti non farà niente. L'unico stato è dato dall'elenco dei video già scoperti.
3) Eviterei di complicare troppo le cose con la gestione dei campi relevance e reason.
Insomma semplifichiamo u po' le cose secondo questa linea e mostrami un piano di implementazione.

Concordo con le tre correzioni: YCTM deve essere un **servizio locale, generico e neutrale** di catalogazione delle fonti YouTube e di recupero controllato dei transcript. Non deve conoscere KB, utilizzi editoriali, criteri di rilevanza né pubblicare artefatti per i consumer. Il codice attuale ha già buone basi per questa semplificazione — SQLite per stato/provenienza, filesystem per i documenti originali e livelli applicativi isolati dalla CLI.[^1]

## Contratto semplificato

YCTM gestisce esclusivamente:

1. Registrazione di canali e playlist.
2. Discovery incrementale dei metadati dei video.
3. Consultazione del catalogo locale.
4. Download puntuale e controllato di un transcript richiesto da un client umano o da una KB.
5. Persistenza del risultato tecnico dell’acquisizione.

Una KB resta esterna e può orchestrare il flusso in questo modo:

```text
KB registra una fonte su YCTM
            |
            v
KB chiede a YCTM i video scoperti
            |
            v
Agente / utente valuta titolo, descrizione e data
            |
            v
KB richiede a YCTM il transcript di video-ID
            |
            v
YCTM salva il documento originale e restituisce il riferimento
            |
            v
KB legge, sintetizza e indicizza autonomamente
```

Nessun campo `scope`, nessuna tabella di assegnazione KB-video, nessun punteggio e nessuna motivazione editoriale. Questa scelta rispetta anche il vincolo già dichiarato nel progetto: nessuna dipendenza LLM, prompt o accesso diretto della LLM Wiki al database di YCTM.[^1]

## Modello dati

La tabella `Video` diventa il catalogo centrale dei video scoperti. Ogni record nasce al discovery e persiste indipendentemente dal fatto che il transcript venga mai richiesto.


| Entità | Campi essenziali | Responsabilità |
| :-- | :-- | :-- |
| `Channel` | `id`, `handle`, `title`, `uploads_playlist_id`, timestamp | Fonte-canale registrata |
| `Playlist` | `id`, `title`, `channel_id`, timestamp | Fonte-playlist registrata |
| `Video` | `id`, `channel_id`, `title`, `description`, `published_at`, `discovered_at`, `updated_at` | Catalogo dei video |
| `TranscriptFile` | `video_id`, `storage_path`, `sha256`, `language_code`, `extracted_at` | Riferimento al transcript archiviato |
| `Acquisition` oppure campi su `Video` | `status`, `attempt_count`, `last_attempt_at`, `last_error` | Solo stato tecnico del download |

Il `status` deve riguardare **soltanto l’acquisizione**, non la valutazione del video:


| Stato | Significato |
| :-- | :-- |
| `not_requested` | Video scoperto; nessuno ha chiesto il transcript |
| `stored` | Transcript estratto e salvato correttamente |
| `retryable_error` | Download richiesto ma fallito per motivo temporaneo |
| `terminal_error` | Transcript non disponibile, disabilitato oppure fallimenti esauriti |

`pending` può essere eliminato, oppure mantenuto solamente se in futuro introdurrai una vera coda locale. Nel piano minimo non serve: il fetch è sincrono e puntuale, quindi un video passa direttamente da `not_requested` a `stored`, `retryable_error` o `terminal_error`.

Il modello attuale usa già stati, contatore di tentativi, ultimo errore e un’entità `TranscriptFile` separata; l’evoluzione consiste principalmente nell’aggiungere `not_requested`, nello smettere di associare “video scoperto” a “video da estrarre”, e nel persistere titolo, descrizione e data durante il discovery.[^1]

## CLI proposta

I comandi devono riflettere le operazioni reali, senza concetti KB.

### Gestione fonti

```bash
yctm channel add @Fireship
yctm playlist add "https://www.youtube.com/playlist?list=..."
yctm channel list
yctm playlist list
yctm channel remove UCxxxxxxxx
yctm playlist remove PLxxxxxxxx
```

Canali e playlist restano fonti autonome. Una KB, un agente o uno script può registrarli quando serve, ma YCTM non sa chi ha effettuato la registrazione o per quale scopo.

### Discovery metadati

```bash
yctm discover channel UCxxxxxxxx
yctm discover playlist PLxxxxxxxx
yctm discover all
```

`discover` chiama solo la YouTube Data API, registra i video nuovi e aggiorna il catalogo; non tenta mai di scaricare caption o transcript. Per la playlist Uploads di un canale, `playlistItems.list` ha un costo di quota di 1 unità per chiamata, quindi il discovery è significativamente meno invasivo del fetch dei transcript.[^2][^3]

Opzioni suggerite:

```bash
yctm discover channel UCxxxxxxxx --max-results 25
yctm discover channel UCxxxxxxxx --since 2026-07-01
yctm discover all --max-results 20
yctm discover all --dry-run
```

`--since` è un filtro aggiuntivo utile, ma non sostituisce la deduplicazione per `video_id`: il controllo dell’identificativo rimane il criterio affidabile per evitare record duplicati.

### Consultazione catalogo

```bash
yctm video list
yctm video list --channel UCxxxxxxxx
yctm video list --playlist PLxxxxxxxx
yctm video list --after 2026-07-01
yctm video list --status not-requested
yctm video list --status stored
yctm video show VIDEO_ID
```

`video list` deve produrre una tabella breve e leggibile:

```text
VIDEO_ID       DATA        CANALE             TITOLO                         TRANSCRIPT
b7DQyS1yFCU    2026-07-12  Vito Lops          Mercati al bivio...            not-requested
h4Pq2KmLx8V    2026-07-11  Fireship           New AI tools explained         stored
```

`video show VIDEO_ID` restituisce i dati completi disponibili localmente: autore, data, titolo, URL, descrizione, playlist eventualmente di origine e stato tecnico del transcript. La Data API definisce `snippet` come sede dei dettagli base del video, inclusi titolo, descrizione e data di pubblicazione.[^4]

### Download esplicito

```bash
yctm transcript fetch VIDEO_ID
yctm transcript fetch VIDEO_ID --language it,en
yctm transcript fetch VIDEO_ID --cookies ~/.config/yctm/youtube-cookies.txt
yctm transcript retry VIDEO_ID
```

`transcript fetch` deve funzionare solo per un video già presente nel catalogo. Se la KB propone un URL o un ID sconosciuto, deve prima fare discovery mirato:

```bash
yctm video discover VIDEO_ID
yctm transcript fetch VIDEO_ID
```

Questa regola evita che il comando di download diventi un secondo canale opaco di discovery e mantiene la provenienza completa nel catalogo.

### Ispezione e manutenzione

```bash
yctm transcript status VIDEO_ID
yctm transcript reset VIDEO_ID
yctm transcript reset --status retryable-error
yctm stats
```

Lo script di manutenzione già presente effettua statistiche e reset degli errori; la sua logica può essere portata nella CLI Typer per offrire una sola interfaccia pubblica coerente.[^1]

## Rimozioni deliberate

Per mantenere YCTM essenziale, escluderei esplicitamente:

- `scope`, `knowledge_base_id`, `source_subscription` e tutte le relazioni con una KB.
- `review_status`, inbox, selezione, scarto, deferimento e code editoriali.
- `relevance_score`, keyword rules, LLM triage, tag o note.
- Manifest JSONL ed export dedicati alle KB.
- Scheduler, processi residenti, web UI e job automatici.
- Fetch batch automatico di tutti i video scoperti.

La separazione rende YCTM riutilizzabile anche fuori dalle LLM Wiki: da CLI, da script Python, da agenti locali o da futuri servizi, senza imporre un flusso editoriale. Il progetto già dichiara come obiettivi semplicità operativa e assenza di componenti server o scheduling; il piano proposto li rafforza.[^1]

## Piano implementativo

### Fase 0 — Aggiornare la specifica

- [ ] Riscrivere `SPEC.md` e `Plan.md`: YCTM è “YouTube Source and Transcript Catalog”, non un monitor che sincronizza automaticamente transcript.
- [ ] Aggiornare `AGENTS.md`: la sincronizzazione si divide in discovery e fetch esplicito.
- [ ] Definire il contratto: YCTM non contiene logica KB/LLM e non genera manifest.
- [ ] Dichiarare `sync` e `playlist-sync` come comandi deprecati durante la migrazione.

**Risultato:** l’implementazione futura ha un confine funzionale netto e non reintroduce concetti editoriali per errore. Il repository possiede già specifica, piano e linee guida architetturali che vanno mantenuti coerenti con il nuovo comportamento.[^1]

### Fase 1 — Evolvere schema e dominio

- [ ] Aggiungere `description` e `discovered_at` a `Video`.
- [ ] Aggiungere il valore `NOT_REQUESTED` a `AcquisitionStatus`.
- [ ] Impostare questo valore come default per ogni video creato dal discovery.
- [ ] Conservare `stored`, `retryable_error`, `terminal_error`, `attempt_count` e `last_error`.
- [ ] Decidere se `pending` viene rimosso subito o mantenuto temporaneamente per compatibilità.
- [ ] Aggiungere una migrazione SQLite leggera/versionata oppure un comando `yctm db upgrade`.

**Risultato:** ogni video esiste nel catalogo prima di essere candidato o meno al recupero. Attualmente il database è generato da SQLAlchemy senza un sistema di migrazioni, quindi introdurre un upgrade esplicito è importante per non costringerti a ricreare `yctm.sqlite3` a ogni modifica di schema.[^1]

### Fase 2 — Separare discovery e fetch

- [ ] Estrarre da `synchronization.py` una funzione/caso d’uso `discover_channel`.
- [ ] Estrarre il caso d’uso analogo `discover_playlist`.
- [ ] Nel discovery: chiamare Data API, upsertare i metadati e fermarsi al primo `video_id` noto quando l’ordine è affidabile.
- [ ] Non invocare `extract_transcript` in alcun percorso `discover`.
- [ ] Creare `fetch_transcript(video_id)` come caso d’uso separato.
- [ ] Rifiutare il fetch per video sconosciuti, con messaggio che indichi `yctm video discover VIDEO_ID`.

**Risultato:** puoi aggiornare il catalogo di tutte le fonti senza eseguire nemmeno una chiamata agli endpoint delle trascrizioni. Il client Data API e il client `youtube-transcript-api` sono già separati in moduli infrastrutturali differenti, perciò il refactoring è circoscritto soprattutto all’orchestrazione applicativa.[^1]

### Fase 3 — Comandi catalogo

- [ ] Aggiungere il gruppo `yctm discover`.
- [ ] Aggiungere `yctm video list`.
- [ ] Aggiungere `yctm video show VIDEO_ID`.
- [ ] Aggiungere `yctm video discover VIDEO_ID` per il singolo video.
- [ ] Aggiungere filtri `--channel`, `--playlist`, `--after`, `--before`, `--status`, `--limit`.
- [ ] Rendere la visualizzazione testuale la modalità standard; prevedere opzionalmente `--format json` per le KB/agenti.

**Risultato:** la KB può interrogare YCTM per decidere autonomamente, senza richiedere al tool alcuna nozione di “interesse”.

### Fase 4 — Comandi transcript

- [ ] Aggiungere il gruppo `yctm transcript`.
- [ ] Implementare `fetch VIDEO_ID`.
- [ ] Implementare `status VIDEO_ID`.
- [ ] Implementare `reset VIDEO_ID` e `reset --status retryable-error`.
- [ ] Spostare nella CLI la funzione `stats` dello script di manutenzione.
- [ ] Conservare la gerarchia attuale di fallback: sottotitoli manuali in italiano, manuali inglesi, ASR italiano, ASR inglese.[^1]

**Risultato:** una KB richiede esattamente un testo, YCTM esegue al massimo quell’acquisizione e restituisce uno stato tecnico verificabile.

### Fase 5 — Protezioni anti-blocco

- [ ] Rendere il fetch esclusivamente singolo nella prima release.
- [ ] Aggiungere `--delay` configurabile e jitter casuale leggero.
- [ ] Interrompere immediatamente al primo 429/blocco IP, senza effettuare retry nel medesimo processo.
- [ ] Persistire errore e timestamp dell’ultimo tentativo.
- [ ] Usare retry solo su invocazione successiva e con un limite totale configurabile.
- [ ] Conservare il supporto opzionale per proxy e cookie come configurazione esterna, senza automatizzare rotazioni o aggiramenti.

**Risultato:** il rischio viene controllato all’origine: non esistono più batch di fetch involontari. Il repository documenta già che il recupero transcript può causare blocchi IP e che il delay è solo una mitigazione; un fetch puntuale è una protezione più strutturale.[^1]

### Fase 6 — Deprecazione e pulizia

- [ ] Modificare `yctm sync` affinché emetta un avviso di deprecazione.
- [ ] Per una release di transizione, farlo equivalere a `discover channel`, senza download automatico.
- [ ] Rimuovere `--interactive`: non ha più ragione di esistere se il fetch è sempre una decisione esplicita e atomica.
- [ ] Rimuovere `manifest rebuild`, `application/manifest.py`, `infrastructure/filesystem/manifest.py` e l’impostazione `manifest_path`.
- [ ] Rimuovere o riscrivere `scripts/syncall.py` come `discover_all.py`, con solo discovery sequenziale.
- [ ] Aggiornare README, `.env.example`, skill operative e tutti gli esempi.

**Risultato:** la superficie pubblica è più piccola e coerente; nessun vecchio comando può scaricare accidentalmente transcript in massa. L’attuale manifest è una proiezione del database che include stato e path dei file, ma, secondo il nuovo confine deciso, quell’esportazione deve appartenere al client/alla KB, non a YCTM.[^1]

### Fase 7 — Test e qualità

- [ ] Test di discovery: crea record `not_requested`, salva descrizione, deduplica per video ID e non chiama l’estrattore.
- [ ] Test di fetch: salva un transcript solo su richiesta esplicita.
- [ ] Test di fetch su video sconosciuto: errore chiaro e nessuna chiamata esterna.
- [ ] Test stati: successo, transcript disabilitato, non disponibile, errore di rete e reset.
- [ ] Test CLI: help, filtri di `video list`, output JSON e comandi deprecati.
- [ ] Aggiornare i test di schema, repository e CLI già esistenti.
- [ ] Eseguire `ruff check .`, `ruff format .`, `pytest` e `mypy .`, come richiesto dalle linee guida del repository.[^1]


## Flusso risultante

```bash
# Una KB registra le fonti che vuole rendere disponibili
yctm channel add @TwoMinutePapers
yctm playlist add "https://www.youtube.com/playlist?list=PL..."

# Quando serve, aggiorna soltanto il catalogo locale
yctm discover all --max-results 20

# L'agente della KB consulta e valuta esternamente
yctm video list --channel UC... --status not-requested --format json
yctm video show b7DQyS1yFCU --format json

# Soltanto dopo la decisione esterna
yctm transcript fetch b7DQyS1yFCU

# La KB individua il file tramite una query puntuale
yctm transcript status b7DQyS1yFCU --format json
```

L’unico punto da definire prima dell’implementazione è il comportamento di `yctm video list`: vuoi che per default mostri **tutti** i video catalogati, oppure soltanto quelli senza transcript (`not_requested`), che probabilmente è la vista operativa più utile?

Perfetto: `yctm video list` mostrerà **tutti i video per default**, mentre `--status not-requested` offrirà la vista operativa dei video catalogati il cui transcript non è mai stato richiesto. Così hai una CLI utile sia per l’inventario generale sia per il triage della singola KB, senza introdurre alcuna logica KB in YCTM. 

## Comportamento definitivo

```bash
# Catalogo completo, ordinato dal più recente
yctm video list

# Solo video scoperti ma mai richiesti
yctm video list --status not-requested

# Video già ottenuti
yctm video list --status stored

# Errori da riesaminare
yctm video list --status retryable-error
yctm video list --status terminal-error
```

Il default “tutti” è importante per trasparenza e manutenzione: permette di verificare il catalogo, individuare duplicati o fonti inattive e conoscere lo storico delle trascrizioni archiviate. Il filtro `not-requested` è invece la vista che una KB o un suo agente useranno normalmente per valutare nuovi candidati.

## Interfaccia prevista

```bash
yctm video list [OPTIONS]
```

| Opzione | Default | Effetto |
|---|---:|---|
| `--status` | tutti | Filtra per stato tecnico |
| `--channel CHANNEL_ID` | tutti | Limita a un canale |
| `--playlist PLAYLIST_ID` | tutte | Limita a una playlist |
| `--after YYYY-MM-DD` | nessuno | Video pubblicati da una data |
| `--before YYYY-MM-DD` | nessuno | Video pubblicati fino a una data |
| `--limit N` | 50 | Limita il numero di righe |
| `--offset N` | 0 | Paginazione locale |
| `--format table\|json` | `table` | Output per umano o agente |
| `--order published-desc\|published-asc` | `published-desc` | Ordinamento |

Esempi:

```bash
# Gli ultimi video non ancora acquisiti di un canale
yctm video list \
  --channel UCxxxxxxxx \
  --status not-requested \
  --limit 20

# Input strutturato per un agente esterno
yctm video list \
  --status not-requested \
  --after 2026-07-01 \
  --format json

# Storico completo di una fonte
yctm video list --playlist PLxxxxxxxx --limit 100
```

`--format json` non è una pubblicazione né un contratto con le KB: è il normale output strutturato di una CLI, utile a qualunque consumer esterno. L’attuale progetto usa Typer, SQLAlchemy e SQLite e già separa CLI, casi d’uso e repository, quindi questa estensione si inserisce senza cambiare il confine architetturale deciso. 

## Semantica degli stati

La lista completa include i soli stati tecnici di acquisizione:

```text
not-requested     Video catalogato, nessun download richiesto
stored            Transcript disponibile nel filesystem
retryable-error   Download richiesto ma fallito temporaneamente
terminal-error    Transcript indisponibile o tentativi esauriti
```

Non ci saranno `scope`, `review_status`, ranking, motivazioni o riferimenti a una KB. Il database continuerà a contenere metadati, deduplicazione, audit tecnico e riferimenti ai file, senza archiviare il testo completo delle trascrizioni. [

## Output tabellare

La tabella deve privilegiare la scansione rapida, non contenere la descrizione completa:

```text
VIDEO_ID       PUBBLICATO   CANALE             TITOLO                              STATO
b7DQyS1yFCU    2026-07-12   Vito Lops          Mercati al bivio: rimbalzo tech…   not-requested
h4Pq2KmLx8V    2026-07-11   Fireship           New AI tools explained              stored
```

La descrizione completa, l’URL YouTube, l’eventuale file transcript, lingua, hash e dati di errore restano disponibili mediante:

```bash
yctm video show b7DQyS1yFCU
yctm video show b7DQyS1yFCU --format json
```

Questa separazione mantiene `list` veloce e leggibile e consente all’agente di una KB di recuperare i dettagli solo per i video che vuole effettivamente valutare.

