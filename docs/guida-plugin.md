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

## 5. Problemi frequenti

| Messaggio | Causa e rimedio |
|---|---|
| L'eseguibile di pixi non è stato trovato | pixi non è installato o QGIS è stato aperto prima dell'installazione; indica il percorso di `pixi.exe` nelle impostazioni |
| La cartella del core deve essere il repository di phrear | la cartella indicata non contiene `pixi.toml` e `src\phrear` |
| Impossibile avviare il core | il percorso di pixi non è valido o pixi non si avvia; prova `pixi run phrear env` da PowerShell nella cartella del repository |
| Il core usa un'altra versione del protocollo degli eventi | plugin e core vengono da versioni diverse del repository; aggiorna entrambi con `git pull` |

Form, controllo, esecuzione e risultati arrivano con i prossimi incrementi di M1b.
