# 0013 – Controlli pre-run e comando `check`

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 15 chiede un elenco di errori bloccanti e avvisi, ciascuno con messaggio IT/EN, riferimento all'oggetto e suggerimento; la sezione 21 un registro `Check`. Fino all'incremento 7 ogni comando si fermava al primo errore, quindi l'utente correggeva un problema per volta.

## Decisione

- **Fasi.** `check` assembla il modello come farà `build`, in fasi: tempo, griglia, parametri, carichi iniziali, condizioni al contorno, controlli del modello. Una fase che dipende da una fase con errori non viene eseguita e il risultato dice da quale dipende (carichi iniziali dalla griglia; condizioni al contorno da tempo, griglia e parametri).
- **Raccolta degli errori.** I caricamenti ricevono un `ErrorCollector`. Di default solleva il primo errore, come in `grid`, `params`, `bc` e nel futuro `build`. In `check` raccoglie un errore per riga di `param_values`, per unità e per feature delle condizioni al contorno, così l'elenco è completo in un solo passaggio. Tempo, griglia e carichi iniziali riportano il primo errore, perché sono vincoli globali.
- **Registro `Check`.** Ogni controllo dichiara nome, etichette, severità, fasi richieste e funzione. Gira solo se le fasi richieste sono passate; altrimenti risulta saltato. I controlli dentro i caricamenti restano dove sono, perché ne dipende la costruzione stessa del modello.
- **Controlli del modello di M1a.**
  - Periodo stazionario iniziale senza carichi imposti attivi (errore). Con soli flussi assegnati la soluzione stazionaria è indeterminata (nota a meno di una costante) oppure non esiste.
  - Pozzo con filtro in celle a carico imposto (avviso). Lì il carico non cambia e la portata arriva dal contorno.
  - Ordine di grandezza (avviso). Portata di un pozzo oltre 200 l/s; ricarica oltre 3000 mm/anno oppure non nulla sotto 1 mm/anno. Le soglie individuano i fattori tipici di un'unità sbagliata (86,4 tra l/s e m³/d, 365,25 tra mm/d e mm/anno) e non sono limiti fisici.
  - Formulazione di Newton disattivata con unità convertibili (avviso). Le celle che si asciugano diventano inattive e la ricarica su di esse si perde.
- **Comando `check`.** Stampa lo stato di ogni fase, poi tutti gli errori, poi tutti gli avvisi, con codice, oggetto (layer, fid, campo) e suggerimento, e l'esito. Con `--json` emette un evento `error` o `warning` per ciascuno e un `result` con il riepilogo. Se ci sono errori termina con `check.failed` e codice di uscita 1.

## Alternative scartate

- **Fermarsi al primo errore anche in `check`.** È l'uso tipico di un modello in costruzione ad avere più errori insieme.
- **Eseguire le condizioni al contorno con parametri provvisori quando i parametri hanno errori.** I risultati intermedi sarebbero inventati; meglio dichiarare la fase non eseguita.
- **Soglie di plausibilità per litologia o per tipo di pozzo.** Richiedono dati che arrivano con M2 e M8.

## Conseguenze

- `build` (incremento 9) userà la stessa ispezione e si fermerà se ci sono errori, con gli avvisi registrati nel log del run.
- Le soglie di plausibilità sono costanti del modulo `phrear.checks.model_checks` e potranno diventare impostazioni del progetto se servirà.
