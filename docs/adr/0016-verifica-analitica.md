# 0016 – Verifica con soluzioni analitiche e comando `verify`

- Data: 2026-11-03
- Stato: accettata

## Contesto

La sezione 20 richiede, per M1a, quattro test con le loro tolleranze sull'errore assoluto massimo nei punti di confronto:

- Thiem entro l'1 % di s_max;
- Theis e Dupuit entro il 3 %;
- flusso monodimensionale entro la chiusura del solutore.

Per i casi con pozzo i punti devono stare ad almeno 3 celle dal pozzo. Ogni caso produce un breve report con grafico ed errore massimo, incluso nella documentazione; il comando `verify` rigenera i report sull'installazione dell'utente.

## Decisione

- **Casi come progetti completi.** Ogni caso si costruisce come un progetto dell'utente: GeoPackage, raster delle superfici, parametri con unità, carichi imposti con stazioni, pozzi, serie temporali. Poi passa per `check`, `build` e `run`. La verifica copre così l'intera catena e non solo MF6. Per scrivere i dati da codice c'è il modulo `phrear.project.editing`, che servirà anche al progetto di esempio.
- **Flusso monodimensionale.** Falda confinata tra due linee CHD (20 e 15 m, distanza 990 m), T = 100 m²/d, ricarica 365,25 mm/anno. La soluzione h = h₁ + (h₂ − h₁) ξ/L + N ξ (L − ξ)/(2T) è quadratica, quindi la differenza centrale è esatta ai nodi. L'errore misura solo la chiusura del solutore: tolleranza 10⁻⁴ m, uguale a `outer_dvclose`.
- **Thiem.** Q = 500 m³/d, T = 100 m²/d, carico 20 m imposto sulle celle con centro oltre R = 900 m, s = Q/(2πT) ln(R/r).
- **Dupuit.** Stessa geometria in falda freatica con base a 0 m e formulazione di Newton, h_R² − h² = Q/(πK) ln(R/r).
- **Theis.** Q = 500 m³/d per 2 giorni, T = 100 m²/d, S = 10⁻³, primo passo 0,001 d, contorno a 1950 m non raggiunto dal cono; s = Q/(4πT) W(u), u = r²S/(4Tt). Il confronto usa ogni passo e i punti tra 3 celle e 1000 m. W(u) = E₁(u) è calcolata con la serie di potenze per u ≤ 1 e con la frazione continua per u > 1 (errore relativo sotto 10⁻¹²), senza dipendere da scipy.
- **Punti di confronto.** Centri delle celle libere (non CHD) ad almeno 3 celle dal pozzo. Per Thiem e Dupuit tutte le celle; per il flusso 1D la riga centrale.
- **Misura.** Errore assoluto massimo diviso per s_max nei punti di confronto, per i casi con pozzo; errore assoluto in metri per il flusso 1D.
- **Comando `verify`.** Esegue tutti i casi o quelli scelti con `--case`. Scrive `report.md`, un grafico per caso e `results.json` in una cartella nuova o vuota (`--output`). I progetti dei casi si costruiscono in una cartella temporanea del sistema, oppure in `<output>/cases` con `--keep`. Se un caso non passa termina con `verify.failed` e codice di uscita 1.
- **Report nella documentazione.** `docs/verification/` contiene il report generato con MF6 6.8.1.

## Esito con MF6 6.8.1

| Caso | Errore massimo | Misura | Tolleranza |
|---|---|---|---|
| Flusso 1D | 2,9·10⁻⁵ m | 2,9·10⁻⁵ m | 10⁻⁴ m |
| Thiem | 0,0126 m | 0,47 % | 1 % |
| Theis | 0,0214 m | 1,11 % | 3 % |
| Dupuit | 0,0056 m | 0,40 % | 3 % |

## Alternative scartate

- **Modelli MF6 scritti a mano con FloPy.** Verificherebbero MF6, non Phrear.
- **scipy per E₁.** Sarebbe una dipendenza in più per una funzione di trenta righe, verificata sui valori tabulati.
- **Confronto anche nella cella pozzo.** Il carico della cella pozzo differisce dal carico nel pozzo (raggio equivalente di Peaceman), come previsto dalla sezione 20.

## Conseguenze

- I quattro casi sono test sul motore e girano nella CI su Windows a ogni modifica.
- Hantush (M2) e i casi di tracciamento (M5) si aggiungono al registro `CASES` con la stessa struttura.
