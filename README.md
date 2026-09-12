# YouTube Channel Transcript Monitor (YCTM)

## Scopo


Questo documento è la fonte primaria per: l'introduzione generale a YCTM, i requisiti di sistema, le istruzioni di installazione, la configurazione iniziale ed il quickstart operativo.

Per la specifica dettagliata di tutti i comandi CLI vedere [docs/cli-reference.md](docs/cli-reference.md).
Per i dettagli architetturali interni vedere [docs/architecture.md](docs/architecture.md).

Documenti correlati:
* [SPEC.md](SPEC.md) — Specifica normativa dei requisiti di prodotto.
* [docs/cli-reference.md](docs/cli-reference.md) — Manuale di riferimento completo della CLI.
* [docs/architecture.md](docs/architecture.md) — Modello architetturale del sistema.
* [docs/troubleshooting.md](docs/troubleshooting.md) — Risoluzione dei problemi ed integrità.
* [CHANGELOG.md](CHANGELOG.md) — Registro delle modifiche.

---

YCTM è uno strumento progettato per la gestione neutrale e locale di contenuti video provenienti da YouTube. Gli utenti possono registrare canali e playlist, monitorare l'uscita di nuovi video e archiviare selettivamente le loro trascrizioni in formato Markdown. L'architettura separa rigorosamente il discovery dei metadati, effettuato tramite API ufficiali, dal recupero dei testi, che avviene solo su richiesta esplicita per ottimizzare le risorse. I dati strutturati sono conservati in un database SQLite, mentre i documenti testuali vengono salvati direttamente sul filesystem con metadati integrati

YCTM è una applicazione a riga di comando (CLI) in Python, ad esecuzione manuale (*on-demand*) che non dipende da LLM, non gestisce Knowledge Base (KB), tag editoriali o valutazioni di rilevanza, e salva le trascrizioni come documenti Markdown nel filesystem locale.


---

## Caratteristiche Principali

- **Registrazione Fonti** : registrare canali e playlist
- **Monitoraggio** : monitorare l'uscita di nuovi video
- **Archiviazione** : archiviare selettivamente le trascrizioni in formato Markdown
- **Catalogo locale** : catalogo locale, generico e neutrale
- **Indipendenza da LLM** : non dipende da LLM
- **Indipendenza da KB** : non gestisce Knowledge Base (KB)
- **Indipendenza da tag editoriali** : non gestisce tag editoriali
- **Indipendenza da valutazioni di rilevanza** : non gestisce valutazioni di rilevanza

---

## Gestione Multi-Catalogo YCTM

È possibile gestire molteplici istanze o cataloghi separati di YCTM ad es. per alimentare diverse LLM Wiki con contenuti tematici specifici (es. finanza, intelligenza artificiale, viaggi). Non esiste alcun vincolo architetturale che imponga la condivisione di un unico catalogo locale.

### Come funziona l'isolamento dei cataloghi

YCTM è stato progettato come un **catalogo locale e neutrale**, disaccoppiato da concetti di Knowledge Base (KB), tag o categorizzazioni editoriali interne. La separazione fisica tra archivi tematici si ottiene personalizzando due impostazioni di configurazione per ciascun ambito:

1. **`YCTM_DATABASE_PATH`**: specifica il percorso del file SQLite dedicato alla tracciabilità dei metadati e degli stati dei video.
2. **`YCTM_TRANSCRIPTS_DIRECTORY`**: specifica la directory del filesystem locale destinata al salvataggio dei file Markdown delle trascrizioni estratte.

### Approcci pratici per la gestione multi-catalogo

Puoi separare i contesti tematici in due modi principali:

* **Directory di progetto o file `.env` distinti**: puoi creare una struttura di directory dedicate per ciascuna tematica (es. `yctm-finanza/`, `yctm-ai/`, `yctm-viaggi/`), ciascuna contenente il proprio file `.env` che definisce database e cartella output specifici.
* **Sovrascrittura delle variabili d'ambiente al volo**: durante l'esecuzione della CLI o da script di automatizzazione, puoi definire i percorsi direttamente nell'ambiente:

```bash
# Esempio per l'archivio Finanza
YCTM_DATABASE_PATH=data/finanza/yctm.sqlite3 \
YCTM_TRANSCRIPTS_DIRECTORY=data/finanza/transcripts \
yctm discover all

# Esempio per l'archivio IA
YCTM_DATABASE_PATH=data/ai/yctm.sqlite3 \
YCTM_TRANSCRIPTS_DIRECTORY=data/ai/transcripts \
yctm discover all
```

