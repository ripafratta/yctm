# AGENTS.md

## Ruolo del documento

Questo documento definisce le regole operative, architetturali e qualitative che devono essere rispettate durante lo sviluppo del progetto **YouTube Channel Transcript Monitor (YCTM)**.

La specifica funzionale del progetto è contenuta in `SPEC.md`. In caso di conflitto tra questo documento e la specifica funzionale, la specifica funzionale prevale per quanto riguarda i requisiti applicativi, mentre questo documento prevale per quanto riguarda gli standard implementativi.

---

# Obiettivi del progetto

YCTM è una applicazione CLI Python destinata alla registrazione delle fonti YouTube (canali e playlist), al discovery dei metadati dei video e all'acquisizione puntuale delle trascrizioni.

YCTM è un catalogo locale, generico e neutrale: non gestisce logiche di Knowledge Base (KB), rilevanza semantica o integrazioni accoppiate con sistemi LLM esterni.

Il progetto deve privilegiare:

* semplicità operativa;
* affidabilità dei dati raccolti;
* tracciabilità delle operazioni;
* manutenibilità del codice;
* assenza di complessità infrastrutturale non necessaria.

YCTM non deve introdurre componenti server, processi residenti o meccanismi di scheduling automatico.


---

# Stack tecnologico

Utilizzare esclusivamente tecnologie mature e ampiamente supportate.

## Linguaggio

* Python >= 3.12
* codice tipizzato tramite type hints
* gestione delle dipendenze tramite `pyproject.toml`

## Componenti principali

* CLI: Typer
* Configurazione: pydantic-settings
* ORM: SQLAlchemy 2.x
* Database: SQLite
* HTTP client: httpx
* Test: pytest
* Qualità codice: Ruff
* Tipizzazione statica: mypy

---

# Principi architetturali

## Separazione delle responsabilità

Il codice deve essere organizzato per livelli:

```
src/yctm/

├── cli/
│   └── comandi applicativi

├── domain/
│   └── modelli e logica di dominio

├── application/
│   └── casi d'uso e orchestrazione

├── infrastructure/
│   ├── database
│   ├── youtube api
│   └── filesystem

└── config/
    └── configurazione applicativa
```

La CLI deve contenere esclusivamente gestione dei comandi e validazione degli input.

La logica applicativa non deve dipendere direttamente dalla CLI.

---

# Gestione della configurazione

La configurazione deve essere esterna al codice.

Regole:

* utilizzare variabili ambiente o file `.env`;
* non inserire chiavi API nel repository;
* utilizzare `pydantic-settings`;
* prevedere valori predefiniti ragionevoli.

Esempi:

* API key YouTube;
* percorso database;
* directory destinazione trascrizioni;
* numero massimo di video analizzati.

---

# Modello dati

SQLAlchemy deve essere utilizzato esclusivamente per:

* persistenza dello stato;
* deduplicazione;
* audit trail.

Il database non deve contenere il testo completo delle trascrizioni.

Le trascrizioni devono essere salvate come documenti filesystem indipendenti.

Relazioni principali:

```
Channel
   |
   └── Video
          |
          └── TranscriptFile
```

Ogni entità persistita deve avere:

* identificativo stabile;
* timestamp di creazione;
* timestamp di aggiornamento ove necessario.

---

# Gestione delle trascrizioni

Regole fondamentali:

* non effettuare chunking;
* non modificare il contenuto originale;
* mantenere una trascrizione come documento unitario;
* conservare metadati sufficienti alla provenienza del documento.

La gerarchia di acquisizione deve essere:

1. sottotitoli manuali;
2. sottotitoli automatici YouTube ASR;
3. gestione esplicita dell'assenza di trascrizione.

---

# Integrazione YouTube

Le chiamate API devono essere:

* minimizzate;
* facilmente testabili;
* isolate dal dominio applicativo.

La sincronizzazione deve essere incrementale:

* analizzare gli ultimi N video;
* confrontare gli identificativi già presenti;
* interrompere la scansione al primo elemento noto.

Non implementare crawling completo salvo esplicita richiesta.

---

# Gestione errori

Gli errori devono:

* essere espliciti;
* utilizzare eccezioni dedicate;
* essere registrati tramite logging.

Non utilizzare:

```python
except Exception:
    pass
```

Gli errori recuperabili devono produrre messaggi CLI chiari.

---

# Logging

Utilizzare esclusivamente il modulo standard `logging`.

Non utilizzare:

```python
print()
```

I messaggi devono distinguere:

* informazioni operative;
* warning;
* errori;
* attività di sincronizzazione.

---

# Testing

Ogni nuova funzionalità deve includere test.

Obiettivi:

* test unitari per logica di dominio;
* mock delle API esterne;
* test del comportamento incrementale;
* test dei casi di errore.

Le chiamate reali a YouTube API non devono essere richieste nei test automatici.

---

# Qualità del codice

Prima di considerare completata una modifica:

Eseguire:

```bash
ruff check .
ruff format .
pytest
mypy .
```

Il codice deve:

* evitare duplicazioni;
* utilizzare nomi descrittivi;
* mantenere funzioni brevi;
* preferire composizione rispetto a ereditarietà.

---

# Gestione Git

Ogni modifica deve essere isolata in commit comprensibili.

Esempi:

```
Add database models
Implement youtube synchronization service
Add transcript extraction fallback
```

Evitare commit generici:

```
fix
update
changes
```

---

# Documentazione

Ogni modifica significativa deve aggiornare:

* README.md;
* documentazione tecnica se necessaria;
* esempi CLI.

La documentazione deve descrivere:

* installazione;
* configurazione;
* utilizzo;
* troubleshooting.

---

# Regole per Codex

Quando implementi nuove funzionalità:

1. leggere sempre `SPEC.md`;
2. analizzare il codice esistente prima di modificare;
3. proporre un piano se la modifica coinvolge più componenti;
4. evitare refactoring non richiesti;
5. non introdurre dipendenze senza motivazione;
6. mantenere il progetto funzionante dopo ogni modifica.

Quando esistono più soluzioni possibili, privilegiare:

* quella più semplice;
* quella più facilmente manutenibile;
* quella con meno dipendenze.

---

# Definition of Done

Una funzionalità è completata solo quando:

* [ ] implementazione conforme a SPEC.md;
* [ ] test aggiunti o aggiornati;
* [ ] controlli qualità superati;
* [ ] documentazione aggiornata;
* [ ] nessun segreto presente nel repository;
* [ ] comportamento verificabile da CLI.
