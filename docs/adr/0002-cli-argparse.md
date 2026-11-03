# 0002 – CLI con argparse

- Data: 2026-11-03
- Stato: accettata

## Contesto

La CLI è l'interfaccia tra plugin e core (sez. 5). Deve produrre eventi JSON su stdout con l'opzione `--json` e restare stabile nel tempo. Interessano la stabilità e il controllo dell'output, più della comodità di scrittura.

## Decisione

La CLI usa `argparse` della libreria standard. Ogni comando è un sottocomando registrato in `phrear.cli`.

## Alternative scartate

- click e typer, più comodi da scrivere ma con una dipendenza in più e un controllo meno diretto su stdout, che deve restare riservato agli eventi JSON.

## Conseguenze

- Nessuna dipendenza aggiuntiva.
- Il formato di help e degli errori di argparse va intercettato in modalità `--json`, perché anche quegli errori devono arrivare al plugin come eventi.
