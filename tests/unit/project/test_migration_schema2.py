"""Migration of a schema 1 project, frozen in tests/data/schema1, to schema 2."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from phrear.errors import ProjectError
from phrear.examples.alluvial import create_example
from phrear.params.values import load_parameters
from phrear.project import Project, gpkg, hashing
from phrear.project.project import GPKG_FILE
from phrear.project.schema import SCHEMA_VERSION, TABLES_BY_NAME

SCHEMA1 = Path(__file__).resolve().parents[2] / "data" / "schema1"
#: Tables the migration changes: units lose param_mode, the log gets a row.
UPDATED_TABLES = ("hydro_units", "change_log")


@pytest.fixture
def old_project(tmp_path: Path) -> Path:
    """The example project as written by schema 1, with unit 2 set to 'interpolated'."""
    root = tmp_path / "esempio"
    shutil.copytree(SCHEMA1, root)
    return root


def columns(path: Path, table: str) -> list[str]:
    with sqlite3.connect(path) as conn:
        return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def test_the_fixture_is_schema_1(old_project: Path) -> None:
    assert SCHEMA_VERSION == 2
    with pytest.raises(ProjectError) as exc:
        Project.open(old_project)
    assert exc.value.code == "project.migration_required"
    assert "param_mode" in columns(old_project / GPKG_FILE, "hydro_units")


def test_migration_to_schema_2(old_project: Path) -> None:
    gpkg_path = old_project / GPKG_FILE
    unchanged = [
        t for t in TABLES_BY_NAME.values() if t.since == 1 and t.name not in UPDATED_TABLES
    ]
    before = hashing.gpkg_hashes(gpkg_path, unchanged)
    report = Project.migrate(old_project)
    assert (report.from_version, report.to_version, report.steps) == (1, 2, (1,))
    assert report.backup is not None and (report.backup / GPKG_FILE).is_file()
    assert "param_mode" in columns(report.backup / GPKG_FILE, "hydro_units")

    project = Project.open(old_project)
    assert project.config.schema_version == 2
    names = columns(gpkg_path, "hydro_units")
    assert "param_mode" not in names and {"k_from_tests", "interp_max_distance"} <= set(names)
    with gpkg.connect(gpkg_path) as conn:
        flags = dict(conn.execute('SELECT position, k_from_tests FROM "hydro_units"'))
        assert flags == {1: None, 2: 1}  # 'interpolated' kept as K from tests
        assert conn.execute('SELECT COUNT(*) FROM "param_zones"').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM "field_tests"').fetchone()[0] == 0
        log = conn.execute('SELECT action, detail FROM "change_log" ORDER BY fid').fetchall()
    assert log[-1] == ("migrate", "schema 1 -> 2")
    for name in ("param_zones", "field_tests"):
        assert set(TABLES_BY_NAME[name].field_names) <= set(columns(gpkg_path, name))
    # The data of the other tables is untouched.
    assert hashing.gpkg_hashes(gpkg_path, unchanged) == before


def test_a_migrated_project_works_like_a_new_one(old_project: Path, tmp_path: Path) -> None:
    Project.migrate(old_project)
    # Rasters are not part of the schema: take them from a fresh example.
    fresh = tmp_path / "fresh"
    create_example(fresh)
    shutil.copytree(fresh / "rasters", old_project / "rasters", dirs_exist_ok=True)
    with gpkg.connect(old_project / GPKG_FILE) as conn:
        conn.execute('UPDATE "hydro_units" SET k_from_tests = 0')
    migrated = load_parameters(Project.open(old_project))
    new = load_parameters(Project.open(fresh))
    assert [u.name for u in migrated.units] == [u.name for u in new.units]
    for a, b in zip(migrated.units, new.units, strict=True):
        assert {k: v.value for k, v in a.values.items()} == {
            k: v.value for k, v in b.values.items()
        }


def test_migrating_twice_does_nothing(old_project: Path) -> None:
    Project.migrate(old_project)
    report = Project.migrate(old_project)
    assert report.steps == () and report.backup is None
