"""Helpers to build small projects with time series."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

import pytest

from phrear.project import Project, gpkg

START = datetime(2020, 1, 1)
END = datetime(2021, 1, 1)

AddSeries = Callable[..., None]


@pytest.fixture(scope="session")
def _template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("timeline") / "site"
    Project.create(root, name="Sito", start=START, end=END)
    return root


@pytest.fixture
def project(_template: Path, tmp_path: Path) -> Project:
    target = tmp_path / "site"
    shutil.copytree(_template, target)
    return Project.open(target)


def add_series(
    project: Project,
    series_id: str,
    points: Sequence[tuple[str, float]],
    *,
    quantity: str = "discharge",
    unit: str = "m3/d",
    interpolation: str = "stepwise",
) -> None:
    with gpkg.connect(project.gpkg_path) as conn:
        conn.execute(
            'INSERT INTO "timeseries_meta" (series_id, quantity, unit, interpolation) '
            "VALUES (?, ?, ?, ?)",
            (series_id, quantity, unit, interpolation),
        )
        conn.executemany(
            'INSERT INTO "timeseries_values" (series_id, "datetime", value) VALUES (?, ?, ?)',
            [(series_id, moment, value) for moment, value in points],
        )


def add_well(
    project: Project,
    name: str,
    series_id: str | None,
    *,
    active: bool = True,
    scenario_id: str | None = None,
) -> int:
    with gpkg.connect(project.gpkg_path) as conn:
        cur = conn.execute(
            'INSERT INTO "wells" (name, active, scenario_id, screen_top, screen_bottom, '
            "series_id) VALUES (?, ?, ?, 5.0, 15.0, ?)",
            (name, int(active), scenario_id, series_id),
        )
        return int(cur.lastrowid or 0)
