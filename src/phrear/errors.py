"""Errors shown to the user (docs/SPEC.md, sections 3.1 and 22).

Every error has a stable ``code``, a message and a hint in Italian and English,
an optional technical ``detail`` and an optional reference to the object involved
(feature, cell, period, file, ...). Message templates live in :data:`CATALOG`,
so the same code always produces the same text in both languages.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

Lang = Literal["it", "en"]
LANGS: tuple[Lang, ...] = ("it", "en")


@dataclass(frozen=True)
class Localized:
    """A value whose text differs by language, e.g. the name of a physical quantity."""

    it: str
    en: str

    def get(self, lang: Lang) -> str:
        return self.it if lang == "it" else self.en


FieldValue = str | int | float | Localized


@dataclass(frozen=True)
class Message:
    """Message and hint templates of an error code, in both languages."""

    it: str
    en: str
    hint_it: str = ""
    hint_en: str = ""

    def template(self, lang: Lang) -> str:
        return self.it if lang == "it" else self.en

    def hint_template(self, lang: Lang) -> str:
        return self.hint_it if lang == "it" else self.hint_en


CATALOG: dict[str, Message] = {
    "cli.usage": Message(
        it="Comando non valido. {reason}",
        en="Invalid command. {reason}",
        hint_it="Esegui «phrear --help» per l'elenco dei comandi e delle opzioni.",
        hint_en="Run 'phrear --help' for the list of commands and options.",
    ),
    "unit.unknown": Message(
        it="Unità di misura non riconosciuta «{unit}».",
        en="Unrecognised unit '{unit}'.",
        hint_it="Usa una forma come m/s, l/s, m³/d, mm/anno o 1/m.",
        hint_en="Use a form such as m/s, l/s, m3/d, mm/year or 1/m.",
    ),
    "unit.dimension": Message(
        it="L'unità «{unit}» non è compatibile con la grandezza {quantity}, "
        "che si esprime per esempio in {expected}.",
        en="Unit '{unit}' is not compatible with {quantity}, "
        "which is expressed for example in {expected}.",
        hint_it="Controlla l'unità indicata e il campo a cui si riferisce.",
        hint_en="Check the unit and the field it refers to.",
    ),
    "project.exists": Message(
        it="La cartella «{path}» esiste e non è vuota.",
        en="Folder '{path}' exists and is not empty.",
        hint_it="Scegli una cartella nuova o vuota per il progetto.",
        hint_en="Choose a new or empty folder for the project.",
    ),
    "project.not_found": Message(
        it="In «{path}» non c'è un progetto, perché manca project.toml.",
        en="'{path}' is not a project, because project.toml is missing.",
        hint_it="Indica la cartella che contiene project.toml, oppure crea un progetto "
        "con «phrear new».",
        hint_en="Give the folder that contains project.toml, or create a project "
        "with 'phrear new'.",
    ),
    "project.config_syntax": Message(
        it="Il file project.toml contiene un errore di sintassi. {reason}",
        en="project.toml has a syntax error. {reason}",
        hint_it="Controlla virgolette, parentesi quadre e date nel formato AAAA-MM-GG.",
        hint_en="Check quotes, square brackets and dates in the YYYY-MM-DD format.",
    ),
    "project.config_invalid": Message(
        it="Valore non valido in project.toml, alla voce «{location}». {reason}",
        en="Invalid value in project.toml at '{location}'. {reason}",
        hint_it="Correggi la voce indicata e riprova.",
        hint_en="Fix the entry and try again.",
    ),
    "project.crs_unknown": Message(
        it="Il codice EPSG:{epsg} non corrisponde a nessun sistema di riferimento noto.",
        en="EPSG:{epsg} is not a known coordinate reference system.",
        hint_it="Usa per esempio EPSG:7791 (RDN2008 / UTM 32N) o EPSG:7792 (UTM 33N).",
        hint_en="Use for example EPSG:7791 (RDN2008 / UTM 32N) or EPSG:7792 (UTM 33N).",
    ),
    "project.crs_not_metric": Message(
        it="Il sistema EPSG:{epsg} ({crs_name}) non è proiettato in metri.",
        en="EPSG:{epsg} ({crs_name}) is not a projected system in metres.",
        hint_it="Il modello lavora in metri. Usa per esempio EPSG:7791 (RDN2008 / UTM 32N) "
        "o EPSG:7792 (UTM 33N).",
        hint_en="The model works in metres. Use for example EPSG:7791 (RDN2008 / UTM 32N) "
        "or EPSG:7792 (UTM 33N).",
    ),
    "project.schema_too_new": Message(
        it="Il progetto usa lo schema {found}, più recente di quello supportato ({supported}).",
        en="The project uses schema {found}, newer than the supported one ({supported}).",
        hint_it="Aggiorna Phrear alla versione che ha creato il progetto o successiva.",
        hint_en="Update Phrear to the version that created the project or later.",
    ),
    "project.migration_required": Message(
        it="Il progetto usa lo schema {found}, mentre questa versione usa lo schema {supported}.",
        en="The project uses schema {found}, while this version uses schema {supported}.",
        hint_it="Esegui «phrear migrate», che prima crea una copia di backup del progetto.",
        hint_en="Run 'phrear migrate', which first makes a backup copy of the project.",
    ),
    "project.gpkg_missing": Message(
        it="Nel progetto «{path}» manca il file model.gpkg.",
        en="Project '{path}' has no model.gpkg file.",
        hint_it="Ripristina il file da una copia di backup o ricrea il progetto.",
        hint_en="Restore the file from a backup or recreate the project.",
    ),
    "project.gpkg_tables_missing": Message(
        it="Nel file model.gpkg mancano le tabelle {tables}.",
        en="model.gpkg lacks the tables {tables}.",
        hint_it="Il file è stato modificato fuori da Phrear o è danneggiato. Ripristina "
        "una copia di backup.",
        hint_en="The file was changed outside Phrear or is damaged. Restore a backup copy.",
    ),
    "series.invalid_quantity": Message(
        it="La serie «{series_id}» ha una grandezza non ammessa «{quantity}».",
        en="Series '{series_id}' has an unsupported quantity '{quantity}'.",
        hint_it="Scegli quota o carico (length), portata (discharge) o ricarica (velocity).",
        hint_en="Choose elevation or head (length), discharge, or recharge (velocity).",
    ),
    "series.empty": Message(
        it="La serie «{series_id}» non ha valori.",
        en="Series '{series_id}' has no values.",
        hint_it="Aggiungi almeno una coppia data-valore in timeseries_values.",
        hint_en="Add at least one date-value pair in timeseries_values.",
    ),
    "series.orphan_values": Message(
        it="Ci sono valori della serie «{series_id}», che non è definita in timeseries_meta.",
        en="There are values for series '{series_id}', which is not defined in timeseries_meta.",
        hint_it="Aggiungi la serie in timeseries_meta oppure elimina quei valori.",
        hint_en="Add the series to timeseries_meta or delete those values.",
    ),
    "series.bad_datetime": Message(
        it="Data non valida «{value}» nella serie «{series_id}».",
        en="Invalid date '{value}' in series '{series_id}'.",
        hint_it="Usa il formato AAAA-MM-GG oppure AAAA-MM-GGTHH:MM:SS.",
        hint_en="Use the YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format.",
    ),
    "series.not_defined": Message(
        it="L'oggetto usa la serie «{series_id}», che non è definita.",
        en="The object uses series '{series_id}', which is not defined.",
        hint_it="Correggi il codice della serie oppure aggiungila in timeseries_meta.",
        hint_en="Fix the series code or add the series to timeseries_meta.",
    ),
    "series.not_covered": Message(
        it="La serie «{series_id}» va dal {start} al {end}, ma serve dal {needed_start} "
        "al {needed_end}.",
        en="Series '{series_id}' spans {start} to {end}, but {needed_start} to "
        "{needed_end} is needed.",
        hint_it="Aggiungi valori che coprano l'intervallo richiesto. Una serie lineare "
        "deve arrivare almeno alla fine del modello.",
        hint_en="Add values covering the required interval. A linear series must reach "
        "at least the end of the model.",
    ),
    "series.after_end": Message(
        it="La serie «{series_id}» inizia il {start}, dopo la fine del modello, quindi "
        "l'oggetto non è mai attivo.",
        en="Series '{series_id}' starts on {start}, after the end of the model, so the "
        "object is never active.",
        hint_it="Controlla le date della serie o il periodo del modello.",
        hint_en="Check the series dates or the model period.",
    ),
    "time.period_merged": Message(
        it="Il periodo dal {start} al {end} dura {duration_d} d, meno del minimo di "
        "{min_d} d, ed è unito al periodo adiacente. Le attivazioni del {moved_from} "
        "passano al {moved_to}.",
        en="The period from {start} to {end} lasts {duration_d} d, less than the minimum "
        "of {min_d} d, and is merged with the adjacent one. Activations on {moved_from} "
        "move to {moved_to}.",
        hint_it="Riduci time.min_period_d in project.toml oppure sposta le date di "
        "attivazione o i cambi di regime.",
        hint_en="Lower time.min_period_d in project.toml or move the activation dates "
        "or the regime changes.",
    ),
    "time.too_many_steps": Message(
        it="Il periodo di {length_d} d richiede più di {limit} passi temporali con le "
        "impostazioni attuali.",
        en="The {length_d} d period needs more than {limit} time steps with the current settings.",
        hint_it="Aumenta time.dt_initial_d o time.dt_max_d in project.toml.",
        hint_en="Increase time.dt_initial_d or time.dt_max_d in project.toml.",
    ),
    "grid.cell_size_missing": Message(
        it="Manca la dimensione delle celle della griglia.",
        en="The grid cell size is missing.",
        hint_it="Indica grid.cell_size_m in project.toml, in metri.",
        hint_en="Set grid.cell_size_m in project.toml, in metres.",
    ),
    "grid.type_not_available": Message(
        it="La griglia di tipo {grid_type} non è ancora disponibile.",
        en="Grid type {grid_type} is not available yet.",
        hint_it='Per ora usa grid.type = "dis"; le griglie DISV arrivano con M4.',
        hint_en='Use grid.type = "dis" for now; DISV grids come with M4.',
    ),
    "grid.isolated_cells": Message(
        it="{n_cells} celle attive non sono collegate a nessun'altra cella attiva, per "
        "esempio layer {layer}, riga {row}, colonna {col}.",
        en="{n_cells} active cells are not connected to any other active cell, for example "
        "layer {layer}, row {row}, column {col}.",
        hint_it="Controlla il dominio e gli spessori delle unità in quella zona.",
        hint_en="Check the domain and the unit thicknesses in that area.",
    ),
    "grid.many_cells": Message(
        it="La griglia ha {n_cells} celle, oltre la soglia di {limit}.",
        en="The grid has {n_cells} cells, above the threshold of {limit}.",
        hint_it="Aumenta grid.cell_size_m oppure alza grid.max_cells_warning se è voluto.",
        hint_en="Increase grid.cell_size_m or raise grid.max_cells_warning if intended.",
    ),
    "geometry.no_domain": Message(
        it="Il layer domain non contiene un dominio attivo del modello base.",
        en="The domain layer has no active domain of the base model.",
        hint_it="Disegna o importa il contorno del modello nel layer domain.",
        hint_en="Draw or import the model outline in the domain layer.",
    ),
    "geometry.domain_invalid": Message(
        it="La geometria del dominio non è valida. {reason}",
        en="The domain geometry is not valid. {reason}",
        hint_it="Correggila in QGIS, per esempio con «Correggi geometrie».",
        hint_en="Fix it in QGIS, for example with 'Fix geometries'.",
    ),
    "geometry.no_units": Message(
        it="Non ci sono unità idrostratigrafiche.",
        en="There are no hydrostratigraphic units.",
        hint_it="Aggiungi almeno un'unità nella tabella hydro_units.",
        hint_en="Add at least one unit to the hydro_units table.",
    ),
    "geometry.unit_positions": Message(
        it="Le posizioni delle unità devono essere 1, 2, 3, … senza salti; trovate {positions}.",
        en="Unit positions must be 1, 2, 3, … without gaps; found {positions}.",
        hint_it="Correggi il campo position della tabella hydro_units.",
        hint_en="Fix the position field of the hydro_units table.",
    ),
    "geometry.surfaces_mismatch": Message(
        it="Per {n_units} unità servono le superfici da 0 a {n_units}; trovate {indices}.",
        en="{n_units} units need surfaces 0 to {n_units}; found {indices}.",
        hint_it="La superficie 0 è il tetto del modello, la superficie i la base dell'unità i.",
        hint_en="Surface 0 is the model top, surface i the bottom of unit i.",
    ),
    "geometry.raster_missing": Message(
        it="Il raster «{path}» non esiste.",
        en="Raster '{path}' does not exist.",
        hint_it="Il percorso è relativo alla cartella del progetto; di solito sta in rasters/.",
        hint_en="The path is relative to the project folder; usually under rasters/.",
    ),
    "geometry.raster_unreadable": Message(
        it="Il raster «{path}» non si può leggere.",
        en="Raster '{path}' cannot be read.",
        hint_it="Controlla che sia un formato raster leggibile da GDAL, per esempio GeoTIFF.",
        hint_en="Check that it is a raster format readable by GDAL, for example GeoTIFF.",
    ),
    "geometry.raster_crs": Message(
        it="Il raster «{path}» è nel sistema {raster_crs}, diverso da quello del progetto "
        "(EPSG:{epsg}).",
        en="Raster '{path}' is in {raster_crs}, different from the project CRS (EPSG:{epsg}).",
        hint_it="Riproietta il raster in QGIS nel sistema del progetto.",
        hint_en="Reproject the raster in QGIS to the project CRS.",
    ),
    "geometry.raster_no_crs": Message(
        it="Il raster «{path}» non dichiara un sistema di riferimento; si assume quello del "
        "progetto (EPSG:{epsg}).",
        en="Raster '{path}' declares no coordinate system; the project one (EPSG:{epsg}) is "
        "assumed.",
        hint_it="Assegna il sistema corretto al raster in QGIS per togliere l'ambiguità.",
        hint_en="Assign the correct CRS to the raster in QGIS to remove the ambiguity.",
    ),
    "geometry.raster_coverage": Message(
        it="Il raster «{path}» non copre {n_cells} celle attive, per esempio riga {row}, "
        "colonna {col}.",
        en="Raster '{path}' does not cover {n_cells} active cells, for example row {row}, "
        "column {col}.",
        hint_it="Estendi il raster a tutto il dominio, senza valori nodata al suo interno.",
        hint_en="Extend the raster over the whole domain, without nodata values inside it.",
    ),
    "geometry.surfaces_crossing": Message(
        it="La superficie {lower} sta sopra la superficie {upper} in {n_cells} celle, fino a "
        "{max_m} m, per esempio riga {row}, colonna {col}.",
        en="Surface {lower} lies above surface {upper} in {n_cells} cells, by up to {max_m} m, "
        "for example row {row}, column {col}.",
        hint_it="Correggi i raster; dove un'unità si chiude le due superfici devono coincidere.",
        hint_en="Fix the rasters; where a unit pinches out the two surfaces must coincide.",
    ),
    "geometry.thin_unit": Message(
        it="L'unità {unit} ha spessore inferiore al minimo di {min_m} m in {n_cells} celle, "
        "che diventano a passaggio verticale.",
        en="Unit {unit} is thinner than the minimum of {min_m} m in {n_cells} cells, which "
        "become vertical pass-through cells.",
        hint_it="Se è voluto non serve fare nulla; altrimenti controlla le superfici o "
        "grid.min_thickness_m.",
        hint_en="If intended nothing is needed; otherwise check the surfaces or "
        "grid.min_thickness_m.",
    ),
    "geometry.empty_columns": Message(
        it="In {n_cells} colonne del dominio tutte le unità sono sotto lo spessore minimo; "
        "quelle colonne sono disattivate.",
        en="In {n_cells} domain columns every unit is below the minimum thickness; those "
        "columns are deactivated.",
        hint_it="Controlla le superfici di contatto in quella zona.",
        hint_en="Check the contact surfaces in that area.",
    ),
    "geometry.top_above_dem": Message(
        it="Il tetto del modello supera il DEM di più di {tolerance_m} m in {n_cells} celle, "
        "fino a {max_m} m.",
        en="The model top exceeds the DEM by more than {tolerance_m} m in {n_cells} cells, "
        "by up to {max_m} m.",
        hint_it="Controlla il raster della superficie 0 e il riferimento verticale del DEM.",
        hint_en="Check the raster of surface 0 and the vertical datum of the DEM.",
    ),
    "params.mode_not_available": Message(
        it="L'unità {unit} usa «{mode}», non ancora disponibile in questa versione.",
        en="Unit {unit} uses '{mode}', not yet available in this version.",
        hint_it="Per ora indica valori uniformi per unità.",
        hint_en="For now give uniform values per unit.",
    ),
    "params.source_not_available": Message(
        it="Il parametro {param} dell'unità {unit} rimanda a {what}, non ancora disponibile "
        "in questa versione.",
        en="Parameter {param} of unit {unit} refers to {what}, not yet available in this version.",
        hint_it="Per ora indica un valore uniforme nel campo value.",
        hint_en="For now give a uniform value in the value field.",
    ),
    "params.unknown_unit": Message(
        it="Una riga di param_values si riferisce all'unità con fid {fid}, che non esiste.",
        en="A param_values row refers to the unit with fid {fid}, which does not exist.",
        hint_it="Correggi object_id oppure elimina la riga.",
        hint_en="Fix object_id or delete the row.",
    ),
    "params.unknown_zone": Message(
        it="Una riga di param_values si riferisce alla zona con fid {fid}, che non esiste.",
        en="A param_values row refers to the zone with fid {fid}, which does not exist.",
        hint_it="Correggi object_id oppure elimina la riga.",
        hint_en="Fix object_id or delete the row.",
    ),
    "params.zone_unknown_unit": Message(
        it="La zona {zone} si riferisce all'unità con fid {fid}, che non esiste.",
        en="Zone {zone} refers to the unit with fid {fid}, which does not exist.",
        hint_it="Scegli l'unità idrostratigrafica della zona.",
        hint_en="Choose the hydrostratigraphic unit of the zone.",
    ),
    "params.zone_invalid": Message(
        it="La geometria della zona {zone} non è valida: {reason}.",
        en="The geometry of zone {zone} is not valid: {reason}.",
        hint_it="Correggila con Vettore → Strumenti di geometria → Correggi geometrie.",
        hint_en="Fix it with Vector → Geometry Tools → Fix Geometries.",
    ),
    "params.zone_empty": Message(
        it="La zona {zone} non ha parametri e non cambia il modello.",
        en="Zone {zone} has no parameters and does not change the model.",
        hint_it="Aggiungi i parametri dal form della zona, oppure eliminala.",
        hint_en="Add the parameters from the form of the zone, or delete it.",
    ),
    "params.zones_overlap": Message(
        it="Le zone {first} e {second} dell'unità {unit} si sovrappongono per {area} m².",
        en="Zones {first} and {second} of unit {unit} overlap by {area} m².",
        hint_it="Le zone di una stessa unità non devono sovrapporsi: correggi i contorni.",
        hint_en="Zones of the same unit must not overlap: fix their outlines.",
    ),
    "params.cells_without_value": Message(
        it="Il parametro {param} dell'unità {unit} non ha valore in {n_cells} celle attive.",
        en="Parameter {param} of unit {unit} has no value in {n_cells} active cells.",
        hint_it="Dai all'unità un valore uniforme, oppure estendi le zone fino a coprirle.",
        hint_en="Give the unit a uniform value, or extend the zones to cover them.",
    ),
    "params.missing": Message(
        it="Manca il parametro {param} per l'unità {unit}.",
        en="Parameter {param} is missing for unit {unit}.",
        hint_it="Aggiungi una riga in param_values con object_type = unit, object_id = {fid} "
        "e param = {param_code}.",
        hint_en="Add a param_values row with object_type = unit, object_id = {fid} and "
        "param = {param_code}.",
    ),
    "params.value_missing": Message(
        it="La riga del parametro {param} dell'unità {unit} non ha un valore.",
        en="The row of parameter {param} of unit {unit} has no value.",
        hint_it="Compila il campo value.",
        hint_en="Fill the value field.",
    ),
    "params.unit_missing": Message(
        it="Il parametro {param} dell'unità {unit} non ha l'unità di misura.",
        en="Parameter {param} of unit {unit} has no unit of measure.",
        hint_it="Compila il campo unit, per esempio {example}.",
        hint_en="Fill the unit field, for example {example}.",
    ),
    "params.kv_or_anisotropy": Message(
        it="Per l'unità {unit} serve K verticale oppure l'anisotropia Kv/Kh.",
        en="Unit {unit} needs either vertical K or the anisotropy Kv/Kh.",
        hint_it="Aggiungi una riga con param = kv oppure param = anisotropy.",
        hint_en="Add a row with param = kv or param = anisotropy.",
    ),
    "params.kv_and_anisotropy": Message(
        it="Per l'unità {unit} sono indicati sia K verticale sia l'anisotropia Kv/Kh.",
        en="Unit {unit} has both vertical K and the anisotropy Kv/Kh.",
        hint_it="Tieni solo uno dei due, per evitare valori in contraddizione.",
        hint_en="Keep only one of the two, to avoid contradictory values.",
    ),
    "params.not_positive": Message(
        it="Il parametro {param} dell'unità {unit} deve essere positivo; vale {value}.",
        en="Parameter {param} of unit {unit} must be positive; it is {value}.",
        hint_it="Correggi il valore o la sua unità di misura.",
        hint_en="Fix the value or its unit.",
    ),
    "params.not_fraction": Message(
        it="Il parametro {param} dell'unità {unit} deve essere compreso tra 0 e 1; vale {value}.",
        en="Parameter {param} of unit {unit} must be between 0 and 1; it is {value}.",
        hint_it="Se il valore è in percentuale, indica % come unità.",
        hint_en="If the value is a percentage, give % as unit.",
    ),
    "params.implausible": Message(
        it="Il parametro {param} dell'unità {unit} vale {value} {internal}, fuori "
        "dall'intervallo plausibile {low}–{high} {internal}.",
        en="Parameter {param} of unit {unit} is {value} {internal}, outside the plausible "
        "range {low}–{high} {internal}.",
        hint_it="Controlla valore e unità di misura.",
        hint_en="Check value and unit.",
    ),
    "params.kv_above_kh": Message(
        it="Nell'unità {unit} K verticale ({kv} m/d) supera K orizzontale ({kh} m/d).",
        en="In unit {unit} vertical K ({kv} m/d) exceeds horizontal K ({kh} m/d).",
        hint_it="È raro nei depositi stratificati; controlla i valori.",
        hint_en="This is rare in layered deposits; check the values.",
    ),
    "params.outside_declared_range": Message(
        it="Il parametro {param} dell'unità {unit} vale {value}, fuori dall'intervallo "
        "dichiarato [{low}, {high}] nella stessa unità di misura.",
        en="Parameter {param} of unit {unit} is {value}, outside its declared range "
        "[{low}, {high}] in the same unit.",
        hint_it="Correggi il valore oppure min e max.",
        hint_en="Fix the value or min and max.",
    ),
    "bc.geometry_missing": Message(
        it="La feature {feature} del layer {layer} non ha geometria.",
        en="Feature {feature} of layer {layer} has no geometry.",
        hint_it="Disegna la geometria oppure disattiva la feature (active = 0).",
        hint_en="Draw the geometry or deactivate the feature (active = 0).",
    ),
    "bc.outside_active": Message(
        it="La feature {feature} del layer {layer} non interessa nessuna cella attiva.",
        en="Feature {feature} of layer {layer} does not touch any active cell.",
        hint_it="Controlla la posizione rispetto al dominio e le unità interessate; una linea "
        "sul bordo del dominio va spostata verso l'interno di mezza cella.",
        hint_en="Check its position against the domain and the units affected; a line on the "
        "domain boundary should be moved inwards by half a cell.",
    ),
    "bc.maw_not_available": Message(
        it="Il pozzo {feature} va rappresentato con MAW, disponibile da M3.",
        en="Well {feature} is to be represented with MAW, available from M3.",
        hint_it="Per ora usa model_as = auto oppure wel.",
        hint_en="For now use model_as = auto or wel.",
    ),
    "bc.z_ref_missing": Message(
        it="Il pozzo {feature} ha i filtri in profondità ma non la quota di riferimento z_ref.",
        en="Well {feature} has its screen as depths but no reference elevation z_ref.",
        hint_it="Compila z_ref in m s.l.m. oppure indica il filtro in quota con "
        "depth_mode = elevation.",
        hint_en="Fill z_ref in m a.s.l. or give the screen as elevations with "
        "depth_mode = elevation.",
    ),
    "bc.screen_order": Message(
        it="Il filtro del pozzo {feature} va da {top} a {bottom} m s.l.m.; l'inizio deve "
        "stare sopra la fine.",
        en="The screen of well {feature} goes from {top} to {bottom} m a.s.l.; its top must be "
        "above its bottom.",
        hint_it="Controlla screen_top, screen_bottom e depth_mode.",
        hint_en="Check screen_top, screen_bottom and depth_mode.",
    ),
    "bc.screen_outside": Message(
        it="Il filtro del pozzo {feature} ({top}–{bottom} m s.l.m.) non attraversa nessuna "
        "cella attiva della colonna riga {row}, colonna {col}.",
        en="The screen of well {feature} ({top}–{bottom} m a.s.l.) crosses no active cell of "
        "the column at row {row}, column {col}.",
        hint_it="Confronta le quote del filtro con quelle delle superfici del modello.",
        hint_en="Compare the screen elevations with those of the model surfaces.",
    ),
    "bc.value_missing": Message(
        it="La feature {feature} del layer {layer} non ha né un valore costante né una serie.",
        en="Feature {feature} of layer {layer} has neither a constant value nor a series.",
        hint_it="Compila {field} oppure series_id.",
        hint_en="Fill {field} or series_id.",
    ),
    "bc.unit_missing": Message(
        it="La feature {feature} del layer {layer} non ha l'unità di misura di {field}.",
        en="Feature {feature} of layer {layer} has no unit of measure for {field}.",
        hint_it="Compila {unit_field}, per esempio l/s per una portata o mm/anno per la ricarica.",
        hint_en="Fill {unit_field}, for example l/s for a rate or mm/year for recharge.",
    ),
    "bc.negative_rate": Message(
        it="Il pozzo {feature} ha una portata negativa ({value}).",
        en="Well {feature} has a negative rate ({value}).",
        hint_it="La portata va in valore assoluto; il segno dipende da role "
        "(extraction o injection).",
        hint_en="The rate is an absolute value; its sign follows role (extraction or injection).",
    ),
    "bc.negative_series": Message(
        it="La serie {series_id}, usata come portata dal pozzo {feature}, ha valori negativi.",
        en="Series {series_id}, used as rate by well {feature}, has negative values.",
        hint_it="Le portate vanno in valore assoluto; il segno dipende da role "
        "(extraction o injection).",
        hint_en="Rates are absolute values; their sign follows role (extraction or injection).",
    ),
    "bc.series_quantity": Message(
        it="La feature {feature} del layer {layer} usa la serie {series_id}, che è una serie "
        "di {actual}; qui serve una serie di {expected}.",
        en="Feature {feature} of layer {layer} uses series {series_id}, which is a series of "
        "{actual}; a series of {expected} is needed here.",
        hint_it="Scegli un'altra serie oppure correggi quantity in timeseries_meta.",
        hint_en="Choose another series or fix quantity in timeseries_meta.",
    ),
    "bc.unit_range": Message(
        it="La feature {feature} del layer {layer} indica le unità da {top_unit} a "
        "{bottom_unit}, ma il modello ha le unità da 1 a {n_units}.",
        en="Feature {feature} of layer {layer} gives the units from {top_unit} to "
        "{bottom_unit}, but the model has units 1 to {n_units}.",
        hint_it="Correggi top_unit e bottom_unit, oppure lasciali vuoti per tutte le unità.",
        hint_en="Fix top_unit and bottom_unit, or leave them empty for all units.",
    ),
    "bc.station_unknown_feature": Message(
        it="La stazione {station} si riferisce alla feature con fid {feature_id} del layer "
        "{feature_layer}, che non esiste.",
        en="Station {station} refers to the feature with fid {feature_id} of layer "
        "{feature_layer}, which does not exist.",
        hint_it="Correggi feature_layer o feature_id, oppure elimina la stazione.",
        hint_en="Fix feature_layer or feature_id, or delete the station.",
    ),
    "bc.no_stations": Message(
        it="La feature {feature} del layer {layer} non ha stazioni con il carico.",
        en="Feature {feature} of layer {layer} has no stations with the head.",
        hint_it="Aggiungi una stazione in line_stations con feature_layer = {layer_code} e "
        "feature_id = {fid}.",
        hint_en="Add a station in line_stations with feature_layer = {layer_code} and "
        "feature_id = {fid}.",
    ),
    "bc.area_stations": Message(
        it="L'area {feature} ha {n} stazioni, ma su un'area il carico è uniforme e la "
        "stazione è una sola.",
        en="Area {feature} has {n} stations, but the head over an area is uniform and needs "
        "a single station.",
        hint_it="Tieni una sola stazione.",
        hint_en="Keep a single station.",
    ),
    "bc.station_no_value": Message(
        it="La stazione {station} non ha né un carico costante né una serie.",
        en="Station {station} has neither a constant head nor a series.",
        hint_it="Compila value oppure series_id.",
        hint_en="Fill value or series_id.",
    ),
    "bc.multipart_line": Message(
        it="La linea {feature} è formata da {n} parti separate.",
        en="Line {feature} is made of {n} separate parts.",
        hint_it="Dividila in feature distinte, ciascuna con le sue stazioni.",
        hint_en="Split it into separate features, each with its own stations.",
    ),
    "bc.chainage_beyond": Message(
        it="La stazione {station} ha progressiva {chainage} m, oltre la lunghezza della linea "
        "{feature} ({length} m).",
        en="Station {station} has chainage {chainage} m, beyond the length of line {feature} "
        "({length} m).",
        hint_it="Correggi chainage oppure lascialo vuoto per calcolarlo dalla posizione.",
        hint_en="Fix chainage or leave it empty to compute it from the position.",
    ),
    "bc.duplicate_chainage": Message(
        it="Le stazioni {first} e {second} della linea {feature} hanno la stessa progressiva "
        "({chainage} m).",
        en="Stations {first} and {second} of line {feature} have the same chainage ({chainage} m).",
        hint_it="Elimina una delle due oppure correggi la progressiva.",
        hint_en="Delete one of them or fix the chainage.",
    ),
    "bc.mixed_interpolation": Message(
        it="Le stazioni della linea {feature} usano serie a gradino e serie lineari.",
        en="The stations of line {feature} use both stepwise and linear series.",
        hint_it="Usa lo stesso tipo di interpolazione per tutte le serie della linea; così "
        "il carico tra due stazioni resta esatto in ogni istante.",
        hint_en="Use the same interpolation for all series of the line, so that the head "
        "between two stations stays exact at every instant.",
    ),
    "bc.head_below_bottom": Message(
        it="Il carico imposto dalla feature {feature} scende a {head} m s.l.m. nella colonna "
        "riga {row}, colonna {col}, sotto la base dell'ultimo layer interessato "
        "({bottom} m s.l.m.).",
        en="The head fixed by feature {feature} drops to {head} m a.s.l. in the column at "
        "row {row}, column {col}, below the bottom of the lowest layer affected "
        "({bottom} m a.s.l.).",
        hint_it="MODFLOW 6 non accetta carichi imposti sotto la base della cella; controlla "
        "carichi, unità interessate e superfici.",
        hint_en="MODFLOW 6 does not accept fixed heads below the cell bottom; check heads, "
        "units affected and surfaces.",
    ),
    "bc.screen_clipped": Message(
        it="Il filtro del pozzo {feature} è lungo {length} m e {inside} m cadono in celle "
        "attive; la portata si ripartisce solo su quei tratti.",
        en="The screen of well {feature} is {length} m long and {inside} m lie in active "
        "cells; the rate is shared among those parts only.",
        hint_it="Confronta le quote del filtro con quelle delle superfici del modello.",
        hint_en="Compare the screen elevations with those of the model surfaces.",
    ),
    "bc.line_outside": Message(
        it="Della linea {feature}, lunga {length} m, {outside} m attraversano celle non attive "
        "o fuori dalle unità interessate e lì non impongono il carico.",
        en="Of line {feature}, {length} m long, {outside} m cross cells that are inactive or "
        "outside the units affected, where no head is fixed.",
        hint_it="Se la linea segue il bordo del dominio, spostala verso l'interno di mezza "
        'cella oppure usa grid.activation = "area".',
        hint_en="If the line follows the domain boundary, move it inwards by half a cell or "
        'use grid.activation = "area".',
    ),
    "bc.station_far": Message(
        it="La stazione {station} dista {distance} m dalla linea {feature}, più del lato di "
        "una cella ({cell} m).",
        en="Station {station} is {distance} m away from line {feature}, more than one cell "
        "side ({cell} m).",
        hint_it="Controlla che la stazione appartenga alla linea giusta.",
        hint_en="Check that the station belongs to the right line.",
    ),
    "bc.chd_overlap": Message(
        it="{n_cells} celle ricevono il carico imposto da più feature, per esempio layer "
        "{layer}, riga {row}, colonna {col} ({first} e {second}); vale la prima.",
        en="{n_cells} cells receive a fixed head from several features, for example layer "
        "{layer}, row {row}, column {col} ({first} and {second}); the first one applies.",
        hint_it="Accorcia o separa le feature che si sovrappongono.",
        hint_en="Shorten or separate the overlapping features.",
    ),
    "bc.chd_layers_excluded": Message(
        it="In {n_cells} celle della feature {feature} il carico imposto scende sotto la base "
        "della cella in parte della simulazione; restano senza carico imposto, per esempio "
        "layer {layer}, riga {row}, colonna {col}.",
        en="In {n_cells} cells of feature {feature} the fixed head drops below the cell "
        "bottom during part of the simulation; they get no fixed head, for example layer "
        "{layer}, row {row}, column {col}.",
        hint_it="MODFLOW 6 non accetta carichi imposti sotto la base della cella; quando il "
        "carico vi risale, quelle celle sono alimentate dai layer sottostanti.",
        hint_en="MODFLOW 6 does not accept fixed heads below the cell bottom; when the head "
        "rises again, those cells are fed by the layers below.",
    ),
    "bc.zone_outside": Message(
        it="La zona di ricarica {feature} non copre nessuna cella attiva.",
        en="Recharge zone {feature} covers no active cell.",
        hint_it="Controlla la posizione della zona rispetto al dominio.",
        hint_en="Check the position of the zone against the domain.",
    ),
    "bc.zone_overlap": Message(
        it="Le zone di ricarica {first} e {second} si sovrappongono per {area} m²; lì le "
        "ricariche si sommano.",
        en="Recharge zones {first} and {second} overlap over {area} m²; there the recharge "
        "rates add up.",
        hint_it="Correggi i contorni se la sovrapposizione non è voluta.",
        hint_en="Fix the outlines if the overlap is not intended.",
    ),
    "check.failed": Message(
        it="Il controllo ha trovato {errors}.",
        en="The check found {errors}.",
        hint_it="Correggi gli errori elencati e ripeti phrear check.",
        hint_en="Fix the errors listed and run phrear check again.",
    ),
    "check.no_fixed_head": Message(
        it="Il periodo stazionario iniziale non ha carichi imposti attivi; senza un carico di "
        "riferimento la soluzione stazionaria non è determinata.",
        en="The initial steady period has no active fixed heads; without a reference head "
        "the steady-state solution is undetermined.",
        hint_it="Aggiungi una linea o un'area a carico imposto attiva dalla data di inizio, "
        "oppure imposta model.steady_initial = false.",
        hint_en="Add a fixed head line or area active from the start date, or set "
        "model.steady_initial = false.",
    ),
    "check.well_in_fixed_head": Message(
        it="Il pozzo {feature} preleva da {n_cells} celle a carico imposto, per esempio layer "
        "{layer}, riga {row}, colonna {col}; lì il carico non cambia e la portata arriva "
        "dal contorno.",
        en="Well {feature} draws from {n_cells} fixed head cells, for example layer {layer}, "
        "row {row}, column {col}; there the head does not change and the rate comes from "
        "the boundary.",
        hint_it="Sposta il pozzo o il carico imposto, oppure limita le unità del carico "
        "imposto con top_unit e bottom_unit.",
        hint_en="Move the well or the fixed head, or restrict the units of the fixed head "
        "with top_unit and bottom_unit.",
    ),
    "check.well_rate_high": Message(
        it="La portata del pozzo {feature} arriva a {value} l/s, oltre {limit} l/s.",
        en="The rate of well {feature} reaches {value} l/s, above {limit} l/s.",
        hint_it="Controlla valore e unità di misura; per esempio m³/d inseriti come l/s "
        "danno una portata 86,4 volte più grande.",
        hint_en="Check value and unit; for example m3/d entered as l/s give a rate 86.4 "
        "times larger.",
    ),
    "check.recharge_high": Message(
        it="La ricarica della zona {feature} arriva a {value} mm/anno, oltre {limit} mm/anno.",
        en="The recharge of zone {feature} reaches {value} mm/year, above {limit} mm/year.",
        hint_it="Controlla valore e unità di misura; per esempio mm/giorno inseriti come "
        "mm/anno danno una ricarica 365 volte più piccola, l'inverso 365 volte più grande.",
        hint_en="Check value and unit; for example mm/day entered as mm/year give a recharge "
        "365 times smaller, the reverse 365 times larger.",
    ),
    "check.recharge_low": Message(
        it="La ricarica della zona {feature} scende a {value} mm/anno, sotto {limit} mm/anno "
        "senza essere nulla.",
        en="The recharge of zone {feature} drops to {value} mm/year, below {limit} mm/year "
        "without being zero.",
        hint_it="Controlla valore e unità di misura, per esempio m/anno inseriti come mm/anno.",
        hint_en="Check value and unit, for example m/year entered as mm/year.",
    ),
    "check.newton_off": Message(
        it="La formulazione di Newton è disattivata e le unità {units} sono convertibili; le "
        "celle che si asciugano diventano inattive e la ricarica su di esse si perde.",
        en="The Newton formulation is off and units {units} are convertible; cells that dry "
        "out become inactive and the recharge on them is lost.",
        hint_it="Imposta options.newton = true, salvo motivi specifici.",
        hint_en="Set options.newton = true unless there are specific reasons.",
    ),
    "run.engine_not_found": Message(
        it="Non trovo l'eseguibile di MODFLOW 6 (mf6).",
        en="The MODFLOW 6 executable (mf6) cannot be found.",
        hint_it="Esegui phrear dall'ambiente del progetto, per esempio pixi run phrear run.",
        hint_en="Run phrear from the project environment, for example pixi run phrear run.",
    ),
    "run.exists": Message(
        it="Il run «{run_id}» esiste già in {path}.",
        en="Run '{run_id}' already exists in {path}.",
        hint_it="Scegli un altro --run-id oppure omettilo per crearne uno nuovo.",
        hint_en="Choose another --run-id or omit it to create a new one.",
    ),
    "run.invalid_id": Message(
        it="L'identificativo del run «{run_id}» non è valido.",
        en="The run identifier '{run_id}' is not valid.",
        hint_it="Usa lettere, cifre, trattini e trattini bassi, fino a 40 caratteri.",
        hint_en="Use letters, digits, hyphens and underscores, up to 40 characters.",
    ),
    "run.engine_error": Message(
        it="MODFLOW 6 ha rifiutato l'input del run {run_id} ({message}).",
        en="MODFLOW 6 rejected the input of run {run_id} ({message}).",
        hint_it="Il listing completo è in {listing}. I controlli di phrear dovrebbero "
        "intercettare gli errori dei dati: se non l'hanno fatto, è un difetto da segnalare.",
        hint_en="The full listing is in {listing}. The phrear checks should catch data "
        "errors: if they did not, it is a defect to report.",
    ),
    "run.convergence": Message(
        it="Nel run {run_id} la soluzione non converge nel periodo {period}, passo {step}.",
        en="In run {run_id} the solution does not converge in period {period}, step {step}.",
        hint_it='Prova solver.preset = "robust", passi iniziali più brevi (time.dt_initial_d) '
        "e controlla le celle che si asciugano; i dettagli sono in {listing}.",
        hint_en='Try solver.preset = "robust", shorter initial steps (time.dt_initial_d) and '
        "check the cells that dry out; details are in {listing}.",
    ),
    "run.terminated": Message(
        it="MODFLOW 6 si è fermato senza terminare normalmente il run {run_id} "
        "(codice {returncode}).",
        en="MODFLOW 6 stopped without completing run {run_id} normally (code {returncode}).",
        hint_it="Controlla il listing in {listing} e l'output in {stdout}.",
        hint_en="Check the listing in {listing} and the output in {stdout}.",
    ),
    "run.budget_discrepancy": Message(
        it="Nel run {run_id} l'errore di bilancio arriva a {value} % nel periodo {period}, "
        "passo {step}.",
        en="In run {run_id} the budget error reaches {value} % in period {period}, step {step}.",
        hint_it="Oltre l'1 % i risultati vanno usati con cautela; stringi le tolleranze del "
        "solutore o riduci i passi.",
        hint_en="Above 1 % the results should be used with care; tighten the solver "
        "tolerances or shorten the steps.",
    ),
    "results.no_run": Message(
        it="Nel progetto non c'è un run completato.",
        en="The project has no completed run.",
        hint_it="Esegui prima phrear run.",
        hint_en="Run phrear run first.",
    ),
    "results.run_not_found": Message(
        it="Il run «{run_id}» non esiste in {path}.",
        en="Run '{run_id}' does not exist in {path}.",
        hint_it="Controlla il nome in runs/ oppure ometti --run per usare l'ultimo run completato.",
        hint_en="Check the name in runs/ or omit --run to use the latest completed run.",
    ),
    "results.not_completed": Message(
        it="Il run «{run_id}» non è completato (stato: {status}).",
        en="Run '{run_id}' is not completed (status: {status}).",
        hint_it="Esegui di nuovo phrear run oppure scegli un altro run.",
        hint_en="Run phrear run again or choose another run.",
    ),
    "results.file_locked": Message(
        it="Non riesco a sostituire {path}; probabilmente è aperto in un altro programma.",
        en="Cannot replace {path}; it is probably open in another program.",
        hint_it="Rimuovi il layer da QGIS, o chiudi il programma che lo usa, e ripeti l'export.",
        hint_en="Remove the layer from QGIS, or close the program using it, and export again.",
    ),
    "verify.unknown_case": Message(
        it="Il caso di verifica «{case}» non esiste; i casi sono {cases}.",
        en="Verification case '{case}' does not exist; the cases are {cases}.",
        hint_it="Indica uno dei casi elencati con --case, oppure nessuno per eseguirli tutti.",
        hint_en="Give one of the listed cases with --case, or none to run them all.",
    ),
    "verify.output_exists": Message(
        it="La cartella {path} esiste e non è vuota.",
        en="Folder {path} exists and is not empty.",
        hint_it="Indica con --output una cartella nuova o vuota per il report.",
        hint_en="Give a new or empty folder for the report with --output.",
    ),
    "verify.failed": Message(
        it="La verifica non è superata per {cases}.",
        en="The verification fails for {cases}.",
        hint_it="Il report in {report} riporta errori e grafici; con MF6 {engine} i casi "
        "devono passare, quindi l'esito indica un problema dell'installazione o del software.",
        hint_en="The report in {report} gives errors and plots; with MF6 {engine} the cases "
        "must pass, so the outcome points to a problem of the installation or the software.",
    ),
    "init.missing": Message(
        it="Mancano i carichi iniziali.",
        en="The initial heads are missing.",
        hint_it='Indica [initial_heads] in project.toml, per esempio mode = "constant" e '
        'value_m, oppure mode = "raster" e raster_path.',
        hint_en='Set [initial_heads] in project.toml, for example mode = "constant" and '
        'value_m, or mode = "raster" and raster_path.',
    ),
    "init.mode_not_available": Message(
        it="I carichi iniziali di tipo «{mode}» non sono ancora disponibili.",
        en="Initial heads of type '{mode}' are not available yet.",
        hint_it='Per ora usa mode = "constant" oppure mode = "raster".',
        hint_en='For now use mode = "constant" or mode = "raster".',
    ),
    "init.dry_columns": Message(
        it="In {n_cells} colonne il carico iniziale è sotto la base dell'ultima cella attiva, "
        "per esempio riga {row}, colonna {col}.",
        en="In {n_cells} columns the initial head is below the bottom of the lowest active "
        "cell, for example row {row}, column {col}.",
        hint_it="Il periodo stazionario iniziale ricalcola i carichi, ma un valore di partenza "
        "così basso può rallentare o impedire la convergenza.",
        hint_en="The initial steady period recomputes the heads, but such a low starting value "
        "may slow down or prevent convergence.",
    ),
    "internal.unexpected": Message(
        it="Errore interno imprevisto.",
        en="Unexpected internal error.",
        hint_it="Segnala il problema allegando il dettaglio tecnico.",
        hint_en="Report the problem attaching the technical detail.",
    ),
}


class ObjectRef(BaseModel):
    """Where an error or warning occurred. Only the relevant fields are set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["feature", "cell", "period", "table", "field", "file", "series"]
    layer: str | None = None
    fid: int | None = None
    cell: tuple[int, ...] | None = None
    period: int | None = None
    field: str | None = None
    path: str | None = None


