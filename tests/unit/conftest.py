"""Fixtures shared by the unit tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from phrear.project import Project

from .sites import build_site


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
