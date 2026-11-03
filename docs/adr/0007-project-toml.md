# 0007 – project.toml: validazione con pydantic, scrittura con tomlkit

- Data: 2026-11-03
- Stato: accettata

## Contesto

project.toml contiene metadati e impostazioni del progetto (sez. 8.1). Lo scrive il software, per esempio alla creazione, a ogni salvataggio e nelle migrazioni, ma l'utente può anche modificarlo a mano, aggiungendo commenti. La libreria standard legge il TOML (`tomllib`) ma non lo scrive.

## Decisione

- **Lettura e validazione.** `tomllib` per la lettura, pydantic per la validazione. Le chiavi sconosciute sono errori, così un refuso non viene ignorato.
- **Errori.** Gli errori di sintassi danno `project.config_syntax`. I valori non validi danno `project.config_invalid`, con il percorso della voce (es. `model.end_date`).
- **Scrittura.** Scrittura con tomlkit, che aggiorna il documento esistente e conserva i commenti delle voci che restano.
- **Date.** Ora civile locale, senza fuso. Una data TOML vale mezzanotte, e le date a mezzanotte vengono riscritte come date.
- **Contenuto della versione 1.** Nome, CRS (codice EPSG, solo sistemi proiettati in metri), unità preferite, periodo del modello con periodo stazionario di riferimento e cambi di regime, DEM, carichi iniziali (costante, raster, interpolati, da run), griglia, solutore, opzioni Newton e XT3D.
- **Dipendenza.** tomlkit 0.15.2, licenza MIT, conda-forge.

## Alternative scartate

- tomli-w, più semplice ma senza conservazione dei commenti.
- Scrittura manuale del TOML, fragile su quoting e date.

## Conseguenze

- Aggiungere voci opzionali con un default non richiede una migrazione. Rinominare o rimuovere voci la richiede.