def placeholders(template: str) -> set[str]:
    """Names of the ``{field}`` placeholders used by a template."""
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def render(code: str, lang: Lang, fields: dict[str, FieldValue], *, hint: bool = False) -> str:
    """Render the message (or hint) of ``code`` in ``lang``."""
    message = CATALOG[code]
    template = message.hint_template(lang) if hint else message.template(lang)
    values = {k: v.get(lang) if isinstance(v, Localized) else v for k, v in fields.items()}
    return template.format(**values)


class PhrearError(Exception):
    """Base class of the errors reported to the user.

    Subclasses restrict the admitted codes through :attr:`prefix`.
    """

    prefix: str = ""

    def __init__(
        self,
        code: str,
        *,
        ref: ObjectRef | None = None,
        detail: str = "",
        **fields: FieldValue,
    ) -> None:
        if code not in CATALOG:
            raise KeyError(f"unknown error code {code!r}")
        if not code.startswith(self.prefix):
            raise ValueError(f"{type(self).__name__} does not admit code {code!r}")
        self.code = code
        self.ref = ref
        self.detail = detail
        self.fields: dict[str, FieldValue] = dict(fields)
        super().__init__(self.message("en"))

    def message(self, lang: Lang = "it") -> str:
        return render(self.code, lang, self.fields)

    def hint(self, lang: Lang = "it") -> str:
        return render(self.code, lang, self.fields, hint=True)


