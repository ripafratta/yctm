---
name: yctm
description: "Advanced operations for YouTube Channel Transcript Monitor (YCTM). Use this skill to perform batch discovery, database maintenance, proxy rotation, and manage the full catalog lifecycle."
---

# YCTM Operations Skill

## Scopo

Questo documento è la fonte primaria per: le istruzioni operative, i prerequisiti ed il workflow sintetico per gli agenti che utilizzano l'applicazione YCTM.

Non contiene: la specifica normativa dei requisiti (vedi [SPEC.md](SPEC.md)) o i dettagli architetturali del sistema (vedi [docs/architecture.md](../../docs/architecture.md)).

Documenti correlati:
* [SPEC.md](SPEC.md) — Requisiti funzionali normativi.
* [docs/troubleshooting.md](../../docs/troubleshooting.md) — Risoluzione dei problemi ed errori.

---

## 1. Architettura e Flusso Operativo


YCTM si basa sul principio della **separazione tra metadati (SQLite) e contenuti (filesystem)**. Le trascrizioni sono salvate come file Markdown con frontmatter YAML, mai dentro il database.

### Flusso a Tre Fasi

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ 1. REGISTRA │───▶│ 2. DISCOVER  │───▶│ 3. TRANSCRIPT │
│ fonti       │    │    metadati  │    │    fetch      │
│ (canali &   │    │    (Data API)│    │    (innertube)│
│  playlist)  │    │              │    │               │
└─────────────┘    └──────────────┘    └───────────────┘
```

Ogni fase è un comando CLI distinto: YCTM non ha demone residente né scheduler automatico.

### Stati di Acquisizione

| Stato | Significato | Terminale |
|---|---|---|
| `not_requested` | Video catalogato, nessun fetch richiesto | No |
| `stored` | Transcript estratto e archiviato | **Sì** |
| `retryable_error` | Fetch fallito per errore temporaneo | No |
| `terminal_error` | Fetch fallito definitivamente (tentativi esauriti o trascrizioni disabilitate) | **Sì** |

---

## 2. Comandi Operativi

Tutti i comandi supportano `--verbose` / `-v` per log dettagliati.

### Database

```bash
yctm init-db              # Inizializza lo schema SQLite
yctm db init              # Alias di init-db
yctm db upgrade           # Migrazioni leggere su DB preesistente
```

### Gestione Fonti

```bash
yctm channel add "https://www.youtube.com/@canale"   # Da ID UC..., handle @... o URL
yctm channel list
yctm channel remove UC...

yctm playlist add "https://youtube.com/playlist?list=PL..."
yctm playlist list
yctm playlist remove PL...
```

### Discovery Metadati (YouTube Data API v3)

Non scarica trascrizioni — solo registrazione metadati a catalogo.

```bash
yctm discover channel UC... [--max-results 25] [--since 2025-01-01] [--dry-run]
yctm discover playlist PL... [--max-results 25] [--dry-run]
yctm discover all [--max-results 25] [--dry-run]
```

`--since` è disponibile solo per canali. `--dry-run` simula senza scrivere su DB.

### Consultazione Catalogo

```bash
yctm video list [--status not_requested|stored|retryable_error|terminal_error]
               [--channel UC...] [--playlist PL...]
               [--after 2025-01-01] [--before 2025-06-30]
               [--limit 50] [--offset 0] [--format table|json]
               [--order published-desc|published-asc]

yctm video show VIDEO_ID [--format table|json]
yctm video discover VIDEO_ID    # Discovery puntuale di un singolo video
```

### Operazioni sulle Trascrizioni

```bash
yctm transcript fetch VIDEO_ID     # Scarica transcript (richiede video a catalogo)
yctm transcript status VIDEO_ID    # Stato tecnico dell'acquisizione
yctm transcript reset VIDEO_ID     # Reimposta a not_requested (singolo video)
yctm transcript reset --status retryable_error   # Reset massivo per stato
yctm transcript retry VIDEO_ID     # Reset + fetch in un comando
```

`--cookies PATH` opzionale per `fetch` e `retry` (file Netscape per autenticare le richieste innertube).

### Utility

```bash
yctm stats       # Statistiche del catalogo
```

---

## 3. Mitigazione del Rate-Limiting e Proxy

YCTM usa `youtube-transcript-api` (scraping innertube) per le trascrizioni — non richiede API key ma interroga direttamente gli endpoint web di YouTube, esponendo l'IP a blocchi temporanei.

### Delay Integrato

Delay configurabile tra richieste nella variabile `YCTM_TRANSCRIPT_FETCH_DELAY` (default: 15 secondi).

### Cookie Netscape

Per ridurre il rischio di blocchi, esporta i cookie da una sessione YouTube autenticata:

```bash
# Esporta i cookie dal browser in formato Netscape
# Chrome: estensione "Get cookies.txt" o "cookies.txt export"
# Firefox: estensione "cookies.txt"

