# YouTube Channel Transcript Monitor (YCTM)

[![CI](https://github.com/ripafratta/yctm/actions/workflows/ci.yml/badge.svg)](https://github.com/ripafratta/yctm/actions/workflows/ci.yml)

## Scopo


Questo documento è la fonte primaria per: l'introduzione generale a YCTM, i requisiti di sistema, le istruzioni di installazione, la configurazione iniziale ed il quickstart operativo.

Non contiene: la specifica dettagliata di tutti i comandi CLI (vedi [docs/cli-reference.md](docs/cli-reference.md)), le regole operative per i coding agent (vedi [AGENTS.md](AGENTS.md)) o i dettagli architetturali interni (vedi [docs/architecture.md](docs/architecture.md)).

Documenti correlati:
* [SPEC.md](SPEC.md) — Specifica normativa dei requisiti di prodotto.
* [docs/cli-reference.md](docs/cli-reference.md) — Manuale di riferimento completo della CLI.
* [docs/architecture.md](docs/architecture.md) — Modello architetturale del sistema.
* [docs/troubleshooting.md](docs/troubleshooting.md) — Risoluzione dei problemi ed integrità.
* [CHANGELOG.md](CHANGELOG.md) — Registro delle modifiche.

---

YCTM è una applicazione a riga di comando (CLI) in Python per la registrazione delle fonti YouTube (canali e playlist), la scoperta incrementale dei metadati dei video e l'acquisizione puntuale e controllata delle trascrizioni.

YCTM funge da **catalogo locale, generico e neutrale**: non contiene dipendenze da LLM, non gestisce Knowledge Base (KB), tag editoriali o valutazioni di rilevanza, e salva le trascrizioni come documenti Markdown immutabili nel filesystem locale.

---

## Requisiti

* Python >= 3.12
* [`uv`](https://docs.astral.sh/uv/) (gestore di pacchetti raccomandato) o `pip`

---

## Installazione

### Con uv (consigliato)

```bash
git clone https://github.com/ripafratta/yctm.git && cd yctm
uv sync                  # installa le dipendenze e crea il virtualenv
uv sync --group dev      # include le dipendenze di sviluppo (test/lint)
```

Verifica l'installazione:

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

Copia `.env.example` in `.env` e configura i valori per il tuo ambiente:

```bash
cp .env.example .env
```

Parametri principali nel file `.env`:

```ini
YCTM_YOUTUBE_API_KEY=AIzaSy...            # Chiave YouTube Data API v3 (obbligatoria)
YCTM_DATABASE_PATH=data/yctm.sqlite3      # Percorso del database SQLite locale
YCTM_TRANSCRIPTS_DIRECTORY=data/transcripts # Directory di destinazione trascrizioni
YCTM_MAX_RESULTS=5                        # Max risultati default per discovery
YCTM_TRANSCRIPT_FETCH_DELAY=15            # Rate-limiting delay (in secondi)
YCTM_COOKIES_PATH=data/cookies.txt        # (Opzionale) File cookie Netscape per innertube
```

---

## Quickstart

### 1. Inizializzazione Database

```bash
yctm init-db
```

### 2. Registrazione Fonti

```bash
yctm channel add "https://www.youtube.com/@canale"
yctm playlist add "https://youtube.com/playlist?list=PL..."
```

### 3. Discovery Metadati (YouTube Data API v3)

Il discovery individua i nuovi video e censisce titolo, descrizione e data con stato `not_requested`. **Non scarica mai i transcript**.

```bash
yctm discover channel UC1234567890
yctm discover all
```

### 4. Consultazione del Catalogo

```bash
yctm video list
yctm video list --status not_requested
yctm video list --format json
yctm video show VIDEO_ID
```

### 5. Fetch Puntuale del Transcript

Scarica e salva su filesystem il transcript per un video specifico già catalogato:

```bash
yctm transcript fetch VIDEO_ID
```

### 6. Verifica Stato e Diagnostica

```bash
yctm transcript status VIDEO_ID
yctm stats
yctm doctor
```

Per il riferimento completo di tutti i comandi, sotto-comandi ed opzioni, consulta la [Guida CLI](docs/cli-reference.md).

---

## Sviluppo e Qualità Codice

Prima di inoltrare modifiche, eseguire la suite di verifica:

```bash
ruff check .
ruff format --check .
pytest
mypy .
```

---

## Contributi e Licenza

Consulta [AGENTS.md](AGENTS.md) per le linee guida di contributo e gli standard di sviluppo del progetto.

YCTM is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
