# YCTM — YouTube Channel Transcript Monitor

YCTM e' una applicazione a riga di comando per la raccolta incrementale di trascrizioni
YouTube. Il programma archivia le trascrizioni come documenti immutabili su filesystem,
mantiene un registro di audit e provenienza in SQLite e pubblica un manifest JSONL
destinato all'ingestione in sistemi LLM (LLM Wiki).

---

## Installazione

```bash
git clone <url> && cd yctm
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[dev]"    # dipendenze sviluppo (opzionale)
```

## Configurazione

Copiare `.env.example` in `.env` e impostare i valori:

```
YCTM_YOUTUBE_API_KEY=AIzaSy...
YCTM_DATABASE_PATH=data/yctm.sqlite3
YCTM_TRANSCRIPTS_DIRECTORY=data/transcripts
YCTM_MANIFEST_PATH=data/manifest.jsonl
YCTM_MAX_RESULTS=5
```

La configurazione viene letta da variabili ambiente o dal file `.env`.

## Utilizzo rapido

```bash
yctm init-db                                    # inizializza il database
yctm channel "https://www.youtube.com/@canale"  # registra un canale
yctm sync UC... --max-results 5                 # sincronizza trascrizioni
yctm sync UC... --max-results 5 --interactive   # modalità interattiva: chiede conferma per ogni video
yctm playlist "https://youtube.com/playlist?list=PL..."  # registra una playlist
yctm playlist-sync PL... --max-results 10       # sincronizza playlist
yctm manifest rebuild                           # rigenera il manifest JSONL
```

## Comandi

| Comando | Descrizione |
|---------|------------|
| `init-db` | Inizializza il database SQLite |
| `channel` | Registra un canale YouTube |
| `sync` | Sincronizza le trascrizioni di un canale |
| `playlist` | Registra una playlist YouTube |
| `playlist-sync` | Sincronizza le trascrizioni di una playlist |
| `manifest` | Rigenera il manifest JSONL |

## Sincronizzazione incrementale

1. Il discovery recupera al massimo N video recenti dal canale o playlist
2. Se un video e' gia' in stato terminale, la scansione si interrompe (early exit)
3. L'estrazione segue il fallback: manuale IT, manuale EN, ASR IT, ASR EN
4. Se la trascrizione non e' disponibile, vengono effettuati fino a 3 tentativi
5. Dopo il terzo fallimento il video passa a `terminal_error`

## Contratto JSONL

Il manifest contiene una riga JSON per ogni video processato. Il consumatore LLM Wiki
deve elaborare esclusivamente i record con `status: "stored"`.

## Architettura API YouTube

YCTM utilizza **due meccanismi distinti** per interagire con YouTube:

### 1. YouTube Data API v3 (ufficiale, richiede API key GCP)

Usata per tutte le operazioni di **discovery e metadati**:
- Risoluzione di canali e playlist da handle/URL
- Recupero della lista degli ultimi video pubblicati
- Dettagli di playlist e canali

Le chiamate vanno a `https://www.googleapis.com/youtube/v3/...` autenticate con
la chiave API (`YCTM_YOUTUBE_API_KEY`) salvata nel file `.env`.

**Costo**: consuma la quota giornaliera del tuo progetto Google Cloud (10.000 unita'
al giorno per default). Ogni chiamata costa ~1-3 unita'.

### 2. youtube-transcript-api (non ufficiale, senza API key)

Usata esclusivamente per **scaricare il testo delle trascrizioni** dai video.
Questa libreria interroga endpoint interni di YouTube (quelli usati dal player web)
e **non utilizza la tua API key** ne' la Data API v3.

**Limitazioni**:
- Non richiede autenticazione ma e' soggetta a **blocchi IP** se vengono effettuate
  troppe richieste in rapida successione
- Non esiste una quota ufficiale; il comportamento e' a discrezione di YouTube
- Puo' essere aggirata usando proxy (configurabili via variabili d'ambiente)

Per mitigare i blocchi, YCTM inserisce un delay di **2 secondi** tra una richiesta
di trascrizione e la successiva.

### Schema

```
                     YouTube Data API v3 (con chiave GCP da .env)
Canali / Playlist ──► googleapis.com/youtube/v3/...    ✓
Metadati video

                     youtube-transcript-api (endpoint interni, senza chiave)
Trascrizioni  ──────► youtube.com/internal/...         delay 2s tra richieste
```

## Formato file trascrizioni

Le trascrizioni vengono salvate come file Markdown (`.md`) con frontmatter YAML:

```yaml
---
title: "Titolo del video"
video_id: b7DQyS1yFCU
channel_id: UCqCYKSvF_sJl78-bxD5q6NQ
channel_title: "Vito Lops"
channel_handle: "@lopsvito"
published_at: 2026-07-12T07:31:46
extracted_at: 2026-07-12T20:20:23
language: it
source: "https://www.youtube.com/watch?v=b7DQyS1yFCU"
description: |
  Descrizione del video...
---

[testo della trascrizione...]
```

## Troubleshooting

- **Quota API esaurita**: attendere il reset giornaliero o ridurre `--max-results`
- **Blocco IP su trascrizioni**: YouTube blocca IP che fanno troppe richieste
  rapide a `youtube-transcript-api`. YCTM ha gia' un delay di 2s integrato,
  ma se il blocco persiste, attendere qualche ora o configurare proxy via
  variabili d'ambiente.
- **Database corrotto**: eliminare `data/yctm.sqlite3` e rieseguire `yctm init-db`

Per il manuale completo dei comandi consultare [YCTM.1.md](YCTM.1.md).