# Puntali in .env
YCTM_COOKIES_PATH=data/cookies.txt

# Oppure passali al volo
yctm transcript fetch VIDEO_ID --cookies data/cookies.txt
```

### Proxy

YCTM rispetta le variabili d'ambiente standard per proxy HTTP/S:

```bash
export HTTP_PROXY="http://<user>:<pass>@proxy.example.com:8080"
export HTTPS_PROXY="http://<user>:<pass>@proxy.example.com:8080"
yctm transcript fetch VIDEO_ID
```

---

## 4. Workflow Batch e Manutenzione

Per pipeline di ingestione automatizzata o manutenzione programmata da parte di agenti:

1. **Aggiornamento Catalogo:** Usare `yctm discover all` per censire in sequenza i nuovi video da tutte le fonti configurate (canali e playlist).
2. **Verifica Stato:** Controllare la consistenza e il volume di video pendenti/archiviati tramite `yctm stats`.
3. **Gestione Errori e Ripristino:** 
   - Non modificare mai direttamente il database SQLite.
   - Reimpostare i tentativi falliti per errori transitori con `yctm transcript reset --status retryable_error`.
   - Se necessario forzare la rielaborazione di errori permanenti, usare `yctm transcript reset --status terminal_error`.
4. **Fetch Sequenziale:** Iterare sui video a catalogo con stato `not_requested` eseguendo `yctm transcript fetch <VIDEO_ID>` rispettando il delay configurato.

---

## 5. Codici di Uscita CLI

| Codice | Significato |
|---|---|
| 0 | Successo |
| 1 | Errore nei parametri di input o generico |
| 2 | Risorsa non trovata o non presente a catalogo |
| 3 | Errore generico API YouTube o di rete |
| 4 | Quota API YouTube superata |

---

## 6. Variabili d'Ambiente

| Variabile | Obbligatoria | Default | Descrizione |
|---|---|---|---|
| `YCTM_YOUTUBE_API_KEY` | **Sì** | — | Chiave YouTube Data API v3 |
| `YCTM_DATABASE_PATH` | No | `data/yctm.sqlite3` | Percorso del database |
| `YCTM_TRANSCRIPTS_DIRECTORY` | No | `data/transcripts` | Directory delle trascrizioni |
| `YCTM_MAX_RESULTS` | No | `5` | Max risultati per discovery |
| `YCTM_TRANSCRIPT_FETCH_DELAY` | No | `15` | Delay in secondi tra fetch |
| `YCTM_COOKIES_PATH` | No | — | File cookie Netscape (per innertube) |

---

## 7. Formato delle Trascrizioni

Ogni trascrizione è un file Markdown con frontmatter YAML:

```markdown
---
title: "Titolo del video"
video_id: abc123...
channel_id: UC...
channel_title: "Nome canale"
channel_handle: "@handle"
published_at: 2026-07-12T07:31:46
extracted_at: 2026-07-12T20:20:23
language: it
source: "https://www.youtube.com/watch?v=abc123..."
description: |
  Descrizione del video...
---

