# Manuale di Riferimento della CLI (YCTM)

## Scopo

Questo documento è la fonte primaria per: il riferimento completo dei comandi, sotto-comandi, opzioni, sintassi, codici di uscita e formati di output dell'interfaccia a riga di comando YCTM.

Non contiene: la specifica dei requisiti di prodotto (vedi [SPEC.md](SPEC.md)) o i principi di progettazione architetturale (vedi [docs/architecture.md](architecture.md)).

Documenti correlati:
* [README.md](../README.md) — Installazione e quickstart.
* [docs/troubleshooting.md](troubleshooting.md) — Risoluzione dei problemi ed errori CLI.

---

## Opzioni Globali

Ogni comando YCTM accetta la seguente opzione globale:

* `--verbose`, `-v`: Attiva il logging dettagliato su console (livello `DEBUG`).

---

## 1. Gestione Database (`yctm init-db` / `yctm db`)

### `yctm init-db` / `yctm db init`
Inizializza lo schema del database SQLite. Se il file non esiste, viene creato assieme alle relative tabelle.

```bash
yctm init-db
yctm db init
```

### `yctm db upgrade`
Applica migrazioni leggere di schema per aggiornare database SQLite preesistenti ad una versione più recente (es. aggiunta tabelle/colonne).

```bash
yctm db upgrade
```

---

## 2. Gestione Fonti Canali (`yctm channel`)

### `yctm channel add IDENTIFIER`
Registra un nuovo canale nel catalogo locale. L'identificativo può essere un ID canonico (`UC...`), un handle (`@nomecanale`) o un URL del canale.

```bash
yctm channel add "https://www.youtube.com/@Fireship"
yctm channel add UC1234567890abcdef
```

### `yctm channel list`
Elenca tutti i canali registrati.

```bash
yctm channel list
```

### `yctm channel remove CHANNEL_ID`
Rimuove un canale dal catalogo locale.

```bash
yctm channel remove UC1234567890abcdef
```

---

## 3. Gestione Fonti Playlist (`yctm playlist`)

### `yctm playlist add IDENTIFIER`
Registra una nuova playlist nel catalogo locale tramite ID canonico (`PL...`) o URL.

```bash
yctm playlist add "https://www.youtube.com/playlist?list=PL1234567890"
```

### `yctm playlist list`
Elenca tutte le playlist registrate.

```bash
yctm playlist list
```

### `yctm playlist remove PLAYLIST_ID`
Rimuove una playlist dal catalogo locale.

```bash
yctm playlist remove PL1234567890
```

---

## 4. Discovery Metadati (`yctm discover`)

Interroga la YouTube Data API v3 per censire i video con stato iniziale `not_requested`. **Non scarica mai i transcript**.

### `yctm discover channel CHANNEL_ID`
Esegue il discovery per un canale registrato.

```bash
yctm discover channel UC1234567890 --max-results 25 --since 2025-01-01 --dry-run
```

* `--max-results INT`: Numero massimo di video da analizzare (default: configurazione ambiente).
* `--since YYYY-MM-DD`: Considera solo video pubblicati a partire da questa data.
* `--dry-run`: Simula l'operazione senza modificare il database.

### `yctm discover playlist PLAYLIST_ID`
Esegue il discovery per una playlist registrata e memorizza l'associazione molti-a-molti tra la playlist ed i video.

```bash
yctm discover playlist PL1234567890 --max-results 50
```

### `yctm discover all`
Esegue il discovery sequenziale su tutti i canali e le playlist registrati.

```bash
yctm discover all --max-results 20
```

---

## 5. Consultazione Catalogo (`yctm video`)

### `yctm video list`
Elenca i video catalogati applicando filtri avanzati.

```bash
yctm video list --status not_requested --channel UC123... --format json --limit 10
```

* `--status TEXT`: Filtra per stato (`not_requested`, `stored`, `retryable_error`, `terminal_error`).
* `--channel TEXT`: Filtra per ID canale.
* `--playlist TEXT`: Filtra per ID playlist (tramite associazione N:M).
* `--after YYYY-MM-DD`: Video pubblicati da questa data.
* `--before YYYY-MM-DD`: Video pubblicati fino a questa data.
* `--limit INT`: Limita il numero di risultati (default: 50).
* `--offset INT`: Offset di paginazione (default: 0).
* `--format table|json`: Formato di output (default: `table`).
* `--order published-desc|published-asc`: Ordinamento per data di pubblicazione.

### `yctm video show VIDEO_ID`
Mostra i dettagli completi di un singolo video catalogato.

```bash
yctm video show abc123XYZ --format json
```

### `yctm video discover VIDEO_ID`
Esegue il discovery puntuale di un singolo video tramite il suo ID YouTube e lo inserisce nel catalogo locale se non ancora presente.

```bash
yctm video discover abc123XYZ
```

---

## 6. Operazioni sulle Trascrizioni (`yctm transcript`)

### `yctm transcript fetch VIDEO_ID`
Scarica puntualmente la trascrizione di un video già censito nel catalogo locale.

```bash
yctm transcript fetch abc123XYZ --cookies data/cookies.txt
```

* `--cookies PATH`: Percorso opzionale ad un file di cookie in formato Netscape per autenticare la richiesta verso gli endpoint innertube di YouTube.

### `yctm transcript status VIDEO_ID`
Mostra lo stato tecnico di acquisizione del transcript per un dato video.

```bash
yctm transcript status abc123XYZ
```

### `yctm transcript reset [VIDEO_ID]`
Reimposta lo stato di acquisizione dei video a `not_requested`.

```bash
yctm transcript reset abc123XYZ                     # Singolo video
yctm transcript reset --status retryable_error      # Reset massivo per stato
```

### `yctm transcript retry VIDEO_ID`
Esegue una sequenza combinata di `reset` e `fetch` per un singolo video in stato d'errore.

```bash
yctm transcript retry abc123XYZ
```

---

## 7. Diagnostica e Statistiche

### `yctm stats`
Visualizza le statistiche aggregate sul catalogo (totale canali, playlist, video per stato e transcript archiviati).

```bash
yctm stats
```

### `yctm doctor`
Esegue una verifica di integrità incrociando i record del database SQLite con i file `.md` presenti su filesystem, evidenziando file orfani o record incompleti.

```bash
yctm doctor
```

---

## 8. Comandi Deprecati

I seguenti comandi sono mantenuti esclusivamente per retrocompatibilità ed emettono un messaggio di avvertimento su stderr:

* `yctm sync`: Deprecato in favore di `yctm discover channel`.
* `yctm playlist-sync`: Deprecato in favore di `yctm discover playlist`.

---

## 9. Codici di Uscita CLI (Exit Codes)

| Codice | Significato |
|---|---|
| `0` | Operazione completata con successo. |
| `1` | Errore generico o parametri CLI non validi. |
| `2` | Risorsa o video non trovato / non presente a catalogo. |
| `3` | Errore di chiamata alla YouTube Data API v3 o errore di rete. |
| `4` | Quota giornaliera YouTube Data API v3 superata. |
