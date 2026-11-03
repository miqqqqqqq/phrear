"""Fixtures shared by the unit tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from phrear.project import Project

from .sites import VALID, AddParam, build_site, insert, unit_fid


@pytest.fixture(scope="session")
def site_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("site") / "site"
    build_site(root)
    return root


@pytest.fixture
def site(site_template: Path, tmp_path: Path) -> Project:
    """A fresh copy of the synthetic site of tests/unit/sites.py."""
    target = tmp_path / "site"
    shutil.copytree(site_template, target)
    return Project.open(target)


@pytest.fixture
def add_param(site: Project) -> AddParam:
    """Insert a row of param_values for the unit at ``position``; returns its fid."""

    def add(position: int, param: str, value: float | None, unit: str | None, **cols: Any) -> int:
        return insert(
            site,
            "param_values",
            object_type="unit",
            object_id=unit_fid(site, position),
            param=param,
            value=value,
            unit=unit,
            **cols,
        )

    return add


@pytest.fixture
def valid_site(site: Project, add_param: AddParam) -> Project:
    """The site with valid parameters for both units."""
    for position, rows in VALID.items():
        for param, value, unit in rows:
            add_param(position, param, value, unit)
    return site
