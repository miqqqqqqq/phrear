# 0011 – Parametri uniformi per unità e carichi iniziali

- Data: 2026-11-03
- Stato: accettata

## Contesto

La milestone M1a chiede parametri uniformi per unità e carichi iniziali costanti o da raster (sez. 24). La sezione 11 elenca i parametri richiesti da MF6 e i controlli, ma non dice quali mancanze bloccano il run, come si trattano le unità di misura né come si controllano i carichi iniziali.

## Decisione

- **Lettura.** Ogni riga di `param_values` con `object_type = unit` e `object_id` uguale al fid di un'unità dà un valore uniforme. Il valore si converte nelle unità interne (m/d per K, 1/m per Ss, adimensionale per Sy, n_e e Kv/Kh) e conserva valore originale, unità, origine, `min` e `max`.
- **Unità di misura.** Per K e Ss è obbligatoria (`params.unit_missing`); per i parametri adimensionali vuota vale 1 e `%` vale 0,01. `min` e `max` sono nella stessa unità del valore.
- **Parametri obbligatori.** Kh e Ss per tutte le unità; Sy per le unità convertibili; esattamente uno tra Kv e Kv/Kh. Una mancanza è un errore bloccante con il riferimento all'unità. Sy per le unità confinate e n_e sono facoltativi; n_e diventerà obbligatorio con il tracciamento di particelle (M5).
- **Errori.** K o Ss non positivi; Sy o n_e fuori da (0, 1); Kv e Kv/Kh indicati insieme; righe senza valore; raster, zone e `param_mode` diversi da `uniform`, che arrivano in M2.
- **Avvisi.** Valore fuori da `[min, max]` dichiarato; valore fuori da intervalli plausibili generali (K tra 10⁻¹¹ e 10⁻¹ m/s, Kv/Kh tra 10⁻⁴ e 10, Ss tra 10⁻⁷ e 10⁻² 1/m, Sy tra 0,01 e 0,40, n_e tra 0,01 e 0,50); Kv maggiore di Kh.
- **Layer.** Ogni sotto-layer prende i valori della sua unità. ICELLTYPE e ICONVERT valgono 1 per le unità convertibili e 0 per le confinate; per queste Sy vale 0, perché MF6 non lo usa.
- **Carichi iniziali.** Valore costante oppure raster campionato sulla griglia con lo stesso metodo delle superfici (ADR 0010), applicato a tutti i layer. Una cella attiva non coperta dal raster è un errore. Le modalità `interpolated` (M3) e `run` non sono ancora disponibili.
- **Controllo dei carichi iniziali.** Avviso se il carico è sotto la base dell'ultima cella attiva della colonna. Un carico sotto la base di una cella convertibile superiore è normale e non produce avvisi.
- **Comando `params`.** Tabella per unità con valore originale, valore interno e origine, più gli avvisi; con `--json` un evento `result` con gli stessi dati.

## Alternative scartate

- **Unità di misura vuota come unità interna.** Un valore di K in m/s scritto senza unità verrebbe letto in m/d, con un errore di un fattore 86 400.
- **Intervalli plausibili per classe litologica.** Richiedono la litologia delle unità, che arriva con i sondaggi (M8).
- **Avviso su ogni cella con carico sotto la base.** Segnalerebbe come anomala la condizione normale di un acquifero freatico sotto i terreni di copertura.
- **Kv dedotto come Kh in assenza di dati.** Sarebbe un default silenzioso su un parametro che controlla il flusso verticale.

## Conseguenze

- I controlli sui parametri vivono per ora nel caricamento; con l'incremento 8 diventano moduli del registro `Check` con gli stessi codici.
- La porosità efficace va inserita prima di M5; il controllo diventerà bloccante in quella milestone.
