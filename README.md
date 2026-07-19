# YCTM — YouTube Channel Transcript Monitor

YCTM è una applicazione a riga di comando per la raccolta incrementale di trascrizioni
YouTube. Il programma archivia le trascrizioni come documenti immutabili su filesystem,
mantiene un registro di audit e provenienza in SQLite e pubblica un manifest JSONL
destinato all'ingestione in sistemi LLM (LLM Wiki).

---

## Installazione

### Prerequisiti

* Python >= 3.12
* [`uv`](https://docs.astral.sh/uv/) (gestore di pacchetti consigliato)

### Con uv (consigliato)

```bash
git clone https://github.com/ripafratta/yctm.git && cd yctm
uv sync                  # installa le dipendenze e crea il virtualenv
uv sync --group dev      # include le dipendenze di sviluppo (test/lint)
```

Verifica che funzioni:

```bash
uv run yctm --help
```

Oppure attiva il virtualenv e usa direttamente `yctm`:

```bash
source .venv/bin/activate
yctm --help
```

### Con pip (alternativa)

```bash
git clone https://github.com/ripafratta/yctm.git && cd yctm
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[dev]"    # dipendenze sviluppo (opzionale, per test/lint)
```

### Skill per agenti AI (opzionale)

YCTM include una skill (`skills/yctm/`) che fornisce procedure operative,
automazione e diagnostica per agenti AI. La skill richiede la CLI installata
(passaggio precedente) per funzionare.

#### Claude Code

```bash
# Copia la directory direttamente nella cartella skills utente
mkdir -p ~/.claude/skills
cp -r skills/yctm ~/.claude/skills/yctm
```

Riavvia Claude Code: la skill `/yctm` sarà disponibile automaticamente.

#### Altri agenti (Codex, Gemini CLI, etc.)

Vedi [skills/yctm/references/](skills/yctm/references/) per le istruzioni
specifiche per ogni piattaforma.

---

## Configurazione

Copiare `.env.example` in `.env` e impostare i valori:

```bash
cp .env.example .env
```

```
YCTM_YOUTUBE_API_KEY=AIzaSy...            # obbligatoria
YCTM_DATABASE_PATH=data/yctm.sqlite3
YCTM_TRANSCRIPTS_DIRECTORY=data/transcripts
YCTM_MANIFEST_PATH=data/manifest.jsonl
YCTM_MAX_RESULTS=5
```

La configurazione viene letta da variabili ambiente o dal file `.env`.
L'unico valore obbligatorio è `YCTM_YOUTUBE_API_KEY`.

---

## Utilizzo rapido

```bash
yctm init-db                                    # inizializza il database
yctm channel "https://www.youtube.com/@canale"  # registra un canale
yctm sync UC... --max-results 5                 # sincronizza trascrizioni
yctm sync UC... --max-results 5 --interactive   # chiede conferma per ogni video
yctm playlist "https://youtube.com/playlist?list=PL..."  # registra una playlist
yctm playlist-sync PL... --max-results 10       # sincronizza playlist
yctm reset retryable                            # resetta i video in errore temporaneo
yctm manifest rebuild                           # rigenera il manifest JSONL
```

Ogni comando accetta il flag `-v` / `--verbose` per output di logging dettagliato.

---

## Comandi

| Comando | Descrizione |
|---------|-------------|
| `init-db` | Inizializza il database SQLite |
| `channel <id>` | Registra un canale YouTube (ID, handle o URL) |
| `sync <channel-id>` | Sincronizza le trascrizioni di un canale |
| `playlist <id>` | Registra una playlist YouTube (ID o URL) |
| `playlist-sync <playlist-id>` | Sincronizza le trascrizioni di una playlist |
| `reset retryable\|terminal\|all` | Reimposta a `pending` i video in errore |
| `manifest rebuild` | Rigenera il manifest JSONL |

### Opzioni comuni

| Opzione | Descrizione |
|---------|-------------|
| `-v`, `--verbose` | Output di logging dettagliato |
| `--max-results N` | Numero massimo di video da analizzare (default: da config) |
| `-i`, `--interactive` | Chiede conferma prima di scaricare ogni trascrizione |

### Codici di uscita

| Codice | Significato |
|--------|-------------|
| `0` | Successo |
| `2` | Canale o playlist non trovata |
| `3` | Errore generico API YouTube o di rete |
| `4` | Quota API YouTube superata |

---

## Sincronizzazione incrementale

1. Il discovery recupera al massimo N video recenti dal canale o playlist
2. Se un video è già in stato terminale (`stored` o `terminal_error`), la scansione si interrompe (early exit)
3. L'estrazione segue il fallback: manuale IT → manuale EN → ASR IT → ASR EN
4. Se la trascrizione non è disponibile, vengono effettuati fino a 3 tentativi
5. Dopo il terzo fallimento il video passa a `terminal_error`

### Modalità interattiva

Usando il flag `--interactive` (o `-i`) con `sync` o `playlist-sync`,
il programma mostra ogni nuovo video scoperto e chiede conferma prima di
scaricarne la trascrizione:

```
Vito Lops — "Mercati al bivio: rimbalzo tech o nuova ondata di volatilità?" (2026-07-12)
  Scaricare la trascrizione? [Y/n]:
```

- **Invio / Y / yes** → scarica la trascrizione
- **n / no** → salta il video (ricomparirà alla prossima sincronizzazione)

Utile per selezionare solo i video che trattano argomenti di interesse,
senza sprecare quota API o riempire il database di contenuti non voluti.

### Reset dei video in errore

Se YouTube blocca l'IP o la trascrizione non è disponibile, i video vengono
marcati come `retryable_error` e ritentati fino a 3 volte. Per forzare un
nuovo tentativo:

```bash
yctm reset retryable    # resetta i video in retryable_error → pending
yctm reset terminal     # resetta i video in terminal_error → pending
yctm reset all          # resetta entrambi
```

---

## Skill per agenti AI

YCTM include una skill (`skills/yctm/`) con procedure operative per agenti AI:

- **Pacchetto**: `skills/yctm.skill`
- **Directory sorgente**: `skills/yctm/`
- **Istruzioni per ogni piattaforma**: [skills/yctm/references/](skills/yctm/references/)

---

## Contratto JSONL

Il manifest contiene una riga JSON per ogni video processato. Il consumatore LLM Wiki
deve elaborare esclusivamente i record con `status: "stored"`.

---

## Architettura API YouTube

YCTM utilizza **due meccanismi distinti** per interagire con YouTube:

### 1. YouTube Data API v3 (ufficiale, richiede API key GCP)

Usata per tutte le operazioni di **discovery e metadati**:
- Risoluzione di canali e playlist da handle/URL
- Recupero della lista degli ultimi video pubblicati
- Dettagli di playlist e canali

Le chiamate vanno a `https://www.googleapis.com/youtube/v3/...` autenticate con
la chiave API (`YCTM_YOUTUBE_API_KEY`) salvata nel file `.env`.

**Costo**: consuma la quota giornaliera del tuo progetto Google Cloud (10.000 unità
al giorno per default). Ogni chiamata costa ~1-3 unità.

### 2. youtube-transcript-api (non ufficiale, senza API key)

Usata esclusivamente per **scaricare il testo delle trascrizioni** dai video.
Questa libreria interroga endpoint interni di YouTube (quelli usati dal player web)
e **non utilizza la tua API key** né la Data API v3.

**Limitazioni**:
- Non richiede autenticazione ma è soggetta a **blocchi IP** se vengono effettuate
  troppe richieste in rapida successione
- Non esiste una quota ufficiale; il comportamento è a discrezione di YouTube
- Può essere aggirata usando proxy (configurabili via variabili d'ambiente `HTTP_PROXY` / `HTTPS_PROXY`)

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

---

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

Il nome del file segue la convenzione: `{YYYYMMDD}_{video_id}_{titolo_sanificato}.md`

---

## Troubleshooting

- **Quota API esaurita**: attendere il reset giornaliero o ridurre `--max-results`
- **Blocco IP su trascrizioni**: YouTube blocca IP che fanno troppe richieste
  rapide a `youtube-transcript-api`. YCTM ha già un delay di 2s integrato,
  ma se il blocco persiste, attendere qualche ora o configurare proxy via
  `HTTP_PROXY` / `HTTPS_PROXY`.
- **Database corrotto**: eliminare `data/yctm.sqlite3` e rieseguire `yctm init-db`

Per il manuale completo dei comandi consultare [YCTM.1.md](YCTM.1.md).
