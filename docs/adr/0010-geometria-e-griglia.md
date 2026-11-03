# 0010 – Geometria e griglia DIS

- Data: 2026-11-03
- Stato: accettata

## Contesto

Le sezioni 10 e 14 della spec chiedono una griglia DIS con rotazione, celle attive dal dominio, superfici di contatto ricampionate sulla griglia con un metodo dichiarato, controlli su ordine, copertura, DEM e spessori, e celle a passaggio verticale dove un'unità si chiude.

## Decisione

- **Convenzioni DIS.** Sono quelle di MF6, cioè origine nell'angolo in basso a sinistra, rotazione antioraria in gradi attorno all'origine, riga 0 a nord. Un test confronta i centri cella con `flopy.discretization.StructuredGrid` per diverse rotazioni.
- **Griglia senza origine.** È la più piccola griglia di passo dato che copre il dominio, con l'origine agganciata a un multiplo del passo nel sistema ruotato.
- **Celle attive.** Una cella è attiva se il centroide cade nel dominio, oppure, con `grid.activation = "area"`, se la frazione d'area interna supera `grid.min_area_fraction`. Il dominio è l'unione delle feature attive del modello base e deve essere geometricamente valido.
- **Ricampionamento delle superfici.** Il valore di una cella è la media, sull'area della cella, dell'interpolazione bilineare del raster. Si calcola con la regola del punto medio su n × n sotto-celle, con n = ⌈2 · passo / pixel⌉ e al massimo 16. Per celle più piccole del pixel n = 1, cioè la bilineare al centro cella. Il metodo non dipende dalla rotazione ed è esatto per superfici lineari.
- **Copertura.** Una cella attiva senza valore è un errore (`geometry.raster_coverage`). Succede se un punto di campionamento cade fuori dal raster o in un pixel nodata. I pixel nodata vicini vengono esclusi dallo stencil, così un raster ritagliato sul dominio conserva i valori fino al bordo.
- **Sistema di riferimento dei raster.** Deve coincidere con quello del progetto, perché la riproiezione al volo sarebbe una trasformazione nascosta. Un raster senza CRS dichiarato viene accettato con un avviso.
- **Ordine delle superfici.** Una superficie sopra la precedente di più di 10⁻⁶ m è un errore bloccante, che riporta numero di celle, scarto massimo e una cella di esempio.
- **Spessori.** Un'unità più sottile di `grid.min_thickness_m` (default 0,5 m) diventa a passaggio verticale (IDOMAIN = -1) in tutti i suoi sotto-layer, con un avviso. Le colonne in cui tutte le unità sono sotto il minimo vengono disattivate.
- **DEM.** Un tetto del modello sopra il DEM di oltre `grid.dem_tolerance_m` (default 1 m) produce un avviso. Un tetto sotto il DEM è ammesso, per esempio quando i terreni di copertura non sono modellati.
- **Celle isolate.** Le celle attive senza vicini attivi, né laterali né verticali attraverso celle -1, producono un avviso.
- **Anteprima.** `phrear grid` riporta dimensioni, celle attive e a passaggio verticale per layer e una stima indicativa della memoria (~1 kB per cella attiva). Con `--export` scrive `exports/grid.gpkg`, un poligono per colonna con tetto, basi, spessori e IDOMAIN per layer.

## Alternative scartate

- **`average` di GDAL.** È esatto su griglie non ruotate, ma su griglie ruotate approssima l'impronta delle celle. Su una superficie lineare con pixel di 10 m ha dato errori fino a 0,1 m a 45°, pari al 22 % della variazione di quota sulla cella quando la cella misura 2 pixel.
- **Riproiezione automatica dei raster.**
- **Troncamento a spessore nullo delle superfici che si incrociano**, che sarebbe una correzione silenziosa dei dati.

## Conseguenze

- Le discontinuità di una superficie si estendono su un pixel, per effetto dell'interpolazione bilineare.
- Il metodo vale per le quote. I parametri useranno le regole della sez. 11 (media geometrica per K) in M2.
