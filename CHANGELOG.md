# Changelog (YCTM)

Tutti i cambiamenti di rilievo apportati a YCTM sono documentati in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

---

## [Unreleased]

### Aggiunto
- **Relazione Molti-a-Molti Playlist-Video**: Introdotta la tabella di associazione `playlist_videos` con chiave primaria composita `(playlist_id, video_id)` per unire le playlist ai video catalogati in modo idempotente.
- **Filtro CLI `--playlist`**: Abilitato il filtraggio dei video per playlist nel comando `yctm video list --playlist PLAYLIST_ID`.
- **Comando `yctm doctor`**: Aggiunto comando di diagnostica per verificare l'integrità tra database e filesystem (rilevamento file orfani e record con file mancanti).
- **Compensazione Transazionale Immediata**: In `yctm transcript fetch`, qualora il commit su SQLite fallisca dopo la scrittura su disco, il file Markdown orfano viene immediatamente rimosso.
- **Suite di Test Estesa**: Aggiunti test e2e CLI, test di integrità file/SHA-256, test di migrazione schema SQLite e test di classificazione delle eccezioni HTTP 429/quota/500 (90 test unitari ed integrazionali attivi).
- **Nuova Struttura di Documentazione**: Creazione della directory `docs/` contenente `architecture.md`, `cli-reference.md`, `database.md`, `troubleshooting.md`, la cartella `docs/adr/` (ADR 0001, 0002, 0003) e l'archivio storico `docs/history/`.

### Modificato
- **Architettura Catalogo Neutrale**: Rimozione totale delle dipendenze da KB, manifest JSONL, tag di rilevanza o scope editoriali.
- **Separazione Discovery / Fetch**: `yctm discover` acquisisce solo i metadati (Data API v3) senza scaricare trascrizioni; `yctm transcript fetch` opera solo su richiesta esplicita per video a catalogo.
- **Dipendenze pyproject.toml**: Aggiunta esplicita di `youtube-transcript-api` alle dipendenze di runtime.
- **Deprecazione Script Legacy**: Deprecati gli script imperfetti in `skills/yctm/scripts/` in favore delle funzioni CLI native `yctm discover all`, `yctm stats` e `yctm transcript reset`.

---

## [0.1.0] - 2026-07-20

### Aggiunto
- Inizializzazione della prima versione della CLI YCTM con Typer.
- Modelli ORM base per Canali, Playlist, Video e TranscriptFile.
- Estrattore di trascrizioni con fallback linguistico (manuale IT/EN -> ASR IT/EN).
