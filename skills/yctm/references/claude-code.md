# Installazione Skill YCTM — Claude Code

## Requisiti

- Claude Code installato
- CLI YCTM installata e funzionante (`pip install -e .`)

## Installazione

### Opzione A: Da pacchetto .skill (consigliato)

```bash
# Estrai il pacchetto nella directory skills utente
unzip -o skills/yctm.skill -d ~/.claude/skills/
```

### Opzione B: Collegamento diretto alla directory sorgente

```bash
ln -sf "$(pwd)/skills/yctm" ~/.claude/skills/yctm
```

Riavvia Claude Code. La skill `/yctm` sarà automaticamente disponibile.

## Verifica

In una sessione Claude Code, digita `/yctm` — dovresti vedere le istruzioni
operative della skill.
