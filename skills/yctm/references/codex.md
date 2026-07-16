# Installazione Skill YCTM — Codex

## Requisiti

- Codex installato
- CLI YCTM installata e funzionante (`pip install -e .`)

## Installazione

Codex rileva automaticamente le skill presenti nella directory `.claude/skills/`
del progetto.

```bash
# Dalla root del progetto YCTM
mkdir -p .claude/skills
ln -sf "$(pwd)/skills/yctm" .claude/skills/yctm
```

In alternativa, estrai il pacchetto .skill:

```bash
unzip -o skills/yctm.skill -d .claude/skills/
```

## Verifica

Avvia Codex in una sessione nella directory del progetto. La skill dovrebbe
essere caricata automaticamente e attivabile tramite `/yctm`.

> **Nota:** Skills in Codex sono caricate nativamente dal contesto del progetto.
> Consulta la documentazione ufficiale di Codex per eventuali aggiornamenti
> sul meccanismo di caricamento.
