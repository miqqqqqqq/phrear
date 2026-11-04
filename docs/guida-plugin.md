# Guida rapida: il plugin Phrear per QGIS 4

Il plugin non contiene logica di calcolo: esegue il core di Phrear nel suo ambiente pixi e ne mostra i risultati in QGIS. Serve quindi il repository di Phrear installato come descritto nella [guida rapida da riga di comando](guida-rapida-cli.md) (`pixi install`). QGIS supportato: 4.x.

Per cominciare: installazione e impostazioni (sezioni 1–3), poi il percorso guidato con il progetto di esempio (sezione 8). La sezione 9 spiega come costruire un modello nuovo.

## 1. Installazione

**Per lo sviluppo**, con il plugin caricato direttamente dal repository:

```powershell
cd "C:\Users\<utente>\Desktop\flow modeling\phrear"
pixi run plugin-link
```

Il comando crea nel profilo predefinito di QGIS 4 (`%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins`) un collegamento (junction) chiamato `phrear_qgis` alla cartella `qgis_plugin\phrear_qgis` del repository. Non servono diritti di amministratore, e una cartella con lo stesso nome già presente non viene mai sostituita. Per un profilo diverso da quello predefinito:

```powershell
pixi run plugin-link --plugins-dir "<cartella del profilo>\python\plugins"
```

La cartella del profilo si trova in QGIS da Impostazioni → Profili utente → Apri la cartella del profilo attivo.

**Da file ZIP**, come un plugin qualsiasi:

```powershell
pixi run plugin-zip
```

Il comando crea `dist\phrear_qgis-<versione>.zip`, da installare in QGIS con Plugin → Gestisci e installa plugin → Installa da ZIP.

Dopo l'installazione: riavvia QGIS, poi attiva **Phrear** in Plugin → Gestisci e installa plugin → Installati.

## 2. Impostazioni

Plugin → Phrear → **Impostazioni di Phrear…**

- **Cartella del core**: il repository di Phrear, cioè la cartella con `pixi.toml` e `src\phrear`. Con l'installazione di sviluppo viene trovata da sola.
- **Eseguibile di pixi**: di norma `C:\Users\<utente>\.pixi\bin\pixi.exe`, trovato da solo se pixi è sul PATH o nella sua cartella predefinita.

**Verifica** esegue il core con i valori inseriti e mostra le versioni trovate; **OK** salva le impostazioni nel profilo di QGIS.

## 3. Verifica dell'ambiente

Il pulsante della barra Phrear, o Plugin → Phrear → **Verifica l'ambiente di Phrear**, mostra le versioni del core, di MODFLOW 6, di Python, FloPy, GDAL e PROJ. Errori e dettagli finiscono anche nel pannello dei messaggi di log, scheda **Phrear** (Visualizza → Pannelli → Messaggi di log).

Il plugin usa la lingua di QGIS: in italiano sono italiani sia i suoi testi sia i messaggi del core.

## 4. Progetti

Menu Plugin → Phrear:

- **Nuovo progetto Phrear…**: nome, cartella di destinazione, cartella del progetto (ricavata dal nome, modificabile), sistema di riferimento (default EPSG:7791, RDN2008 / UTM 32N), inizio e fine del modello. Il progetto viene creato con `phrear new` e subito aperto.
- **Apri un progetto Phrear…**: scegli la cartella che contiene `project.toml` e `model.gpkg`.
- **Crea il progetto di esempio…**: crea la piana alluvionale di esempio (`phrear example`) in una cartella nuova o vuota e la apre.
- **Riepilogo del progetto**: nome, cartella, sistema di riferimento, periodo del modello, numero di righe di ogni tabella e hash del contenuto del progetto aperto.

All'apertura, layer e tabelle di `model.gpkg` finiscono in un gruppo **Phrear – <nome>** in cima al pannello dei layer:

- **Modello concettuale**: pozzi, stazioni e prove in sito, poi linee a carico imposto, poi dominio, aree a carico imposto, zone di ricarica e zone dei parametri, così le feature piccole stanno sopra quelle grandi;
- **Tabelle** (chiuso): unità, superfici, parametri, serie temporali, scenari, registro delle modifiche.

I nomi sono quelli dello schema del core, in italiano o in inglese secondo la lingua di QGIS. Se il progetto QGIS è vuoto, il suo sistema di riferimento diventa quello del progetto Phrear; la mappa si centra sul dominio. Un progetto già aperto non viene caricato due volte. Il progetto Phrear aperto resta associato al progetto QGIS quando lo salvi.

**Progetti di una versione precedente.** Se il progetto usa uno schema dei dati più vecchio, il plugin propone di aggiornarlo, all'apertura o al primo comando. Prima dell'aggiornamento (`phrear migrate`) project.toml e model.gpkg vengono copiati nella cartella `backups` del progetto; i layer già caricati vengono chiusi e ricaricati.