[testo della trascrizione...]
```

Convenzione di naming: `{YYYYMMDD}_{video_id}_{titolo_sanificato}.md`.

---



# Manuale di Riferimento della CLI (YCTM)

---

## Opzioni Globali

Ogni comando YCTM accetta la seguente opzione globale:

* `--verbose`, `-v`: Attiva il logging dettagliato su console (livello `DEBUG`).

---

## 1. Gestione Database (`yctm init-db` / `yctm db`)

### `yctm init-db` / `yctm db init`
Inizializza lo schema del database SQLite. Se il file non esiste, viene creato assieme alle relative tabelle.

```bash
yctm init-db
yctm db init
```

### `yctm db upgrade`
Applica migrazioni leggere di schema per aggiornare database SQLite preesistenti ad una versione più recente (es. aggiunta tabelle/colonne).

```bash
yctm db upgrade
```

---

## 2. Gestione Fonti Canali (`yctm channel`)

### `yctm channel add IDENTIFIER`
Registra un nuovo canale nel catalogo locale. L'identificativo può essere un ID canonico (`UC...`), un handle (`@nomecanale`) o un URL del canale.

```bash
yctm channel add "https://www.youtube.com/@Fireship"
yctm channel add UC1234567890abcdef
```

### `yctm channel list`
Elenca tutti i canali registrati.

```bash
yctm channel list
```

### `yctm channel remove CHANNEL_ID`
Rimuove un canale dal catalogo locale.

```bash
yctm channel remove UC1234567890abcdef
```

---

## 3. Gestione Fonti Playlist (`yctm playlist`)

### `yctm playlist add IDENTIFIER`
Registra una nuova playlist nel catalogo locale tramite ID canonico (`PL...`) o URL.

```bash
yctm playlist add "https://www.youtube.com/playlist?list=PL1234567890"
```

### `yctm playlist list`
Elenca tutte le playlist registrate.

```bash
yctm playlist list
```

### `yctm playlist remove PLAYLIST_ID`
Rimuove una playlist dal catalogo locale.

```bash
yctm playlist remove PL1234567890
```

---

## 4. Discovery Metadati (`yctm discover`)

Interroga la YouTube Data API v3 per censire i video con stato iniziale `not_requested`. **Non scarica mai i transcript**.

### `yctm discover channel CHANNEL_ID`
Esegue il discovery per un canale registrato.

```bash
yctm discover channel UC1234567890 --max-results 25 --since 2025-01-01 --dry-run
```

* `--max-results INT`: Numero massimo di video da analizzare (default: configurazione ambiente).
* `--since YYYY-MM-DD`: Considera solo video pubblicati a partire da questa data.
* `--dry-run`: Simula l'operazione senza modificare il database.

### `yctm discover playlist PLAYLIST_ID`
Esegue il discovery per una playlist registrata e memorizza l'associazione molti-a-molti tra la playlist ed i video.

```bash
yctm discover playlist PL1234567890 --max-results 50
```

### `yctm discover all`
Esegue il discovery sequenziale su tutti i canali e le playlist registrati.

```bash
yctm discover all --max-results 20
```

---

## 5. Consultazione Catalogo (`yctm video`)

### `yctm video list`
Elenca i video catalogati applicando filtri avanzati.

```bash
yctm video list --status not_requested --channel UC123... --format json --limit 10
```

* `--status TEXT`: Filtra per stato (`not_requested`, `stored`, `retryable_error`, `terminal_error`).
* `--channel TEXT`: Filtra per ID canale.
* `--playlist TEXT`: Filtra per ID playlist (tramite associazione N:M).
* `--after YYYY-MM-DD`: Video pubblicati da questa data.
* `--before YYYY-MM-DD`: Video pubblicati fino a questa data.
* `--limit INT`: Limita il numero di risultati (default: 50).
* `--offset INT`: Offset di paginazione (default: 0).
* `--format table|json`: Formato di output (default: `table`).
* `--order published-desc|published-asc`: Ordinamento per data di pubblicazione.

### `yctm video show VIDEO_ID`
Mostra i dettagli completi di un singolo video catalogato.

```bash
yctm video show abc123XYZ --format json
```

### `yctm video discover VIDEO_ID`
Esegue il discovery puntuale di un singolo video tramite il suo ID YouTube e lo inserisce nel catalogo locale se non ancora presente.

```bash
yctm video discover abc123XYZ
```

---

## 6. Operazioni sulle Trascrizioni (`yctm transcript`)

### `yctm transcript fetch VIDEO_ID`
Scarica puntualmente la trascrizione di un video già censito nel catalogo locale.

```bash
yctm transcript fetch abc123XYZ --cookies data/cookies.txt
```

* `--cookies PATH`: Percorso opzionale ad un file di cookie in formato Netscape per autenticare la richiesta verso gli endpoint innertube di YouTube.

### `yctm transcript status VIDEO_ID`
Mostra lo stato tecnico di acquisizione del transcript per un dato video.

```bash
yctm transcript status abc123XYZ
```

### `yctm transcript reset [VIDEO_ID]`
Reimposta lo stato di acquisizione dei video a `not_requested`.

```bash
yctm transcript reset abc123XYZ                     # Singolo video
yctm transcript reset --status retryable_error      # Reset massivo per stato
```

### `yctm transcript retry VIDEO_ID`
Esegue una sequenza combinata di `reset` e `fetch` per un singolo video in stato d'errore.

```bash
yctm transcript retry abc123XYZ
```

---

## 7. Diagnostica e Statistiche

### `yctm stats`
Visualizza le statistiche aggregate sul catalogo (totale canali, playlist, video per stato e transcript archiviati).

```bash
yctm stats
```

### `yctm doctor`
Esegue una verifica di integrità incrociando i record del database SQLite con i file `.md` presenti su filesystem, evidenziando file orfani o record incompleti.

```bash
yctm doctor
```

---

## 8. Comandi Deprecati

I seguenti comandi sono mantenuti esclusivamente per retrocompatibilità ed emettono un messaggio di avvertimento su stderr:

* `yctm sync`: Deprecato in favore di `yctm discover channel`.
* `yctm playlist-sync`: Deprecato in favore di `yctm discover playlist`.

