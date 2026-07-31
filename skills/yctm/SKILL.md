---
name: yctm
description: "Advanced operations for YouTube Channel Transcript Monitor (YCTM). Use this skill to perform batch discovery, database maintenance, proxy rotation, and manage the full catalog lifecycle."
---

# YCTM Operations Skill

Questa skill fornisce istruzioni operative, script e reference per l'utilizzo avanzato di **YCTM — YouTube Source and Transcript Catalog**.

> **Documentazione di riferimento:** Il manuale completo è [YCTM.1.md](../../YCTM.1.md) (formato man page).
> **Installazione specifica per piattaforma:** vedi [references/](references/) per guide dedicate.

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
export HTTP_PROXY="http://user:pass@proxy.example.com:8080"
export HTTPS_PROXY="http://user:pass@proxy.example.com:8080"
yctm transcript fetch VIDEO_ID
```

---

## 4. Automazione Batch

### Discovery di Tutte le Fonti in un Comando

```bash
yctm discover all [--max-results 25] [--dry-run]
```

Esegue il discovery sequenziale dei metadati per tutti i canali e playlist registrati nel catalogo locale.

### Manutenzione e Reset del Catalogo

Invece di utilizzare script diretti sul DB SQLite, utilizzare l'interfaccia CLI nativa:

```bash
# Visualizzare statistiche del catalogo
yctm stats

# Ripristinare i video in errore per permetterne il ri-tentativo
yctm transcript reset VIDEO_ID                          # Singolo video
yctm transcript reset --status retryable_error         # Per stato specifico
yctm transcript reset --status terminal_error          # Reset errori terminali
```

### Script Deprecato `sync_all.py`

Lo script `scripts/sync_all.py` è un wrapper di compatibilità verso `yctm discover all`:

```bash
python3 skills/yctm/scripts/sync_all.py
```

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

## 8. Manuale di Riferimento (YCTM.1.md)

Il contenuto integrale del manuale è disponibile in [YCTM.1.md](../../YCTM.1.md). Estratto dei comandi:

| Gruppo / Comando | Descrizione |
|---|---|
| `init-db` / `db init` / `db upgrade` | Inizializza o aggiorna lo schema SQLite |
| `channel add\|list\|remove` | Gestione fonti canale |
| `playlist add\|list\|remove` | Gestione fonti playlist |
| `discover channel\|playlist\|all` | Discovery metadati (Data API v3) |
| `video list\|show\|discover` | Consultazione catalogo e discovery video singolo |
| `transcript fetch\|status\|reset\|retry` | Operazioni puntuali sulle trascrizioni |
| `stats` | Statistiche operative e del catalogo |
| `auth` | **[SPERIMENTALE]** OAuth 2.0 — non utilizzato |
