# 0018 – Plugin QGIS: collegamento al core, processi, traduzioni, pacchetto

- Data: 2026-11-04
- Stato: accettata

## Contesto

M1b porta il plugin minimo per QGIS 4 (sez. 18 e 24). La sezione 5 stabilisce che il plugin invoca la CLI del core come sottoprocesso, in un ambiente separato, e ne legge gli eventi JSON. Le scelte di dettaglio approvate prima dell'avvio sono:

- core tramite `pixi run`;
- solo QGIS 4.x;
- logica senza Qt testata in CI e interfaccia verificata a mano;
- traduzioni IT/EN con il sistema di Qt.

## Decisione

- **Posizione e licenza.** Il plugin sta in `qgis_plugin/phrear_qgis/`, con licenza GPL-2.0-or-later e un suo `LICENSE`. Il core resta EUPL-1.2.
- **Versioni di QGIS.** `qgisMinimumVersion=4.0` e `qgisMaximumVersion=4.99`, senza `supportsQt6`, rimosso in QGIS 4. Gli import passano solo da `qgis.PyQt`, `QAction` viene da `QtGui` e gli enum di Qt sono scritti per esteso.
- **Collegamento al core.** `pixi run --manifest-path <repository>/pixi.toml --frozen phrear --json --lang <it|en> …`, con il percorso di pixi e la cartella del repository nelle impostazioni di QGIS. Entrambi vengono trovati da soli quando possibile: pixi sul PATH o in `~/.pixi/bin`, il repository risalendo dalla cartella del plugin quando questo è installato con il collegamento di sviluppo. `--frozen` usa il lockfile senza risolvere di nuovo l'ambiente.
- **Ambiente del sottoprocesso.** QGIS imposta variabili per il proprio Python e GDAL (PYTHONHOME, PYTHONPATH, GDAL_DATA, PROJ_LIB, QT_PLUGIN_PATH, OSGEO4W_ROOT, …) e mette le proprie cartelle sul PATH. Il plugin le rimuove, e toglie dal PATH le cartelle di installazione di QGIS, prima di avviare il core; altrimenti il Python del core caricherebbe librerie di QGIS. I nomi delle variabili si confrontano senza distinguere maiuscole e minuscole, come fa Windows.
- **Processi.** QProcess asincrono, quindi QGIS resta reattivo. Gli eventi si leggono riga per riga anche quando arrivano spezzati, e le righe non JSON vanno nel log. Un evento con un'altra versione di `schema` rende il comando non riuscito, con un messaggio dedicato. L'annullamento chiude l'intero albero dei processi (pixi, core, MF6): su Windows con `taskkill /T /F`; altrove avviando il comando in un proprio gruppo di processi (`setsid`) e terminando il gruppo. Chiudere solo pixi lasciava il core in esecuzione.
- **Comando `env` del core.** Riporta le versioni di phrear, del protocollo degli eventi, di Python, FloPy, GDAL, PROJ e MF6 con il suo percorso. Il plugin lo usa per verificare il collegamento.
- **Traduzioni.** I testi del plugin sono in inglese dentro `tr("…")` con stringhe letterali. `scripts/plugin_i18n.py` li estrae in `i18n/phrear_it.ts`, conserva le traduzioni esistenti e compila `phrear_it.qm` con `lrelease`. `lrelease` sta nell'ambiente pixi separato `i18n` (`qt6-main`), così l'ambiente predefinito, usato dall'utente e dalla CI, non scarica gli strumenti di Qt. Il `.qm` compilato è nel repository. La lingua è quella di QGIS (`QgsApplication.locale()`) e viene passata anche al core.
- **Pacchetto e installazione.** `pixi run plugin-zip` crea lo ZIP installabile da QGIS (senza `__pycache__` e `.ts`). `pixi run plugin-link` collega la cartella del plugin al profilo di QGIS 4: junction su Windows, che non chiede diritti di amministratore; link simbolico altrove. Un elemento con lo stesso nome non viene mai sostituito.
- **Test.**
  - In CI: costruzione del comando, pulizia dell'ambiente, lettura degli eventi ed esito, metadati, licenza, traduzioni (ogni testo tradotto, segnaposto conservati, `.qm` aggiornato), contenuto dello ZIP, collegamento.
  - Una prova reale: il core avviato tramite pixi con un ambiente contenente PYTHONPATH e GDAL_DATA estranei, ripuliti dal plugin, risponde correttamente.
  - Durante lo sviluppo il plugin è stato provato anche dentro QGIS 4.2.3 senza finestre: caricamento dallo ZIP con il caricatore di QGIS, menu e azioni, impostazioni, `env`, errori tradotti, annullamento, `unload`. Questo ambiente con QGIS non fa parte del repository.

## Alternative scartate

- **Eseguibile del core senza pixi.** Più rapido, ma senza attivazione dell'ambiente GDAL e PROJ possono non trovare i loro dati.
- **Traduzioni con un dizionario Python.** Più semplice, ma fuori dal sistema standard di Qt richiesto dalla sezione 18.
- **Strumenti di Qt nell'ambiente predefinito.** Circa 90 MB in più per ogni utente e per la CI, solo per compilare le traduzioni.
- **QGIS nella CI.** Più copertura, ma un ambiente di diversi GB da mantenere; per scelta C l'interfaccia la verifica l'utente.

## Conseguenze

- Ogni testo nuovo del plugin va passato a `tr` come stringa letterale e tradotto con `pixi run plugin-i18n`; un test segnala i testi non tradotti.
- La prima esecuzione dopo un aggiornamento del lockfile può essere lenta, perché `pixi run` aggiorna l'ambiente.
