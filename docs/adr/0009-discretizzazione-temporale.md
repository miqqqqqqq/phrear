# 0009 – Discretizzazione temporale

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 13 della spec stabilisce stress period solo ai cambi di regime e serie temporali che variano dentro i periodi tramite i file TS di MODFLOW 6. Servivano regole precise su significato delle serie, attivazione degli oggetti, periodo stazionario, accorpamento dei periodi brevi e passi temporali.

## Decisione

- **Significato delle serie.**
  - Prima della prima data una serie non è definita, e l'oggetto che la usa è inattivo.
  - A gradino: ogni valore vale dalla sua data fino alla successiva, e l'ultimo fino alla fine del modello.
  - Lineare: interpolazione tra i punti. Dopo l'ultimo punto la serie non è definita, quindi una serie lineare in uso deve arrivare almeno alla fine del modello (errore `series.not_covered`).
- **Cambi di regime.** Un nuovo stress period inizia all'avvio del modello, a ogni data di `model.period_breaks` e alla prima data di ogni serie in uso, che è l'attivazione dell'oggetto. Le altre variazioni delle serie entrano tramite TS.
- **Serie in uso.** Sono quelle richiamate da feature attive del modello base. Un richiamo a una serie non definita è un errore (`series.not_defined`).
- **Periodo stazionario.** È il primo periodo, lungo 1 d. Il tempo di simulazione 0 cade quindi un giorno prima di `start_date`, e ogni data passata a MF6 va convertita con `Calendar.sim_time`. I valori sono le medie esatte delle serie sul periodo di riferimento `model.steady_reference`, oppure i valori a `start_date`. Gli oggetti che si attivano dopo l'avvio sono esclusi dal periodo stazionario.
- **Periodi brevi.** Un periodo più breve di `time.min_period_d` (default 1 d) si unisce al successivo, oppure al precedente se è l'ultimo. Le attivazioni del periodo eliminato vengono anticipate all'inizio del periodo unito e il primo valore della serie è esteso all'indietro. Ogni accorpamento produce l'avviso `time.period_merged`.
- **Passi temporali.** MF6 ammette un solo moltiplicatore per periodo. Per ogni periodo transitorio si cercano il minimo numero di passi e il moltiplicatore più alto, non oltre `time.tsmult`, tali che il primo passo sia ≤ `time.dt_initial_d` e l'ultimo ≤ `time.dt_max_d`. Con un moltiplicatore unico, ottenere insieme passi iniziali brevi e passo massimo limitato può richiedere di abbassare il moltiplicatore. Default 1 d, 1,2 e 30 d, da confermare con l'uso.
- **TS di MF6.** I record vanno dall'attivazione alla fine del modello, in tempo di simulazione. I nomi sono `sNNN_<codice>` in minuscolo, al massimo 40 caratteri.
- **Verifica.** Il test `tests/engine/test_mf6_time_series.py` confronta, per serie a gradino e lineari, il volume estratto in ogni periodo dal bilancio di MF6 con l'integrale esatto della serie, entro 10⁻⁹ relativo. Il test conferma anche che MF6 usa la media della serie su ogni passo.

## Alternative scartate

- Stress period all'unione dei punti di cambio di tutte le serie (spec 0.1), che produce migliaia di periodi.
- Valore della serie a inizio passo, che non conserva i volumi.
- Passi temporali con moltiplicatore e numero fissi, senza garanzie su primo e ultimo passo.

## Conseguenze

- La fine di una serie a gradino non disattiva l'oggetto. Per spegnere un pozzo si inserisce una portata nulla.
- Il calendario si può vedere prima di ogni run con `phrear calendar`.
