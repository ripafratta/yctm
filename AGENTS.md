# AGENTS.md — Guida Operativa per Coding Agent e Manutentori

## Scopo

Questo documento è la fonte primaria per: gli standard di sviluppo, le regole architetturali non negoziabili, i comandi di verifica della qualità ed i criteri di Definition of Done per i maintainer e gli agenti di codifica automatizzata.

Non contiene: la specifica dei requisiti di prodotto (vedi [SPEC.md](SPEC.md)) o il manuale utente completo della CLI (vedi [docs/cli-reference.md](docs/cli-reference.md)).

Documenti correlati:
* [SPEC.md](SPEC.md) — Fonte primaria normativa per i requisiti funzionali.
* [docs/architecture.md](docs/architecture.md) — Dettagli dell'architettura del software.
* [docs/database.md](docs/database.md) — Regole e modelli del database SQLite.

---

## 1. Gerarchia delle Fonti di Verità

In caso di ambiguità o apparenti conflitti tra i documenti del repository:
1. **`SPEC.md`** prevale per quanto riguarda i requisiti funzionali e di prodotto.
2. **`AGENTS.md`** prevale per quanto riguarda gli standard implementativi, la qualità del codice e le regole operative di sviluppo.
3. **Il Codice ed i Test (`src/` e `tests/`)** costituiscono l'autorità finale per determinare il comportamento effettivo del sistema ed il funzionamento corretto delle funzionalità esistenti.

---

## 2. Principi Architetturali Non Negoziabili

* **CLI Sottile**: Il livello `src/yctm/cli/` deve occuparsi esclusivamente del parsing degli argomenti, della validazione degli input dell'utente e della formattazione dell'output.
* **Livello Applicativo Indipendente**: I moduli in `src/yctm/application/` non devono importare `typer` né dipendere dal livello CLI.
* **Infrastruttura Isolata**: Il database, le API di YouTube ed il filesystem risiedono in `src/yctm/infrastructure/` e sono isolati dalla logica di dominio.
* **Separazione dei Dati**: Il testo dei transcript **non deve mai essere salvato nel database SQLite**. Il DB traccia unicamente i metadati e lo stato dell'acquisizione, mentre i transcript risiedono come file `.md` separati su filesystem.
* **Logging Standard**: Usare unicamente il modulo standard `logging`. È vietato l'uso di `print()` nel codice applicativo.
* **Gestione Errore Esplicita**: È vietato utilizzare blocchi silenziosi `except Exception: pass`. Ogni eccezione deve essere tipizzata o registrata nei log.

---

## 3. Regole per Modifiche al Database e Migrazioni

* Modifiche allo schema SQLAlchemy in `src/yctm/infrastructure/database/models.py` richiedono un aggiornamento corrispondente della funzione `upgrade_database` in `src/yctm/infrastructure/database/session.py` per garantire la compatibilità con i database SQLite esistenti.
* La tabella di associazione tra `Playlist` e `Video` (`playlist_videos`) è una relazione molti-a-molti (N:M) gestita con chiave primaria composita `(playlist_id, video_id)` per garantire l'idempotenza degli inserimenti.

---

## 4. Regole per Testing e Mocking

* **Nessuna Chiamata Reale alle API**: I test automatici (`pytest`) non devono mai effettuare chiamate di rete reali verso YouTube Data API v3 o gli endpoint innertube.
* Utilizzare `unittest.mock.patch` o fixture pytest per simulare risposte HTTP ed eccezioni API.
* Ogni nuova funzionalità o correzione di bug deve includere corrispondenti test unitari o end-to-end (`tests/unit/`).

---

## 5. Comandi Obbligatori di Qualità

Prima di considerare completata qualsiasi modifica, è **obbligatorio** eseguire la seguente sequenza e verificare che non vi siano errori:

```bash
ruff check .
ruff format --check .
pytest
mypy .
```

Se la formattazione necessita di aggiustamenti, eseguire `ruff format .` prima dei controlli finali.

---

## 6. Definition of Done (DoD)

Una funzionalità o correzione è considerata completata solo quando:
- [ ] L'implementazione è conforme a `SPEC.md`.
- [ ] I test unitari ed e2e sono stati aggiunti o aggiornati e passano.
- [ ] La sequenza di controlli di qualità (`ruff`, `pytest`, `mypy`) restituisce esito positivo senza errori.
- [ ] La documentazione impattata in `docs/` o nei file radice è stata aggiornata.
- [ ] Nessun segreto, chiave API o credential è presente nel repository.
- [ ] Il comportamento è verificabile tramite riga di comando CLI.