I layer si modificano con gli strumenti standard di QGIS. Prima di ogni comando del core, se un layer del progetto ha modifiche non salvate, il plugin chiede se salvarle, scartarle o annullare il comando, perché il core legge il GeoPackage e non vedrebbe le modifiche in sospeso.

Mentre un comando è in corso, la barra dei messaggi mostra «… in corso» con una barra di avanzamento e il pulsante **Annulla**.

## 5. Form, relazioni e stili

All'apertura il plugin configura ogni layer secondo lo schema del core. Tutto viene salvato nel progetto QGIS.

**Campi.**

- Etichette con l'unità, per esempio «Inizio filtro [m]».
- Scelte ammesse in un elenco: ruolo del pozzo, riferimento dei filtri, tipo di interpolazione.
- Serie temporali in un elenco limitato alla grandezza giusta: portate per i pozzi, livelli per le stazioni, velocità per la ricarica.
- Unità superiore e inferiore dei carichi imposti scelte per nome.
- Caselle per i valori sì/no, calendario per le date.
- `fid` e i campi di sistema (creato il, modificato il) in sola lettura.
- Il riquadro **Guida**, chiuso, in fondo al form, descrive la tabella e i campi.

**Vincoli e default.**

- Un campo obbligatorio vuoto, o un codice di serie o di scenario già usato, impedisce di salvare la feature.
- Un valore fuori intervallo, per esempio un raggio negativo, dà solo un avviso nel form.
- `check` ricontrolla tutto prima del calcolo.
- I campi nuovi partono dai default dello schema: pozzo in estrazione, filtri in profondità, portata in l/s, oggetto attivo.

**Relazioni.**

| Form | Mostra |
|---|---|
| Unità idrostratigrafica | i suoi parametri (K, Ss, Sy, …) |
| Zona dei parametri | i suoi parametri, che nella zona prevalgono su quelli dell'unità |
| Serie temporale | le coppie data–valore |
| Linea o area a carico imposto | le sue stazioni |

Dal form del padre si aggiungono i figli già collegati: un parametro aggiunto dal form di un'unità riceve da solo l'unità e il tipo di oggetto. Eliminare un'unità, una serie o una linea elimina anche i figli, dopo la conferma di QGIS.

**Date.** Date e ore sono l'ora civile del modello, senza fuso. Il plugin le salva in modo che l'ora resti quella inserita, anche con il calcolatore di campi; nel GeoPackage possono comparire con lo scarto di fuso (`2024-07-15T00:00:00+02:00`), che il core ignora.

**Stili.** Pozzi blu, stazioni arancioni, prove in sito come quadrati rosso scuro, linee a carico imposto blu scuro, aree a carico imposto, zone di ricarica e zone dei parametri (viola) con riempimento trasparente, dominio con il solo contorno.

## 6. Controllo ed esecuzione

Il **pannello Phrear** si apre da solo con il progetto, oppure da Plugin → Phrear → **Pannello Phrear** o dal pulsante della barra. Si aggancia a destra della mappa e si sposta come gli altri pannelli di QGIS.

- **Controlla** esegue `phrear check`: tempo, griglia, parametri, carichi iniziali, condizioni al contorno e controlli del modello. Il pannello mostra l'esito di ogni fase; una fase che dipende da un'altra con errori risulta «non controllata».
- **Esegui** esegue `phrear run`: ripete il controllo e, senza errori, scrive i file di MODFLOW 6, esegue il modello e scrive i carichi in `runs/<nome>/heads.nc`. Il nome del run è facoltativo; vuoto vale data e ora. Sono ammessi lettere, cifre, `_` e `-`, fino a 40 caratteri, e un run esistente non viene mai sovrascritto.
- **Annulla** interrompe il comando, MODFLOW compreso.

Prima di ogni comando il plugin chiede di salvare le modifiche in sospeso. Durante il run la barra segue i passi temporali.

**Problemi.** Errori (✗) e avvisi (⚠) compaiono man mano che il core li trova. Per ognuno ci sono il messaggio, il luogo (layer, `fid`, campo o cella), il codice e il suggerimento. Quando il problema riguarda una feature:

- **Mostra la feature** la seleziona e centra la mappa su di essa; per una tabella apre la tabella degli attributi su quella riga;
- **Apri il form** apre il form della feature, per correggerla subito.

Dopo la correzione si salva e si preme di nuovo Controlla.

**Log.** Ora, avvio e fine di ogni comando, avvisi, errori e cartella dei risultati. I dettagli completi restano nel pannello dei messaggi di log, scheda Phrear.

