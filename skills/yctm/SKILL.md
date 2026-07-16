---
name: yctm
description: "Advanced operations for YouTube Channel Transcript Monitor (YCTM). Use this skill to perform batch synchronization, database maintenance, proxy rotation, and integration with LLM Wiki downstream pipelines."
---

# YCTM Operations Skill

Questa skill fornisce istruzioni operative, script e query SQL per l'utilizzo avanzato di **YouTube Channel Transcript Monitor (YCTM)**. È progettata sia per gli operatori umani che per agenti AI che devono orchestrare YCTM in scenari di produzione, gestire grandi volumi di dati o risolvere problemi di quota e rate-limiting.

> **Installazione specifica per piattaforma:** vedi [references/](references/) per
> guide dedicate a Claude Code, Codex, Gemini CLI e altri agenti.

---

## 1. Architettura dei Dati e Flusso Operativo

YCTM si basa su un principio fondamentale: **separazione tra metadati (SQLite) e contenuti (Filesystem)**.
Le trascrizioni estratte non vengono mai caricate nel database per mantenere quest'ultimo leggero e veloce.

### Tabella degli Stati dei Video

Ogni video nel database SQLite passa attraverso i seguenti stati (definiti in `AcquisitionStatus`):

| Stato | Significato | Comportamento in Sincronizzazione |
| :--- | :--- | :--- |
| `pending` | Video rilevato ma non ancora elaborato. | Verrà processato nella prossima run. |
| `stored` | Trascrizione salvata con successo su filesystem. | **Terminale**: Ignorato e attiva l'early exit. |
| `retryable_error` | Errore temporaneo (es. rete, blocco IP o `NoTranscriptFound`). | Verrà riprovato fino a 3 tentativi totali. |
| `terminal_error` | Raggiunti 3 fallimenti o trascrizioni disabilitate. | **Terminale**: Ignorato e attiva l'early exit. |

> [!IMPORTANT]
> **Early Exit (Sincronizzazione Incrementale):**
> Sia `yctm sync` che `yctm playlist-sync` scorrono i video dal più recente al più vecchio. Appena incontrano un video in stato `stored` o `terminal_error`, interrompono immediatamente la scansione per risparmiare API quota.

---

## 2. Gestione Avanzata del Database (CLI)

Oltre ai comandi base, YCTM offre strumenti integrati per la manutenzione del database.

### Visualizzare le Statistiche di Acquisizione

Usando lo script di manutenzione (`scripts/db_maintenance.py`):

```bash
python3 skills/yctm/scripts/db_maintenance.py stats
```

Oppure direttamente via SQL:

```sql
SELECT status, COUNT(*) as count 
FROM videos 
GROUP BY status;
```

### Resettare i Video in Errore (Comando Integrato)

YCTM ha un comando nativo per resettare lo stato dei video:

```bash
# Resetta i video con errore temporaneo
yctm reset retryable

# Resetta i video con errore terminale
yctm reset terminal

# Resetta entrambi
yctm reset all
```

Il comando resetta anche `attempt_count` e `last_error`, permettendo ai video
di essere riprocessati alla prossima sincronizzazione.

In alternativa, lo script `scripts/db_maintenance.py` permette filtri più granulari
(per singolo canale o video):

```bash
# Statistiche di acquisizione
python3 skills/yctm/scripts/db_maintenance.py stats

# Reset di tutti i video in terminal_error
python3 skills/yctm/scripts/db_maintenance.py reset-errors

# Reset per un canale specifico
python3 skills/yctm/scripts/db_maintenance.py reset-errors --channel UC...

# Reset per un video specifico
python3 skills/yctm/scripts/db_maintenance.py reset-errors --video abc123
```

---

## 3. Mitigazione del Rate-Limiting e Uso dei Proxy

L'estrazione delle trascrizioni avviene tramite `youtube-transcript-api` che non richiede chiavi API, ma interroga direttamente gli endpoint web di YouTube. Questo espone l'IP a temporanei blocchi.

### Delay Integrato

Per mitigare i blocchi, YCTM applica automaticamente un delay di **2 secondi** tra una richiesta di trascrizione e la successiva, sia in `sync` che in `playlist-sync`. Il delay è applicato tramite `try/except/else/finally` per garantire che scatti sempre dopo ogni estrazione, successo o errore che sia.

