# ADR 0003: Relazione Molti-a-Molti tra Playlist e Video

## Stato
Accettata

## Contesto
Nella prima versione del modello dati relazionale, la relazione tra `Playlist` e `Video` era assente o implicitamente modellata come 1:N (un video associato ad una singola playlist). Su YouTube, tuttavia, uno stesso video può appartenere a molteplici playlist (es. caricamenti generali, serie tematiche, corsi) e viceversa.

L'assenza di una tabella di associazione rendeva inefficace il filtraggio CLI `yctm video list --playlist PLAYLIST_ID`.

## Decisione
Si è deciso di modellare la relazione tra `Playlist` e `Video` come **relazione molti-a-molti (N:M)** tramite una tabella di associazione dedicata `playlist_videos`.

La tabella impiega una **Chiave Primaria composita `(playlist_id, video_id)`**, che garantisce l'idempotenza degli inserimenti tramite il vincolo di unicità a livello di database.

## Conseguenze
- **Positive**: Rappresentazione fedele delle strutture di YouTube; filtraggio CLI `--playlist` pienamente funzionante ed accurato; inserimento associazione idempotente via `ON CONFLICT DO NOTHING`.
- **Negative**: Richiede una JOIN esplicita nelle query di filtraggio `list_videos`.

## Alternative Considerate
- Foreign key unica `playlist_id` sulla tabella `videos` (Scartata perché impediva l'appartenenza a più playlist).
