# Plan: Roadmap e Attività Aperte YCTM

## Scopo

Questo documento riassume lo stato del progetto, le milestone completate e le attività aperte o future per YCTM.

Documenti correlati:
* [SPEC.md](SPEC.md) — Fonte primaria normativa per i requisiti funzionali.
* [CHANGELOG.md](CHANGELOG.md) — Registro sintetico dei cambiamenti rilasciati.

---

## Stato del Progetto

Il rifattorizzazione di YCTM a **catalogo locale neutrale di fonti e trascrizioni YouTube** è completato al 100%.

Tutte le milestone primarie (configurazione, catalogo relazionale N:M, discovery Data API v3, fetch puntuale innertube, gestione integrità e suite CLI) sono state implementate, testate ed integrate.

---

## Attività Future Opzionali (Roadmap)

Le seguenti attività rappresentano possibili evoluzioni future ed ottimizzazioni non bloccanti:

- [ ] **Esportazione Sottotitoli VTT/SRT**: Valutare il supporto all'esportazione opzionale in formato VTT o SRT affiancato al formato Markdown nativo.
- [ ] **Filtro per Lingua nel Discovery**: Consentire di specificare una lingua preferita durante la consultazione o il discovery.
- [ ] **Miglioramento CLI Progress Bar**: Aggiungere indicatori visivi di progresso durante i comandi di `discover all` su cataloghi con centinaia di fonti registrate.
