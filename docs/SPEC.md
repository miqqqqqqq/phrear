# Specifica di progetto – Piattaforma di modellazione delle acque sotterranee

- Versione documento: 0.3 – 2026-11-03
- Nome del software: Phrear (nel documento anche "la piattaforma"); nel codice `phrear`, `phrear_qgis`, `phrear_viewer`
- Licenze: core EUPL-1.2; plugin QGIS GPL-2.0-or-later; viewer come il core [DA CONFERMARE]
- Autore e titolare dei diritti: Michele (sviluppo personale)
- Stato: bozza da revisionare

---

## 0. Come usare questo documento

Istruzioni per l'agente di sviluppo:

- Questo documento è la fonte di verità del progetto. Se una richiesta in chat è in conflitto con il documento, segnala il conflitto e chiedi quale delle due prevale.
- Le sezioni 3 (Principi) e 22 (Convenzioni di codice) sono vincolanti.
- Le scelte marcate [DA CONFERMARE] sono proposte. Puoi proporre alternative motivate prima di implementarle.
- I punti marcati [DA DEFINIRE] sono decisioni aperte. Non inventare la risposta: chiedi, oppure lascia il punto parametrizzato.
- Ogni decisione architetturale presa durante lo sviluppo va registrata nella sezione 27 e in `docs/adr/`.
- Lavora per milestone (sezione 24). Non anticipare funzioni di milestone successive, salvo preparare le interfacce.
- Copia questo documento nel repository come `docs/SPEC.md` e aggiornalo insieme al codice. A fine milestone aggiorna lo stato (sezione 24) e il registro decisioni.
- Comunica con l'utente in italiano. Codice e identificatori vanno in inglese.

Priorità in caso di compromesso, in ordine:
1. correttezza dei risultati;
2. tracciabilità e riproducibilità;
3. semplicità d'uso;
4. prestazioni;
5. completezza funzionale.

---

## 1. Contesto e obiettivo

La piattaforma è un ambiente integrato in QGIS per la modellazione numerica delle acque sotterranee: prima il flusso, poi il trasporto di soluti. È il successore moderno di FREEWAT, il plugin QGIS sviluppato nell'omonimo progetto H2020 e usato oggi dagli utenti target.

| Limite di FREEWAT | Risposta della piattaforma |
|---|---|
| v1.x legata a QGIS 2.18, Python 2.7 e Qt4; nessuna versione per QGIS 3 (ultima release 1.2.0, 2019) | Core indipendente da QGIS; plugin per QGIS 4 (Qt6) |
| MODFLOW-2005 (core precedente, non più sviluppato attivamente) più MT3D, SEAWAT e MODPATH come codici separati | MODFLOW 6 come unico motore (modelli GWF, poi GWT, PRT e GWE; pacchetto BUY per la densità variabile) |
| Solo griglie regolari | Griglie DIS e DISV con raffinamento locale |
| Calibrazione con UCODE_2014 (gradiente locale, pochi parametri) | PEST++ IES e pyEMU: parametrizzazione densa e analisi di incertezza |
| SpatiaLite monoutente; dati del modello legati alla griglia | GeoPackage più file di progetto testuale; modello concettuale indipendente dalla griglia |
| Logica e interfaccia accoppiate; nessun uso senza GUI | Core utilizzabile da script, tramite CLI e API Python |
| Visualizzazione layer per layer; export VTK | Mesh layer QGIS con dimensione temporale, viewer 3D, monitor in tempo reale |
| Installazione complessa; manuali PDF non allineati al software | Ambiente isolato e riproducibile; documentazione versionata con il codice |

Obiettivo: permettere a un ingegnere di costruire, eseguire e documentare un modello di flusso affidabile con meno passaggi e meno errori rispetto a FREEWAT, ottenendo risultati verificabili e tracciabili.

---

## 2. Utenti e casi d'uso

Gli utenti sono ingegneri e geologi professionisti che usano la modellazione negli studi di caratterizzazione e nella progettazione. Conoscono MODFLOW a livello d'uso, tramite FREEWAT. Non sono necessariamente programmatori.

Casi d'uso, in ordine di priorità:

1. **Siti contaminati e barriere idrauliche.**
   - Dimensionamento dei pozzi barriera: numero, posizione, portate.
   - Verifica della cattura del plume.
   - Verifica dell'inversione del gradiente sui piezometri di controllo.
   - Effetto di barriere fisiche come diaframmi e palancole.
2. **Concessioni di emungimento.**
   - Abbassamenti indotti.
   - Interferenza con pozzi vicini e con corpi idrici superficiali.
   - Bilancio idrico.
   - Zone di rispetto dei pozzi a uso potabile tramite isocrone.
3. **Modelli di falda estesi.** Bilanci idrici a scala di bacino o regionale.

Scala dei modelli: dai singoli siti, con domini dell'ordine di 1 km² [DA CONFERMARE], fino alle falde regionali. Le celle vanno da poche migliaia a centinaia di migliaia; la progettazione deve reggere 10^6 celle.

Deliverable degli utenti: tabelle, grafici, bilanci idrici e mappe da inserire nelle relazioni tecniche, a supporto delle decisioni progettuali e per gli enti. La piattaforma li produce direttamente, già formattati.

---

## 3. Principi di progetto (vincolanti)

### 3.1 Semplicità e intuitività

- L'utente lavora con oggetti fisici (pozzo, fiume, barriera, zona di ricarica), date reali e unità tecniche (l/s, m³/anno, mm/anno, m/s). La traduzione in pacchetti, celle e stress period di MODFLOW è compito del software.
- L'interfaccia ha due livelli:
  - **base**: valori di default sensati e terminologia idrogeologica;
  - **esperto**: accesso alle opzioni di MF6.
  Il livello base non mostra mai un termine MODFLOW senza spiegarlo.
- Ogni campo di input mostra unità di misura, valore di default, intervallo plausibile e una descrizione breve.
- Lo stato del progetto è sempre visibile: cosa è definito, cosa manca per eseguire, cosa è cambiato dall'ultima esecuzione. Il confronto usa gli hash di contenuto del progetto e il manifest dell'ultimo run (sezioni 8 e 16).
- Il modello concettuale è indipendente dalla griglia: cambiare la griglia non richiede di ridefinire nulla.
- Ogni errore dice cosa è successo, dove (feature, cella, periodo) e come correggerlo.

### 3.2 Correttezza e precisione professionale

- **Test.** Ogni funzione di calcolo è coperta da test. Il motore è verificato contro soluzioni analitiche e casi di riferimento USGS (sezione 20).
- **Nessuna trasformazione silenziosa.** Conversioni di unità, cambi di CRS, ricampionamenti e troncamenti di spessore vengono registrati nel log del run. Se alterano i dati, compaiono anche come avviso.
- **Unità esplicite.** Le unità sono esplicite ovunque. Le unità interne del modello sono metri e giorni.
- **Tracciabilità.**
  - Ogni parametro conserva la sua origine e la sua incertezza.
  - Ogni run conserva un manifest con versioni del software, versione di MF6, hash del contenuto degli input e impostazioni.
- **Riproducibilità.** Stesso progetto e stessa versione producono gli stessi risultati entro la tolleranza del solutore; l'identità bit a bit tra sistemi operativi o build diverse non è garantita. I file di run si rigenerano sempre dal progetto.

### 3.3 Aggiornabilità e modificabilità

- **Componenti separati.** Il core non dipende da QGIS. Plugin e viewer sono client sostituibili.
- **Architettura a registri (sezione 21).** Aggiungere un tipo di condizione al contorno, un adattatore dati o un formato di export significa aggiungere un modulo che implementa un'interfaccia, senza toccare il resto.
- **Schema dati versionato.** Le migrazioni sono automatiche: i progetti vecchi si aprono sempre nelle versioni nuove.
- **Dipendenze isolate.** Vivono in un ambiente riproducibile con versioni bloccate, inclusi gli eseguibili esterni (MF6, GRIDGEN).
- **Documentazione nel repository.** Documentazione utente e sviluppatore stanno nel repository, generate e versionate insieme al codice.

---

## 4. Ambito e roadmap

1. **Fase 1 – Flusso** (milestone M1–M8, sezione 24). Comprende:
   - modello di flusso MF6 completo;
   - scenari come varianti del modello base;
   - risultati e report;
   - distribuzione con installer;
   - monitor in tempo reale;
   - import da FREEWAT;
   - geometria da sondaggi.
2. **Fase 2 – Calibrazione.** Comprende:
   - PEST++ IES e pyEMU;
   - pilot point;
   - analisi di incertezza;
   - statistiche di calibrazione.
3. **Fase 3 – Trasporto.** Comprende:
   - MF6 GWT: avvezione, dispersione, adsorbimento, decadimento;
   - sorgenti di contaminazione;
   - confronto con le analisi chimiche;
   - efficacia delle barriere in termini di massa.
4. **Fase 4 – Estensioni** [DA CONFERMARE]. Comprende:
   - zona insatura (UZF/UZT);
   - SFR;
   - densità variabile (BUY);
   - trasporto di calore (GWE);
   - catene di degradazione con accoppiamento a un codice geochimico.

Fuori ambito in fase 1:
- trasporto;
- calibrazione automatica;
- griglie DISU;
- più modelli accoppiati;
- esecuzione su cluster o cloud.

---

## 5. Architettura

Tre componenti:

