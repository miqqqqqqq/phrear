"""Helpers to write the parameters of the synthetic site."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from phrear.project import Project, gpkg

#: Valid parameters of the site: unit 1 convertible, unit 2 confined.
VALID: dict[int, list[tuple[str, float, str]]] = {
    1: [("kh", 1e-4, "m/s"), ("anisotropy", 0.1, ""), ("ss", 1e-4, "1/m"), ("sy", 15.0, "%")],
    2: [("kh", 50.0, "m/d"), ("kv", 5.0, "m/d"), ("ss", 1e-5, "1/m"), ("ne", 0.2, "")],
}

AddParam = Callable[..., int]


def unit_fid(project: Project, position: int) -> int:
    with gpkg.connect(project.gpkg_path) as conn:
        row = conn.execute(
            'SELECT fid FROM "hydro_units" WHERE position = ?', (position,)
        ).fetchone()
    return int(row[0])


@pytest.fixture
def add_param(site: Project) -> AddParam:
    """Insert a row of param_values for the unit at ``position``; returns its fid."""

    def add(position: int, param: str, value: float | None, unit: str | None, **cols: Any) -> int:
        values: dict[str, Any] = {
            "object_type": "unit",
            "object_id": unit_fid(site, position),
            "param": param,
            "value": value,
            "unit": unit,
            **cols,
        }
        names = ", ".join(f'"{k}"' for k in values)
        marks = ", ".join("?" for _ in values)
        with gpkg.connect(site.gpkg_path) as conn:
            cursor = conn.execute(
                f'INSERT INTO "param_values" ({names}) VALUES ({marks})', tuple(values.values())
            )
            return int(cursor.lastrowid or 0)

    return add


@pytest.fixture
def valid_site(site: Project, add_param: AddParam) -> Project:
    for position, rows in VALID.items():
        for param, value, unit in rows:
            add_param(position, param, value, unit)
    return site
