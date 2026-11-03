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


class InternalError(PhrearError):
    """Unexpected failure inside the software, not caused by the input."""

    prefix = "internal."
