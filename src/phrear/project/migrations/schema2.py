"""Schema 1 → 2 (milestone M2): parameter zones and field tests.

- New layers ``param_zones`` and ``field_tests``.
- ``hydro_units`` loses ``param_mode``: the sources of a parameter combine cell by
  cell (raster, interpolated field, zones, uniform value; ADR 0024), so a single
  mode per unit no longer applies. A unit that asked for ``interpolated`` gets
  ``k_from_tests`` true; the other values were not usable in schema 1.
- ``hydro_units`` gains ``k_from_tests`` and ``interp_max_distance``.

Every step checks the current state first, so a later migration that changes the
same tables finds what it expects.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from phrear.project import gpkg
from phrear.project.config import read_config
from phrear.project.schema import TABLES_BY_NAME

NEW_TABLES = ("param_zones", "field_tests")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def upgrade(root: Path) -> None:
    path = root / "model.gpkg"
    epsg = read_config(root / "project.toml").crs
    with gpkg.connect(path) as conn:
        present = gpkg.existing_tables(conn)
    for name in NEW_TABLES:
        if name not in present:
            gpkg.create_table(path, TABLES_BY_NAME[name], epsg)
    with gpkg.connect(path) as conn:
        columns = _columns(conn, "hydro_units")
        if "k_from_tests" not in columns:
            conn.execute('ALTER TABLE "hydro_units" ADD COLUMN "k_from_tests" BOOLEAN')
        if "interp_max_distance" not in columns:
            conn.execute('ALTER TABLE "hydro_units" ADD COLUMN "interp_max_distance" REAL')
        if "param_mode" in columns:
            conn.execute(
                'UPDATE "hydro_units" SET "k_from_tests" = 1 WHERE "param_mode" = \'interpolated\''
            )
            conn.execute('ALTER TABLE "hydro_units" DROP COLUMN "param_mode"')
