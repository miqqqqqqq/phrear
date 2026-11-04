# 0022 – Plugin QGIS: risultati, elenco dei run, griglia e celle

- Data: 2026-11-04
- Stato: accettata

## Contesto

L'incremento 5 di M1b porta i risultati nel plugin. La sezione 24 chiede che il plugin «carica i risultati come mesh layer». Le sezioni 3.1 e 18 chiedono di sapere cosa è cambiato dall'ultimo run e di caricare i risultati in un gruppo dedicato con stile predefinito. Per controllare le scelte del modello servono anche la griglia e le celle assegnate alle condizioni al contorno, che il core sa già esportare (`grid --export`, `bc --export`).

## Decisione

- **Comando `runs` del core.** Elenca le cartelle di `runs/`, dalla più recente, con:
  - stato del run e sua etichetta in italiano e inglese;
  - data di creazione e di avvio, durata;
  - versioni di MF6 e di phrear;
  - hash del contenuto e `same_project`, cioè se il progetto è ancora quello da cui il run è stato costruito;
  - numero di periodi e di avvisi, errore di bilancio massimo, eventuale errore;
  - prodotti presenti, per esempio `heads.nc`.

  Gli stati sono `built` (costruito, non eseguito), `running`, `completed`, `failed` e `incomplete`, quest'ultimo per una cartella senza manifest.
- **Stato `running`.** Prima di avviare MF6 il manifest passa da `built` a `running`, con l'ora di avvio. Un run annullato o interrotto resta quindi riconoscibile come «in corso o interrotto» e non si confonde con un run soltanto costruito.
- **Dataset predefinito.** MDAL e QGIS chiamano ogni variabile del NetCDF con il suo `long_name`, non con il nome della variabile. Il registro degli exporter dichiara quindi il dataset da mostrare per primo con il nome che gli danno i visualizzatori. Per `heads` è il carico della prima cella attiva satura, la superficie freatica o piezometrica. `run` lo riporta come `heads_default`, `runs` come `default_datasets`; il plugin non ripete il nome.
- **Carichi in QGIS.**
  - `heads.nc` diventa un mesh layer MDAL «Carichi – <run>» nel sottogruppo «Risultati» del progetto.
  - È attivo il dataset predefinito, con la rampa Viridis tra minimo e massimo su tutti i tempi.
  - Ogni cella ha un solo colore: la media sui vicini attenuerebbe i coni di depressione dei pozzi.
  - L'intervallo temporale del layer passa al progetto e al controllo temporale, un fotogramma al giorno, con lo stato stazionario alla data di inizio.
  - Un run già caricato non viene caricato due volte.
  - Dopo un run riuscito avviato dal pannello, i carichi si caricano da soli.
- **Elenco dei run.** Scheda Run del pannello con nome, data, stato, durata e l'indicazione «progetto modificato» quando `same_project` è falso. I pulsanti sono «Carica i carichi» (solo per i run completati con `heads.nc`), «Apri la cartella» e «Aggiorna». L'elenco si aggiorna all'apertura del progetto e dopo ogni run.
- **Griglia e celle.**
  - «Mostra la griglia» esegue `grid --export` e carica le celle con contorno grigio.
  - «Mostra le celle assegnate» esegue `bc --export` e colora le celle secondo il layer di origine, con il colore che quel layer ha nello schema.

  Entrambi vanno nel sottogruppo «Griglia e celle». Prima di un nuovo export il plugin rimuove il layer precedente, perché su Windows un file aperto in QGIS non si può sostituire. Se il file resta bloccato, il core riporta `results.file_locked` invece di un errore interno.
- **Ordine nel gruppo del progetto.** Modello concettuale, Griglia e celle, Risultati, Tabelle: le feature restano sopra le celle, le celle sopra i carichi, che coprono l'intero dominio.

## Alternative scartate

- **Lettura dei manifest direttamente nel plugin.** Duplicherebbe il formato del manifest, che è del core.
- **Scelta del dataset per nome di variabile.** MDAL non espone il nome della variabile.
- **Interpolazione ai nodi della mesh.** Più gradevole, ma mostra valori che il modello non ha calcolato.
- **Un fotogramma per passo temporale.** Il controllo temporale di QGIS usa fotogrammi di durata costante, e i passi del modello crescono in progressione geometrica.

## Conseguenze

- Il core ha il comando `runs`, utile anche da riga di comando.
- I manifest dei run nuovi passano per lo stato `running`. I run eseguiti prima di questa modifica e interrotti restano `built`.
- Le prove automatiche in QGIS 4.2.3 hanno richiesto HDF5 1.14 nell'ambiente di prova, perché il provider MDAL del pacchetto conda-forge non trovava la sua libreria. L'installazione di QGIS per Windows contiene già MDAL.
- L'incremento 6 confronterà i carichi del plugin con quelli da CLI sul progetto di esempio e completerà la guida.
