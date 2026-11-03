# 0014 – Build e run di MODFLOW 6 in M1a

- Data: 2026-11-03
- Stato: accettata

## Contesto

M1a chiede build e run di MF6 tramite l'eseguibile, con un manifest con gli hash di contenuto (sez. 16 e 24). Esecuzione via modflowapi, istantanee, stop del run e analisi dettagliata del listing sono in M7.

## Decisione

- **Ispezione prima del build.** `build` e `run` usano l'ispezione di `check` (ADR 0013) e non scrivono nulla se ci sono errori.
- **Cartella del run.** `runs/<run_id>/`, con `run_id` dato dall'utente (lettere, cifre, `-` e `_`, fino a 40 caratteri) oppure data e ora (`AAAAMMGG-hhmmss`, con suffisso se esiste già). Una cartella esistente non viene mai riusata né sovrascritta.
- **File MF6.** Scritti con FloPy: TDIS in giorni, IMS, un modello GWF con DIS in metri (origine, rotazione, IDOMAIN con celle a passaggio verticale), IC, NPF, STO, WEL, CHD, RCH, OC. I numeri sono scritti con 15 cifre significative invece delle 8 di default di FloPy, così serie, moltiplicatori dei passi e array passano senza perdita.
- **Pacchetti delle condizioni al contorno.** Dalle assegnazioni del registro (ADR 0012), con BOUNDNAMES e, per WEL e RCH, la variabile ausiliaria `mult` come AUXMULTNAME. Un blocco PERIOD si scrive solo quando le righe cambiano rispetto al periodo precedente, perché MF6 mantiene in vigore l'ultimo blocco. Le serie vanno in file TS per pacchetto, uno per ogni insieme di date comuni (per esempio tutte le celle di una linea CHD).
- **Solutore.** Preset `standard` (IMS moderate), `robust` (IMS complex), `expert` (moderate con le opzioni dell'utente). Tolleranze comuni: variazione di carico 10⁻⁴ m nelle iterazioni esterne e 10⁻⁵ m in quelle interne, residuo 10⁻³ m³/d. Con Newton o XT3D l'accelerazione è BICGSTAB.
- **Uscite.** Carichi e bilanci a ogni passo (`gwf.hds`, `gwf.cbc`), bilancio per passo in CSV (`gwf.bud.csv`), iterazioni del solutore in CSV (`ims_outer.csv`).
- **Manifest.** `manifest.json` con versione di phrear e di MF6, percorso dell'eseguibile, hash di contenuto del progetto, impostazioni complete, dimensioni del modello, righe per pacchetto, avvisi dell'ispezione e file. Dopo il run riporta stato, durata, codice di uscita, ultimo passo ed errore di bilancio massimo. Si scrive in modo atomico.
- **Run.** L'eseguibile gira nella cartella del run e il suo output va in `mf6.stdout.txt`. Ogni riga «Stress period … Time step …» diventa un evento `progress` con la frazione del tempo simulato. Alla fine si leggono i listing: terminazione normale, voci dell'ERROR REPORT (`run.engine_error`), mancata convergenza con periodo e passo (`run.convergence`), altre interruzioni (`run.terminated`). Un errore di bilancio oltre l'1 % produce un avviso.
- **Eventi.** `run_started`, `progress`, poi `run_completed` oppure `run_failed`, e il `result` del comando.

## Alternative scartate

- **modflowapi già in M1a.** Il monitor dettagliato e lo stop sono in M7; per M1a bastano esecuzione e verifica numerica.
- **Sovrascrivere un run con lo stesso nome.** Si perderebbero risultati senza conferma.
- **Precisione di default di FloPy.** Con 8 cifre il carico nelle celle CHD differiva dal valore atteso di circa 2,5·10⁻⁷ m. Con 15 cifre coincide entro 10⁻⁹ m.
- **Un file TS per serie.** Una linea CHD ne produrrebbe uno per cella.

## Verifica

Un test sul motore esegue il sito sintetico con stazioni CHD a serie, un pozzo costante, un pozzo con serie attivata a metà simulazione e una zona di ricarica. In ogni passo:

- il carico di ogni cella CHD coincide entro 10⁻⁹ m con la media esatta della sua serie derivata sul passo;
- la portata di ogni pozzo coincide con quella assegnata, e il pozzo con serie è assente prima dell'attivazione;
- la ricarica totale è uguale a tasso × area.

I passi calcolati da MF6 coincidono con quelli del calendario.

## Conseguenze

- Su un layer convertibile la quota di portata di un pozzo si calcola sulla geometria del filtro: se il layer è asciutto, MF6 preleva comunque. AUTO_FLOW_REDUCE e l'export delle portate effettive restano in M3.
- L'export dei carichi in NetCDF (incremento 10) legge `gwf.hds` della cartella del run.
