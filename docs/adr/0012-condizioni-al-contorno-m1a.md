# 0012 – Condizioni al contorno di M1a: pozzi, carichi imposti, ricarica

- Data: 2026-11-03
- Stato: accettata

## Contesto

M1a richiede WEL, CHD con i valori alle stazioni (`line_stations`) e RCH, più l'infrastruttura del registro `BoundaryConditionType` (sez. 12, 21 e 24). Servono regole per assegnare le feature alle celle, per far variare i valori nel tempo con le serie TS (ADR 0009) e per rispettare i vincoli di MF6. Tre comportamenti di MF6 6.8.1 sono stati verificati con modelli di prova:

- un CHD con carico sotto la base della cella è un errore di input («HEAD IS LESS THAN CELL BOTTOM»), con e senza Newton;
- due CHD nella stessa cella sono un errore («Cell is already a constant head»);
- WEL e RCH accettano più righe nella stessa cella e la variabile ausiliaria AUXMULTNAME, anche quando il valore è una serie TS; le portate del bilancio coincidono con valore × moltiplicatore.

## Decisione

- **Registro.** Ogni tipo dichiara nome, etichette IT/EN, pacchetto MF6, layer del GeoPackage letti e una funzione che produce un `PackageInput`: un elenco di assegnazioni (cella, forzante, moltiplicatore, boundname, feature di origine). Campi e unità restano nello schema unico (ADR 0008); lo stile QGIS arriva con il plugin (M1b). Il pacchetto MF6 si scrive dall'elenco nell'incremento 9.
- **Forzante.** Valore costante oppure serie in unità interne, data di attivazione dal calendario e valore del periodo stazionario. Ogni oggetto entra nel modello dal periodo che inizia alla sua attivazione. Il moltiplicatore va nella variabile ausiliaria AUXMULTNAME, così i valori restano quelli inseriti e una serie può essere condivisa.
- **Intersezione.** Con shapely sulla geometria della griglia ruotata. Un punto va alla cella che lo contiene; una linea a ogni cella che attraversa per una lunghezza positiva, con la progressiva del punto medio del tratto; un poligono a ogni cella che copre, con la frazione d'area. Le celle sono chiuse, quindi una linea lungo un lato appartiene alle celle dei due lati.
- **Pozzi (WEL).** Il filtro, in quota o in profondità da `z_ref`, si interseca con i layer attivi della colonna; la portata si ripartisce in proporzione a T_k = K_k · l_k, con l_k lunghezza del filtro nel layer. Si usa la geometria delle celle e non lo spessore saturo durante il run. L'estrazione ha moltiplicatore negativo. `model_as = auto` vale WEL; MAW arriva in M3.
- **Carichi imposti lungo linee (CHD).** Il carico di una cella è l'interpolazione lineare per progressiva tra le stazioni ai due lati; oltre la prima e l'ultima stazione vale il valore di estremità. Con le serie, la cella riceve la serie w · h_a(t) + (1 − w) · h_b(t) sull'unione delle date, esatta in ogni istante se le due serie sono entrambe a gradino o entrambe lineari; per questo una linea non può mescolarle. La linea si attiva quando tutte le sue stazioni sono definite.
- **Carichi imposti su aree.** Una sola stazione, carico uniforme, celle scelte con la regola di attivazione della griglia (centroide o frazione d'area).
- **Layer dei carichi imposti.** Quelli delle unità da `top_unit` a `bottom_unit`, solo celle attive. Un layer riceve il carico solo se la sua base sta sotto il carico minimo della simulazione. Un layer che il carico attraversa durante il run resta libero, con un avviso; un layer sempre sopra il carico resta libero senza avviso, perché lì è asciutto. Se nessun layer della colonna rispetta la condizione è un errore.
- **Sovrapposizioni CHD.** Una cella già assegnata tiene la prima feature (linee prima delle aree, per fid), con un avviso.
- **Ricarica (RCH).** Alla cella attiva più alta di ogni colonna coperta dalla zona, con moltiplicatore uguale alla frazione coperta, così il volume è esattamente tasso × area coperta. Zone sovrapposte si sommano, con un avviso.
- **Errori.** Feature senza geometria; pozzo o linea senza celle attive; filtro senza `z_ref`, invertito o fuori dalle celle attive; portata negativa (anche nelle serie); valore o unità mancanti; serie di grandezza sbagliata; stazione di una feature inesistente, senza valore, con progressiva doppia o oltre la linea; area con più stazioni; linea in più parti; intervallo di unità non valido; carico sotto la base dell'ultimo layer.
- **Avvisi.** Filtro in parte fuori dalle celle attive; linea in parte su celle non attive; stazione a più di una cella dalla sua linea; layer lasciati liberi dal CHD; sovrapposizioni CHD; zona di ricarica fuori dal modello; zone sovrapposte.
- **Comando `bc`.** Per pacchetto: feature, celle, righe, serie e righe per periodo; con `--export` scrive `exports/bc.gpkg` con una cella per assegnazione.

## Alternative scartate

- **FloPy GridIntersect.** Usa anch'esso shapely, ma l'API è cambiata tra le versioni e la gestione dei tratti sui lati non è documentata. Con shapely diretto la regola è esplicita e coerente con i poligoni della griglia già usati per dominio ed export.
- **Carico costante nel periodo per le celle tra due stazioni.** Perderebbe la variazione dentro il periodo, contro ADR 0009.
- **Carico della stazione più vicina.** Introdurrebbe gradini lungo la linea.
- **Attivazione cella per cella lungo una linea.** Una parte della linea sarebbe attiva prima del resto, senza significato fisico.
- **CHD su tutti i layer indicati anche sotto il carico.** MF6 rifiuta l'input.
- **Errore sulle sovrapposizioni CHD.** Le linee che si incontrano agli angoli del dominio condividono quasi sempre una cella.
- **Pozzi fuori dal dominio come avviso.** La portata sparirebbe dal bilancio senza un errore.

## Conseguenze

- La ripartizione su più layer, prevista in M3, è disponibile da M1a. Restano in M3 AUTO_FLOW_REDUCE e MAW.
- Le serie derivate dei CHD sono una per colonna; l'incremento 9 le raggruppa in file TS per pacchetto.
- I controlli tra condizioni diverse, per esempio un pozzo in una cella CHD, entrano nel registro dei controlli (incremento 8).
- Le feature degli scenari (`scenario_id` non vuoto) sono escluse; gli scenari si applicano con M5.
