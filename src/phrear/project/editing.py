"""Writing conceptual-model data from code: features, table rows, rasters.

Used by the verification cases and the example project; the QGIS plugin edits
the GeoPackage directly. Geometries are stored as GeoPackage binary blobs
(little endian, no envelope) in the project CRS, promoted to multi-part types
where the layer requires them.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio
import shapely
from rasterio.transform import from_origin

from phrear.project import gpkg
from phrear.project.project import Project
from phrear.project.schema import TABLES_BY_NAME, GeometryType

FloatArray = npt.NDArray[np.float64]
Field = Callable[[FloatArray, FloatArray], FloatArray]


def geometry_blob(geometry: shapely.Geometry, srs_id: int) -> bytes:
    header = b"GP" + bytes([0, 0x01]) + struct.pack("<i", srs_id)
    wkb: bytes = shapely.to_wkb(geometry, byte_order=1)
    return header + wkb


def _promote(geometry: shapely.Geometry, kind: GeometryType | None) -> shapely.Geometry:
    if kind is GeometryType.MULTIPOLYGON and geometry.geom_type == "Polygon":
        return shapely.MultiPolygon([geometry])
    if kind is GeometryType.MULTILINESTRING and geometry.geom_type == "LineString":
        return shapely.MultiLineString([geometry])
    return geometry


def add_row(
    project: Project, layer: str, geometry: shapely.Geometry | None = None, **fields: Any
) -> int:
    """Insert one feature or table row; returns its fid."""
    values = dict(fields)
    if geometry is not None:
        kind = TABLES_BY_NAME[layer].geometry
        values[gpkg.GEOMETRY_COLUMN] = geometry_blob(_promote(geometry, kind), project.config.crs)
    names = ", ".join(f'"{k}"' for k in values)
    marks = ", ".join("?" for _ in values)
    with gpkg.connect(project.gpkg_path) as conn:
        cursor = conn.execute(
            f'INSERT INTO "{layer}" ({names}) VALUES ({marks})', tuple(values.values())
        )
        return int(cursor.lastrowid or 0)


def write_raster(
    project: Project,
    relative: str,
    bounds: tuple[float, float, float, float],
    pixel: float,
    field: Field | float,
) -> str:
    """GeoTIFF of ``field`` (a constant or z = f(x, y)) over ``bounds`` in the project CRS."""
    xmin, ymin, xmax, ymax = bounds
    ncol = round((xmax - xmin) / pixel)
    nrow = round((ymax - ymin) / pixel)
    cols, rows = np.meshgrid(np.arange(ncol), np.arange(nrow))
    x = xmin + (cols + 0.5) * pixel
    y = ymax - (rows + 0.5) * pixel
    if callable(field):
        z = np.asarray(field(x.astype(np.float64), y.astype(np.float64)), dtype=np.float32)
    else:
        z = np.full((nrow, ncol), field, dtype=np.float32)
    path = project.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=nrow,
        width=ncol,
        count=1,
        dtype="float32",
        crs=f"EPSG:{project.config.crs}",
        transform=from_origin(xmin, ymax, pixel, pixel),
        nodata=-9999.0,
    ) as dst:
        dst.write(z, 1)
    return relative


def add_series(
    project: Project,
    series_id: str,
    quantity: str,
    unit: str,
    points: list[tuple[str, float]],
    interpolation: str = "stepwise",
) -> None:
    """A time series with ISO dates and values in ``unit``."""
    add_row(
        project,
        "timeseries_meta",
        series_id=series_id,
        quantity=quantity,
        unit=unit,
        interpolation=interpolation,
    )
    for moment, value in points:
        add_row(project, "timeseries_values", series_id=series_id, datetime=moment, value=value)


def add_unit(
    project: Project,
    position: int,
    name: str,
    *,
    convertible: bool,
    sublayers: int = 1,
    params: dict[str, tuple[float, str]],
    source: str | None = None,
) -> int:
    """A hydrostratigraphic unit with uniform parameters ``{param: (value, unit)}``."""
    fid = add_row(
        project,
        "hydro_units",
        position=position,
        name=name,
        sublayers=sublayers,
        convertible=int(convertible),
    )
    for param, (value, unit) in params.items():
        add_row(
            project,
            "param_values",
            object_type="unit",
            object_id=fid,
            param=param,
            value=value,
            unit=unit,
            source=source,
        )
    return fid


def add_surface(project: Project, index: int, raster: str) -> int:
    return add_row(project, "surfaces", surface_index=index, raster_path=raster)


def raster_path(project: Project, relative: str) -> Path:
    return project.root / relative
