# Installazione Skill YCTM — Gemini CLI

## Requisiti

- Gemini CLI installato
- CLI YCTM installata e funzionante (`pip install -e .`)

## Installazione

Le skill in Gemini CLI vengono attivate tramite l'apposito strumento
`activate_skill`. Per installare la skill YCTM:

```bash
# Copia la skill nella directory skills di Gemini CLI
mkdir -p ~/.gemini/skills
cp -r skills/yctm ~/.gemini/skills/yctm
```

Poi attivala nella sessione Gemini CLI usando il comando di attivazione skill
della piattaforma.

## Verifica

In una sessione Gemini CLI, verifica che la skill sia disponibile usando
il comando di elenco skill della piattaforma (`/skills` o equivalente).

> **Nota:** Gemini CLI utilizza un sistema di attivazione skill nativo con
> lo strumento `activate_skill`. La directory di installazione esatta può
> variare in base alla versione. Consulta la documentazione ufficiale per
> la procedura aggiornata.
