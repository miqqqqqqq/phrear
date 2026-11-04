"""Single definition of the project data schema (docs/SPEC.md, section 8.2).

Creation of the GeoPackage, validation, JSON export for the QGIS plugin and
migrations all derive from :data:`TABLES`. Version 1 contains the tables needed
by milestone M1a; version 2 adds parameter zones and field tests (M2). Later
versions come with numbered migrations.

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

SCHEMA_VERSION: Final = 2


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
class Lookup:
    """Values of a field taken from another table, optionally filtered (a value list in forms)."""

    table: str
    key: str
    filter: tuple[tuple[str, str], ...] = ()
    """(field, value) pairs the rows of ``table`` must match."""
    value: str | None = None
    """Field shown to the user instead of the key; ``None`` shows the key."""


@dataclass(frozen=True)
class Relation:
    """Child rows that refer to a parent row, shown inside the parent form.

    For a polymorphic relation ``parents`` lists the possible parent tables and
    ``parent_table_field`` is the child field that holds the name of the parent table.
    """

    name: str
    label: Localized
    child: str
    child_field: str
    parent_field: str
    parent: str | None = None
    parents: tuple[str, ...] = ()
    parent_table_field: str | None = None
    child_filter: tuple[tuple[str, str], ...] = ()
    """Values the child rows of this relation have (set as defaults in new child rows)."""


@dataclass(frozen=True)
class LayerStyle:
    """Look of a layer, shared by the plugin, the reports and the viewer (section 18)."""

    kind: str
    """``marker``, ``line`` or ``fill``."""
    color: str
    outline: str | None = None
    size_mm: float | None = None
    width_mm: float | None = None
    shape: str | None = None
    fill_opacity: float | None = None


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
    lookup: Lookup | None = None

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
    style: LayerStyle | None = None
    since: int = 1
    """Schema version that introduced the table."""

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
        lookup=Lookup("scenarios", "scenario_id"),
    ),
)

NOTES = FieldDef("notes", FieldType.TEXT, L("Note", "Notes"))

#: Hydrostratigraphic unit of a zone or a field test, chosen by name.
UNIT_LOOKUP = Lookup("hydro_units", "fid", value="name")

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
        lookup=Lookup("hydro_units", "position", value="name"),
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
        lookup=Lookup("hydro_units", "position", value="name"),
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
        style=LayerStyle("fill", "#52514e", fill_opacity=0.0, width_mm=0.6),
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
            FieldDef(
                "k_from_tests",
                FieldType.BOOLEAN,
                L("K dalle prove in sito", "K from field tests"),
                L(
                    "Se vero, K orizzontale si interpola in log10 dalle prove dell'unità "
                    "(inverso della distanza al quadrato). Raster e campo interpolato prevalgono "
                    "su zone e valore uniforme.",
                    "If true, horizontal K is interpolated in log10 from the tests of the unit "
                    "(inverse squared distance). Rasters and the interpolated field take "
                    "precedence over zones and the uniform value.",
                ),
                default=False,
            ),
            FieldDef(
                "interp_max_distance",
                FieldType.REAL,
                L("Distanza massima dell'interpolazione", "Interpolation distance limit"),
                L(
                    "Oltre questa distanza dalla prova più vicina valgono zone e valore "
                    "uniforme; vuota = tutta l'unità.",
                    "Beyond this distance from the nearest test, zones and the uniform value "
                    "apply; empty = the whole unit.",
                ),
                unit="m",
                minimum=0,
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
                default="unit",
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
                lookup=Lookup("timeseries_meta", "series_id", (("quantity", "discharge"),)),
            ),
        ),
        style=LayerStyle("marker", "#2a78d6", outline="#fcfcfb", size_mm=3.2, shape="circle"),
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
        style=LayerStyle("line", "#1b4f8f", width_mm=0.9),
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
        style=LayerStyle("fill", "#2a78d6", outline="#1b4f8f", fill_opacity=0.25, width_mm=0.4),
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
                lookup=Lookup("timeseries_meta", "series_id", (("quantity", "length"),)),
            ),
        ),
        style=LayerStyle("marker", "#eb6834", outline="#fcfcfb", size_mm=2.8, shape="triangle"),
    ),
    TableDef(
        "field_tests",
        GeometryType.POINT,
        L("Prove in sito", "Field tests"),
        L(
            "Prove idrauliche e granulometrie, con il risultato (T, K o S), il tratto provato "
            "e lo spessore usato nell'interpretazione.",
            "Hydraulic tests and grain size analyses, with the result (T, K or S), the tested "
            "interval and the thickness used in the interpretation.",
        ),
        (
            *COMMON_FEATURE_FIELDS,
            FieldDef(
                "type",
                FieldType.TEXT,
                L("Tipo di prova", "Test type"),
                required=True,
                choices=(
                    _c("pumping_test", "Prova di pompaggio", "Pumping test"),
                    _c("slug_test", "Slug test", "Slug test"),
                    _c("lefranc", "Prova Lefranc", "Lefranc test"),
                    _c("lugeon", "Prova Lugeon", "Lugeon test"),
                    _c("grain_size", "Granulometria", "Grain size analysis"),
                ),
            ),
            FieldDef(
                "result_param",
                FieldType.TEXT,
                L("Grandezza misurata", "Measured quantity"),
                required=True,
                choices=(
                    _c("T", "Trasmissività T", "Transmissivity T"),
                    _c("K", "Conducibilità idraulica K", "Hydraulic conductivity K"),
                    _c("S", "Coefficiente di immagazzinamento S", "Storage coefficient S"),
                ),
            ),
            FieldDef("value", FieldType.REAL, L("Valore", "Value"), required=True, minimum=0),
            FieldDef(
                "unit",
                FieldType.TEXT,
                L("Unità di misura", "Unit"),
                L(
                    "Per esempio m²/s per T, m/s per K; vuota per S.",
                    "For example m²/s for T, m/s for K; empty for S.",
                ),
            ),
            FieldDef(
                "depth_mode",
                FieldType.TEXT,
                L("Riferimento delle quote", "Depth reference"),
                L(
                    "Vale per filtri e livello statico. In profondità i valori crescono verso "
                    "il basso a partire da z_ref.",
                    "Applies to screens and static level. Depths increase downwards from z_ref.",
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
                    "Piano campagna o testa pozzo, m s.l.m.; obbligatoria con valori "
                    "in profondità.",
                    "Ground or wellhead elevation, m a.s.l.; required when values are depths.",
                ),
                unit="m",
            ),
            FieldDef(
                "screen_top",
                FieldType.REAL,
                L("Inizio del tratto provato", "Tested interval top"),
                unit="m",
            ),
            FieldDef(
                "screen_bottom",
                FieldType.REAL,
                L("Fine del tratto provato", "Tested interval bottom"),
                unit="m",
            ),
            FieldDef(
                "ref_thickness",
                FieldType.REAL,
                L("Spessore di riferimento", "Reference thickness"),
                L(
                    "Spessore b usato nell'interpretazione (K = T/b, Ss = S/b). Se vuoto si stima "
                    "da geometria e livello statico, con un avviso.",
                    "Thickness b used in the interpretation (K = T/b, Ss = S/b). If empty it is "
                    "estimated from geometry and static level, with a warning.",
                ),
                unit="m",
                minimum=0,
            ),
            FieldDef(
                "static_level",
                FieldType.REAL,
                L("Livello statico", "Static level"),
                L(
                    "Alla data della prova, con lo stesso riferimento delle quote.",
                    "On the test date, with the same reference as the depths.",
                ),
                unit="m",
            ),
            FieldDef(
                "unit_id",
                FieldType.INTEGER,
                L("Unità idrostratigrafica", "Hydrostratigraphic unit"),
                L(
                    "Se vuota, l'unità con il tratto provato più lungo.",
                    "If empty, the unit with the longest tested interval.",
                ),
                lookup=UNIT_LOOKUP,
            ),
            FieldDef("date", FieldType.DATETIME, L("Data della prova", "Test date")),
            FieldDef(
                "reliability",
                FieldType.TEXT,
                L("Affidabilità", "Reliability"),
                choices=(
                    _c("high", "Alta", "High"),
                    _c("medium", "Media", "Medium"),
                    _c("low", "Bassa", "Low"),
                ),
            ),
        ),
        milestone="M2",
        style=LayerStyle("marker", "#b8336a", outline="#fcfcfb", size_mm=3.0, shape="square"),
        since=2,
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
                lookup=Lookup("timeseries_meta", "series_id", (("quantity", "velocity"),)),
            ),
        ),
        style=LayerStyle("fill", "#1baf7a", outline="#1baf7a", fill_opacity=0.15, width_mm=0.4),
    ),
    TableDef(
        "param_zones",
        GeometryType.MULTIPOLYGON,
        L("Zone dei parametri", "Parameter zones"),
        L(
            "Zone di un'unità con parametri propri, in param_values con object_type = zone. "
            "Dentro la zona prevalgono sul valore uniforme dell'unità.",
            "Zones of a unit with their own parameters, in param_values with object_type = "
            "zone. Inside the zone they take precedence over the uniform value of the unit.",
        ),
        (
            *COMMON_FEATURE_FIELDS,
            FieldDef(
                "unit_id",
                FieldType.INTEGER,
                L("Unità idrostratigrafica", "Hydrostratigraphic unit"),
                L(
                    "I parametri della zona valgono solo in questa unità.",
                    "The parameters of the zone apply only to this unit.",
                ),
                required=True,
                lookup=UNIT_LOOKUP,
            ),
        ),
        milestone="M2",
        style=LayerStyle("fill", "#8a5cd6", outline="#6a3fb8", fill_opacity=0.15, width_mm=0.5),
        since=2,
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
            FieldDef(
                "series_id",
                FieldType.TEXT,
                L("Serie", "Series"),
                required=True,
                lookup=Lookup("timeseries_meta", "series_id"),
            ),
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
            FieldDef(
                "scenario_id",
                FieldType.TEXT,
                L("Scenario", "Scenario"),
                required=True,
                lookup=Lookup("scenarios", "scenario_id"),
            ),
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

#: Child rows shown in the form of their parent.
RELATIONS: tuple[Relation, ...] = (
    Relation(
        "unit_parameters",
        L("Parametri dell'unità", "Unit parameters"),
        child="param_values",
        child_field="object_id",
        parent="hydro_units",
        parent_field="fid",
        child_filter=(("object_type", "unit"),),
    ),
    Relation(
        "zone_parameters",
        L("Parametri della zona", "Zone parameters"),
        child="param_values",
        child_field="object_id",
        parent="param_zones",
        parent_field="fid",
        child_filter=(("object_type", "zone"),),
    ),
    Relation(
        "series_values",
        L("Valori della serie", "Series values"),
        child="timeseries_values",
        child_field="series_id",
        parent="timeseries_meta",
        parent_field="series_id",
    ),
    Relation(
        "feature_stations",
        L("Stazioni", "Stations"),
        child="line_stations",
        child_field="feature_id",
        parents=("fixed_head_lines", "fixed_head_areas"),
        parent_table_field="feature_layer",
        parent_field="fid",
    ),
)


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
    if f.lookup is not None:
        doc["lookup"] = {
            "table": f.lookup.table,
            "key": f.lookup.key,
            "value": f.lookup.value or f.lookup.key,
            "filter": dict(f.lookup.filter),
        }
    return doc


def _style_document(style: LayerStyle | None) -> dict[str, Any] | None:
    if style is None:
        return None
    return {k: v for k, v in style.__dict__.items() if v is not None}


def _relation_document(r: Relation) -> dict[str, Any]:
    return {
        "name": r.name,
        "label": _localized(r.label),
        "child": r.child,
        "child_field": r.child_field,
        "parent": r.parent,
        "parents": list(r.parents),
        "parent_table_field": r.parent_table_field,
        "parent_field": r.parent_field,
        "child_filter": dict(r.child_filter),
    }


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
                "style": _style_document(t.style),
            }
            for t in TABLES
        ],
        "relations": [_relation_document(r) for r in RELATIONS],
        "param_quantities": {k: v.value for k, v in PARAM_QUANTITIES.items()},
        "series_quantities": {k: v.value for k, v in SERIES_QUANTITIES.items()},
    }


__all__ = [
    "PARAM_QUANTITIES",
    "RELATIONS",
    "SCHEMA_VERSION",
    "SERIES_QUANTITIES",
    "TABLES",
    "TABLES_BY_NAME",
    "Choice",
    "FieldDef",
    "FieldType",
    "GeometryType",
    "LayerStyle",
    "Lookup",
    "Relation",
    "TableDef",
    "schema_document",
]
