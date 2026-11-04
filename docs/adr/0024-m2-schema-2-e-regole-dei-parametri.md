# 0024 – M2: schema 2, migrazione e regole di assegnazione dei parametri

- Data: 2026-11-04
- Stato: accettata

## Contesto

M2 porta i parametri completi (sez. 11 e 24): zone, raster, prove in sito, interpolazione in log K, ricampionamento, conversioni T → K e S → Ss. Il piano in 8 incrementi e le scelte A1, B1, C1 e D1 sono stati approvati dall'utente prima dell'avvio. Il primo incremento porta lo schema dei dati alla versione 2 e fissa le regole che i successivi implementano.

## Decisione

**Regole di M2**, approvate:

- **Interpolazione (A1).** Inverso della distanza al quadrato (IDW) su log₁₀K, per unità. Il kriging potrà aggiungersi come secondo interpolatore registrato.
- **Combinazione delle fonti (B1).** Priorità per cella e per parametro, come nella sezione 11: raster dove ha dati > campo interpolato > zone > valore uniforme. Il campo interpolato si attiva per unità con `k_from_tests` e vale entro `interp_max_distance` dalla prova più vicina; se il campo è vuoto copre tutta l'unità.
- **Prova → unità (C1).** `unit_id` se indicato. Altrimenti l'unità con il tratto provato più lungo, con un avviso se il tratto attraversa più unità.
- **Parametri dalle prove (D1).** Si interpola solo Kh; Kv viene dall'anisotropia (o da Kv) dell'unità. Ss ricavato da S si confronta con il valore dell'unità e dà un avviso se se ne discosta.

**Regole decise in fase di progetto:**

- in una cella coperta solo in parte da zone o raster, la media pesata sull'area si fa sulla parte che ha un valore;
- una cella senza alcun valore per un parametro richiesto è un errore;
- n_e si assegna come gli altri parametri, obbligatoria da M5.

**Schema 2:**

- **`param_zones`** (poligoni): zone di un'unità (`unit_id`) con parametri propri in `param_values` con `object_type = zone`.
- **`field_tests`** (punti), con i campi della sezione 8.2:
  - tipo di prova, grandezza misurata (`T`, `K`, `S`), valore e unità di misura;
  - riferimento delle quote, quota di riferimento e tratto provato;
  - `ref_thickness`, livello statico, `unit_id`, data e affidabilità.
- **`hydro_units`**: perde `param_mode`, che con la combinazione per cella non ha più senso, e guadagna `k_from_tests` e `interp_max_distance`.
- **Unità nelle zone e nelle prove.** `unit_id` contiene il `fid` dell'unità, come `object_id` dei parametri. I form la mostrano per nome.
- **Relazione «Parametri della zona».** Collega `param_values` a `param_zones` con il filtro `object_type = zone`, come quella dei parametri dell'unità.
- **Stili.** Zone viola trasparenti; prove come quadrati rosso scuro.
- **Versione delle tabelle.** Ogni tabella dichiara la versione dello schema che l'ha introdotta (`since`). Un progetto da migrare si apre con le sole tabelle della sua versione, così `migrate` funziona anche se mancano quelle nuove.

**Migrazione 1 → 2** (`project/migrations/schema2.py`):

- dopo la copia di backup crea le due tabelle;
- aggiunge le colonne a `hydro_units`;
- porta `param_mode = interpolated` in `k_from_tests` = vero, poi elimina `param_mode`; gli altri valori non erano utilizzabili nello schema 1.

Ogni passo controlla prima lo stato del file. È provata su un progetto di esempio scritto dallo schema 1 e conservato in `tests/data/schema1`: le altre tabelle restano identiche (stesso hash) e i parametri letti coincidono con quelli di un progetto nuovo.

**Plugin.** Quando il core risponde che il progetto va migrato, all'apertura, nel riepilogo o in un comando del pannello, il plugin propone l'aggiornamento. Mostra il messaggio del core e ricorda la copia di backup. Se i layer sono già caricati li chiude, esegue `phrear migrate` e riapre il progetto.

**Fino agli incrementi successivi** il core segnala come «non ancora disponibili in questa versione» i parametri di zona, i raster e `k_from_tests`. Zone e prove si possono già inserire.

## Alternative scartate

- **Tenere `param_mode`.** Una sola modalità per unità contraddice la combinazione per cella (B1).
- **Migrazione ricostruita al contrario nei test.** Un file vero dello schema 1 prova la migrazione su ciò che gli utenti hanno.
- **Riferimento all'unità per posizione** nelle zone e nelle prove. Cambia quando si inserisce un'unità; il `fid` no.

## Conseguenze

- I progetti esistenti vanno aggiornati una volta, dal plugin o con `phrear migrate`; la copia di backup resta in `backups/`.
- `tests/data/schema1` non va rigenerato: è il riferimento delle migrazioni future dallo schema 1.