1. **Core (`phrear`).** Pacchetto Python puro che contiene tutta la logica: modello dati, import, geometria, griglia, scrittura MF6, esecuzione, post-processing e report. Non importa nulla da QGIS o Qt. È esposto come API Python e come CLI.
2. **Plugin QGIS (`phrear_qgis`).** Interfaccia per QGIS 4 (Qt6): editing delle feature, form, procedure guidate, visualizzazione dei risultati. Non contiene logica di calcolo.
3. **Viewer 3D (`phrear_viewer`).** Applicazione separata basata su PyVista, per volumi, sezioni, superfici e traiettorie delle particelle.

Comunicazione tra i componenti:

- **Ambiente separato.** Il core gira in un ambiente Python dedicato, distinto da quello incluso in QGIS. Così si evitano i conflitti di dipendenze, frequenti su Windows, e l'interfaccia resta reattiva durante il calcolo.
- **CLI ed eventi.** Il plugin invoca la CLI del core come sottoprocesso. Avanzamento, avvisi, errori e risultati intermedi arrivano come eventi JSON, uno per riga su stdout, con uno schema versionato (sezione 16).
- **Scambio tramite file.** I dati passano sempre attraverso i file del progetto (GeoPackage, GeoTIFF, NetCDF), mai tramite oggetti condivisi in memoria.
- **Scritture strutturali dal core.** Il plugin può leggere e modificare direttamente il GeoPackage per l'editing. Le operazioni strutturali, come migrazioni e generazione della griglia, passano dal core. Il core non scrive sul GeoPackage mentre il plugin ha una sessione di editing aperta; il plugin chiude le sessioni prima di invocare un comando che scrive.
- **Schema condiviso.** Il plugin non importa il core, perché gira in un altro ambiente. Il comando `schema` esporta lo schema dei dati in JSON; il plugin lo usa per generare i form e validare l'editing.

```
QGIS 4 + plugin ──(CLI + eventi JSON)──> core phrear ──> MODFLOW 6 (mf6 / libmf6 via modflowapi)
      │                                      │
      └──── legge/modifica ── progetto (GeoPackage, TOML, raster, risultati) ──┘
                                             │
                               viewer 3D ────┘ (legge i risultati)
```

Comandi CLI minimi: `new`, `check`, `grid`, `params`, `bc`, `build`, `run`, `results`, `export`, `migrate`, `info`, `schema`, `calendar`, `import`, `scenario`, `verify`. Ogni comando accetta l'opzione `--json` per produrre l'output come eventi. Il comando `verify` esegue i test di verifica sull'installazione dell'utente e produce il report di affidabilità (sezione 20). Codici di uscita: 0 successo, 1 errore nell'input o nel progetto, 2 riga di comando non valida, 3 errore interno (ADR 0006).

---

## 6. Stack tecnologico [DA CONFERMARE]

| Ambito | Scelta |
|---|---|
| Linguaggio | Python 3.12 per il core; il Python incluso in QGIS 4 per il plugin |
| Motore di calcolo | MODFLOW 6.8.1 dal pacchetto `modflow6` di conda-forge, che contiene eseguibile e libmf6; versione bloccata nel lockfile e registrata nel manifest (ADR 0001) |
| CLI | argparse della libreria standard (ADR 0002) |
| Lettura e scrittura modelli | FloPy |
| Controllo del run | modflowapi (callback a ogni timestep) |
| Array e tabelle | numpy, pandas, xarray |
| Geodati | geopandas, shapely, pyogrio, rasterio, pyproj |
| Mesh e UGRID | xugrid, per NetCDF UGRID leggibili dai mesh layer di QGIS |
| Unità di misura | pint |
| Validazione della configurazione | pydantic |
| Interpolazione geostatistica (M2, M8) | gstools o equivalente |
| Griglie raffinate | GRIDGEN (quadtree) e/o Voronoi con generatore di punti proprio e shapely/GEOS, senza Triangle; XT3D per le griglie quadtree (sezione 14) |
| Grafici e report | matplotlib, openpyxl |
| Viewer 3D | PyVista (VTK) |
| Gestione dell'ambiente | pixi, con `pixi.lock` per win-64 (supportata) e linux-64 (solo sviluppo) |
| Qualità del codice | pytest, ruff, mypy, pre-commit, CI |
| Documentazione | Sphinx o MkDocs, pubblicata a ogni release |

Regola: nessuna nuova dipendenza senza una voce nel registro decisioni con motivo, alternative considerate e licenza.

---

## 7. Struttura del repository

```
phrear/
├─ src/phrear/
│  ├─ project/       # schema GeoPackage ed export JSON, project.toml, migrazioni, CRS, unità, hash di contenuto
│  ├─ data/
│  │  └─ adapters/   # un modulo per fonte: CSV, XLSX, banche dati regionali, FREEWAT
│  ├─ geology/       # superfici da raster o sondaggi, controlli stratigrafici, dizionario litologico
│  ├─ params/        # assegnazione parametri: uniforme, zone, raster, punti di prova; ricampionamento
│  ├─ conceptual/    # tipi di condizioni al contorno (registro), serie temporali, stazioni lungo le linee
│  ├─ timeline/      # date → stress period e timestep, file TS/TAS
│  ├─ scenarios/     # varianti rispetto al modello base
│  ├─ grid/          # DIS, DISV, raffinamento, layering
│  ├─ build/         # intersezione feature-griglia, scrittura MF6
│  ├─ checks/        # controlli pre-run (registro)
│  ├─ run/           # esecuzione, modflowapi, eventi, manifest, stop, run di tracciamento PRT
│  ├─ results/       # carichi, abbassamenti, bilanci, idrogrammi, particelle, statistiche, confronto scenari
│  ├─ report/        # export XLSX, CSV, grafici, mappe (registro)
│  ├─ events.py      # schema degli eventi JSON
│  ├─ errors.py      # gerarchia degli errori con codice e messaggio utente
│  └─ cli.py
├─ qgis_plugin/phrear_qgis/  # plugin QGIS 4: UI, provider Processing, traduzioni, template di layout
├─ viewer/                    # viewer 3D
├─ tests/
│  ├─ unit/
│  ├─ verification/   # soluzioni analitiche, esempi USGS
│  └─ regression/     # progetti di riferimento con risultati attesi
├─ examples/          # progetti dimostrativi completi
├─ docs/
│  ├─ SPEC.md         # questo documento
│  ├─ adr/            # registro delle decisioni architetturali
│  ├─ user/           # manuale utente (IT/EN)
│  └─ dev/            # guida per sviluppatori
├─ .github/workflows/ # CI
├─ pixi.toml + pixi.lock
├─ pyproject.toml
├─ LICENSE            # EUPL-1.2
└─ CHANGELOG.md
```

---

## 8. Formato del progetto e modello dati

Un progetto è una cartella:

```
nome_progetto/
├─ project.toml     # metadati, versione schema, CRS, unità, impostazioni
├─ model.gpkg       # modello concettuale: feature e tabelle
├─ rasters/         # superfici, DEM, parametri e carichi iniziali (GeoTIFF)
├─ runs/<run_id>/   # file MF6, log, risultati, manifest (rigenerabili)
└─ exports/         # tabelle, grafici, mappe prodotti
```

- **Fonte del progetto.** `project.toml`, `model.gpkg` e `rasters/` sono la fonte del progetto e si possono versionare con Git. Gli scenari stanno nel GeoPackage (sezione 8.2).
- **Cartelle rigenerabili.** `runs/` ed `exports/` si rigenerano dalla fonte del progetto.

### 8.1 project.toml (campi minimi)

