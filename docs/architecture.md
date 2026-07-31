# Architettura del Sistema YCTM

## Scopo

Questo documento è la fonte primaria per: la descrizione dell'architettura software a livelli, le responsabilità dei moduli, il disaccoppiamento dei componenti ed i flussi interni dei dati.

Non contiene: il riferimento completo dei comandi CLI (vedi [docs/cli-reference.md](docs/cli-reference.md)) o il dettaglio dello schema del database (vedi [docs/database.md](docs/database.md)).

Documenti correlati:
* [SPEC.md](../SPEC.md) — Requisiti funzionali e modello operativo.
* [docs/database.md](database.md) — Dettagli sul livello di persistenza.
* [docs/adr/0001-neutral-source-catalog.md](adr/0001-neutral-source-catalog.md) — ADR sul catalogo neutrale.
* [docs/adr/0002-explicit-transcript-fetch.md](adr/0002-explicit-transcript-fetch.md) — ADR su separazione discovery/fetch.

---

## 1. Organizzazione a Livelli

Il codice sorgente in `src/yctm/` è strutturato secondo il principio della separazione delle responsabilità (Clean Architecture / Layered Architecture):

```text
src/yctm/
├── cli/              # Interfaccia Utente CLI (Typer)
├── application/      # Caso d'uso e orchestrazione dei flussi
├── domain/           # Modelli di dominio, stati ed eccezioni core
├── infrastructure/   # Database (SQLAlchemy), YouTube API, Filesystem
└── config/           # Gestione configurazione (pydantic-settings)
```

### Regole di Dipendenza tra Livelli

* **`cli`** dipende da `application`, `domain`, `config` e `infrastructure/database` (esclusivamente per la gestione della sessione DB).
* **`application`** dipende da `domain`, `infrastructure` e `config`. Non dipendere mai da `cli`.
* **`domain`** è il cuore del sistema e non dipende da alcun altro livello.
* **`infrastructure`** implementa i dettagli tecnici di persistenza, API esterne e I/O filesystem.

---

## 2. Flusso di Discovery dei Metadati

Il discovery è il processo mediante il quale YCTM scopre nuovi video pubblicati su canali o playlist e li registra nel catalogo locale.

```text
┌─────────────┐       ┌───────────────────────┐       ┌──────────────────────┐       ┌────────────────┐
│ CLI Command │──────▶│ application/discovery │──────▶│ infra/youtube/data_api│──────▶│ YouTube API v3 │
└─────────────┘       └───────────────────────┘       └──────────────────────┘       └────────────────┘
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │ Video (not_requested) │ ──▶ Salvataggio in SQLite
                      └───────────────────────┘
```

1. La CLI riceve il comando (es. `yctm discover channel UC...`).
2. Il modulo `application/discovery.py` invoca `infrastructure/youtube/data_api.py`.
3. Il client HTTP (`httpx`) interroga gli endpoint della YouTube Data API v3 (`/playlistItems` o `/videos`).
4. Ogni nuovo video viene inserito nella tabella `videos` di SQLite con stato `not_requested` e timestamp `discovered_at`.
5. **Interruzione Anticipata (Early Exit)**: Nel discovery di un canale, la scansione si interrompe al primo video già presente in database per minimizzare il consumo di quota API.

---

## 3. Flusso di Fetch Puntuale del Transcript

Il download del transcript avviene esclusivamente per un video già catalogato e su richiesta esplicita.

```text
┌──────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ CLI Command  │─────▶│ application/transcripts │─────▶│ infra/youtube/transcripts│
└──────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                   │                                │ (innertube API)
                                   │                                ▼
                                   │                   ┌─────────────────────────┐
                                   │                   │ Testo Transcript (.md)  │
                                   │                   └─────────────────────────┘
                                   │                                │
                                   ▼                                ▼
                      ┌─────────────────────────┐      ┌─────────────────────────┐
                      │ DB SQLite (Status/File) │      │  Filesystem (.md)       │
                      └─────────────────────────┘      └─────────────────────────┘
```

1. `application/transcripts.py` verifica che il video esista in database (solleva `VideoNotDiscoveredError` in caso contrario).
2. Viene invocato l'estrattore `infrastructure/youtube/transcripts.py` (basato su `youtube-transcript-api`).
3. **Fallback Linguistico**: L'estrazione segue una gerarchia rigida:
   - Sottotitoli manuali in Italiano (`it`)
   - Sottotitoli manuali in Inglese (`en`)
   - Sottotitoli automatici ASR in Italiano (`it`)
   - Sottotitoli automatici ASR in Inglese (`en`)
4. Il testo viene formattato come documento Markdown con frontmatter YAML e scritto in modo atomico nel filesystem.
5. In SQLite viene registrato un record `TranscriptFile` (con path, SHA-256 e lingua) e lo stato del video viene aggiornato a `stored`.

---

## 4. Separazione Netta tra Database e Filesystem

* **Database SQLite**: Conserva unicamente le informazioni strutturate del catalogo, i metadati dei video, le associazioni molti-a-molti con le playlist, la provenienza e lo stato dell'acquisizione. **Non contiene mai il testo delle trascrizioni**.
* **Filesystem Locale**: Conserva le trascrizioni come documenti `.md` indipendenti. Ciascun file è autosufficiente grazie al frontmatter YAML contenente i metadati di provenienza.

---

## 5. Principi di Idempotenza e Compensazione

* **Idempotenza**: I comandi di registrazione e discovery possono essere eseguiti più volte senza produrre errori o duplicati.
* **Compensazione Transazionale**: Se la transazione sul database SQLite fallisce durante la fase di salvataggio di un transcript, il sistema esegue una compensazione immediata rimuovendo il file `.md` appena creato su filesystem per prevenire la formazione di file orfani.
