# ADR 0001: Catalogo Neutrale per le Fonti YouTube

## Stato
Accettata

## Contesto
Nelle fasi iniziali di progettazione, YCTM prevedeva l'integrazione diretta con consumer esterni, la pubblicazione di manifest JSONL e la tracciabilità di punteggi di rilevanza semantica, scope o review status per Knowledge Base (KB) o sistemi LLM.

Questa impostazione introduceva un forte accoppiamento con casi d'uso editoriali specifici e complicava il dominio applicativo con campi e concetti non appartenenti al problema base dell'acquisizione dei dati da YouTube.

## Decisione
Si è deciso di ridefinire YCTM come un **servizio locale, generico e neutrale di catalogazione delle fonti YouTube e di recupero controllato dei transcript**.

YCTM gestisce esclusivamente:
- La registrazione di fonti (canali e playlist).
- Il discovery incrementale dei metadati dei video.
- La consultazione del catalogo locale.
- Il recupero puntuale ed esplicito delle trascrizioni.

YCTM **non contiene**:
- Dipendenze o integrazioni dirette con sistemi LLM.
- Generatori di manifest o esportatori per consumer specifici.
- Campi di scope, rilevanza semantica o status editoriale.

## Conseguenze
- **Positive**: Dominio applicativo essenziale, manutenibile e stabile nel tempo. Nessun accoppiamento con consumer esterni.
- **Negative**: I consumer esterni (es. sistemi KB o LLM Wiki) devono orchestrare autonomamente l'ingestione leggendo la CLI di YCTM o i file Markdown generati sul filesystem.

## Alternative Considerate
- Mantenere un modulo di pubblicazione manifest JSONL interno a YCTM (Scartata per evitare accoppiamento con formati di ingestion specifici).