class UsageError(PhrearError):
    """Invalid command line."""

    prefix = "cli."


class UnitError(PhrearError):
    """Unit of measure missing, unknown or incompatible with the quantity."""

    prefix = "unit."


class ProjectError(PhrearError):
    """Project folder, project.toml or GeoPackage missing, invalid or outdated."""

    prefix = "project."


class SeriesError(PhrearError):
    """Time series missing, inconsistent or not covering the needed interval."""

    prefix = "series."


class TimeError(PhrearError):
    """Time discretisation that cannot be built from the settings."""

    prefix = "time."


class GeometryError(PhrearError):
    """Domain, units, surfaces or rasters missing or inconsistent."""

    prefix = "geometry."


class GridError(PhrearError):
    """Grid that cannot be built from the settings."""

    prefix = "grid."


class ParameterError(PhrearError):
    """Hydrogeological parameters missing, inconsistent or physically impossible."""

    prefix = "params."


class InitialHeadsError(PhrearError):
    """Initial heads missing or of an unsupported kind."""

    prefix = "init."


class BoundaryError(PhrearError):
    """Boundary condition features that cannot be turned into model input."""

    prefix = "bc."


class CheckError(PhrearError):
    """Outcome of a check that found blocking errors."""

    prefix = "check."


class RunError(PhrearError):
    """Build or execution of a MODFLOW 6 run that cannot be completed."""

    prefix = "run."


class ResultsError(PhrearError):
    """Results of a run that cannot be read or exported."""

    prefix = "results."


class VerificationError(PhrearError):
    """Verification against analytical solutions not passed or not runnable."""

    prefix = "verify."


class ErrorCollector:
    """Raises each error at once (default) or gathers them.

    Loaders call :meth:`fail` for every error tied to one object, so that a check
    can report all of them in a single pass instead of stopping at the first.
    """

    def __init__(self, *, collect: bool = False) -> None:
        self.collect = collect
        self.errors: list[PhrearError] = []

    def fail(self, error: PhrearError) -> None:
        if not self.collect:
            raise error
        self.errors.append(error)


class InternalError(PhrearError):
    """Unexpected failure inside the software, not caused by the input."""

    prefix = "internal."