### Modalità Interattiva

I comandi `sync` e `playlist-sync` supportano il flag `--interactive` (o `-i`)
per chiedere conferma prima di scaricare ogni trascrizione:

```bash
yctm sync UC... --max-results 5 --interactive
```

Il prompt mostra autore, titolo e data di pubblicazione del video:

```
Vito Lops — "Mercati al bivio: rimbalzo tech o nuova ondata di volatilità?" (2026-07-12)
  Scaricare la trascrizione? [Y/n]:
```

- **Invio / Y / yes** → scarica la trascrizione
- **n / no** → salta il video (ricomparirà alla prossima sincronizzazione)

### Configurazione di Proxy
YCTM rispetta le variabili d'ambiente standard di sistema per i proxy. È possibile configurare un proxy HTTP/S prima di avviare la sincronizzazione:

```bash
# Definizione del proxy nella sessione corrente
export HTTP_PROXY="http://username:password@proxy.example.com:8080"
export HTTPS_PROXY="http://username:password@proxy.example.com:8080"

# Esecuzione del comando YCTM con proxy attivo
yctm sync UCqCYKSvF_sJl78-bxD5q6NQ
```

> [!TIP]
> Nelle esecuzioni batch o schedulate, si consiglia di ruotare i proxy o utilizzare servizi di proxy rotativi residenziali per evitare interruzioni se si sincronizzano centinaia di video contemporaneamente.

---

## 4. Automazione Batch: Sincronizzazione di Tutti i Canali

YCTM non implementa un demone residente. Per sincronizzare tutti i canali registrati nel database in un colpo solo, si consiglia di utilizzare il seguente script di automazione (disponibile sotto `scripts/`).

### Script di Esecuzione Batch (`scripts/sync_all.py`)
Lo script esegue:
1. Lettura di tutti i canali registrati nel database SQLite.
2. Invocazione sequenziale del comando di sync per ciascuno.
3. Gestione e tracciamento degli errori per canale.
4. Ricostruzione finale del manifest JSONL.

Vedere [sync_all.py](file:///Users/marco/Desktop/GitHub/yctm/skills/yctm/scripts/sync_all.py) per il codice sorgente completo dello script.

---

## 5. Ingestione Downstream (Contratto LLM Wiki)

Il manifest `data/manifest.jsonl` viene rigenerato atomicamente al termine di ogni sincronizzazione. Il formato è JSON Lines (JSONL), ideale per l'ingestione incrementale in database vettoriali o LLM Wiki.

Ogni riga rappresenta un record del database. Esempio di riga per un video acquisito con successo (`stored`):

```json
{
  "video_id": "b7DQyS1yFCU",
  "channel_id": "UCqCYKSvF_sJl78-bxD5q6NQ",
  "title": "Mercati al bivio: rimbalzo tech o nuova ondata di volatilità?",
  "published_at": "2026-07-12T07:31:46",
  "status": "stored",
  "last_error": null,
  "storage_path": "data/transcripts/20260712_b7DQyS1yFCU_mercati_al_bivio.md",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "language_code": "it",
  "extracted_at": "2026-07-12T20:20:23"
}
```

### Regole per il Consumatore LLM Wiki:
1. **Filtrare per Stato**: Leggere ed elaborare esclusivamente le righe in cui `"status": "stored"`.
2. **Controllo Duplicati / Aggiornamenti**: Utilizzare il campo `sha256` per verificare se il contenuto del file di trascrizione è cambiato rispetto all'ultima lettura.
3. **Lettura del File**: Il percorso effettivo del file di trascrizione è indicato in `storage_path`. Il file è in formato Markdown (`.md`) e contiene un frontmatter YAML con i metadati del video (canale, titolo, lingua, data, descrizione), seguito dal testo della trascrizione senza alcuna modifica o chunking.

### Formato del File di Trascrizione

Le trascrizioni vengono salvate come file Markdown con frontmatter YAML:

```markdown
---
title: "Mercati al bivio: rimbalzo tech o nuova ondata di volatilità?"
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

Il nome del file segue la convenzione `{YYYYMMDD}_{video_id}_{titolo_sanificato}.md`.
