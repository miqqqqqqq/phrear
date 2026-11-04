# 0025 – Parametri per cella: valori uniformi e zone

- Data: 2026-11-04
- Stato: accettata

## Contesto

L'incremento 2 di M2 passa dai parametri uniformi per unità a valori cella per cella, con le zone dei parametri (ADR 0024). La sezione 11 fissa il ricampionamento: media geometrica pesata sull'area per Kh e Kv, aritmetica per Ss, Sy e n_e, anche per le zone che coprono una cella solo in parte.

## Decisione

- **Campi per unità e per colonna.** Ogni parametro di ogni unità è un campo sulle colonne della griglia; i sotto-layer di un'unità lo condividono (`params/cells.py`).
- **Pesi.**
  - Ogni zona dell'unità che ha il parametro pesa con la frazione dell'area della cella che copre.
  - Il valore uniforme dell'unità, se c'è, pesa con la parte restante della cella.
  - La media si fa sulla parte coperta: geometrica per Kh, Kv e Kv/Kh, aritmetica per Ss, Sy e n_e.
  - Dove contribuisce una sola fonte il valore è esattamente il suo, senza passare dal logaritmo, così i progetti con soli valori uniformi danno gli stessi numeri di prima.
- **K verticale.** Un'unità indica Kv oppure Kv/Kh, e le sue zone allo stesso modo; un'unità che li mescola dà errore. Con Kv/Kh, il rapporto ha un suo campo (media geometrica) e Kv di cella = rapporto × Kh di cella. Una zona che dà solo Kh conserva quindi il rapporto dell'unità.
- **Errori.**
  - **Zone sovrapposte** della stessa unità. La media pesata non avrebbe senso; lo scarto ammesso è 10⁻⁶ dell'area di una cella.
  - **Celle attive senza valore** per un parametro richiesto, con il numero di celle. Per Kv dato come rapporto si controlla il rapporto.
  - **Zona di un'unità inesistente**, **geometria non valida**, **riga di parametri di una zona inesistente.**
- **Avviso.** Zona senza parametri.
- **Zone non attive o di uno scenario.** Sono ignorate insieme alle loro righe, come le altre feature (`read_features`).
- **Celle inattive.** Le celle che nessuna fonte copre ricevono la media del campo dell'unità, solo perché MF6 vuole un valore in ogni cella. MF6 non le usa; una cella attiva senza valore è un errore e il run non parte.
- **Origine.** Per ogni cella e parametro si conservano la fonte con la quota maggiore (uniforme o zona, con il fid), la sua quota sulla parte coperta e il numero di fonti. Raster e campo interpolato si aggiungeranno come altre origini.
- **Controllo.** La fase Parametri del controllo legge i valori e, se la griglia è stata costruita, li assegna alle celle. Gli errori delle celle appartengono quindi a quella fase. Senza griglia restano i controlli sui valori.
- **`phrear params --export`** scrive `exports/params.gpkg`, layer `cells`. C'è una feature per cella (layer, riga, colonna) con:
  - unità e IDOMAIN;
  - Kh, Kv (in m/d e in m/s), Ss, Sy e n_e;
  - per ogni parametro origine, zona e quota.

  Il testo e il JSON di `params` elencano anche i valori delle zone.

## Alternative scartate

- **Regola della maggioranza** (la cella prende la zona che ne copre più della metà). Più semplice, ma contraddice la sezione 11 e sposta i contorni delle zone di mezza cella.
- **Kv mediato a parte quando una zona dà solo Kh.** Kv della cella resterebbe quello dell'unità anche dentro una zona molto più permeabile, e il rapporto Kv/Kh varierebbe senza motivo.
- **Una feature per colonna con colonne per layer** nell'export. Con cinque parametri e le loro origini sarebbero decine di campi per layer; una feature per cella si filtra per layer in QGIS.

## Conseguenze

- Pozzi e condizioni al contorno usano già le K di cella, per esempio nella ripartizione della portata tra i layer per trasmissività.
- I numeri dei progetti con soli valori uniformi non cambiano. Il progetto di esempio e i suoi test di regressione restano validi.
- La mappa dei parametri nel plugin arriva con l'incremento 6.
