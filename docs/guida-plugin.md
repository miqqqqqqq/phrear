# Guida rapida: il plugin Phrear per QGIS 4

Il plugin non contiene logica di calcolo: esegue il core di Phrear nel suo ambiente pixi e ne mostra i risultati in QGIS. Serve quindi il repository di Phrear installato come descritto nella [guida rapida da riga di comando](guida-rapida-cli.md) (`pixi install`). QGIS supportato: 4.x.

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

- **Modello concettuale**: pozzi e stazioni, poi linee a carico imposto, poi dominio, aree a carico imposto e zone di ricarica, così le feature piccole stanno sopra quelle grandi;
- **Tabelle** (chiuso): unità, superfici, parametri, serie temporali, scenari, registro delle modifiche.

I nomi sono quelli dello schema del core, in italiano o in inglese secondo la lingua di QGIS. Se il progetto QGIS è vuoto, il suo sistema di riferimento diventa quello del progetto Phrear; la mappa si centra sul dominio. Un progetto già aperto non viene caricato due volte. Il progetto Phrear aperto resta associato al progetto QGIS quando lo salvi.

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
| Serie temporale | le coppie data–valore |
| Linea o area a carico imposto | le sue stazioni |

Dal form del padre si aggiungono i figli già collegati: un parametro aggiunto dal form di un'unità riceve da solo l'unità e il tipo di oggetto. Eliminare un'unità, una serie o una linea elimina anche i figli, dopo la conferma di QGIS.

**Date.** Date e ore sono l'ora civile del modello, senza fuso. Il plugin le salva in modo che l'ora resti quella inserita, anche con il calcolatore di campi; nel GeoPackage possono comparire con lo scarto di fuso (`2024-07-15T00:00:00+02:00`), che il core ignora.

**Stili.** Pozzi blu, stazioni arancioni, linee a carico imposto blu scuro, aree a carico imposto e zone di ricarica con riempimento trasparente, dominio con il solo contorno.

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

Dopo un run riuscito lo stato riporta la durata e l'errore di bilancio massimo, con periodo e passo. I carichi si caricano per ora a mano come mesh layer (guida CLI, sezione 6); il caricamento automatico arriva con il prossimo incremento.

## 7. Problemi frequenti

| Messaggio | Causa e rimedio |
|---|---|
| L'eseguibile di pixi non è stato trovato | pixi non è installato o QGIS è stato aperto prima dell'installazione; indica il percorso di `pixi.exe` nelle impostazioni |
| La cartella del core deve essere il repository di phrear | la cartella indicata non contiene `pixi.toml` e `src\phrear` |
| Impossibile avviare il core | il percorso di pixi non è valido o pixi non si avvia; prova `pixi run phrear env` da PowerShell nella cartella del repository |
| Il core usa un'altra versione del protocollo degli eventi | plugin e core vengono da versioni diverse del repository; aggiorna entrambi con `git pull` |
| Il run «…» esiste già | ogni run ha una cartella sua che non viene sovrascritta; scegli un altro nome o lascia il campo vuoto |
| L'identificativo del run non è valido | solo lettere, cifre, `_` e `-`, senza spazi |

Caricamento dei risultati ed elenco dei run arrivano con il prossimo incremento di M1b.
