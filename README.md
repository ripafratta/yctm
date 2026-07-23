# YCTM — YouTube Source and Transcript Catalog

YCTM è una applicazione a riga di comando per la registrazione delle fonti YouTube (canali e playlist), la scoperta incrementale dei metadati dei video e il download puntuale controllato delle trascrizioni.

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

### Con pip (alternativa)

```bash
git clone https://github.com/ripafratta/yctm.git && cd yctm
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[dev]"    # dipendenze sviluppo (opzionale)
```

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
YCTM_MAX_RESULTS=5
YCTM_TRANSCRIPT_FETCH_DELAY=15
YCTM_COOKIES_PATH=data/cookies.txt
```

---

## Utilizzo rapido

```bash
yctm init-db                                    # inizializza il database

# Gestione fonti
yctm channel add "https://www.youtube.com/@canale"
yctm channel list
yctm channel remove UC...
yctm playlist add "https://youtube.com/playlist?list=PL..."
yctm playlist list
yctm playlist remove PL...

# Discovery metadati (nessun download transcript)
yctm discover channel UC... --max-results 25 --since 2025-01-01
yctm discover playlist PL...
yctm discover all

# Consultazione catalogo locale
yctm video list
yctm video list --status not_requested
yctm video list --format json
yctm video show VIDEO_ID
yctm video discover VIDEO_ID

# Download esplicito transcript
yctm transcript fetch VIDEO_ID
yctm transcript status VIDEO_ID
yctm transcript reset VIDEO_ID
yctm transcript retry VIDEO_ID

# Manutenzione database
yctm db upgrade

# Utility e Statistiche
yctm stats
yctm auth                                        # [SPERIMENTALE] Autenticazione OAuth (non utilizzata)
```

---

## Sviluppo e Qualità Codice

Prima di sottoporre modifiche o considerare completata una feature, eseguire la suite completa di test e controlli di qualità:

```bash
# Esecuzione test unitari
pytest

# Controllo formattazione e linter
ruff check .
ruff format --check .

# Analisi statica dei tipi
mypy .
```

---

## Estratto Comandi

| Gruppo / Comando | Descrizione |
|---|---|
| `init-db` / `db init` / `db upgrade` | Inizializza o aggiorna lo schema SQLite |
| `channel add\|list\|remove` | Gestione fonti canale |
| `playlist add\|list\|remove` | Gestione fonti playlist |
| `discover channel\|playlist\|all` | Discovery metadati (Data API v3) |
| `video list\|show\|discover` | Consultazione catalogo e discovery video singolo |
| `transcript fetch\|status\|reset\|retry` | Operazioni puntuali sulle trascrizioni |
| `stats` | Statistiche operative e del catalogo |
| `auth` | [SPERIMENTALE] Autenticazione OAuth 2.0 — non utilizzata dall'implementazione transcript attiva |

> **Nota:** Il flag `--verbose` (o `-v`) è disponibile su tutti i comandi per log dettagliati.

