"""Creation and inspection of the project GeoPackage (model.gpkg).

Tables are created with pyogrio/GDAL from :data:`phrear.project.schema.TABLES`,
so that QGIS and GDAL see a standard GeoPackage. Unique indexes and the triggers
maintaining ``created_at``/``modified_at`` are added afterwards with SQLite.

GDAL's R-tree triggers call the SQL functions ST_IsEmpty, ST_MinX, ST_MinY,
ST_MaxX and ST_MaxY of the GeoPackage specification. A plain sqlite3 connection
does not have them, so :func:`connect` registers Python implementations; without
them any insert into a layer fails.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely

from phrear.project.schema import TABLES, FieldType, TableDef

GEOMETRY_COLUMN = "geom"
TIMESTAMP_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"

_DTYPES: dict[FieldType, str] = {
    FieldType.INTEGER: "int64",
    FieldType.REAL: "float64",
    FieldType.TEXT: "object",
    FieldType.BOOLEAN: "bool",
    FieldType.DATETIME: "datetime64[ms]",
}


# --- GeoPackage geometry blobs ----------------------------------------------------

_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
_EMPTY_FLAG = 0b10000


def blob_wkb(blob: bytes) -> bytes:
    """WKB part of a GeoPackage geometry blob (header and envelope removed)."""
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob")
    envelope = _ENVELOPE_BYTES[(blob[3] >> 1) & 0b111]
    return blob[8 + envelope :]


def blob_is_empty(blob: bytes) -> bool:
    return bool(blob[3] & _EMPTY_FLAG) or shapely.from_wkb(blob_wkb(blob)).is_empty


def _st_is_empty(blob: bytes | None) -> int | None:
    return None if blob is None else int(blob_is_empty(blob))


def _st_bound(index: int, blob: bytes | None) -> float | None:
    if blob is None or blob_is_empty(blob):
        return None
    return float(shapely.from_wkb(blob_wkb(blob)).bounds[index])


def register_gpkg_functions(conn: sqlite3.Connection) -> None:
    """Register the ST_* functions used by the GeoPackage R-tree triggers."""
    conn.create_function("ST_IsEmpty", 1, _st_is_empty, deterministic=True)
    for name, index in (("ST_MinX", 0), ("ST_MinY", 1), ("ST_MaxX", 2), ("ST_MaxY", 3)):
        conn.create_function(name, 1, partial(_st_bound, index), deterministic=True)


# --- table creation -----------------------------------------------------------------


def _empty_frame(table: TableDef, epsg: int) -> pd.DataFrame:
    columns = {f.name: pd.Series([], dtype=_DTYPES[f.type]) for f in table.fields}
    if table.geometry is None:
        return pd.DataFrame(columns)
    frame: pd.DataFrame = gpd.GeoDataFrame(columns, geometry=gpd.GeoSeries([], crs=f"EPSG:{epsg}"))
    return frame


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _timestamp_triggers(table: TableDef) -> list[str]:
    if "modified_at" not in table.field_names:
        return []
    t = _quote(table.name)
    return [
        f"CREATE TRIGGER {_quote('trg_' + table.name + '_insert')} AFTER INSERT ON {t} "
        f"FOR EACH ROW BEGIN UPDATE {t} SET "
        f"created_at = COALESCE(NEW.created_at, {TIMESTAMP_SQL}), "
        f"modified_at = {TIMESTAMP_SQL} WHERE fid = NEW.fid; END",
        f"CREATE TRIGGER {_quote('trg_' + table.name + '_update')} AFTER UPDATE ON {t} "
        f"FOR EACH ROW WHEN NEW.modified_at IS OLD.modified_at BEGIN UPDATE {t} SET "
        f"modified_at = {TIMESTAMP_SQL} WHERE fid = NEW.fid; END",
    ]


def _unique_indexes(table: TableDef) -> list[str]:
    statements = []
    for columns in table.unique:
        name = _quote(f"uq_{table.name}_{'_'.join(columns)}")
        cols = ", ".join(_quote(c) for c in columns)
        statements.append(f"CREATE UNIQUE INDEX {name} ON {_quote(table.name)} ({cols})")
    return statements


def create_table(path: Path, table: TableDef, epsg: int) -> None:
    """Create one table (layer or attribute table) with its indexes and triggers."""
    frame = _empty_frame(table, epsg)
    if table.geometry is None:
        pyogrio.write_dataframe(frame, path, layer=table.name, driver="GPKG")
    else:
        pyogrio.write_dataframe(
            frame,
            path,
            layer=table.name,
            driver="GPKG",
            geometry_type=table.geometry.value,
            layer_options={"GEOMETRY_NAME": GEOMETRY_COLUMN},
        )
    with connect(path) as conn:
        for statement in _unique_indexes(table) + _timestamp_triggers(table):
            conn.execute(statement)


def create_gpkg(path: Path, epsg: int, tables: tuple[TableDef, ...] = TABLES) -> None:
    """Create a new GeoPackage with all the tables of the schema."""
    if path.exists():
        raise FileExistsError(path)
    for table in tables:
        create_table(path, table, epsg)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """SQLite connection committed on success and always closed."""
    conn = sqlite3.connect(path)
    register_gpkg_functions(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def existing_tables(conn: sqlite3.Connection) -> set[str]:
    """Tables registered in gpkg_contents."""
    return {row[0] for row in conn.execute("SELECT table_name FROM gpkg_contents")}


def missing_tables(path: Path, tables: tuple[TableDef, ...] = TABLES) -> list[str]:
    with connect(path) as conn:
        present = existing_tables(conn)
    return [t.name for t in tables if t.name not in present]


def row_counts(path: Path, tables: tuple[TableDef, ...] = TABLES) -> dict[str, int]:
    with connect(path) as conn:
        return {
            t.name: int(conn.execute(f"SELECT COUNT(*) FROM {_quote(t.name)}").fetchone()[0])
            for t in tables
        }
