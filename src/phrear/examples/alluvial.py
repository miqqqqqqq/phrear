"""Example project: a synthetic alluvial plain, runnable from the CLI.

The site is invented, placed in EPSG:7791 (RDN2008 / UTM 32N). A plain 3 km × 2 km
gently sloping eastwards towards a river:

- two units: silty cover (convertible, 4-6 m, pinching out along the western
  edge, where the gravels crop out) over sandy gravels split into two sublayers;
- fixed head 47 m along the western, upgradient boundary, half a cell inside the
  domain; the river on the east side with monthly stages at an upstream and a
  downstream station (the head between them follows the chainage);
- a public-supply well at 15 l/s for the whole year and an irrigation well that
  starts on 1 April, doubles in June and stops in September;
- recharge 250 mm/year on farmland and 80 mm/year on the urban area;
- one year, 2024, after an initial steady state.

Every value carries its unit and, for the parameters, its source and range.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import shapely

from phrear.project import Project, gpkg
from phrear.project.config import ConstantHeads, Dem
from phrear.project.editing import (
    FloatArray,
    add_row,
    add_series,
    add_surface,
    add_unit,
    write_raster,
)

X0, Y0 = 681_000.0, 4_846_000.0
SIZE = (3000.0, 2000.0)
CELL = 50.0
DOMAIN = shapely.Polygon(
    [(X0 + 100, Y0 + 100), (X0 + 2900, Y0 + 150), (X0 + 2950, Y0 + 1900),
     (X0 + 1500, Y0 + 1950), (X0 + 150, Y0 + 1850)]
)  # fmt: skip
URBAN = shapely.Polygon(
    [(X0 + 300, Y0 + 1200), (X0 + 1300, Y0 + 1250), (X0 + 1250, Y0 + 1900),
     (X0 + 350, Y0 + 1850)]
)  # fmt: skip
RIVER_UP = [41.2, 41.5, 41.8, 41.6, 41.3, 41.0, 40.8, 40.7, 40.9, 41.2, 41.6, 41.8]
"""Monthly stage at the upstream (northern) station, 2024, m a.s.l."""
RIVER_DROP = 1.0
"""Stage drop between the upstream and the downstream station, m."""


def dem(x: FloatArray, y: FloatArray) -> FloatArray:
    """Ground and model top: 50 m in the west, 2 per mille towards east, 1 per mille north."""
    return 50.0 - 0.002 * (x - X0) + 0.001 * (y - Y0 - 1000.0)


def cover_base(x: FloatArray, y: FloatArray) -> FloatArray:
    """Base of the cover: 4 m thick in the south to 6 m in the north, 0.3 m in the west."""
    thickness = np.where(x - X0 < 400.0, 0.3, 4.0 + 2.0 * (y - Y0) / SIZE[1])
    return dem(x, y) - thickness


def aquifer_base(x: FloatArray, y: FloatArray) -> FloatArray:
    return -5.0 - 0.002 * (x - X0)


def _z(x: float, y: float) -> float:
    return float(dem(np.array(x), np.array(y)))


def create_example(root: Path) -> Project:
    """Create the example project in ``root``, which must be new or empty."""
    project = Project.create(
        root,
        name="Esempio - piana alluvionale",
        start=datetime(2024, 1, 1),
        end=datetime(2025, 1, 1),
    )
    project.config.description = (
        "Sito sintetico di esempio: falda alluvionale tra un limite a carico imposto e un "
        "fiume, con un pozzo idropotabile, un pozzo irriguo stagionale e ricarica per zone."
    )
    project.config.grid.cell_size_m = CELL
    project.config.initial_heads = ConstantHeads(value_m=44.0)

    # geometry: domain, DEM and contact surfaces
    add_row(project, "domain", DOMAIN, name="Piana", active=1)
    bounds = (X0, Y0, X0 + SIZE[0], Y0 + SIZE[1])
    surfaces = (("dem", dem), ("base_copertura", cover_base), ("base_acquifero", aquifer_base))
    for index, (name, field) in enumerate(surfaces):
        raster = write_raster(project, f"rasters/{name}.tif", bounds, 10.0, field)
        add_surface(project, index, raster)
    project.config.dem = Dem(raster_path="rasters/dem.tif", vertical_datum="m s.l.m. (sintetico)")
    project.save()

    # hydrostratigraphic units with their parameters
    cover = {
        "kh": (1e-6, "m/s"),
        "anisotropy": (0.1, ""),
        "ss": (1e-4, "1/m"),
        "sy": (5.0, "%"),
    }
    add_unit(project, 1, "Limi di copertura", convertible=True, params=cover, source="literature")
    gravels = {
        "kh": (1e-3, "m/s"),
        "anisotropy": (0.1, ""),
        "ss": (5e-5, "1/m"),
        "sy": (15.0, "%"),
        "ne": (20.0, "%"),
    }
    fid = add_unit(
        project,
        2,
        "Ghiaie e sabbie",
        convertible=True,
        sublayers=2,
        params=gravels,
        source="pumping_test",
    )
    _kh_range(project, fid, 5e-4, 2e-3)

    # upgradient boundary: one station, uniform head
    west = add_row(
        project,
        "fixed_head_lines",
        shapely.LineString([(X0 + 200, Y0 + 230), (X0 + 230, Y0 + 1800)]),
        name="Limite a monte",
    )
    add_row(
        project,
        "line_stations",
        shapely.Point(X0 + 215, Y0 + 1000),
        name="Monte",
        feature_layer="fixed_head_lines",
        feature_id=west,
        value=47.0,
    )

    # river: monthly stages at two stations, interpolated along the line
    up, down = (X0 + 2875, Y0 + 1850), (X0 + 2825, Y0 + 230)
    river = add_row(project, "fixed_head_lines", shapely.LineString([up, down]), name="Fiume")
    months = [f"2024-{m:02d}-01T00:00:00" for m in range(1, 13)]
    upstream = list(zip(months, RIVER_UP, strict=True))
    add_series(project, "fiume_monte", "length", "m", upstream)
    add_series(project, "fiume_valle", "length", "m", [(t, v - RIVER_DROP) for t, v in upstream])
    for (x, y), name, series in (
        (up, "Ponte nord", "fiume_monte"),
        (down, "Ponte sud", "fiume_valle"),
    ):
        add_row(
            project,
            "line_stations",
            shapely.Point(x, y),
            name=name,
            feature_layer="fixed_head_lines",
            feature_id=river,
            series_id=series,
        )

    # wells: screens as depths below the ground
    add_row(
        project,
        "wells",
        shapely.Point(X0 + 1600, Y0 + 1000),
        name="P1 acquedotto",
        role="extraction",
        depth_mode="depth",
        z_ref=_z(X0 + 1600, Y0 + 1000),
        screen_top=15.0,
        screen_bottom=35.0,
        radius=0.2,
        model_as="auto",
        rate=15.0,
        rate_unit="l/s",
    )
    irrigation = [
        ("2024-04-01T00:00:00", 10.0),
        ("2024-06-01T00:00:00", 20.0),
        ("2024-09-01T00:00:00", 0.0),
    ]
    add_series(project, "q_irriguo", "discharge", "l/s", irrigation)
    add_row(
        project,
        "wells",
        shapely.Point(X0 + 2200, Y0 + 700),
        name="P2 irriguo",
        role="extraction",
        depth_mode="depth",
        z_ref=_z(X0 + 2200, Y0 + 700),
        screen_top=10.0,
        screen_bottom=30.0,
        radius=0.15,
        model_as="auto",
        series_id="q_irriguo",
    )

    # recharge zones, without overlaps
    farmland = shapely.box(*bounds).difference(URBAN)
    add_row(project, "recharge_zones", farmland, name="Agricolo", rate=250.0, rate_unit="mm/anno")
    add_row(project, "recharge_zones", URBAN, name="Urbano", rate=80.0, rate_unit="mm/anno")
    return Project.open(project.root)


def _kh_range(project: Project, unit_fid: int, low: float, high: float) -> None:
    """Range of K from the pumping tests, in the unit of the value (m/s)."""
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute(
            'UPDATE "param_values" SET "min" = ?, "max" = ? WHERE object_id = ? AND param = ?',
            (low, high, unit_fid, "kh"),
        )
