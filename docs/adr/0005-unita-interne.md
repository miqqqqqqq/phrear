# 0005 – Unità interne e convenzioni sulle unità

- Data: 2026-11-03
- Stato: accettata

## Contesto

La spec fissa metri e giorni come unità interne (sez. 3.2) e richiede che ogni grandezza fisica in input passi da pint (sez. 22). Servono anche convenzioni esplicite sulle notazioni accettate e sulla durata dell'anno, perché portate in m³/anno e ricariche in mm/anno sono comuni nei dati degli utenti.

## Decisione

- Il modulo `phrear.units` definisce le grandezze del modello (`PhysicalQuantity`) e per ciascuna una sola unità interna. Lunghezza in m, tempo in d, portata in m³/d. La categoria velocità, in m/d, comprende conducibilità idraulica, ricarica e flusso specifico. Trasmissività e conduttanza sono in m²/d, immagazzinamento specifico in 1/m e caratteristica idraulica delle barriere in 1/d.
- La conversione è sempre value_interno = f · value_utente, con f da `conversion_factor`. Il fattore resta disponibile per il log del run, così nessuna conversione è silenziosa.
- L'anno è l'anno giuliano, 365,25 d, che è il default di pint. Ne segue 1 m³/anno = 1/365,25 m³/d.
- Notazioni accettate: `m3/d`, `m³/d`, `m**3/d`, `l/s`, `mm/anno`, `1/m`, `%`. Le parole italiane anno, giorno, ora, minuto, secondo e litro, con i plurali, vengono tradotte prima del parsing. Stringa vuota, `-` e `1` indicano una grandezza adimensionale.
- Unità sconosciute o con dimensioni incompatibili con la grandezza producono `UnitError`, con codice `unit.unknown` o `unit.dimension` e messaggio in italiano e inglese.

## Alternative scartate

- Anno di 365 d, che darebbe uno scarto dello 0,07 % rispetto all'anno giuliano. Si può introdurre come opzione esplicita se gli enti lo richiedono.
- Accettare solo la sintassi nativa di pint, che non riconosce `m3` né le parole italiane.

## Conseguenze

- Il dominio della conversione è chiuso. Aggiungere una grandezza, per esempio la temperatura per GWE in fase 4, richiede una voce in `PhysicalQuantity` e, per le unità con offset come °C, una conversione diversa dal solo fattore.
