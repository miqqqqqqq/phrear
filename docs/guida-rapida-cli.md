# Guida rapida: Phrear da riga di comando

Questa guida porta dal clone del repository a un modello eseguito e ai suoi carichi in QGIS. I comandi sono per PowerShell su Windows, la piattaforma supportata.

## 1. Installazione

Serve [pixi](https://pixi.sh), che installa Python, MODFLOW 6 6.8.1 e le librerie in versioni bloccate dal file `pixi.lock`.

```powershell
git clone https://github.com/miqqqqqqq/phrear.git
cd phrear
pixi install
pixi run phrear --version
```

Dopo l'installazione di pixi la finestra di PowerShell va riaperta, perché il PATH si aggiorna solo nelle nuove finestre. Tutti i comandi si eseguono con `pixi run phrear …` dalla cartella del repository; il percorso del progetto si passa come argomento.

## 2. Il progetto di esempio

```powershell
pixi run phrear example "C:\Users\<utente>\Desktop\esempio"
```

Crea una piana alluvionale sintetica di 3 × 2 km:

- due unità, limi di copertura (che si chiudono a ovest) su ghiaie e sabbie divise in due sotto-layer;
- un limite a carico imposto a monte e un fiume con livelli mensili a due stazioni;
- un pozzo idropotabile a 15 l/s e un pozzo irriguo attivo da aprile ad agosto;
- ricarica di 250 mm/anno sui campi e 80 mm/anno sull'area urbana;
- il 2024 come periodo simulato, dopo uno stato stazionario iniziale.

La cartella deve essere nuova o vuota.

## 3. La cartella del progetto

```
esempio/
├─ project.toml   impostazioni: date, griglia, carichi iniziali, solutore
├─ model.gpkg     modello concettuale: dominio, unità, superfici, parametri, pozzi, ...
├─ rasters/       DEM e superfici di contatto (GeoTIFF)
├─ runs/          un sotto-cartella per run, rigenerabile
└─ exports/       export per il controllo in QGIS, rigenerabili
```

`model.gpkg` si apre in QGIS e si modifica come qualsiasi GeoPackage. Le quote sono in m s.l.m. Ogni valore fisico ha la sua unità di misura accanto, per esempio `rate` e `rate_unit` nei pozzi, oppure `value` e `unit` in `param_values`. L'elenco completo di layer, campi, unità e valori ammessi si ottiene con:

```powershell
pixi run phrear schema
```

## 4. Controlli

```powershell
pixi run phrear info  "C:\...\esempio"     # riepilogo e hash del contenuto
pixi run phrear check "C:\...\esempio"     # tutti gli errori e gli avvisi
```

`check` assembla il modello per fasi: tempo, griglia, parametri, carichi iniziali, condizioni al contorno, controlli del modello. Elenca tutti gli errori bloccanti e poi gli avvisi; ognuno indica il layer, il fid e il campo da correggere e dà un suggerimento. Con errori termina con codice di uscita 1.

Per vedere i singoli passaggi:

| Comando | Cosa mostra |
|---|---|
| `calendar` | stress period, passi temporali e motivo di ogni periodo |
| `grid --export` | dimensioni della griglia e celle attive; `exports/grid.gpkg` con quote e IDOMAIN per colonna |
| `params` | parametri per unità, valore originale e valore in m e giorni |
| `bc --export` | celle assegnate a pozzi, carichi imposti e ricarica; `exports/bc.gpkg` |

## 5. Esecuzione

```powershell
pixi run phrear run "C:\...\esempio" --run-id base
```

`run` ripete i controlli e, se non ci sono errori, scrive i file di MODFLOW 6 in `runs/base/`, esegue MF6 e scrive i carichi in `runs/base/heads.nc`. Senza `--run-id` il nome è la data e l'ora; un run esistente non viene mai sovrascritto. Per scrivere i file senza eseguirli c'è `build`.

Nella cartella del run:

- `manifest.json`: versioni di phrear e MF6, hash del progetto, impostazioni, esito ed errore di bilancio massimo;
- `mfsim.lst`, `gwf.lst`: listing di MF6;
- `gwf.hds`, `gwf.cbc`, `gwf.bud.csv`: carichi, flussi e bilancio per passo;
- `heads.nc`: carichi in NetCDF UGRID.

`runs` elenca i run del progetto, dal più recente, con stato (completato, non riuscito, costruito, in corso o interrotto, incompleto), durata e l'indicazione dei run costruiti da una versione precedente del progetto:

```powershell
pixi run phrear runs "C:\...\esempio"
```

`export` rigenera `heads.nc` per un run qualsiasi, di default l'ultimo completato:

```powershell
pixi run phrear export "C:\...\esempio" --run base
```

## 6. Risultati in QGIS

`heads.nc` si carica come mesh layer: Layer → Aggiungi layer → Aggiungi layer mesh. Contiene una variabile per layer, `head_l1`, `head_l2`, …, con le celle inattive, a passaggio verticale o asciutte lasciate vuote. `head_upper` è il carico della prima cella satura dall'alto, cioè la superficie freatica o piezometrica. Il tempo è in giorni dalla data di inizio, con lo stato stazionario a 0, e si scorre con il controllo temporale di QGIS.

## 7. Verifica dell'installazione

```powershell
pixi run phrear verify --output "C:\...\verifica"
```

Esegue i casi di Thiem, Theis, Dupuit e del flusso monodimensionale e scrive un report con tabelle e grafici. Il report di riferimento è in [docs/verification/report.md](verification/report.md).

## 8. Uso da altri programmi

Con `--json` ogni comando scrive eventi JSON, uno per riga in UTF-8: `command_started`, `warning`, `error`, `progress`, `result`, `command_completed` oppure `command_failed`, e per `run` anche `run_started` e `run_completed` o `run_failed`. Con `--lang en` i testi sono in inglese. Codici di uscita: 0 riuscito, 1 errore nell'input o nel progetto, 2 riga di comando non valida, 3 errore interno.

```powershell
pixi run phrear --json check "C:\...\esempio"
```