Questa impostazione si adatta perfettamente al modello architetturale di YCTM: ciascuna LLM Wiki (o il relativo agente d'ingestione) potrà interfacciarsi con la propria istanza/cartella per leggere ed elaborare in modo indipendente solo i documenti Markdown di propria competenza.

---

## Integrazione YCTM in LLM Wiki

Ecco le istruzioni passo passo per configurare e integrare **YCTM** all'interno della cartella di progetto di una **LLM Wiki** gestita da un agente locale (come Claude Code, Codex o altri agenti).

### Passaggio 1: Configurazione dell'ambiente locale (`.env`)
Nella cartella radice della tua LLM Wiki, crea o aggiorna il file `.env` impostando il percorso del database SQLite e definendo la directory di destinazione per l'esportazione dei documenti, ad es. `Clippings`:

```ini
YCTM_YOUTUBE_API_KEY=la_tua_api_key_youtube
YCTM_DATABASE_PATH=data/yctm.sqlite3
YCTM_TRANSCRIPTS_DIRECTORY=Clippings
YCTM_MAX_RESULTS=10
```
*Grazie a questa configurazione, ogni trascrizione scaricata da YCTM verrà archiviata come file Markdown con metadati YAML direttamente nella cartella `Clippings/` del progetto.*

### Passaggio 2: Inizializzazione del Catalogo Locale
Esegui il comando di inizializzazione per creare lo schema del database SQLite dedicato a questo specifico progetto:

```bash
yctm init-db
```

### Passaggio 3: Installazione della Skill YCTM per l'Agente
Per consentire all'agente di interagire autonomamente con YCTM all'interno del progetto, collega la skill nella struttura del workspace:

* **Per Claude Code o Codex (integrazione a livello di progetto)**:
  ```bash
  mkdir -p .claude/skills
  ln -sf /percorso/sorgente/yctm/skills/yctm .claude/skills/yctm
  ```
* **Per installazione globale (es. Claude Code utente)**:
  ```bash
  unzip -o /percorso/sorgente/yctm/skills/yctm.skill -d ~/.claude/skills/
  ```

---

### Passaggio 4: Registrazione delle Fonti del Dominio
L'agente (o l'utente) censisce i canali o le playlist pertinenti per il dominio di conoscenza della Wiki:

```bash
# Registrazione canali tematici
yctm channel add "https://www.youtube.com/@CanaleSpecializzato"

# Registrazione playlist di interesse
yctm playlist add "https://www.youtube.com/playlist?list=PL1234567890"
```

---

### Passaggio 5: Flusso Operativo dell'Agente (Monitoraggio, Triage, Fetch e Ingestione)

1. **Discovery (Monitoraggio nuovi contenuti)**: L'agente aggiorna il catalogo dei metadati tramite la YouTube Data API v3 senza scaricare i testi, registrando i nuovi video in stato `not_requested`:
   ```bash
   yctm discover all
   ```
2. **Consultazione e Triage (Valutazione)**: L'agente richiede l'elenco dei nuovi video catalogati in formato JSON per analizzare titoli e descrizioni:
   ```bash
   yctm video list --status not_requested --format json
   ```
3. **Fetch del Transcript (Esportazione in `Clippings/`)**: Per i video giudicati rilevanti, l'agente avvia il download puntuale:
   ```bash
   yctm transcript fetch VIDEO_ID
   ```
   YCTM genera il file `.md` nella cartella `Clippings/` inserendo nel frontmatter YAML dati di provenienza quali `title`, `video_id`, `channel_title`, `published_at`, `language` e `source`.
4. **Ingestione nella LLM Wiki**: L'agente legge i file Markdown generati in `Clippings/`, sintetizza le informazioni ed aggiorna le pagine o il grafo di conoscenza della LLM Wiki.

---

## NOTA: Sincronizzazione Dati YCTM e processo di ingestione della LLM Wiki

Se imposti `YCTM_TRANSCRIPTS_DIRECTORY=Clippings`:
1. Quando esegui `yctm transcript fetch VIDEO_ID`, YCTM salva la trascrizione in `Clippings/` e registra nel database SQLite lo stato `stored` insieme al percorso `storage_path`.
2. Quando l'agente della LLM Wiki sposta o cancella il file da `Clippings/` dopo l'elaborazione, lo `storage_path` presente nella tabella `transcript_files` di YCTM non punta più a un file esistente su disco.
3. Se in seguito esegui il comando di diagnostica `yctm doctor`, il sistema rileverà correttamente questa discrepanza segnalando un *Record DB con file mancante su disco* .

### Soluzioni Architetturali

Per gestire questo disallineamento senza complicare l'ingestione dell'agente, puoi adottare uno dei tre modelli seguenti a seconda del contesto e dei requisiti del tuo progetto:

