"""project.toml: metadata and settings of a project (docs/SPEC.md, section 8.1).

The file is read with :mod:`tomllib`, validated with pydantic and written with
tomlkit, which keeps the comments a user may have added by hand (docs/adr/0007).
Dates are local civil time without time zone; a TOML date means midnight.
"""

from __future__ import annotations

import tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import tomlkit
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from phrear.errors import ProjectError, UnitError
from phrear.units import PhysicalQuantity, conversion_factor


def _to_datetime(value: Any) -> Any:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day)
    return value


LocalDateTime = Annotated[datetime, BeforeValidator(_to_datetime)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Units(_Section):
    """Preferred units for input and display. Internal units stay metres and days."""

    discharge: str = "l/s"
    conductivity: str = "m/s"
    recharge: str = "mm/anno"
    storage: str = "1/m"

    @model_validator(mode="after")
    def _check_units(self) -> Units:
        expected = {
            "discharge": PhysicalQuantity.DISCHARGE,
            "conductivity": PhysicalQuantity.VELOCITY,
            "recharge": PhysicalQuantity.VELOCITY,
            "storage": PhysicalQuantity.SPECIFIC_STORAGE,
        }
        for name, quantity in expected.items():
            try:
                conversion_factor(getattr(self, name), quantity)
            except UnitError as exc:
                raise ValueError(f"units.{name}: {exc.message('en')}") from exc
        return self


class SteadyReference(_Section):
    """Period whose series averages define the initial steady state (section 13)."""

    start: LocalDateTime
    end: LocalDateTime

    @model_validator(mode="after")
    def _ordered(self) -> SteadyReference:
        if self.end <= self.start:
            raise ValueError("end must follow start")
        return self


class ModelTime(_Section):
    start_date: LocalDateTime
    end_date: LocalDateTime
    steady_initial: bool = True
    steady_reference: SteadyReference | None = None
    period_breaks: list[LocalDateTime] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> ModelTime:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must follow start_date")
        for moment in self.period_breaks:
            if not self.start_date < moment < self.end_date:
                raise ValueError(f"period break {moment.isoformat()} is outside the model period")
        if len(set(self.period_breaks)) != len(self.period_breaks):
            raise ValueError("period_breaks contains duplicates")
        self.period_breaks.sort()
        return self


class TimeStepping(_Section):
    """Automatic time steps of each stress period (docs/SPEC.md, section 13).

    Each transient period starts with a step no longer than ``dt_initial_d`` and
    grows by at most ``tsmult`` per step, without exceeding ``dt_max_d``, which
    also sets the resolution with which time series enter the model.
    """

    dt_initial_d: float = Field(default=1.0, gt=0)
    tsmult: float = Field(default=1.2, ge=1.0)
    dt_max_d: float = Field(default=30.0, gt=0)
    min_period_d: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> TimeStepping:
        if self.dt_max_d < self.dt_initial_d:
            raise ValueError("dt_max_d must not be smaller than dt_initial_d")
        return self


class Dem(_Section):
    raster_path: str
    vertical_datum: str = ""


class ConstantHeads(_Section):
    mode: Literal["constant"] = "constant"
    value_m: float


class RasterHeads(_Section):
    mode: Literal["raster"] = "raster"
    raster_path: str


class InterpolatedHeads(_Section):
    mode: Literal["interpolated"] = "interpolated"


class RunHeads(_Section):
    mode: Literal["run"] = "run"
    run_id: str


InitialHeads = Annotated[
    ConstantHeads | RasterHeads | InterpolatedHeads | RunHeads, Field(discriminator="mode")
]


class Grid(_Section):
    """Model grid (docs/SPEC.md, sections 10.3 and 14).

    ``origin_x``/``origin_y`` are the lower-left corner of the grid and
    ``rotation_deg`` the counter-clockwise rotation about it, as in MF6 DIS
    (XORIGIN, YORIGIN, ANGROT). Without an origin the grid covers the domain.
    """

    type: Literal["dis", "disv"] = "dis"
    cell_size_m: float | None = Field(default=None, gt=0)
    rotation_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    origin_x: float | None = None
    origin_y: float | None = None
    min_thickness_m: float = Field(default=0.5, gt=0)
    activation: Literal["centroid", "area"] = "centroid"
    """A cell is active if its centroid is in the domain, or its area fraction is."""
    min_area_fraction: float = Field(default=0.5, gt=0, le=1)
    dem_tolerance_m: float = Field(default=1.0, ge=0)
    """Maximum height of the model top above the DEM before a warning."""
    max_cells_warning: int = Field(default=1_000_000, gt=0)

    @model_validator(mode="after")
    def _origin_pair(self) -> Grid:
        if (self.origin_x is None) != (self.origin_y is None):
            raise ValueError("origin_x and origin_y must be given together")
        return self


class Solver(_Section):
    preset: Literal["standard", "robust", "expert"] = "standard"
    ims: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ims_only_for_expert(self) -> Solver:
        if self.ims and self.preset != "expert":
            raise ValueError("solver.ims options require preset = 'expert'")
        return self


class Options(_Section):
    newton: bool = True
    xt3d: Literal["auto", "on", "off"] = "auto"


class ProjectConfig(_Section):
    schema_version: int = Field(ge=1)
    software_version_created: str
    software_version_last_saved: str
    name: str = Field(min_length=1)
    description: str = ""
    crs: int = Field(gt=0, description="EPSG code of the project CRS")
    units: Units = Field(default_factory=Units)
    model: ModelTime
    time: TimeStepping = Field(default_factory=TimeStepping)
    dem: Dem | None = None
    initial_heads: InitialHeads | None = None
    grid: Grid = Field(default_factory=Grid)
    solver: Solver = Field(default_factory=Solver)
    options: Options = Field(default_factory=Options)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


def _location(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc) or "/"


def parse_config(text: str) -> ProjectConfig:
    """Parse and validate the content of project.toml."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ProjectError("project.config_syntax", reason=str(exc), detail=str(exc)) from exc
    try:
        return ProjectConfig.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ProjectError(
            "project.config_invalid",
            location=_location(first["loc"]),
            reason=first["msg"],
            detail=str(exc),
        ) from exc


def read_config(path: Path) -> ProjectConfig:
    return parse_config(path.read_text(encoding="utf-8"))


def _toml_value(value: Any) -> Any:
    if isinstance(value, datetime) and value.time() == datetime.min.time():
        return value.date()
    if isinstance(value, list):
        return [_toml_value(v) for v in value]
    return value


def _merge(table: Any, data: dict[str, Any]) -> None:
    """Update a tomlkit table in place, keeping comments of the entries that remain."""
    for key in [k for k in table if k not in data]:
        del table[key]
    for key, value in data.items():
        if isinstance(value, dict):
            if key not in table or not isinstance(table[key], dict):
                table[key] = tomlkit.table()
            _merge(table[key], value)
        else:
            table[key] = _toml_value(value)


def _prune_empty(data: dict[str, Any]) -> dict[str, Any]:
    """Drop empty tables (e.g. ``[solver.ims]`` with no options)."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            value = _prune_empty(value)
            if not value:
                continue
        out[key] = value
    return out


def dump_config(config: ProjectConfig, previous: str | None = None) -> str:
    """Serialise ``config`` as TOML; if ``previous`` is given, keep its comments."""
    data = _prune_empty(config.model_dump(mode="python", exclude_none=True))
    # top-level scalars first, then tables, as TOML requires
    ordered = {k: v for k, v in data.items() if not isinstance(v, dict)}
    ordered |= {k: v for k, v in data.items() if isinstance(v, dict)}
    document = tomlkit.parse(previous) if previous else tomlkit.document()
    _merge(document, ordered)
    return tomlkit.dumps(document)


def write_config(config: ProjectConfig, path: Path) -> None:
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(dump_config(config, previous), encoding="utf-8", newline="\n")