Dopo un run riuscito lo stato riporta la durata e l'errore di bilancio massimo, con periodo e passo, e i carichi si caricano da soli (sezione 7).

**Griglia e celle.** Per controllare il modello prima del run:

- **Mostra la griglia** costruisce la griglia (`phrear grid --export`) e ne carica le celle, con tetto, fondi, spessori e IDOMAIN di ogni layer negli attributi;
- **Mostra le celle assegnate** (`phrear bc --export`) carica le celle che ricevono pozzi, carichi imposti e ricarica, colorate come il layer da cui vengono. Negli attributi ci sono pacchetto, feature di origine, layer, riga, colonna, moltiplicatore e serie.

I layer finiscono nel sottogruppo **Griglia e celle** e vengono sostituiti a ogni nuovo export.

## 7. Risultati

**Carichi.** I carichi di un run diventano un mesh layer **Carichi – <run>** nel sottogruppo **Risultati**.

- Si vede la superficie freatica o piezometrica, cioè il carico della prima cella attiva satura dall'alto. Gli altri dataset (carico per layer, tetto, fondi, IDOMAIN) si scelgono in Proprietà del layer → Simbologia.
- La scala di colori va dal minimo al massimo su tutti i tempi, così i colori restano confrontabili da un tempo all'altro. Ogni cella ha un solo colore, senza interpolazione.
- Il tempo si scorre con il **controllo temporale** di QGIS (icona dell'orologio nella barra di navigazione della mappa): l'intervallo è già quello del modello, un fotogramma al giorno. Il primo istante è lo stato stazionario iniziale, alla data di inizio.

Le celle inattive, asciutte o a passaggio verticale restano vuote.

**Elenco dei run.** Scheda **Run** del pannello: nome, data, stato e durata di ogni run, dal più recente. Lo stato è uno tra completato, non riuscito, costruito ma non eseguito, in corso o interrotto, incompleto. «Progetto modificato» indica che il progetto è cambiato dopo il run, quindi i risultati non corrispondono più ai dati attuali.

- **Carica i carichi**, o doppio clic, carica i carichi di un run completato;
- **Apri la cartella** apre la cartella del run, con file di MODFLOW 6, listing, bilancio e manifest;
- **Aggiorna** rilegge l'elenco.

## 8. Percorso guidato con il progetto di esempio

Una prova completa in una ventina di minuti, dopo installazione e impostazioni (sezioni 1–3).

1. **Crea l'esempio.** Plugin → Phrear → Crea il progetto di esempio…, in una cartella nuova. Compaiono il gruppo «Phrear – Esempio - piana alluvionale» e, a destra, il pannello Phrear. Il sito è una piana alluvionale sintetica di 3 × 2 km, simulata per il 2024 dopo uno stato stazionario.
2. **Guarda i dati.** Con lo strumento Informazioni o con la tabella degli attributi:
   - **Pozzi**: P1 acquedotto, 15 l/s costanti, filtri tra 15 e 35 m di profondità sotto `z_ref`; P2 irriguo, con la serie `q_irriguo` (10 l/s da aprile, 20 l/s da giugno, fermo da settembre);
   - **Carichi imposti lungo linee**: il limite a monte a 47 m, con una stazione, e il fiume, con due stazioni e livelli mensili; il form della linea mostra le stazioni;
   - **Unità idrostratigrafiche** (in Tabelle): limi di copertura e ghiaie e sabbie, con i parametri nel form dell'unità;
   - **Zone di ricarica**: 250 mm/anno sui campi, 80 mm/anno sull'area urbana.
3. **Controlla.** Nessun errore e un avviso voluto: i limi si chiudono verso ovest, e dove sono più sottili di 0,5 m le celle diventano a passaggio verticale.
4. **Griglia e celle.** **Mostra la griglia** carica le celle di 50 m con tetto, fondi e IDOMAIN di ogni layer; **Mostra le celle assegnate** carica le celle di pozzi, carichi imposti e ricarica, colorate come il layer di origine.
5. **Esegui.** Scrivi `base` come nome del run e premi Esegui. In pochi secondi lo stato riporta durata ed errore di bilancio, e «Carichi – base» compare in Risultati.
6. **Scorri il tempo.** Apri il controllo temporale e scorri il 2024: attorno a P2 il carico scende da aprile, di più da giugno, e risale da settembre. I livelli del fiume cambiano ogni mese.
7. **Cambia un dato.** Porta P1 a 30 l/s e salva. Nella scheda Run accanto a `base` compare «progetto modificato». Esegui un run `p1_30`: i due layer dei carichi restano entrambi in Risultati e si confrontano accendendoli e spegnendoli.
8. **Prova un errore.** Nel form di P1 metti Fine filtro = 10, più in alto dell'inizio, e salva. Controlla dà un errore in Condizioni al contorno. **Mostra la feature** centra P1 e **Apri il form** lo apre per correggerlo: rimetti 35, salva e ricontrolla.
9. **Apri la cartella del run.** Scheda Run → Apri la cartella: file di MODFLOW 6, listing (`mfsim.lst`, `gwf.lst`), bilancio per passo (`gwf.bud.csv`), carichi (`heads.nc`) e `manifest.json` con versioni, hash del progetto ed esito.
10. **Salva il progetto QGIS.** Riaprendolo ritrovi layer, form, risultati e il collegamento al progetto Phrear.

## 9. Un modello nuovo

**Nuovo progetto Phrear…** crea un progetto vuoto. I passi seguono l'ordine in cui il controllo li chiede: dopo ognuno, **Controlla** indica il dato che manca e come aggiungerlo.

1. **Impostazioni in `project.toml`.** Per ora si modificano con un editor di testo, per esempio VS Code; il core rilegge il file a ogni comando.

   ```toml
   [grid]
   cell_size_m = 50.0          # obbligatoria

   [initial_heads]
   mode = "constant"           # oppure mode = "raster" con raster_path = "rasters/carichi.tif"
   value_m = 45.0

   [dem]                       # facoltativo, per i controlli sulle quote
   raster_path = "rasters/dem.tif"
   ```

   Nella stessa sezione `[grid]` ci sono rotazione, spessore minimo e regola di attivazione delle celle; in `[time]` i passi temporali. L'elenco dei campi è nella sezione 8.1 della [SPEC](SPEC.md); il `project.toml` del progetto di esempio è un modello completo.
2. **Dominio.** Metti in modifica il layer Dominio del modello, disegna il contorno e salva.
3. **Unità idrostratigrafiche** (Tabelle). Una riga per unità: posizione (1 = la più alta), nome, convertibile, numero di sotto-layer.
4. **Superfici.** Copia nella cartella `rasters` del progetto i GeoTIFF delle superfici di contatto, nello stesso sistema di riferimento del progetto e in modo che coprano il dominio. Nella tabella Superfici aggiungi una riga per ogni superficie: indice 0 per il tetto del modello, indice i per la base dell'unità i, percorso relativo come `rasters/base_ghiaie.tif`. Per n unità servono le superfici da 0 a n.
5. **Parametri.** Nel form di ogni unità, sezione Parametri dell'unità: K orizzontale, K verticale oppure anisotropia Kv/Kh, Ss e, per le unità convertibili, Sy. Ogni valore ha la sua unità di misura (`m/s`, `m/d`, `1/m`, `%`, …) e un'origine.
6. **Carichi imposti.** Il periodo stazionario iniziale ne richiede almeno uno. Disegna una linea (o un'area) a carico imposto, poi aggiungi le stazioni dal suo form: ogni stazione ha un valore costante o una serie di livelli. Con più stazioni il carico si interpola lungo la linea.
7. **Pozzi e ricarica.** Pozzi come punti, con filtri in profondità o in quota, portata costante o serie. Zone di ricarica come poligoni che non si sovrappongono, con tasso costante o serie.
8. **Serie temporali.** Nella tabella Serie temporali una riga per serie: codice, grandezza (portata, livello, velocità), unità, interpolazione a gradini o lineare. Le coppie data–valore si aggiungono dal form della serie. Il codice si sceglie poi nel campo serie della feature, dove compaiono solo le serie della grandezza giusta.
9. **Controlla ed esegui.** Quando Controlla non dà più errori, Esegui. Gli avvisi non bloccano il run, ma vanno letti.

## 10. Problemi frequenti

| Messaggio | Causa e rimedio |
|---|---|
| L'eseguibile di pixi non è stato trovato | pixi non è installato o QGIS è stato aperto prima dell'installazione; indica il percorso di `pixi.exe` nelle impostazioni |
| La cartella del core deve essere il repository di phrear | la cartella indicata non contiene `pixi.toml` e `src\phrear` |
| Impossibile avviare il core | il percorso di pixi non è valido o pixi non si avvia; prova `pixi run phrear env` da PowerShell nella cartella del repository |
| Il core usa un'altra versione del protocollo degli eventi | plugin e core vengono da versioni diverse del repository; aggiorna entrambi con `git pull` |
| Il run «…» esiste già | ogni run ha una cartella sua che non viene sovrascritta; scegli un altro nome o lascia il campo vuoto |
| L'identificativo del run non è valido | solo lettere, cifre, `_` e `-`, senza spazi |
| Non riesco a sostituire …\exports\grid.gpkg | il file è aperto in un altro programma, o in un altro progetto QGIS; chiudilo e ripeti |
