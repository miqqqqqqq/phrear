"""Single definition of the project data schema (docs/SPEC.md, section 8.2).

Creation of the GeoPackage, validation, JSON export for the QGIS plugin and
migrations all derive from :data:`TABLES`. Version 1 contains the tables needed
by milestone M1a; later milestones add tables through numbered migrations.

Conventions
-----------
- Elevations and lengths are in metres (elevations above sea level); fields that
  accept other units have a companion ``*_unit`` field.
- Stored enumeration values are English identifiers; labels are in Italian and
  English for the user interface.
- Default values are applied by the readers (core) and by the plugin forms; the
  GeoPackage columns themselves carry no SQL defaults.
- ``created_at`` and ``modified_at`` are maintained by SQLite triggers and are
  excluded from content hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from phrear.errors import Localized
from phrear.units import PhysicalQuantity

SCHEMA_VERSION: Final = 1


class FieldType(StrEnum):
    INTEGER = "integer"
    REAL = "real"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATETIME = "datetime"


class GeometryType(StrEnum):
    POINT = "Point"
    MULTILINESTRING = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"


@dataclass(frozen=True)
class Choice:
    value: str
    label: Localized


_NO_TEXT: Final = Localized("", "")


@dataclass(frozen=True)
class FieldDef:
    """A column of a table, with everything a form needs to present it."""

    name: str
    type: FieldType
    label: Localized
    help: Localized = _NO_TEXT
    required: bool = False
    default: str | int | float | bool | None = None
    choices: tuple[Choice, ...] = ()
    unit: str | None = None
    """Fixed unit of the stored value, e.g. ``m``."""
    quantity: PhysicalQuantity | None = None
    """For ``*_unit`` fields: the quantity the unit must express."""
    minimum: float | None = None
    maximum: float | None = None
    system: bool = False
    """Maintained by the software (timestamps); read-only in forms, not hashed."""

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.choices)


@dataclass(frozen=True)
class TableDef:
    """A layer (with geometry) or an attribute table of the GeoPackage."""

    name: str
    geometry: GeometryType | None
    label: Localized
    help: Localized
    fields: tuple[FieldDef, ...]
    unique: tuple[tuple[str, ...], ...] = ()
    milestone: str = "M1a"

    @property
    def is_layer(self) -> bool:
        return self.geometry is not None

    def field(self, name: str) -> FieldDef:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"{self.name}.{name}")

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


L = Localized


def _c(value: str, it: str, en: str) -> Choice:
    return Choice(value, L(it, en))


# --- common fields of feature layers (section 8.2) -----------------------------

COMMON_FEATURE_FIELDS: tuple[FieldDef, ...] = (
    FieldDef("name", FieldType.TEXT, L("Nome", "Name")),
    FieldDef(
        "active",
        FieldType.BOOLEAN,
        L("Attivo", "Active"),
        L("Se falso, l'oggetto è ignorato nel modello.", "If false, the object is ignored."),
        default=True,
    ),
    FieldDef("notes", FieldType.TEXT, L("Note", "Notes")),
    FieldDef("created_at", FieldType.DATETIME, L("Creato il", "Created at"), system=True),
    FieldDef("modified_at", FieldType.DATETIME, L("Modificato il", "Modified at"), system=True),
    FieldDef(
        "scenario_id",
        FieldType.TEXT,
        L("Scenario", "Scenario"),
        L(
            "Vuoto per il modello base; altrimenti l'oggetto esiste solo nello scenario.",
            "Empty for the base model; otherwise the object exists only in that scenario.",
        ),
    ),
)

NOTES = FieldDef("notes", FieldType.TEXT, L("Note", "Notes"))

_UNIT_RANGE = (
    FieldDef(
        "top_unit",
        FieldType.INTEGER,
        L("Unità superiore", "Top unit"),
        L(
            "Posizione della prima unità idrostratigrafica interessata; vuoto = tutte.",
            "Position of the first hydrostratigraphic unit affected; empty = all.",
        ),
        minimum=1,
    ),
    FieldDef(
        "bottom_unit",
        FieldType.INTEGER,
        L("Unità inferiore", "Bottom unit"),
        L(
            "Posizione dell'ultima unità interessata; vuoto = fino all'ultima.",
            "Position of the last unit affected; empty = down to the last one.",
        ),
        minimum=1,
    ),
)

#: Quantity expressed by each hydrogeological parameter of ``param_values``.
#: ``anisotropy`` is the ratio Kv/Kh.
PARAM_QUANTITIES: dict[str, PhysicalQuantity] = {
    "kh": PhysicalQuantity.VELOCITY,
    "kv": PhysicalQuantity.VELOCITY,
    "anisotropy": PhysicalQuantity.DIMENSIONLESS,
    "ss": PhysicalQuantity.SPECIFIC_STORAGE,
    "sy": PhysicalQuantity.DIMENSIONLESS,
    "ne": PhysicalQuantity.DIMENSIONLESS,
}

#: Quantities admitted for a time series.
SERIES_QUANTITIES: dict[str, PhysicalQuantity] = {
    "length": PhysicalQuantity.LENGTH,
    "discharge": PhysicalQuantity.DISCHARGE,
    "velocity": PhysicalQuantity.VELOCITY,
}


TABLES: tuple[TableDef, ...] = (
    TableDef(
        "domain",
        GeometryType.MULTIPOLYGON,
        L("Dominio del modello", "Model domain"),
        L(
            "Contorno attivo del modello. Le celle fuori dal dominio sono inattive.",
            "Active outline of the model. Cells outside the domain are inactive.",
        ),
        COMMON_FEATURE_FIELDS,
    ),
    TableDef(
        "hydro_units",
        None,
        L("Unità idrostratigrafiche", "Hydrostratigraphic units"),
        L(
            "Unità dall'alto verso il basso. Ogni unità diventa uno o più layer del modello.",
            "Units from top to bottom. Each unit becomes one or more model layers.",
        ),
        (
            FieldDef(
                "position",
                FieldType.INTEGER,
                L("Posizione", "Position"),
                L("1 = unità più alta.", "1 = topmost unit."),
                required=True,
                minimum=1,
            ),
            FieldDef("name", FieldType.TEXT, L("Nome", "Name"), required=True),
            FieldDef(
                "geometry_mode",
                FieldType.TEXT,
                L("Origine della geometria", "Geometry source"),
                default="raster",
                choices=(
                    _c("raster", "Raster", "Raster"),
                    _c("boreholes", "Sondaggi", "Boreholes"),
                    _c("mixed", "Mista", "Mixed"),
                ),
            ),
            FieldDef(
                "param_mode",
                FieldType.TEXT,
                L("Assegnazione dei parametri", "Parameter assignment"),
                default="uniform",
                choices=(
                    _c("uniform", "Uniforme", "Uniform"),
                    _c("zones", "Zone", "Zones"),
                    _c("raster", "Raster", "Raster"),
                    _c("interpolated", "Interpolata dalle prove", "Interpolated from tests"),
                ),
            ),
            FieldDef(
                "convertible",
                FieldType.BOOLEAN,
                L("Convertibile", "Convertible"),
                L(
                    "Se vero, la cella passa da confinata a libera quando il carico scende "
                    "sotto il tetto (MF6 ICELLTYPE).",
                    "If true, the cell switches from confined to unconfined when the head "
                    "drops below its top (MF6 ICELLTYPE).",
                ),
                default=True,
            ),
            FieldDef(
                "sublayers",
                FieldType.INTEGER,
                L("Sotto-layer", "Sublayers"),
                L(
                    "Numero di layer del modello in cui l'unità è suddivisa in parti uguali.",
                    "Number of model layers the unit is split into, in equal parts.",
                ),
                default=1,
                minimum=1,
            ),
            NOTES,
        ),
        unique=(("position",),),
    ),
    TableDef(
        "surfaces",
        None,
        L("Superfici di contatto", "Contact surfaces"),
        L(
            "N+1 superfici per N unità: 0 è il tetto del modello, i è la base dell'unità i.",
            "N+1 surfaces for N units: 0 is the model top, i is the bottom of unit i.",
        ),
        (
            FieldDef(
                "surface_index",
                FieldType.INTEGER,
                L("Indice", "Index"),
                L(
                    "0 = tetto del modello; i = base dell'unità i.",
                    "0 = model top; i = bottom of unit i.",
                ),
                required=True,
                minimum=0,
            ),
            FieldDef(
                "raster_path",
                FieldType.TEXT,
                L("Raster", "Raster"),
                L(
                    "Percorso del raster, relativo alla cartella del progetto.",
                    "Raster path, relative to the project folder.",
                ),
                required=True,
            ),
            FieldDef("source", FieldType.TEXT, L("Fonte", "Source")),
            FieldDef(
                "vertical_datum",
                FieldType.TEXT,
                L("Riferimento verticale", "Vertical datum"),
                L("Per esempio m s.l.m. (Genova 1942).", "For example m a.s.l. (Genova 1942)."),
            ),
            NOTES,
        ),
        unique=(("surface_index",),),
    ),
    TableDef(
        "param_values",
        None,
        L("Valori dei parametri", "Parameter values"),
        L(
            "Un valore per parametro e oggetto, con unità, origine e intervallo.",
            "One value per parameter and object, with unit, source and range.",
        ),
        (
            FieldDef(
                "object_type",
                FieldType.TEXT,
                L("Tipo di oggetto", "Object type"),
                required=True,
                choices=(_c("unit", "Unità", "Unit"), _c("zone", "Zona", "Zone")),
            ),
            FieldDef(
                "object_id",
                FieldType.INTEGER,
                L("Oggetto", "Object"),
                L("fid dell'unità o della zona.", "fid of the unit or zone."),
                required=True,
            ),
            FieldDef(
                "param",
                FieldType.TEXT,
                L("Parametro", "Parameter"),
                required=True,
                choices=(
                    _c("kh", "K orizzontale", "Horizontal K"),
                    _c("kv", "K verticale", "Vertical K"),
                    _c("anisotropy", "Anisotropia Kv/Kh", "Anisotropy Kv/Kh"),
                    _c("ss", "Immagazzinamento specifico Ss", "Specific storage Ss"),
                    _c("sy", "Resa specifica Sy", "Specific yield Sy"),
                    _c("ne", "Porosità efficace", "Effective porosity"),
                ),
            ),
            FieldDef(
                "value",
                FieldType.REAL,
                L("Valore", "Value"),
                L(
                    "Valore uniforme; in alternativa indica un raster.",
                    "Uniform value; alternatively give a raster.",
                ),
            ),
            FieldDef(
                "raster_path",
                FieldType.TEXT,
                L("Raster", "Raster"),
                L("Relativo alla cartella del progetto.", "Relative to the project folder."),
            ),
            FieldDef(
                "unit",
                FieldType.TEXT,
                L("Unità di misura", "Unit"),
                L(
                    "Per esempio m/s per K, 1/m per Ss; vuota per le grandezze adimensionali.",
                    "For example m/s for K, 1/m for Ss; empty for dimensionless quantities.",
                ),
            ),
            FieldDef(
                "source",
                FieldType.TEXT,
                L("Origine", "Source"),
                choices=(
                    _c("pumping_test", "Prova di pompaggio", "Pumping test"),
                    _c("slug_test", "Slug test", "Slug test"),
                    _c("lefranc", "Prova Lefranc", "Lefranc test"),
                    _c("lugeon", "Prova Lugeon", "Lugeon test"),
                    _c("grain_size", "Granulometria", "Grain size analysis"),
                    _c("literature", "Letteratura", "Literature"),
                    _c("calibration", "Calibrazione", "Calibration"),
                    _c("expert_judgement", "Giudizio esperto", "Expert judgement"),
                ),
            ),
            FieldDef(
                "min",
                FieldType.REAL,
                L("Minimo", "Minimum"),
                L("Stessa unità del valore.", "Same unit as the value."),
            ),
            FieldDef(
                "max",
                FieldType.REAL,
                L("Massimo", "Maximum"),
                L("Stessa unità del valore.", "Same unit as the value."),
            ),
            FieldDef(
                "std_log10",
                FieldType.REAL,
                L("Deviazione standard log10", "Standard deviation of log10"),
                minimum=0,
            ),
            NOTES,
        ),
        unique=(("object_type", "object_id", "param"),),
    ),
    TableDef(
        "wells",
        GeometryType.POINT,
        L("Pozzi", "Wells"),
        L(
            "Pozzi di estrazione o iniezione. La portata si inserisce in valore assoluto; "
            "il segno dipende dal ruolo.",
            "Extraction or injection wells. The rate is entered as an absolute value; "
            "its sign follows the role.",
        ),
        (
            *COMMON_FEATURE_FIELDS,
            FieldDef(
                "role",
                FieldType.TEXT,
                L("Ruolo", "Role"),
                default="extraction",
                choices=(
                    _c("extraction", "Estrazione", "Extraction"),
                    _c("injection", "Iniezione", "Injection"),
                ),
            ),
            FieldDef(
                "depth_mode",
                FieldType.TEXT,
                L("Riferimento dei filtri", "Screen reference"),
                L(
                    "In profondità i valori crescono verso il basso a partire da z_ref.",
                    "Depths increase downwards from z_ref.",
                ),
                default="depth",
                choices=(
                    _c("depth", "Profondità da z_ref", "Depth below z_ref"),
                    _c("elevation", "Quota s.l.m.", "Elevation a.s.l."),
                ),
            ),
            FieldDef(
                "z_ref",
                FieldType.REAL,
                L("Quota di riferimento", "Reference elevation"),
                L(
                    "Piano campagna o testa pozzo, m s.l.m.; obbligatoria con filtri "
                    "in profondità.",
                    "Ground or wellhead elevation, m a.s.l.; required when screens are depths.",
                ),
                unit="m",
            ),
            FieldDef(
                "screen_top",
                FieldType.REAL,
                L("Inizio filtro", "Screen top"),
                required=True,
                unit="m",
            ),
            FieldDef(
                "screen_bottom",
                FieldType.REAL,
                L("Fine filtro", "Screen bottom"),
                required=True,
                unit="m",
            ),
            FieldDef("radius", FieldType.REAL, L("Raggio", "Radius"), unit="m", minimum=0),
            FieldDef(
                "model_as",
                FieldType.TEXT,
                L("Rappresentazione", "Representation"),
                default="auto",
                choices=(
                    _c("auto", "Automatica", "Automatic"),
                    _c("wel", "WEL", "WEL"),
                    _c("maw", "MAW", "MAW"),
                ),
            ),
            FieldDef(
                "rate",
                FieldType.REAL,
                L("Portata", "Rate"),
                L("Valore assoluto.", "Absolute value."),
                minimum=0,
            ),
            FieldDef(
                "rate_unit",
                FieldType.TEXT,
                L("Unità della portata", "Rate unit"),
                default="l/s",
                quantity=PhysicalQuantity.DISCHARGE,
            ),
            FieldDef(
                "series_id",
                FieldType.TEXT,
                L("Serie della portata", "Rate series"),
                L(
                    "Se presente, sostituisce la portata costante.",
                    "If set, it replaces the constant rate.",
                ),
            ),
        ),
    ),
    TableDef(
        "fixed_head_lines",
        GeometryType.MULTILINESTRING,
        L("Carichi imposti lungo linee", "Fixed heads along lines"),
        L(
            "Carico imposto (CHD) lungo una linea. I valori stanno nelle stazioni.",
            "Fixed head (CHD) along a line. Values are given at stations.",
        ),
        (*COMMON_FEATURE_FIELDS, *_UNIT_RANGE),
    ),
    TableDef(
        "fixed_head_areas",
        GeometryType.MULTIPOLYGON,
        L("Carichi imposti su aree", "Fixed heads over areas"),
        L(
            "Carico imposto (CHD) su un'area, per esempio un lago. Il valore sta in una stazione.",
            "Fixed head (CHD) over an area, for example a lake. The value is given at a station.",
        ),
        (*COMMON_FEATURE_FIELDS, *_UNIT_RANGE),
    ),
    TableDef(
        "line_stations",
        GeometryType.POINT,
        L("Stazioni", "Stations"),
        L(
            "Valori di carico o livello lungo una feature, interpolati linearmente per "
            "progressiva. Una sola stazione equivale a un valore uniforme.",
            "Head or stage values along a feature, linearly interpolated by chainage. "
            "A single station means a uniform value.",
        ),
        (
            *COMMON_FEATURE_FIELDS,
            FieldDef(
                "feature_layer",
                FieldType.TEXT,
                L("Layer della feature", "Feature layer"),
                required=True,
                choices=(
                    _c(
                        "fixed_head_lines", "Carichi imposti lungo linee", "Fixed heads along lines"
                    ),
                    _c("fixed_head_areas", "Carichi imposti su aree", "Fixed heads over areas"),
                ),
            ),
            FieldDef(
                "feature_id",
                FieldType.INTEGER,
                L("Feature", "Feature"),
                L("fid della feature.", "fid of the feature."),
                required=True,
            ),
            FieldDef(
                "chainage",
                FieldType.REAL,
                L("Progressiva", "Chainage"),
                L(
                    "Distanza lungo la linea; se vuota si calcola dalla posizione del punto.",
                    "Distance along the line; if empty it is computed from the point position.",
                ),
                unit="m",
                minimum=0,
            ),
            FieldDef(
                "value",
                FieldType.REAL,
                L("Carico", "Head"),
                L("Valore costante, m s.l.m.", "Constant value, m a.s.l."),
                unit="m",
            ),
            FieldDef(
                "series_id",
                FieldType.TEXT,
                L("Serie del carico", "Head series"),
                L(
                    "Se presente, sostituisce il valore costante.",
                    "If set, it replaces the constant value.",
                ),
            ),
        ),
    ),
    TableDef(
        "recharge_zones",
        GeometryType.MULTIPOLYGON,
        L("Zone di ricarica", "Recharge zones"),
        L(
            "Ricarica applicata alla cella attiva più alta.",
            "Recharge applied to the uppermost active cell.",
        ),
        (
            *COMMON_FEATURE_FIELDS,
            FieldDef("rate", FieldType.REAL, L("Ricarica", "Recharge rate")),
            FieldDef(
                "rate_unit",
                FieldType.TEXT,
                L("Unità della ricarica", "Recharge unit"),
                default="mm/anno",
                quantity=PhysicalQuantity.VELOCITY,
            ),
            FieldDef(
                "series_id",
                FieldType.TEXT,
                L("Serie della ricarica", "Recharge series"),
                L(
                    "Se presente, sostituisce il valore costante.",
                    "If set, it replaces the constant value.",
                ),
            ),
        ),
    ),
    TableDef(
        "timeseries_meta",
        None,
        L("Serie temporali", "Time series"),
        L(
            "Descrizione di ogni serie: grandezza, unità, interpolazione.",
            "Each series: quantity, unit, interpolation.",
        ),
        (
            FieldDef("series_id", FieldType.TEXT, L("Codice", "Code"), required=True),
            FieldDef("name", FieldType.TEXT, L("Nome", "Name")),
            FieldDef(
                "quantity",
                FieldType.TEXT,
                L("Grandezza", "Quantity"),
                required=True,
                choices=(
                    _c("length", "Quota o carico", "Elevation or head"),
                    _c("discharge", "Portata", "Discharge"),
                    _c("velocity", "Ricarica o velocità", "Recharge or velocity"),
                ),
            ),
            FieldDef("unit", FieldType.TEXT, L("Unità di misura", "Unit"), required=True),
            FieldDef(
                "interpolation",
                FieldType.TEXT,
                L("Interpolazione", "Interpolation"),
                L(
                    "A gradino: ogni valore vale fino al successivo. Lineare: tra i punti.",
                    "Stepwise: each value holds until the next. Linear: between points.",
                ),
                default="stepwise",
                choices=(
                    _c("stepwise", "A gradino", "Stepwise"),
                    _c("linear", "Lineare", "Linear"),
                ),
            ),
            NOTES,
        ),
        unique=(("series_id",),),
    ),
    TableDef(
        "timeseries_values",
        None,
        L("Valori delle serie", "Series values"),
        L(
            "Coppie data-valore, nell'unità della serie.",
            "Date-value pairs, in the unit of the series.",
        ),
        (
            FieldDef("series_id", FieldType.TEXT, L("Serie", "Series"), required=True),
            FieldDef(
                "datetime",
                FieldType.DATETIME,
                L("Data e ora", "Date and time"),
                L("Ora locale.", "Local time."),
                required=True,
            ),
            FieldDef("value", FieldType.REAL, L("Valore", "Value"), required=True),
        ),
        unique=(("series_id", "datetime"),),
    ),
    TableDef(
        "scenarios",
        None,
        L("Scenari", "Scenarios"),
        L("Varianti del modello base.", "Variants of the base model."),
        (
            FieldDef("scenario_id", FieldType.TEXT, L("Codice", "Code"), required=True),
            FieldDef("name", FieldType.TEXT, L("Nome", "Name")),
            FieldDef("description", FieldType.TEXT, L("Descrizione", "Description")),
        ),
        unique=(("scenario_id",),),
    ),
    TableDef(
        "scenario_changes",
        None,
        L("Modifiche degli scenari", "Scenario changes"),
        L(
            "Feature del modello base disattivate o modificate da uno scenario.",
            "Base-model features disabled or modified by a scenario.",
        ),
        (
            FieldDef("scenario_id", FieldType.TEXT, L("Scenario", "Scenario"), required=True),
            FieldDef("target_layer", FieldType.TEXT, L("Layer", "Layer"), required=True),
            FieldDef("target_fid", FieldType.INTEGER, L("Feature", "Feature"), required=True),
            FieldDef(
                "action",
                FieldType.TEXT,
                L("Azione", "Action"),
                required=True,
                choices=(_c("disable", "Disattiva", "Disable"), _c("modify", "Modifica", "Modify")),
            ),
            FieldDef("field", FieldType.TEXT, L("Campo", "Field")),
            FieldDef("value", FieldType.TEXT, L("Nuovo valore", "New value")),
        ),
    ),
    TableDef(
        "change_log",
        None,
        L("Registro delle modifiche", "Change log"),
        L("Modifiche strutturali al progetto.", "Structural changes to the project."),
        (
            FieldDef(
                "time", FieldType.DATETIME, L("Data e ora", "Time"), required=True, system=True
            ),
            FieldDef(
                "action",
                FieldType.TEXT,
                L("Azione", "Action"),
                required=True,
                choices=(
                    _c("create", "Creazione", "Creation"),
                    _c("migrate", "Migrazione", "Migration"),
                    _c("import", "Import", "Import"),
                ),
            ),
            FieldDef("detail", FieldType.TEXT, L("Dettaglio", "Detail")),
            FieldDef(
                "software_version", FieldType.TEXT, L("Versione del software", "Software version")
            ),
        ),
    ),
)

TABLES_BY_NAME: dict[str, TableDef] = {t.name: t for t in TABLES}


def _localized(value: Localized) -> dict[str, str]:
    return {"it": value.it, "en": value.en}


def _field_document(f: FieldDef) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "name": f.name,
        "type": f.type.value,
        "label": _localized(f.label),
        "help": _localized(f.help),
        "required": f.required,
        "default": f.default,
        "system": f.system,
    }
    if f.choices:
        doc["choices"] = [{"value": c.value, "label": _localized(c.label)} for c in f.choices]
    if f.unit is not None:
        doc["unit"] = f.unit
    if f.quantity is not None:
        doc["unit_quantity"] = f.quantity.value
    if f.minimum is not None:
        doc["minimum"] = f.minimum
    if f.maximum is not None:
        doc["maximum"] = f.maximum
    return doc


def schema_document() -> dict[str, Any]:
    """The data schema as a JSON-serialisable document (``phrear schema``)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tables": [
            {
                "name": t.name,
                "geometry": t.geometry.value if t.geometry else None,
                "label": _localized(t.label),
                "help": _localized(t.help),
                "unique": [list(u) for u in t.unique],
                "fields": [_field_document(f) for f in t.fields],
            }
            for t in TABLES
        ],
        "param_quantities": {k: v.value for k, v in PARAM_QUANTITIES.items()},
        "series_quantities": {k: v.value for k, v in SERIES_QUANTITIES.items()},
    }


__all__ = [
    "PARAM_QUANTITIES",
    "SCHEMA_VERSION",
    "SERIES_QUANTITIES",
    "TABLES",
    "TABLES_BY_NAME",
    "Choice",
    "FieldDef",
    "FieldType",
    "GeometryType",
    "TableDef",
    "schema_document",
]
