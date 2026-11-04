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

## 4. Problemi frequenti

| Messaggio | Causa e rimedio |
|---|---|
| L'eseguibile di pixi non è stato trovato | pixi non è installato o QGIS è stato aperto prima dell'installazione; indica il percorso di `pixi.exe` nelle impostazioni |
| La cartella del core deve essere il repository di phrear | la cartella indicata non contiene `pixi.toml` e `src\phrear` |
| Impossibile avviare il core | il percorso di pixi non è valido o pixi non si avvia; prova `pixi run phrear env` da PowerShell nella cartella del repository |
| Il core usa un'altra versione del protocollo degli eventi | plugin e core vengono da versioni diverse del repository; aggiorna entrambi con `git pull` |

Le funzioni di progetto, controllo, esecuzione e risultati arrivano con i prossimi incrementi di M1b.