#### 1. Approccio Archivio Permanente (`raw/youtube/`) + Triage via CLI/JSON
Invece di scaricare i file direttamente in `Clippings/`, imposta la directory di destinazione di YCTM su una cartella di archivio grezzo permanente all'interno della Wiki (ad esempio `raw/youtube/` o `data/transcripts/`).

* **Come evita l'inconsistenza**: I file salvati da YCTM non vengono mai mossi o cancellati. `storage_path` rimane valido e l'integrità del catalogo verificabile con `yctm doctor` resta perfetta.
* **Come l'agente sa cosa elaborare**: L'agente non deve scansionare alla cieca la cartella dei file, ma usa la CLI di YCTM per sapere cosa c'è da elaborare:
  * Quando l'agente esegue `yctm transcript fetch VIDEO_ID`, la CLI restituisce direttamente l'esito del salvataggio e il percorso generato .
  * L'agente può interrogare il catalogo in formato JSON con `yctm video list --status stored --format json` per ottenere l'elenco dei video scaricati .
  * L'agente legge il file da `raw/youtube/`, crea la nota sintetica o la pagina nella Wiki ed evita di toccare il file Markdown originale.

#### 2. Approccio Outbox Volatile: `Clippings/` come cartella temporanea (Disaccoppiamento)
Se la convenzione della tua LLM Wiki impone che l'elaborazione passi da `Clippings/` con successiva eliminazione/spostamento, puoi **accettare il disaccoppiamento esplicito**:

* In questo modello, la cartella `Clippings/` viene considerata da YCTM solo come una "Outbox" temporanea di consegna verso la Wiki.
* Per YCTM, lo stato `stored` indica unicamente che *il transcript è stato estratto con successo da YouTube ed consegnato*. L'hash `sha256` a database garantisce comunque la tracciabilità dell'estrazione avvenuta.
* Se in futuro la Wiki avesse bisogno di riscaricare un transcript il cui file locale è stato eliminato, l'agente potrà ripristinare lo stato con `yctm transcript reset VIDEO_ID` e lanciare nuovamente `yctm transcript fetch` .

#### 3. Approccio Ibrido: Archivio in `raw/` + Copia/Symlink temporaneo in `Clippings/`
Se l'agente si basa su uno script automatico che scansiona fisicamente la cartella `Clippings/` per avviare il flusso di lavoro:

1. YCTM salva la trascrizione nella sua destinazione di archivio `raw/youtube/`.
2. L'agente o uno script di post-fetch crea una copia temporanea (o un link simbolico) del file `.md` dentro `Clippings/`.
3. L'agente processa il file in `Clippings/` e lo elimina a fine lavoro. Il file originale in `raw/youtube/` rimane intatto e tracciato da YCTM.



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
YCTM_YOUTUBE_API_KEY=...             # Richiesta solo per discovery/metadati canali e playlist (non per le trascrizioni)
YCTM_DATABASE_PATH=data/yctm.sqlite3      # Percorso del database SQLite locale
YCTM_TRANSCRIPTS_DIRECTORY=data/transcripts # Directory di destinazione trascrizioni
YCTM_MAX_RESULTS=5                        # Max risultati default per discovery
YCTM_TRANSCRIPT_FETCH_DELAY=15            # Rate-limiting delay (in secondi)
YCTM_COOKIES_PATH=data/cookies.txt        # (Opzionale) File cookie Netscape per innertube
```

La configurazione viene letta da variabili ambiente o dal file `.env`.
Note sulle credenziali:
* **Per le trascrizioni**: NON serve alcuna API Key né autenticazione (usa scraping via `youtube-transcript-api`).
* **Per discovery e metadati** (`channel`, `playlist`, `sync`): serve `YCTM_YOUTUBE_API_KEY` (YouTube Data API v3 di Google Cloud).


### Mitigazione del Rate-Limiting e Uso dei Cookie

L'estrazione delle trascrizioni avviene tramite scraping diretto degli endpoint web di YouTube (`youtube-transcript-api`). In caso di download frequenti o blocchi IP (HTTP 429), è fortemente consigliato autenticare le richieste fornendo i cookie di una sessione browser attiva :

1. **Esporta i cookie dal browser** in formato Netscape utilizzando un'estensione dedicata:
   - **Chrome**: *"Get cookies.txt"* o *"cookies.txt export"* 
   - **Firefox**: *"cookies.txt"* 
2. **Salva il file** all'interno del progetto (ad esempio come `data/cookies.txt`) .
3. **Collega il file a YCTM**:
   - Impostando la variabile nel file `.env`:
     ```ini
     YCTM_COOKIES_PATH=data/cookies.txt
     ```
   - Oppure passandolo direttamente al comando CLI tramite l'opzione `--cookies`:
     ```bash
     yctm transcript fetch VIDEO_ID --cookies data/cookies.txt
     ``` 
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
