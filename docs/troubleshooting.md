# Guida alla Risoluzione dei Problemi (Troubleshooting)

## Scopo

Questo documento è la fonte primaria per: la diagnosi, la gestione delle eccezioni, la mitigazione degli errori tecnici e le procedure di ripristino operativo in YCTM.

Non contiene: la specifica dei requisiti (vedi [SPEC.md](../SPEC.md)) o il riferimento completo dei comandi CLI (vedi [docs/cli-reference.md](cli-reference.md)).

Documenti correlati:
* [docs/cli-reference.md](cli-reference.md) — Riferimento comandi CLI.
* [docs/database.md](database.md) — Dettagli su persistenza e integrità.

---

## 1. Problemi di Configurazione ed API Key

### Errore: `YouTubeAPIError` / API Key Mancante
* **Causa**: La variabile d'ambiente `YCTM_YOUTUBE_API_KEY` non è stata impostata o il file `.env` non è presente.
* **Soluzione**: Verificare che il file `.env` esista nella radice del progetto e contenga una chiave valida per le YouTube Data API v3:
  ```ini
  YCTM_YOUTUBE_API_KEY=AIzaSy...
  ```

### Errore: `QuotaExceededError` (Exit Code 4)
* **Causa**: È stata superata la quota giornaliera di unità per la YouTube Data API v3 (solitamente 10.000 unità/giorno per progetto GCP).
* **Soluzione**: Ridurre la frequenza di discovery o impostare un valore più basso per `--max-results`. Attendere il reset della quota giornaliera (mezzanotte PST).

---

## 2. Rate-Limiting e Blocchi sull'Estrazione Trascrizioni

L'estrazione dei transcript via `youtube-transcript-api` (endpoint web innertube) non consuma quota API YouTube, ma è soggetta ad IP rate-limiting e blocchi anti-scraping da parte di YouTube.

### Errore: HTTP 429 Too Many Requests
* **Causa**: YouTube ha temporaneamente bloccato l'indirizzo IP a causa di troppe richieste ravvicinate.
* **Soluzioni**:
  1. **Aumentare il delay tra fetch**: Impostare nel file `.env` un intervallo di attesa superiore tra i comandi:
     ```ini
     YCTM_TRANSCRIPT_FETCH_DELAY=30
     ```
  2. **Utilizzare Cookie Netscape Autenticati**: Esportare i cookie da una sessione browser attiva ed utilizzarli tramite opzione CLI o `.env`:
     ```bash
     yctm transcript fetch VIDEO_ID --cookies data/cookies.txt
     ```
  3. **Proxy HTTP/HTTPS**: Impostare le variabili d'ambiente per instradare il traffico tramite un proxy:
     ```bash
     export HTTP_PROXY="http://user:pass@proxy.example.com:8080"
     export HTTPS_PROXY="http://user:pass@proxy.example.com:8080"
     ```

---

## 3. Gestione Stati d'Errore dei Video (`retryable_error` vs `terminal_error`)

* **`retryable_error`**: Indica che il download è fallito per un motivo temporaneo (rete, timeout, HTTP 429). Si può riprovare l'estrazione eseguendo:
  ```bash
  yctm transcript retry VIDEO_ID
  ```
  oppure resettando massivamente gli errori temporanei:
  ```bash
  yctm transcript reset --status retryable_error
  ```
* **`terminal_error`**: Indica che i sottotitoli sono disabilitati dal creator del video, il video non possiede trascrizioni o sono stati superati i 3 tentativi consecutivi di retry.

---

## 4. Diagnostica ed Integrità Database/Filesystem

### Risoluzione Disallineamenti con `yctm doctor`
Qualora si sospettino disallineamenti tra i record nel database SQLite e i file Markdown archiviati su disco, eseguire:

```bash
yctm doctor
```

Il comando rileverà ed elencherà:
- **File orfani**: File `.md` presenti nella directory delle trascrizioni ma non associati ad alcun video nel DB.
- **Record incompleti**: Video marcati come `stored` ma con il file `.md` mancante dal filesystem.

### Ripristino Schema Database (`yctm db upgrade`)
Se a seguito di un aggiornamento di versione il database SQLite riscontra colonne o tabelle mancanti, aggiornare lo schema mediante:

```bash
yctm db upgrade
```
