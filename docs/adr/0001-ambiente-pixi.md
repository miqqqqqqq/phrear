# 0001 – Ambiente pixi, Python 3.12, MODFLOW 6.8.1 da conda-forge

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 3.3 della spec richiede dipendenze isolate con versioni bloccate, eseguibili esterni compresi. Su Windows GDAL, PROJ e HDF5 installati da PyPI sono la fonte più frequente di conflitti, e MODFLOW 6 non è un pacchetto Python.

## Decisione

- L'ambiente è gestito con pixi (`pixi.toml` e `pixi.lock`) sul canale conda-forge.
- Il lockfile copre `win-64`, piattaforma supportata, e `linux-64`, usata solo per lo sviluppo.
- Python 3.12 per il core.
- MODFLOW 6 viene dal pacchetto `modflow6` di conda-forge, bloccato a `==6.8.1`. Il pacchetto contiene eseguibile `mf6` e `libmf6`, licenza CC0-1.0. Un test verifica che l'eseguibile corrisponda alla versione bloccata in `pixi.toml`, che resta l'unica fonte del numero di versione.
- Il pacchetto `phrear` è installato in modalità editable come dipendenza PyPI locale. Non dichiara dipendenze proprie, per cui la mappatura dei nomi conda → PyPI è disattivata (`conda-pypi-map = false`).

## Alternative scartate

- conda o mamba con `environment.yml`, perché il lockfile multipiattaforma richiede strumenti aggiuntivi.
- pip con venv, per i problemi di GDAL e PROJ su Windows e perché MF6 andrebbe gestito a parte.
- `get-modflow` di FloPy, che scarica gli eseguibili fuori dal lockfile.

## Conseguenze

- Aggiornare MF6 significa cambiare il pin in `pixi.toml`, rigenerare il lockfile e far passare i test di verifica e regressione (sez. 21).
- Se in futuro si aggiungono dipendenze PyPI, la mappatura conda → PyPI va riattivata o fornita localmente, altrimenti pixi può installare doppioni.
- La dichiarazione delle dipendenze per installazioni via pip rientra in M6 (distribuzione).
