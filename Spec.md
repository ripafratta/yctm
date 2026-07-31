# Specifica Normativa Architetturale e Funzionale (YCTM)

## Scopo

Questo documento è la fonte primaria per: la specifica dei requisiti di prodotto, gli attori supportati, il modello operativo, la macchina a stati ed i non-obiettivi espliciti del sistema.

Non contiene: esempi esaustivi d'uso della CLI (vedi [docs/cli-reference.md](docs/cli-reference.md)), la guida di sviluppo per gli agenti (vedi [AGENTS.md](AGENTS.md)) o la descrizione dei componenti tecnici ORM/SQLAlchemy (vedi [docs/database.md](docs/database.md)).

Documenti correlati:
* [README.md](README.md) — Panoramica e quickstart.
* [docs/architecture.md](docs/architecture.md) — Architettura a livelli e flussi di sistema.
* [docs/database.md](docs/database.md) — Modello dati ed entità relazionali.
* [docs/adr/0001-neutral-source-catalog.md](docs/adr/0001-neutral-source-catalog.md) — ADR sul catalogo neutrale.
* [docs/adr/0002-explicit-transcript-fetch.md](docs/adr/0002-explicit-transcript-fetch.md) — ADR su separazione discovery/fetch.

---

## 1. Scopo del Sistema

**YouTube Channel Transcript Monitor (YCTM)** è uno strumento a riga di comando (CLI) ad esecuzione manuale (*on-demand*) destinato alla registrazione delle fonti YouTube (canali e playlist), al discovery dei metadati dei video ed all'estrazione puntuale delle trascrizioni.

YCTM è un **catalogo locale, generico e neutrale** di fonti e video YouTube. Il sistema non conosce utilizzi editoriali, criteri di rilevanza o ranking e non genera né pubblica artefatti, manifest o esportazioni per consumatori esterni.

---

## 2. Attori ed Utilizzatori Ammessi

1. **Utente Umano**: Esegue comandi dalla CLI per gestire le fonti, monitorare il catalogo e scaricare trascrizioni di specifico interesse.
2. **Script ed Automazioni Locali**: Invocano la CLI di YCTM come strumento di utilità privo di stato persistente proprio.
3. **Agenti ed Applicazioni Esterne (es. Knowledge Base / LLM)**: Interagiscono con YCTM esclusivamente tramite l'interfaccia CLI pubblica o consultando direttamente i documenti Markdown generati sul filesystem locale.

---

## 3. Modello Operativo

Il ciclo di vita operativo di YCTM è articolato su quattro fasi distinte:

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. REGISTRAZIONE│───▶│ 2. DISCOVERY    │───▶│ 3. CONSULTAZIONE│───▶│ 4. FETCH        │
│    FONTI        │    │    METADATI     │    │    CATALOGO     │    │    TRANSCRIPT   │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

1. **Registrazione Fonti**: Registrazione nel database locale di canali (ID `UC...` o `@handle`) o playlist (ID `PL...`).
2. **Discovery Metadati**: Interrogazione della YouTube Data API v3 per censire i video scoperti. Ogni video viene registrato con lo stato iniziale `not_requested`. **Nessuna chiamata all'estrattore di trascrizioni viene effettuata durante il discovery**.
3. **Consultazione Catalogo**: Ispezione ed elencazione del catalogo locale tramite filtri (`status`, `channel`, `playlist`, date, ecc.) con output tabellare o JSON.
4. **Fetch Puntuale Transcript**: Scaricamento ed archiviazione su filesystem del transcript per uno specifico video censito nel catalogo, innescato **esclusivamente su richiesta esplicita dell'utente o client**.

---

## 4. Stati Tecnici di Acquisizione dei Video

Lo stato del video riguarda **esclusivamente la gestione tecnica dell'acquisizione della trascrizione**:

* `not_requested`: Video scoperto e registrato nel catalogo locale; la trascrizione non è ancora stata richiesta.
* `stored`: Trascrizione scaricata con successo e salvata come file Markdown nel filesystem (Stato terminale).
* `retryable_error`: Richiesta di download fallita per un errore temporaneo (es. errore di rete, timeout HTTP, rate-limit 429).
* `terminal_error`: Richiesta di download fallita in via definitiva (trascrizioni disabilitate dal creator, video privo di sottotitoli o 3 tentativi di retry esauriti) (Stato terminale).

---

## 5. Non-Obiettivi Espliciti

YCTM **non deve**:
* Integrazione diretta con LLM, librerie di AI generative o prompt engineering.
* Gestione di Knowledge Base (KB), concetti di scope, review status, ranking o punteggi di rilevanza semantica.
* Generazione di manifest JSONL, file di esportazione o feed destinati a consumer esterni.
* Chunking, riassunto, traduzione automatica o modifica del testo originale delle trascrizioni.
* Processi residenti in memoria, demoni di sottofondo o meccanismi di scheduling automatico.
* Interfacce grafiche (GUI) o server web/REST.

---

## 6. Criteri di Accettazione ad Alto Livello

* **Neutralità e Tracciabilità**: Ogni trascrizione salvata deve essere un documento Markdown unitario completo di frontmatter YAML indicante provenienza (`video_id`, `channel_id`, `source`, `published_at`, `extracted_at`, `language`).
* **Idempotenza**: La registrazione di fonti o video già presenti nel database non deve produrre duplicati o errori.
* **Separazione Netta**: Nessuna operazione di discovery deve invocare servizi di estrazione trascrizioni (`youtube-transcript-api`).
* **Sicurezza Transazionale**: In caso di errore durante il salvataggio o il commit su database durante un fetch, eventuali file orfani creati su disco devono essere immediatamente compensati tramite eliminazione.
