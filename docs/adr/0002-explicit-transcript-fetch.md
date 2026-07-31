# ADR 0002: Separazione Netta tra Discovery e Fetch Transcript

## Stato
Accettata

## Contesto
I primi modelli operativi di YCTM scaricavano automaticamente i transcript di tutti i video individuati durante la scansione di un canale. Questo comportamento causava un elevato ed ingiustificato numero di richieste HTTP verso gli endpoint web di YouTube, provocando frequenti blocchi di IP (HTTP 429 Rate Limiting) e spreco di risorse per video non d'interesse.

## Decisione
Si è deciso di separare in modo rigido ed esplicito le due fasi operative:

1. **Discovery (Metadati)**: Interroga unicamente la YouTube Data API v3 per censire titolo, descrizione e data di pubblicazione. Imposta lo stato a `not_requested` e **non effettua alcuna chiamata all'estrattore di sottotitoli**.
2. **Transcript Fetch (Estrazione)**: Avviene **esclusivamente su richiesta esplicita ed individuale** per uno specifico `video_id` già catalogato.

## Conseguenze
- **Positive**: Consumo di quota minimizzato, rischio di blocchi rate-limiting azzerato durante la scansione delle fonti, totale controllo dell'utente su quali trascrizioni scaricare.
- **Negative**: Impossibilità di effettuare il download massivo automatico "in un solo passaggio" senza un loop/script esplicito lato utente.

## Alternative Considerate
- Download automatico dei transcript con throttling durante il discovery (Scartata per evitare rate-limiting e rispettare il principio di estrazione controllata).
