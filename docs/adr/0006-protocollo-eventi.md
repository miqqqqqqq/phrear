# 0006 – Protocollo degli eventi, errori e codici di uscita

- Data: 2026-11-03
- Stato: accettata

## Contesto

Il plugin invoca la CLI del core come sottoprocesso e riceve avanzamento, avvisi, errori e risultati come eventi JSON (sez. 5 e 16). Su Windows lo stdout di un sottoprocesso usa di norma la codifica locale (cp1252), che non rappresenta caratteri come «³» o ««».

## Decisione

- **Formato.** JSON Lines in UTF-8, una riga per evento terminata da `\n`, scritta su stdout in modalità binaria e svuotata a ogni riga. La codifica non dipende quindi dalla console.
- **Campi comuni.** `schema` (versione del protocollo, oggi `"1"`), `event` (tipo) e `time` (UTC, ISO 8601). Campi sconosciuti e versioni diverse vengono rifiutati in lettura.
- **Tipi della versione 1.**
  - Comandi: `command_started`, `command_completed`, `command_failed`, `progress`, `warning`, `error`.
  - Run: `run_started`, `period_started`, `timestep_completed`, `snapshot_written`, `flow_reduced`, `run_completed`, `run_failed`.
- **Unità nei nomi.** I campi numerici dichiarano l'unità nel nome (`_m`, `_d`, `_s`, `_m3d`, `_pct`).
- **Errori.** Ogni errore ha un codice stabile con prefisso di categoria (`cli.`, `unit.`, `internal.`, …), messaggio e suggerimento in italiano e inglese dal catalogo `phrear.errors.CATALOG`, dettaglio tecnico e riferimento all'oggetto (`ObjectRef`). Gli eventi portano entrambe le lingue e la scelta spetta al client.
- **Codici di uscita della CLI.** 0 successo; 1 errore nell'input o nel progetto; 2 riga di comando non valida; 3 errore interno.
- **Errori di argparse.** Anche gli errori di uso diventano eventi quando è attivo `--json`.

## Alternative scartate

- Testo libero su stdout, perché obbligherebbe il plugin a interpretarlo.
- Un solo messaggio nella lingua scelta, perché il plugin può cambiare lingua senza rilanciare il comando.
- `PYTHONIOENCODING` o la modalità UTF-8 di Python, perché dipendono dall'ambiente del processo chiamante.

## Conseguenze

- Il plugin, che non importa il core, ottiene lo schema JSON degli eventi dal core (`event_json_schema`), esposto dal comando `schema` nell'incremento 3.
- Un cambiamento incompatibile del protocollo richiede `schema: "2"` e una nuova voce nel registro.