- `schema_version`, `software_version_created`, `software_version_last_saved`.
- `crs`: codice EPSG del progetto. Default RDN2008/UTM 32N (EPSG:7791) oppure 33N (EPSG:7792), con assi in ordine E-N; i codici 6707 e 6708 hanno ordine N-E.
- `units`: unità preferite per inserimento e visualizzazione (`discharge`, `conductivity`, `recharge`, `storage`), ciascuna controllata contro la sua grandezza.
- `model.start_date`, `model.end_date`, `model.steady_initial` (booleano), `model.steady_reference` (inizio e fine del periodo di riferimento per le medie del periodo stazionario; se assente si usano i valori alla `start_date`), `model.period_breaks` (date dei cambi di regime indicate dall'utente).
- `time`: passi temporali automatici (`dt_initial_d`, `tsmult`, `dt_max_d`) e durata minima dei periodi (`min_period_d`), sezione 13.
- `dem`: raster del DEM e riferimento verticale.
- `initial_heads`: modalità (costante, raster, interpolazione delle misure alla `start_date`, risultato di un run precedente) con il relativo valore, raster o `run_id`.
- `grid`: tipo, dimensione base, rotazione e origine (convenzioni MF6: angolo in basso a sinistra, rotazione antioraria), spessore minimo (`min_thickness_m`, default 0,5 m), regola di attivazione delle celle (`activation`, `min_area_fraction`), tolleranza sul DEM (`dem_tolerance_m`), soglia di avviso sul numero di celle; regole di raffinamento da M4.
- `solver`: preset standard, robusto oppure esperto con le opzioni IMS. Con Newton o XT3D il preset usa BICGSTAB.
- `options.newton`: formulazione di Newton; default attivo per falde freatiche [DA CONFERMARE].
- `options.xt3d`: automatico per le griglie quadtree (sezione 14).

### 8.2 Layer e tabelle del GeoPackage

Campi comuni a tutti i layer di feature: `fid`, `name`, `active`, `notes`, `created_at`, `modified_at`, `scenario_id` (vuoto per il modello base).

| Layer o tabella | Geometria | Campi principali |
|---|---|---|
| `domain` | Poligono | contorno attivo del modello |
| `hydro_units` | – | `position` (1 = unità più alta), `name`, `geometry_mode` (raster/sondaggi/mista), `param_mode` (uniforme/zone/raster/interpolato), `convertible`, `sublayers`; i valori dei parametri stanno in `param_values` |
| `surfaces` | – | `surface_index` (0 = top del modello; i = bottom dell'unità i), `raster_path`, `source`, `vertical_datum` |
| `param_zones` | Poligono | `unit_id`; i valori stanno in `param_values` |
| `param_values` | – | `object_type` (unità, zona), `object_id`, `param` (kh, kv, anisotropy, ss, sy, ne, …), `value` oppure `raster_path`, `unit`, `source`, `min`, `max`, `std_log10` |
| `field_tests` | Punto | `type` (pompaggio, slug, Lefranc, Lugeon, granulometria), `result_param` (T, K, S), `value`, `unit`, `screen_top`, `screen_bottom`, `z_ref`, `depth_mode`, `ref_thickness` (spessore usato nell'interpretazione), `static_level` (livello statico alla data della prova), `unit_id`, `date`, `reliability` |
| `boreholes` | Punto | `code`, `z_collar`, `depth`, `source`, `reliability` |
| `borehole_intervals` | – | `borehole_id`, `from_depth`, `to_depth`, `description` (testo originale), `lith_class`, `unit_id` |
| `wells` | Punto | `role` (estrazione, iniezione), `screen_top`, `screen_bottom`, `z_ref`, `depth_mode` (profondità/quota), `radius`, `model_as` (auto/WEL/MAW), `series_id` oppure `rate` costante con `rate_unit` |
| `rivers` | Linea o poligono | `width`, `bed_thickness`, `bed_k`; livello e quota del fondo in `line_stations` |
| `drains` | Linea | `conductance_mode` (fisica/diretta), parametri fisici; quota in `line_stations` |
| `fixed_head_lines`, `fixed_head_areas` | Linea; poligono | `top_unit`, `bottom_unit` (unità interessate; vuoto = tutte); carico in `line_stations`. Da M3: `type` (carico imposto/carico generale) e parametri di conduttanza per GHB |
| `line_stations` | Punto | `feature_layer`, `feature_id`, `chainage` (progressiva in m, calcolata dalla posizione), `value` costante oppure `series_id` (livello o carico); da M3 `bed_bottom` o `elevation`; una sola stazione equivale a un valore uniforme |
| `barriers` | Linea | `k`, `thickness`, `top`, `bottom` |
| `recharge_zones` | Poligono | `rate` costante con `rate_unit`, oppure `series_id` |
| `distributed_inputs` | – | `kind` (ricarica, ET massima), `raster_path`, `unit`, `multiplier_series_id` |
| `et_zones` | Poligono | `surface` (default DEM), `max_rate_series_id`, `extinction_depth` |
| `budget_zones` | Poligono | `zone_name`, layer interessati |
| `observations` | Punto | `code`, `screen_top`, `screen_bottom`, `z_ref`, `depth_mode`, `unit_id`, `weight` (usato in fase 2) |
| `control_pairs` | – | `upstream_id`, `downstream_id`, `expected_sign`: coppie di piezometri per la verifica del gradiente |
| `timeseries_meta` | – | `series_id`, `name`, `quantity`, `unit`, `interpolation` (gradino/lineare) |
| `timeseries_values` | – | `series_id`, `datetime`, `value` |
| `obs_measurements` | – | `observation_id`, `datetime`, `value`, `value_type` (quota/soggiacenza), `quality` |
| `scenarios` | – | `scenario_id`, `name`, `description` |
| `scenario_changes` | – | `scenario_id`, `target_layer`, `target_fid`, `action` (disattiva/modifica), `field`, `value` |
| `change_log` | – | modifiche strutturali al progetto: migrazioni, import |

Regole:

- **Quote.** Le quote sono in metri s.l.m. I campi che accettano una profondità dichiarano esplicitamente il riferimento.
- **Unità originali.** Ogni valore inserito conserva la sua unità originale; la conversione avviene in `build`. Parametri e serie hanno una colonna `unit`. Gli altri attributi fisici diversi da quote e lunghezze hanno una colonna di unità affiancata (per esempio `bed_k_unit`).
- **Quote di riferimento.** Per pozzi, piezometri e prove `depth_mode` indica se filtri e misure sono espressi in profondità da `z_ref` o in quota. La conversione avviene in `build`.
- **Scenari.** Il modello base è l'insieme delle feature con `scenario_id` vuoto. Uno scenario aggiunge feature proprie e registra in `scenario_changes` le feature del modello base disattivate o modificate. Il core costruisce il modello di uno scenario applicando le differenze al modello base.
- **Hash di contenuto.** Per ogni tabella si calcola un hash del contenuto (righe ordinate per `fid`, geometrie in WKB), esclusa `layer_styles`; per i raster si usa l'hash del file. Gli hash servono al manifest (sezione 16) e allo stato "modificato dall'ultimo run" (sezione 3.1).
- **Schema unico.** Lo schema è definito in un unico modulo (`project/schema.py`). Creazione, validazione, export JSON e migrazioni derivano tutte da lì. L'elenco completo dei campi, con tipi, unità, default ed etichette, si ottiene con `phrear schema`. La tabella sopra ne è una sintesi e in caso di differenza prevale lo schema (ADR 0008).
- **Layer per tipo di geometria.** Le feature che possono essere linee o poligoni hanno un layer per ciascun tipo, perché QGIS digitalizza un solo tipo di geometria per layer (ADR 0008).

---

## 9. Flusso di lavoro dell'utente

1. **Nuovo progetto.** Si indicano nome, cartella, CRS, date di inizio e fine e unità preferite. I dati in CRS diversi, per esempio Gauss-Boaga (EPSG:3003/3004), vengono riproiettati all'import con le griglie di trasformazione ufficiali quando disponibili, anche fornite dall'utente in formato NTv2. Se si usa una trasformazione meno precisa, compare un avviso esplicito.
2. **Dominio.** Si disegna o si importa il contorno del modello e si carica il DEM.
3. **Stratigrafia.** Si caricano le superfici di contatto, cioè il top del modello e il bottom di ogni unità idrostratigrafica, da raster (modalità principale), oppure si usano i sondaggi (M8). Seguono controlli automatici e anteprima in sezione.
4. **Parametri.** Per ogni unità si assegnano valori uniformi, zone, raster o prove in sito, sempre con origine e intervallo, inclusa la porosità efficace.
5. **Condizioni al contorno.** Pozzi, fiumi, drenaggi, carichi imposti, barriere, ricarica ed evapotraspirazione si inseriscono come feature con attributi fisici e serie temporali datate. Per le feature lineari livelli, quote e carichi si assegnano a stazioni lungo il tracciato.
6. **Osservazioni e carichi iniziali.** Si inseriscono i piezometri con le misure, in quota o in soggiacenza, e le coppie di controllo per le barriere. Si scelgono i carichi iniziali: costante, raster, interpolazione delle misure alla data di inizio o risultato di un run precedente.
7. **Griglia.** Si scelgono tipo, dimensione base e raffinamento automatico attorno alle feature. L'anteprima mostra numero di celle e dimensione minima.
8. **Controlli.** Elenco di errori bloccanti e avvisi, ciascuno collegato alla feature o alla cella interessata.
9. **Esecuzione.** Monitor in tempo reale, con possibilità di interrompere il run.
10. **Risultati.** Mappe, bilanci, idrogrammi, zone di cattura, isocrone e tabelle esportabili.
11. **Scenari**. Varianti del modello base (per esempio con o senza barriera, portate diverse) che registrano solo le differenze, e confronto dei risultati.

---

## 10. Geometria e stratigrafia

### 10.1 Modalità

- **A – Raster (principale).** Superfici di contatto da GeoTIFF o da qualunque altro formato raster leggibile da GDAL. Per N unità servono N+1 superfici, cioè il top del modello e il bottom di ogni unità. Il top di un'unità coincide per costruzione con il bottom di quella sopra.
- **B – Sondaggi (M8).** I contatti tra unità si estraggono dagli intervalli dei sondaggi e si interpolano in superfici, per esempio con kriging con deriva esterna dal DEM. Il risultato include una mappa di incertezza.
- **C – Mista (M8).** I raster fanno da base. I sondaggi servono a verificarli, tramite gli scarti nei punti di sondaggio, oppure a correggerli localmente.

### 10.2 Controlli sulle superfici

- **Ordine.** Ogni superficie deve stare sotto quella precedente, o coincidere con essa dove l'unità si chiude. Dove non è così l'errore è bloccante, con mappa delle celle interessate.
- **DEM.** Il top del modello non deve superare il DEM di oltre una tolleranza configurabile (avviso). Un top sotto il DEM è ammesso, per esempio quando i terreni di copertura non sono modellati.
- **Copertura.** I raster devono coprire tutto il dominio, senza valori nodata al suo interno; una cella attiva senza valore è un errore bloccante. I raster devono essere nel sistema di riferimento del progetto.
- **Risoluzione.** Raster con risoluzioni diverse vengono ricampionati sulla griglia del modello con un metodo dichiarato. Per le quote il valore di una cella è la media sull'area della cella dell'interpolazione bilineare del raster, che per celle più piccole del pixel coincide con la bilineare al centro; il metodo non dipende dalla rotazione della griglia (ADR 0010). Per i parametri valgono le regole della sezione 11.
- **Spessori.** Gli spessori sotto il minimo configurato vengono segnalati.

### 10.3 Dalle unità ai layer del modello

- **Layer per unità.** Default: un layer per unità. Un'unità si può suddividere in N sotto-layer proporzionali.
- **Spessore nullo.** Dove un'unità ha spessore nullo o sotto il minimo, le celle diventano a passaggio verticale (IDOMAIN = -1). Non vengono disattivate, così il flusso verticale non si interrompe.
- **Quote derivate.** Le quote dei layer (top, botm) sono un prodotto derivato e si rigenerano a ogni `grid` e `build`.

### 10.4 Litologia da testo libero (solo modalità B e C)

- La descrizione originale si conserva sempre.
- Un dizionario configurabile assegna a ogni intervallo una classe litologica (ghiaia, sabbia, limo, argilla e loro combinazioni) e un'unità idrostratigrafica.
- Le assegnazioni automatiche si revisionano in una tabella. Quelle confermate dall'utente non vengono mai sovrascritte.
- La classe litologica fornisce un intervallo di K da letteratura come valore iniziale quando mancano prove in sito.

---

## 11. Parametri idrogeologici

Parametri richiesti da MF6 per il flusso:
- K orizzontale;
- K verticale, oppure rapporto di anisotropia;
- Ss e Sy;
- tipo di cella: confinata o convertibile.

Parametro richiesto dal tracciamento di particelle (PRT, pacchetto MIP) e in fase 3 dal trasporto:
- porosità efficace n_e.

Modalità di assegnazione per unità. Si possono combinare; la priorità è raster > campo interpolato > zone > uniforme.
1. Valore uniforme.
2. Zone poligonali.
3. Raster.
4. Campo interpolato in log K dai punti di prova (M2).

Ogni valore sta in `param_values` e registra:
- `unit`: unità di misura originale;
- `source`: prova di pompaggio, slug test, Lefranc, Lugeon, granulometria, letteratura, calibrazione o giudizio esperto;
- `min` e `max`, oppure la deviazione standard in log10. Sono la base per i limiti e le distribuzioni a priori di PEST++ in fase 2.

Ricampionamento sulla griglia, valido anche per le zone che coprono una cella solo in parte:
- Kh e Kv con media geometrica pesata sull'area;
- Ss, Sy e n_e con media aritmetica pesata sull'area.

Conversioni:
- **Da trasmissività a K.** La trasmissività di una prova di pompaggio diventa K = T / b, dove b è lo spessore usato nell'interpretazione della prova, registrato con la prova (`ref_thickness`) insieme al livello statico misurato alla data della prova. Se b manca, si stima da geometria e livello statico, con un avviso. Il carico iniziale del modello non si usa, per evitare una derivazione circolare. Il valore derivato conserva entrambi i dati di origine.
- **Da S a Ss.** Per le unità confinate, Ss = S / b.

Obbligatori per il run (ADR 0011):
- Kh e Ss per tutte le unità;
- Sy per le unità convertibili;
- esattamente uno tra Kv e Kv/Kh;
- l'unità di misura per K e Ss; per i parametri adimensionali vuota vale 1 e `%` vale 0,01;
- n_e da M5.

Controlli bloccanti:
- parametro o unità di misura mancante;
- K o Ss non positivi;
- Sy o n_e fuori da (0, 1);
- Kv e Kv/Kh indicati insieme.

Controlli come avviso:
- valore fuori dall'intervallo `[min, max]` dichiarato;
- valore fuori dagli intervalli plausibili generali (K tra 10⁻¹¹ e 10⁻¹ m/s, Kv/Kh tra 10⁻⁴ e 10, Ss tra 10⁻⁷ e 10⁻² 1/m, Sy tra 0,01 e 0,40, n_e tra 0,01 e 0,50); da M8 per classe litologica;
- Kv maggiore di Kh.

Il comando `params` mostra per ogni unità valore originale, valore nelle unità interne e origine.

---

## 12. Condizioni al contorno

| Concetto utente | Pacchetto MF6 | Input fisici | Calcolo |
|---|---|---|---|
| Pozzo con filtro in una sola unità | WEL | portata (l/s, m³/d, m³/anno), filtro | portata assegnata alla cella che contiene il filtro |
| Pozzo con filtro su più layer | WEL distribuito o MAW | portata, filtro, raggio | WEL: ripartizione proporzionale alla trasmissività dei tratti filtrati, T_k = K_k · l_k (da M1a). MAW: scelta automatica se `model_as = auto` [DA CONFERMARE] |
| Fiume, canale | RIV | livello (serie) e quota del fondo per stazioni lungo il tracciato, larghezza, spessore e K dell'alveo | C = K_alveo · L · W / M, con L lunghezza del tratto nella cella; layer scelto in base alla quota del fondo (rbot), che non può stare sotto il bottom della cella |
| Trincea drenante, drenaggio | DRN | quota per stazioni; parametri fisici o conduttanza diretta | come RIV, oppure conduttanza inserita |
| Carico imposto | CHD | carico (serie) per stazioni | solo layer con base sotto il carico minimo della simulazione (MF6 rifiuta carichi sotto la base) |
| Carico generale (limite distante) | GHB | carico (serie) per stazioni; distanza e K, oppure conduttanza | C = K · A / d, con K della cella, A = lato della cella × spessore saturo, d distanza dal limite |
| Diaframma, palancole | HFB | K, spessore, top, bottom | caratteristica idraulica = K / spessore, applicata ai soli layer intersecati verticalmente, sulle facce condivise tra celle adiacenti attraversate dalla linea; penetrazione parziale con hydchr equivalente (regole sotto) |
| Ricarica | RCH | tasso (mm/anno, mm/d), per zone o da raster con moltiplicatore nel tempo | conversione in m/d; si applica alla cella attiva più alta |
| Evapotraspirazione | EVT | superficie (default DEM), tasso massimo, profondità di estinzione | – |

Regole:

- **Intersezione con la griglia.** Le feature lineari e poligonali si intersecano con la griglia con shapely, calcolando lunghezze e aree effettive per cella; le celle sono chiuse, quindi una linea lungo un lato appartiene alle celle dei due lati (ADR 0012). I pozzi si assegnano punto → cella. Le barriere si intersecano con le facce condivise tra celle adiacenti; su DIS una barriera obliqua diventa una sequenza di facce a gradini, e la lunghezza effettiva viene riportata nel log.
- **Barriere a penetrazione parziale.** Se il piede della barriera cade dentro un layer, un HFB su tutta la faccia chiuderebbe anche il passaggio sotto il piede. Si usa una hydchr equivalente. Con f frazione ostruita della faccia, C_c conduttanza cella–cella e C_s conduttanza della faccia intera con la barriera in serie, la conduttanza totale è C_tot = f · C_s + (1 − f) · C_c, cioè il parallelo tra parte ostruita e parte libera. Ne segue hydchr_eq = [L · b · (1/C_tot − 1/C_c)]⁻¹, con L lunghezza della faccia e b spessore saturo. L'approssimazione trascura la deviazione verticale del flusso attorno al piede; se il piede cade a metà di un'unità spessa, un avviso suggerisce di suddividere il layer alla quota del piede.
- **Variazione lungo le linee.** I valori delle stazioni si interpolano linearmente per progressiva, con la progressiva del punto medio del tratto nella cella; oltre le stazioni di estremità vale il loro valore. Le serie di stazioni diverse si combinano sull'unione delle date, in modo esatto se sono tutte a gradino o tutte lineari; una linea non può mescolare i due tipi. Una linea si attiva quando tutte le sue stazioni sono definite. Un'area ha una sola stazione (ADR 0012).
- **Carichi imposti e layer.** Un layer riceve il carico solo se la sua base sta sotto il carico minimo della simulazione; un layer attraversato dal carico durante il run resta libero, con un avviso. Una cella con più carichi imposti tiene il primo (linee prima delle aree, per fid), con un avviso.
- **Ricarica.** Il tasso va alla cella attiva più alta, moltiplicato per la frazione della cella coperta dalla zona; zone sovrapposte si sommano, con un avviso.
- **Moltiplicatori.** Quote di portata per layer, segno dell'estrazione e frazioni d'area vanno nella variabile ausiliaria AUXMULTNAME di MF6, così valori e serie restano quelli inseriti.
- **Pozzi in celle convertibili con Newton.** Si attiva AUTO_FLOW_REDUCE e si esportano le portate effettive (AUTO_FLOW_REDUCE_CSV). Se la portata effettiva scende sotto quella di progetto, il run emette un avviso e i risultati riportano entrambe; in quel caso la portata di progetto non è sostenibile nella cella.
- **Tipi registrati.** Ogni tipo di condizione è registrato secondo la sezione 21: schema dei campi, validazione, generazione dell'input MF6, etichette IT/EN. Il comando `bc` mostra per pacchetto feature, celle e righe per periodo e con `--export` scrive le celle assegnate in `exports/bc.gpkg`.
- **Osservazioni.** Le osservazioni di carico generano il pacchetto OBS di MF6. Il confronto con le misure interpola i valori simulati alle date di misura. Un'opzione permette di far terminare un timestep in corrispondenza di ciascuna data di misura. Per i piezometri con filtro su più layer il carico simulato è la media dei carichi dei layer filtrati, pesata sulla trasmissività dei tratti filtrati.

---

## 13. Discretizzazione temporale

- **Stress period ai cambi di regime.** L'utente inserisce serie temporali con date. Un nuovo stress period inizia solo a un cambio di regime, cioè all'avvio del modello, alla prima data di una serie in uso (attivazione dell'oggetto che la usa) o a una data indicata dall'utente in `model.period_breaks` (per esempio l'avvio della barriera). Prima della prima data l'oggetto è inattivo (ADR 0009).
- **Serie dentro i periodi.** Le serie entrano nel modello tramite i file di serie temporali di MF6, TS per le condizioni a lista e TAS per gli array. MF6 applica a ogni timestep il valore medio della serie sull'intervallo, come verificato da un test che confronta i volumi del bilancio con l'integrale esatto delle serie.
- **Periodo iniziale.** Il primo periodo è stazionario, opzione attiva di default, e dura 1 d, quindi il tempo di simulazione 0 cade un giorno prima di `start_date`. Usa le medie esatte delle serie sul periodo di riferimento `model.steady_reference`; se non è indicato, usa i valori alla `start_date`. Gli oggetti che si attivano dopo l'avvio non partecipano al periodo stazionario.
- **Interpolazione delle serie.**
  - Serie a gradino (STEPWISE): ogni valore vale fino al punto successivo; l'ultimo vale fino alla fine del modello.
  - Serie lineari (LINEAR): interpolazione lineare tra i punti; una serie lineare in uso deve arrivare almeno alla fine del modello.
- **Timestep.** Per ogni periodo transitorio si sceglie il numero minimo di passi con il moltiplicatore più alto, non oltre `time.tsmult`, tali che il primo passo sia ≤ `time.dt_initial_d` e l'ultimo ≤ `time.dt_max_d`. Default 1 d, 1,2 e 30 d [DA CONFERMARE i valori]. Il passo massimo fissa la risoluzione con cui le serie entrano nel modello.
- **Durata minima.** È configurabile (`time.min_period_d`, default 1 d). I periodi più brevi vengono uniti al successivo, o al precedente se sono gli ultimi, con un avviso; le attivazioni interessate sono anticipate all'inizio del periodo unito.
- **Calendario visibile.** Prima del run l'utente vede la tabella periodo → date → numero di timestep, con il motivo di ogni cambio di regime (`phrear calendar`).

---

## 14. Griglia

- **DIS.** Celle regolari o a spaziatura variabile, con rotazione opzionale.
- **DISV (M4).** Raffinamento quadtree (GRIDGEN) o Voronoi attorno a pozzi, barriere, fiumi e zone indicate dall'utente. Per ogni tipo di feature si fissano dimensione obiettivo e numero di livelli di raffinamento. Le griglie quadtree non rispettano la condizione CVFD alle interfacce di raffinamento, perché la congiungente dei centri non è ortogonale alla faccia condivisa; si attiva quindi XT3D nel pacchetto NPF. Le griglie Voronoi la rispettano. Con XT3D il solutore usa BICGSTAB. Le griglie Voronoi si generano con un generatore di punti proprio, con densità funzione della distanza dalle feature e rilassamento di Lloyd, e con il diagramma di Voronoi di shapely/GEOS. Coppie di punti speculari rispetto a barriere e bordo del dominio allineano le facce delle celle a queste linee. Il centro di cella passato a MF6 è il punto generatore, che garantisce la condizione CVFD.
- **Celle fuori dominio.** Hanno IDOMAIN = 0. Una cella è attiva se il suo centroide cade nel dominio (default) oppure se la frazione d'area interna supera una soglia configurabile.
- **Anteprima.** Prima della generazione mostra:
  - numero di celle per layer;
  - dimensione minima e massima delle celle;
  - stima della memoria.
- **Nessun dato concettuale.** La griglia non contiene dati del modello concettuale: rigenerarla non richiede di ridefinire nulla.
- **Controlli.** Si controllano:
  - il rapporto di dimensione tra celle adiacenti;
  - le celle troppo sottili;
  - le celle isolate.

---

## 15. Controlli pre-run

Ogni controllo è un modulo registrato e comprende:
- severità: errore bloccante, avviso o informazione;
- messaggio in italiano e inglese;
- riferimento alla feature o alla cella interessata;
- suggerimento di correzione.

Elenco iniziale:

- **Geometria.**
  - Superfici incoerenti.
  - Spessori nulli non gestiti.
  - Dominio non coperto dai raster.
- **Parametri.**
  - Valori mancanti o fuori intervallo, inclusa la porosità efficace.
  - Kv maggiore di Kh.
- **Condizioni al contorno.**
  - Feature fuori dal dominio: errore per pozzi e carichi imposti, avviso per le zone di ricarica; avviso per le linee in parte fuori dalle celle attive.
  - Filtri dei pozzi fuori dalle celle attive: errore se del tutto fuori, avviso se in parte.
  - Livello del fiume sotto il fondo dell'alveo.
  - Fondo dell'alveo sotto il bottom della cella assegnata (MF6 lo rifiuta).
  - Quota di drenaggio sopra il top della cella.
  - Piede di una barriera a metà di un'unità spessa (avviso, suggerisce la suddivisione del layer).
  - Stazioni mancanti (errore) o lontane dalla linea a cui appartengono (avviso, oltre una cella).
  - Carico imposto sotto la base della cella (layer lasciato libero, errore se lo sono tutti).
  - Più carichi imposti nella stessa cella (avviso, vale il primo); CHD nella stessa cella di altre condizioni.
  - Zone di ricarica sovrapposte (avviso).
  - Serie temporali che non coprono il periodo simulato.
- **Condizioni iniziali.**
  - Carichi iniziali sotto la base dell'ultima cella attiva della colonna (avviso). Sotto la base di una cella convertibile superiore il carico è normale (ADR 0011).
  - Raster dei carichi che non copre le celle attive (errore).
- **Tempo.**
  - Periodi troppo brevi.
  - Nessuna osservazione nel periodo simulato (avviso).
- **Griglia.**
  - Numero di celle oltre una soglia configurabile (avviso).
  - Celle isolate.
- **Unità di misura.** Valori sospetti per ordine di grandezza, per esempio una portata in l/s inserita come m³/d. Unità incompatibili con la grandezza della serie (errore).

Solo gli errori bloccano il run. Gli avvisi restano registrati nel log del run.

---

## 16. Esecuzione e monitor in tempo reale

- **File e manifest.** Il core genera i file MF6 in `runs/<run_id>/` e scrive un `manifest.json` con:
  - versione del software e versione di MF6;
  - hash di contenuto di `project.toml`, delle tabelle del GeoPackage e dei raster (sezione 8.2);
  - impostazioni del run;
  - data e ora.
- **Esecuzione e istantanee.** Il run usa modflowapi con libmf6. Una callback a fine timestep emette gli eventi. Ogni N timestep (configurabile) scrive un'istantanea dei carichi per il monitor. Ogni istantanea è un file nuovo, mai modificato dopo la scrittura, perché su Windows un NetCDF aperto in QGIS resta bloccato (lock HDF5).
- **Eventi JSON.** Uno per riga in UTF-8, con campo `schema` versionato (ADR 0006). Ogni comando emette `command_started`, `progress`, `command_completed` o `command_failed`. Gli eventi del run sono:
  - `run_started`, `period_started`;
  - `timestep_completed`, con periodo, passo, tempo simulato, iterazioni, massima variazione di carico ed errore di bilancio percentuale;
  - `snapshot_written`, `warning`, `error`, `flow_reduced` (pozzo con portata effettiva inferiore a quella di progetto);
  - `run_completed`, `run_failed`.
- **Interruzione.** Il plugin crea un file di stop nella cartella del run; la callback lo controlla a ogni timestep. Il core chiude la simulazione in modo pulito al primo timestep utile e conserva i risultati parziali. Con l'eseguibile `mf6` il processo viene terminato e restano i risultati scritti fino all'ultimo timestep completato.
- **Mancata convergenza.** Il messaggio indica periodo, timestep e celle con i residui maggiori. Suggerisce anche cosa provare: attivare Newton, ridurre il passo, controllare le celle che si asciugano.
- **Listing file.** Il listing file di MF6 viene analizzato; errori e avvisi di MF6 arrivano all'utente in forma leggibile.
- **Fallback.** Se libmf6 non è disponibile, il run usa l'eseguibile `mf6`, senza monitor dettagliato.
- **Run di tracciamento.** PRT gira come simulazione separata, che legge carichi e flussi di un run di flusso completato tramite l'interfaccia FMI. Ha un proprio `run_id` e un manifest che rimanda al run di flusso.

---

## 17. Risultati e report

Prodotti da generare:

- **Carichi e abbassamenti.**
  - Carichi per layer e per tempo.
  - Abbassamenti rispetto allo stato iniziale o a uno scenario di riferimento.
  - Isopieze con intervallo configurabile e direzioni di flusso.
- **Bilanci.**
  - Bilancio idrico globale e per zona (`budget_zones`), per periodo e cumulato.
  - Dettaglio per componente: pozzi, fiumi, ricarica, drenaggi, flussi tra zone, immagazzinamento.
- **Portate dei pozzi.** Portate effettive confrontate con quelle di progetto, per pozzo e per periodo.
- **Confronto con le osservazioni.**
  - Idrogrammi simulati contro osservati.
  - Carico simulato nei piezometri con filtro su più layer pesato sulla trasmissività (sezione 12).
  - Statistiche ME, MAE, RMSE, RMSE normalizzato.
  - Grafico osservati/simulati.
- **Verifica delle barriere.** Differenza di carico nel tempo per ogni coppia di controllo, con evidenza dei periodi in cui il gradiente non è invertito.
- **Zona di cattura dei pozzi.** Mappa dell'area il cui flusso termina nei pozzi, con tracciamento all'indietro dai pozzi oppure in avanti da una griglia di particelle su tutto il dominio.
- **Efficienza di cattura del plume.** Tracciamento in avanti con PRT dall'impronta del plume, con rilascio 3D nei layer interessati e densità configurabile. Restituisce la percentuale di particelle catturate dai pozzi barriera.
- **Isocrone.** Isocrone dei pozzi a uso potabile per le zone di rispetto, con tempi configurabili (per esempio 60, 180, 365 giorni). Richiedono tracciamento all'indietro: PRT su carichi e flussi invertiti nel segno e nel tempo, in coerenza con la decisione 1. Tracciamento, zone di cattura e isocrone usano la porosità efficace (sezione 11).
- **Confronto tra scenari.** Differenze di carico, bilanci e portate tra uno scenario e il modello base o un altro scenario.
- **Errore di bilancio di massa.** Riportato per ogni periodo.

Formati di export:

- **NetCDF UGRID**, con una variabile per layer, per i mesh layer di QGIS con dimensione temporale.
- **GeoTIFF e GeoPackage** per mappe e isolinee.
- **XLSX e CSV** per le tabelle, con intestazioni chiare, unità e metadati del run.
- **PNG e SVG** per i grafici, con stile coerente e pronti per le relazioni.
- **Mappe.** Il core produce i dati (GeoTIFF, GeoPackage) e mappe semplici in PNG (matplotlib) per l'uso da CLI. Le tavole da relazione si impaginano con template di layout QGIS forniti dal plugin (sezione 18).

Ogni export registra il `run_id` da cui deriva.

---

## 18. Interfaccia QGIS e principi UX

Componenti del plugin:

- **Pannello di progetto ad albero:** Progetto → Dominio → Stratigrafia → Parametri → Condizioni al contorno → Osservazioni → Griglia → Scenari → Run → Risultati. Ogni voce mostra il suo stato: completo, incompleto o con errori.
- **Form delle feature** con unità, default, intervalli e descrizioni, generati dallo schema JSON esportato dal core (sezione 5). L'editing avviene direttamente sulla mappa con gli strumenti standard di QGIS.
- **Procedure guidate** per i passaggi iniziali: nuovo progetto, import della stratigrafia, prima griglia.
- **Algoritmi Processing** per ogni comando del core, utilizzabili in batch e nel Model Builder.
- **Pannello di esecuzione:**
  - avanzamento del run;
  - grafico della convergenza;
  - mappa dei carichi aggiornata dalle istantanee;
  - pulsante di stop.
- **Pannello dei risultati:**
  - scelta di run, scenario, layer e tempo;
  - bilanci e idrogrammi;
  - export.
- **Template di layout** per le tavole delle relazioni (carichi, abbassamenti, isopieze, zone di cattura, isocrone).
- **Traduzioni IT/EN** con il sistema standard di Qt.

Principi:

- **Terminologia.** Nel livello base si usa la terminologia idrogeologica. I termini MF6 compaiono solo nel livello esperto o tra parentesi.
- **Conferme.** Nessuna azione distruttiva senza conferma. Le operazioni rigenerabili, come griglia e build, non chiedono conferma.
- **Risultati caricati.** I risultati si caricano in un gruppo di layer dedicato, con stile predefinito.
- **Coerenza.** Nomi, unità e colori sono gli stessi in plugin, report e viewer.

---

## 19. Viewer 3D

- Applicazione separata (PyVista/VTK), aperta dal plugin su un run o sulla sola geometria.
- Contenuti visualizzabili:
  - unità idrostratigrafiche, esplose o tagliate;
  - sezioni verticali lungo una polilinea;
  - superfici piezometriche;
  - carichi e abbassamenti nel volume;
  - traiettorie delle particelle;
  - pozzi con i filtri e barriere.
- Esagerazione verticale regolabile; export di immagini e animazioni.
- Il viewer legge solo i file del progetto e non modifica mai il modello.

---

## 20. Verifica e qualità

Livelli di test:

- **Unitari.** Coprono ogni funzione del core.
- **Di verifica.** Confronto con soluzioni analitiche, entro tolleranze dichiarate:
  - Thiem: pozzo in falda confinata, regime stazionario;
  - Theis: pozzo in falda confinata, regime transitorio;
  - flusso monodimensionale tra due carichi imposti;
  - Dupuit: falda freatica, regime stazionario, verifica della formulazione di Newton (M1a);
  - Hantush: falda semiconfinata (M2);
  - Javandel–Tsang: zona di cattura di un pozzo in flusso uniforme, con punto di ristagno a valle x₀ = Q / (2π b q) e larghezza massima a monte Q / (b q), dove q è il flusso specifico regionale (M5);
  - Wyssling: isocrone di un pozzo in flusso uniforme (M5);
  - tempo di percorso in flusso uniforme, t = n_e · L / q (M5).

  Per i test con pozzo (Thiem, Theis, Dupuit) il confronto si fa su punti ad almeno 3 celle dal pozzo, perché il carico della cella pozzo differisce dal carico nel pozzo.

  Tolleranze sull'errore assoluto massimo nei punti di confronto, riferito all'abbassamento massimo s_max negli stessi punti: Thiem 1 %; Theis e Dupuit 3 %; flusso monodimensionale entro la tolleranza di chiusura del solutore.
- **Confronto con gli esempi ufficiali MF6**, dove applicabile.
- **Di regressione.** Progetti di esempio con risultati attesi. Ogni modifica che altera quei risultati va giustificata.
- **Confronto con FREEWAT.** Progetti importati confrontati con gli originali su DIS identica (M7).
- **Di interfaccia.** Test del plugin, per esempio con pytest-qgis [DA CONFERMARE].

Ogni test di verifica produce un breve report, con grafico analitico contro numerico ed errore massimo, incluso nella documentazione. È la prova di affidabilità da mostrare agli utenti professionali. Il comando `verify` rigenera gli stessi report sull'installazione dell'utente.

CI e versioni:
- **CI a ogni modifica:** test, linting, type check e build della documentazione.
- **Prima di ogni release:** test di verifica completi.
- **Versionamento:** semantic versioning. Ogni release aggiorna il CHANGELOG e dichiara la versione di MF6 supportata.

---

## 21. Estendibilità e manutenzione

Registri interni:

- **`BoundaryConditionType`:**
  - nome ed etichette IT/EN;
  - schema dei campi con unità e intervalli;
  - validazione;
  - conversione in input MF6;
  - stile QGIS.
- **`DataAdapter`:**
  - riconoscimento del formato;
  - lettura;
  - mappatura sullo schema interno;
  - report di import.
- **`Check`:** id, severità, funzione di controllo, messaggio e suggerimento.
- **`Exporter`:** formato, opzioni e funzione di scrittura.
- **`ResultProduct`:** calcolo di un prodotto (bilancio, idrogramma, zona di cattura) a partire dai file del run.

Aggiungere una funzione significa scrivere un modulo che implementa l'interfaccia e registrarlo. Dove possibile, il plugin genera form e voci di menu dagli schemi JSON esportati dal core con il comando `schema`, senza codice UI dedicato.

Schema dati:
- **Versione e migrazioni.** La versione dello schema sta in `project.toml`. Le migrazioni sono numerate in `project/migrations/` e ognuna è testata su un progetto della versione precedente.
- **Backup.** Quando si apre un progetto vecchio, il software propone la migrazione e crea prima una copia di backup.

Compatibilità:
- **Versioni di QGIS.** Il core non dipende dalla versione di QGIS. Il plugin dichiara la versione minima di QGIS 4 supportata.
- **Aggiornamenti di MF6 e FloPy.** Prima del rilascio passano i test di verifica e di regressione.

---

## 22. Convenzioni di codice

- **Lingua.** Codice, identificatori, commenti e docstring sono in inglese. I testi dell'interfaccia stanno nei file di traduzione IT/EN.
- **Tipi.** Type hints ovunque; mypy in modalità rigorosa sul core.
- **Core isolato.** Nessun import di `qgis` o `PyQt` nel core, verificato da un test automatico.
- **Funzioni pure.** Le funzioni di calcolo sono pure dove possibile; l'I/O resta separato dalla logica.
- **Unità.** Ogni grandezza fisica in input passa da pint. Dentro `build` si usano solo metri e giorni.
- **Errori.** La gerarchia degli errori sta in `errors.py`. Ogni errore ha:
  - un `code`;
  - un messaggio utente IT/EN;
  - un dettaglio tecnico;
  - il riferimento all'oggetto interessato.
- **Logging.** Logging strutturato; nessun `print` nel core.
- **Docstring.** Le docstring indicano l'unità di misura di ogni parametro fisico.
- **Test obbligatori.** Nessuna funzionalità senza test.

---

## 23. Metodo di lavoro per l'agente

Per ogni milestone:

1. Rileggi le sezioni pertinenti di questo documento e il registro decisioni.
2. Proponi un piano breve: moduli da creare o modificare, interfacce, test. Se una scelta [DA CONFERMARE] incide sull'architettura, chiedi prima di procedere.
3. Implementa per piccoli incrementi, ognuno con i suoi test, mantenendo la CI verde.
4. Aggiorna la documentazione utente e sviluppatore insieme al codice.
5. Registra le decisioni prese, nella sezione 27 e in `docs/adr/`.
6. Chiudi la milestone verificando i criteri di accettazione (sezione 24). Riporta cosa è stato fatto, cosa resta e quali rischi vedi.

Regole:

- **Niente aggiunte non registrate.** Non introdurre dipendenze, formati o comportamenti non previsti senza registrarli.
- **Niente scorciatoie sulla fisica.** Non semplificare la fisica per far passare un test: se un risultato non torna, segnalalo.
- **Semplicità.** Preferisci soluzioni semplici e leggibili a generalizzazioni premature, rispettando però le interfacce di registro della sezione 21.
- **Ambiguità.** Se un requisito del documento è ambiguo o contraddittorio, chiedi.
- **Codice di terzi.** Il codice di FREEWAT è GPL-2.0 e non può entrare nel core EUPL-1.2. Si consulta solo per ricavare il formato dei database da importare. Lo stesso vale per qualunque codice con licenza incompatibile.

---

## 24. Milestone e criteri di accettazione

### M1a – Core, CLI e verifica numerica

**Ambito:**
- struttura del repository, ambiente e CI;
- schema di progetto v1 con `domain`, `hydro_units`, `surfaces`, `param_values`, `wells`, `fixed_heads` (solo CHD), `line_stations`, `recharge_zones`, `timeseries_meta`, `timeseries_values`, `scenarios` e `scenario_changes` (solo struttura);
- geometria da raster con superfici di contatto e DEM;
- parametri uniformi per unità;
- pozzi (WEL, anche con filtro su più layer), carichi imposti (CHD) da stazioni lungo linee e su aree, ricarica (RCH) per zone;
- carichi iniziali costanti o da raster;
- griglia DIS;
- stress period ai cambi di regime e file TS;
- build e run di MF6 tramite eseguibile;
- manifest con hash di contenuto;
- infrastruttura dei registri (`BoundaryConditionType`, `Check`, `Exporter`) con i controlli di base;
- comando `schema`;
- carichi esportati in NetCDF UGRID;

**Criteri di accettazione:**
- test di verifica Thiem, Theis e Dupuit superati entro la tolleranza dichiarata;
- un progetto di esempio completo, eseguibile da CLI;
- nessun import di QGIS nel core;
- guida rapida per l'uso da CLI e guida iniziale per gli sviluppatori.

### M1b – Plugin minimo

**Ambito:** plugin minimo che crea il progetto, carica i layer, esegue tramite la CLI e carica i risultati come mesh layer; form generati dallo schema JSON.

**Accettazione:** il progetto di esempio di M1a eseguito dal plugin dà risultati identici a quelli da CLI; guida rapida per l'utente del plugin.

### M2 – Parametri completi

**Ambito:**
- assegnazione per zone, raster e punti di prova;
- interpolazione in log K;
- origine e intervalli per ogni valore;
- porosità efficace;
- regole di ricampionamento dei parametri;
- conversioni T → K e S → Ss;
- controlli sui parametri.

**Accettazione:** un progetto di esempio con parametri a zone e da prove in sito, più un report dei parametri assegnati per cella con la loro origine. Test di verifica Hantush superato.

### M3 – Condizioni al contorno complete

**Ambito:**
- pacchetti RIV, DRN, GHB, HFB, EVT e MAW;
- stazioni lungo le linee;
- HFB sulle facce, con penetrazione parziale;
- ricarica ed ET da raster;
- AUTO_FLOW_REDUCE con export delle portate effettive;
- OBS, con piezometri su più layer;
- serie temporali lineari e a gradino;
- calendario degli stress period visibile.

**Accettazione:**
- test unitari per ogni tipo di condizione;
- conduttanze verificate a mano su casi semplici;
- un caso di verifica per HFB, con flusso attraverso la barriera, anche a penetrazione parziale.

### Verifica su caso reale (tra M3 e M4)

**Ambito:** un caso reale fornito dall'utente, costruito ed eseguito con le funzioni di M1a–M3 tramite il plugin.

**Accettazione:** modello eseguito e risultati discussi con l'utente; elenco dei problemi di usabilità e delle correzioni, approvato prima di avviare M4.

### M4 – Griglia raffinata e controlli

**Ambito:**
- DISV con raffinamento automatico e XT3D per le griglie quadtree;
- anteprima della griglia;
- registro dei controlli completo.

**Accettazione:**
- lo stesso progetto risolto su DIS e su DISV dà differenze entro tolleranza;
- tutti i controlli della sezione 15 sono coperti da test.

### M5 – Risultati e report

**Ambito:**
- bilanci per zona;
- abbassamenti e isopieze;
- idrogrammi con statistiche;
- verifica delle coppie di controllo;
- zona di cattura dei pozzi, efficienza di cattura del plume, isocrone con PRT all'indietro;
- portate effettive dei pozzi;
- scenari e confronto dei risultati;
- template di layout QGIS per le tavole;
- export XLSX, CSV e PNG.

**Accettazione:** report completo generato sui due progetti di esempio, "barriera idraulica" e "concessione", con almeno due scenari ciascuno. Test di verifica Javandel–Tsang, Wyssling e tempo di percorso superati.

### M6 – Distribuzione

**Ambito:**
- installer dell'ambiente del core con versioni bloccate, inclusi MF6 e gli eseguibili esterni;
- individuazione dell'ambiente da parte del plugin;
- aggiornamento dell'ambiente e del plugin;
- pubblicazione del plugin nel repository ufficiale QGIS.

**Accettazione:** installazione pulita sui sistemi operativi supportati [DA DEFINIRE] da parte di un utente non sviluppatore, senza passaggi manuali oltre all'installer, ed esecuzione di un progetto di esempio dal plugin.

### M7 – Monitor e import

**Ambito:**
- esecuzione via modflowapi con eventi e istantanee;
- stop del run;
- analisi del listing file;
- import di progetti FREEWAT e MODFLOW-2005, secondo una strategia da scrivere prima dell'avvio: array convertiti in raster sulla griglia originale, celle con condizioni convertite in feature, confronto su DIS identica e documentazione delle differenze attese tra il wetting di MF2005 e la formulazione di Newton di MF6.

**Accettazione:**
- monitor funzionante nel plugin;
- almeno [N, DA DEFINIRE] progetti FREEWAT reali importati, con risultati confrontati con gli originali.

### M8 – Geometria da sondaggi e banche dati

**Ambito:**
- modalità B e C;
- dizionario litologico con tabella di revisione;
- adattatori CSV e XLSX;
- adattatori per le banche dati regionali [elenco DA DEFINIRE].

**Accettazione:** superfici interpolate con incertezza su un caso reale, confrontate con i raster esistenti.

**Stato attuale:** M1a in corso. Completati gli incrementi 1 (scheletro del repository, ambiente, CI), 2 (unità, errori, eventi JSON), 3 (formato del progetto, comandi `new`, `info`, `schema`, `migrate`) 4 (serie temporali, stress period, passi temporali, comando `calendar`), 5 (griglia DIS, superfici, layer, controlli geometrici, comando `grid`), 6 (parametri uniformi per unità, carichi iniziali costanti o da raster, comando `params`) e 7 (registro delle condizioni al contorno, WEL, CHD da stazioni, RCH, comando `bc`).

---

## 25. Questioni aperte

- [DA CONFERMARE] Contributi esterni accettati solo con un accordo di contribuzione (CLA), per conservare la possibilità di doppia licenza.
- [DA DEFINIRE] Distribuzione: come l'utente installa l'ambiente del core e come il plugin lo trova.
- [DA DEFINIRE] Lingue dell'interfaccia nella prima versione.
- [DA CONFERMARE] Scelta automatica tra WEL e MAW per i pozzi con filtro su più layer.
- [DA CONFERMARE] Formulazione di Newton attiva di default.
- [DA DEFINIRE] Elenco delle banche dati regionali da supportare e relativi formati.
- [DA DEFINIRE] Progetti FREEWAT reali disponibili per i test di import. Già disponibile il database completo del tutorial di intrusione salina (`sw.sqlite`, modello del Cornia).
- [DA DEFINIRE] Lavoro in team sullo stesso progetto e processo di revisione QA/QC.

---

## 26. Glossario

| Termine utente | Termine MF6 / tecnico | Note |
|---|---|---|
| Unità idrostratigrafica | – | uno o più layer del modello |
| Superficie di contatto | – | top del modello o bottom di un'unità |
| Strato del modello | layer | |
| Cella a passaggio verticale | IDOMAIN = -1 | unità di spessore nullo |
| Periodo di sollecitazione | stress period | inizia a un cambio di regime |
| Passo temporale | time step | |
| Serie temporale | TS, TAS | valori che variano dentro uno stress period |
| Pozzo | WEL / MAW | |
| Fiume | RIV | |
| Drenaggio | DRN | |
| Carico imposto | CHD | |
| Carico generale | GHB | |
| Barriera fisica | HFB | |
| Ricarica | RCH | |
| Evapotraspirazione | EVT | |
| Conducibilità idraulica orizzontale/verticale | K, K33 | pacchetto NPF |
| Immagazzinamento specifico, resa specifica | Ss, Sy | pacchetto STO |
| Porosità efficace | POROSITY | pacchetto MIP del modello PRT |
| Zona di cattura | – | area il cui flusso termina nei pozzi; PRT all'indietro dai pozzi o in avanti da una griglia |
| Efficienza di cattura | – | percentuale delle particelle rilasciate nel plume catturate dai pozzi (PRT in avanti) |
| Isocrona | – | tracciamento all'indietro (PRT su flussi invertiti) |
| Bilancio per zona | ZONEBUDGET | |
| Scenario | – | variante con le sole differenze rispetto al modello base |

---

## 27. Registro decisioni

| # | Data | Decisione | Motivazione | Alternative scartate |
|---|---|---|---|---|
| 1 | 2026-11-03 | MODFLOW 6 come unico motore | È la versione core dell'USGS e integra flusso, trasporto, particelle e calore | MODFLOW-2005, NWT |
| 2 | 2026-11-03 | Core indipendente da QGIS + plugin QGIS 4 + viewer 3D separato | Evitare il blocco che ha colpito FREEWAT con le API di QGIS 2; il GIS è già disponibile | Solo plugin; software autonomo |
| 3 | 2026-11-03 | Modello concettuale separato dalla griglia | La griglia si rigenera senza perdere dati | Modello per celle (FREEWAT) |
| 4 | 2026-11-03 | Geometria primaria da raster top/bottom; sondaggi opzionali | È la prassi attuale degli utenti e i dati spesso esistono già | Solo sondaggi |
| 5 | 2026-11-03 | Ogni parametro con origine e intervallo | Tracciabilità e base per la calibrazione con PEST++ | Solo valore puntuale |
| 6 | 2026-11-03 | Stress period generati dalle date | Gli utenti ragionano in date | Periodi inseriti a mano |
| 7 | 2026-11-03 | Ordine delle fasi: flusso → calibrazione → trasporto | Il trasporto richiede un campo di flusso calibrato | Flusso e trasporto insieme |
| 8 | 2026-11-03 | Scenari come varianti del modello base | Confronto diretto tra alternative progettuali senza duplicare i dati | Copie del progetto |
| 9 | 2026-11-03 | Parametri in una tabella unica `param_values`, con unità e origine | Nuovi parametri senza migrazioni; unità esplicite | Colonne fisse per parametro |
| 10 | 2026-11-03 | N+1 superfici di contatto | Vuoti e sovrapposizioni esclusi per costruzione | Coppie top/bottom per unità |
| 11 | 2026-11-03 | Valori a stazioni lungo le feature lineari | Gradiente di livello lungo fiumi e limiti | Un valore per feature |
| 12 | 2026-11-03 | Ricarica ed ET anche da raster (M3) | Necessarie per i modelli regionali | Solo zone poligonali |
| 13 | 2026-11-03 | HFB con hydchr equivalente per la penetrazione parziale | Mantiene il layering per unità; avviso nei casi critici | Suddivisione automatica dei layer |
| 14 | 2026-11-03 | Stress period ai cambi di regime, serie con file TS/TAS (sostituisce in parte la 6) | Evita migliaia di periodi e non altera le serie | Unione dei punti di cambio di tutte le serie |
| 15 | 2026-11-03 | Periodo stazionario sulle medie di un periodo di riferimento | Condizioni iniziali rappresentative | Solo valori alla data di inizio |
| 16 | 2026-11-03 | Mappe semplici dal core, tavole con layout QGIS | Core indipendente da QGIS; qualità da relazione | Impaginazione nel core |
| 17 | 2026-11-03 | Isocrone con PRT su flussi invertiti | Un solo motore (decisione 1) | MODPATH 7 |
| 18 | 2026-11-03 | Milestone di distribuzione dopo M5 | L'installazione è stata il limite pratico principale di FREEWAT | Installer a fine progetto |
| 19 | 2026-11-03 | XT3D per le griglie quadtree | Le quadtree violano la condizione CVFD alle interfacce di raffinamento | Solo Voronoi; nessuna correzione |
| 20 | 2026-11-03 | CRS di default EPSG:7791/7792 | Assi E-N, nessuna inversione di coordinate | EPSG:6707/6708 |
| 21 | 2026-11-03 | Porosità efficace tra i parametri di fase 1 | Richiesta da PRT per zone di cattura e isocrone | Rinvio alla fase 3 |
| 22 | 2026-11-03 | M1 divisa in M1a (core, CLI, verifica) e M1b (plugin minimo) | Numerica e modello dati validati prima dell'interfaccia; il plugin si appoggia su una CLI stabile | M1 unica |
| 23 | 2026-11-03 | Verifica su caso reale tra M3 e M4 | Problemi di usabilità individuati quando correggerli costa poco | Verifica a fine fase 1 |
| 24 | 2026-11-03 | Voronoi con generatore di punti proprio e shapely/GEOS | Dipendenze open source; facce allineabili a barriere e bordo | Triangle tramite FloPy |
| 25 | 2026-11-03 | Nome Phrear, pacchetto `phrear` | Dal greco φρέαρ, pozzo, radice di "freatico"; libero su PyPI, senza omonimie nel settore | phlow (occupato su PyPI), phreflux (assonanza con reflux), falda |
| 26 | 2026-11-03 | Core EUPL-1.2, plugin GPL-2.0-or-later | Copyleft anche per l'uso in rete; testo ufficiale in italiano; compatibile con la GPL e con le dipendenze; per il plugin la GPL è richiesta da QGIS | Apache-2.0, GPL-3.0-or-later |
| 27 | 2026-11-03 | Repository e CI su GitHub (ADR 0003) | Ecosistema QGIS, MF6 e FloPy già su GitHub; runner Windows senza configurazione | GitLab |
| 28 | 2026-11-03 | Per ora solo Windows; Linux solo per lo sviluppo (ADR 0003) | Piattaforma degli utenti target | Windows e Linux supportati da subito |
| 29 | 2026-11-03 | pixi con lockfile, Python 3.12, MF6 6.8.1 da conda-forge (ADR 0001) | Versioni bloccate inclusi gli eseguibili; GDAL e PROJ affidabili su Windows | conda con environment.yml, pip con venv, get-modflow |
| 30 | 2026-11-03 | CLI con argparse (ADR 0002) | Nessuna dipendenza; controllo diretto di stdout per gli eventi JSON | click, typer |
| 31 | 2026-11-03 | Unità interne per grandezza, anno giuliano di 365,25 d (ADR 0005) | Conversioni esplicite e tracciabili; default di pint | Anno di 365 d; solo sintassi nativa di pint |
| 32 | 2026-11-03 | Eventi JSON Lines UTF-8 su stdout binario, messaggi IT/EN, codici di uscita 0–3 (ADR 0006) | Indipendenza dalla codifica della console Windows; il plugin sceglie la lingua | Testo libero; una sola lingua; PYTHONIOENCODING |
| 33 | 2026-11-03 | project.toml letto con tomllib, validato con pydantic, scritto con tomlkit (ADR 0007) | Errori con il percorso della voce; commenti dell'utente conservati | tomli-w; scrittura manuale |
| 34 | 2026-11-03 | Schema GeoPackage v1: un layer per tipo di geometria, nomi senza parole riservate, default nello schema, timestamp da trigger, hash di contenuto canonici, migrazioni con backup (ADR 0008) | Compatibilità con la digitalizzazione di QGIS; tracciabilità senza falsi positivi | Layer `Geometry` misti; hash del file; tutte le tabelle subito |
| 35 | 2026-11-03 | Serie indefinite prima della prima data (attivazione), periodo stazionario di 1 d, accorpamento dei periodi brevi, passi con moltiplicatore massimo compatibile con primo e ultimo passo (ADR 0009) | Volumi conservati esattamente, verificati con MF6; nessuna estrapolazione silenziosa | Unione dei punti di cambio; valore a inizio passo; nstp e tsmult fissi |
| 36 | 2026-11-03 | Griglia DIS con convenzioni MF6; superfici come media sulla cella della bilineare; copertura stretta; raster nel CRS del progetto; superfici incrociate come errore; DEM come avviso (ADR 0010) | Metodo esatto per superfici lineari a ogni rotazione; nessuna correzione silenziosa | Average di GDAL (impreciso su griglie ruotate); riproiezione automatica; troncamento degli spessori |
| 37 | 2026-11-03 | Parametri uniformi per unità con unità di misura obbligatoria per K e Ss; Kh, Ss, Kv o Kv/Kh obbligatori, Sy solo per le unità convertibili; intervalli plausibili generali come avviso; carichi iniziali costanti o da raster, avviso solo sotto l'ultima cella attiva (ADR 0011) | Nessun default silenzioso su grandezze dimensionali; avvisi solo su condizioni anomale | Unità vuota come unità interna; Kv = Kh di default; intervalli per litologia prima di M8; avviso su ogni cella sotto la base |
| 38 | 2026-11-03 | Registro `BoundaryConditionType`; intersezioni con shapely su celle chiuse; WEL ripartito per trasmissività dei tratti filtrati (anticipato da M3); CHD interpolato per progressiva con serie combinate sull'unione delle date, attivazione dell'intera linea, solo layer con base sotto il carico minimo, prima feature nelle sovrapposizioni; RCH alla cella attiva più alta con frazione d'area; moltiplicatori in AUXMULTNAME (ADR 0012) | Vincoli di MF6 verificati (CHD sotto la base e CHD doppi rifiutati, righe WEL/RCH multiple accettate); volumi e carichi esatti nel tempo | FloPy GridIntersect; carico costante nel periodo; stazione più vicina; CHD su tutti i layer; errore sulle sovrapposizioni CHD |
