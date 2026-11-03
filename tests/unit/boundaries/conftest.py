"""Helpers to add boundary features to the synthetic site and build them."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
import shapely

from phrear.boundaries.base import PackageInput
from phrear.boundaries.registry import Boundaries, build_boundaries
from phrear.grid.model_grid import build_model_grid
from phrear.params.layers import layer_parameters
from phrear.params.values import load_parameters
from phrear.project import Project
from phrear.timeline import project_timeline

from ..sites import X0, Y0, insert

Build = Callable[[], Boundaries]


def center(row: int, col: int) -> tuple[float, float]:
    """Centre of cell (row, col) of the site grid, 0-based."""
    return X0 + 550.0 + 100.0 * col, Y0 + 1950.0 - 100.0 * row


def cell_box(row: int, col: int) -> shapely.Geometry:
    x, y = center(row, col)
    return shapely.box(x - 50, y - 50, x + 50, y + 50)


def add_series(
    project: Project,
    series_id: str,
    quantity: str,
    unit: str,
    points: list[tuple[datetime, float]],
    interpolation: str = "stepwise",
) -> None:
    insert(
        project,
        "timeseries_meta",
        series_id=series_id,
        quantity=quantity,
        unit=unit,
        interpolation=interpolation,
    )
    for moment, value in points:
        insert(
            project,
            "timeseries_values",
            series_id=series_id,
            datetime=moment.isoformat(),
            value=value,
        )


def add_well(project: Project, x: float, y: float, **fields: Any) -> int:
    values: dict[str, Any] = {
        "name": "P",
        "role": "extraction",
        "depth_mode": "elevation",
        "screen_top": 45.0,
        "screen_bottom": 10.0,
        "model_as": "auto",
        "rate": 10.0,
        "rate_unit": "l/s",
    }
    values.update(fields)
    return insert(project, "wells", shapely.Point(x, y), **values)


def add_line(project: Project, coords: list[tuple[float, float]], **fields: Any) -> int:
    return insert(
        project, "fixed_head_lines", shapely.MultiLineString([coords]), **{"name": "L", **fields}
    )


def add_area(project: Project, polygon: shapely.Geometry, **fields: Any) -> int:
    return insert(
        project, "fixed_head_areas", shapely.MultiPolygon([polygon]), **{"name": "A", **fields}
    )


def add_station(
    project: Project, layer: str, feature_id: int, x: float, y: float, **fields: Any
) -> int:
    return insert(
        project,
        "line_stations",
        shapely.Point(x, y),
        feature_layer=layer,
        feature_id=feature_id,
        **fields,
    )


def add_zone(project: Project, polygon: shapely.Geometry, **fields: Any) -> int:
    values: dict[str, Any] = {"name": "Z", "rate": 365.25, "rate_unit": "mm/anno"}
    values.update(fields)
    return insert(project, "recharge_zones", shapely.MultiPolygon([polygon]), **values)


def package(boundaries: Boundaries, name: str) -> PackageInput:
    return next(p for p in boundaries.packages if p.bc_type == name)


@pytest.fixture
def build(valid_site: Project) -> Build:
    def run() -> Boundaries:
        grid = build_model_grid(valid_site)
        layers = layer_parameters(grid, load_parameters(valid_site))
        return build_boundaries(valid_site, grid, layers, project_timeline(valid_site))

    return run
