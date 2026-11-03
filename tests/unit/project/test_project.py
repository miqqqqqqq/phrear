"""Creating, opening and migrating projects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from phrear.errors import ProjectError
from phrear.project import Project, gpkg
from phrear.project import migrations as migrations_module
from phrear.project.project import GPKG_FILE, PROJECT_FILE, crs_name
from phrear.project.schema import SCHEMA_VERSION

START = datetime(2020, 1, 1)
END = datetime(2021, 1, 1)


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("tpl") / "site"
    Project.create(root, name="Sito", start=START, end=END)
    return root


@pytest.fixture
def project_dir(template: Path, tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "site"
    shutil.copytree(template, target)
    return target


def test_create_builds_the_folder_layout(template: Path) -> None:
    for name in (PROJECT_FILE, GPKG_FILE, "rasters", "runs", "exports"):
        assert (template / name).exists(), name
    project = Project.open(template)
    assert project.config.name == "Sito"
    assert project.config.schema_version == SCHEMA_VERSION
    counts = project.summary()["tables"]
    assert counts["change_log"] == 1
    assert counts["wells"] == 0


def test_create_refuses_a_non_empty_folder(tmp_path: Path) -> None:
    (tmp_path / "something.txt").write_text("x")
    with pytest.raises(ProjectError) as exc:
        Project.create(tmp_path, name="X", start=START, end=END)
    assert exc.value.code == "project.exists"


def test_open_accepts_the_toml_path(template: Path) -> None:
    assert Project.open(template / PROJECT_FILE).root == template.resolve()


def test_open_missing_project(tmp_path: Path) -> None:
    with pytest.raises(ProjectError) as exc:
        Project.open(tmp_path)
    assert exc.value.code == "project.not_found"


def test_open_detects_missing_gpkg(project_dir: Path) -> None:
    (project_dir / GPKG_FILE).unlink()
    with pytest.raises(ProjectError) as exc:
        Project.open(project_dir)
    assert exc.value.code == "project.gpkg_missing"


def test_open_detects_missing_tables(project_dir: Path) -> None:
    with gpkg.connect(project_dir / GPKG_FILE) as conn:
        conn.execute("DELETE FROM gpkg_contents WHERE table_name = 'wells'")
    with pytest.raises(ProjectError) as exc:
        Project.open(project_dir)
    assert exc.value.code == "project.gpkg_tables_missing"
    assert "wells" in exc.value.message("it")


def _set_schema_version(root: Path, version: int) -> None:
    path = root / PROJECT_FILE
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(f"schema_version = {SCHEMA_VERSION}", f"schema_version = {version}")
    )


def test_newer_schema_is_refused(project_dir: Path) -> None:
    _set_schema_version(project_dir, SCHEMA_VERSION + 1)
    with pytest.raises(ProjectError) as exc:
        Project.open(project_dir)
    assert exc.value.code == "project.schema_too_new"


def test_migration_backs_up_then_upgrades(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pretend this version uses schema 2 and register a migration 1 -> 2."""
    from phrear.project import project as project_module

    calls: list[Path] = []
    monkeypatch.setattr(project_module, "SCHEMA_VERSION", SCHEMA_VERSION + 1)
    monkeypatch.setitem(migrations_module.MIGRATIONS, SCHEMA_VERSION, calls.append)
    with pytest.raises(ProjectError) as exc:
        Project.open(project_dir)
    assert exc.value.code == "project.migration_required"

    report = Project.migrate(project_dir)
    assert calls == [project_dir.resolve()]
    assert report.steps == (SCHEMA_VERSION,)
    assert report.backup is not None and (report.backup / GPKG_FILE).is_file()
    backed_up = (report.backup / PROJECT_FILE).read_text(encoding="utf-8")
    assert f"schema_version = {SCHEMA_VERSION}" in backed_up
    project = Project.open(project_dir)
    assert project.config.schema_version == SCHEMA_VERSION + 1
    assert project.summary()["tables"]["change_log"] == 2


def test_migrate_current_project_is_a_no_op(project_dir: Path) -> None:
    report = Project.migrate(project_dir)
    assert report.steps == () and report.backup is None


def test_content_hash_changes_with_settings_not_with_software_version(project_dir: Path) -> None:
    project = Project.open(project_dir)
    base = project.summary()["content_hash"]
    project.config.software_version_last_saved = "9.9.9"
    assert project.summary()["content_hash"] == base
    project.config.description = "nuova descrizione"
    assert project.summary()["content_hash"] != base


def test_rasters_enter_the_content_hash(project_dir: Path) -> None:
    project = Project.open(project_dir)
    base = project.summary()["content_hash"]
    (project_dir / "rasters" / "dem.tif").write_bytes(b"fake")
    assert "rasters/dem.tif" in project.content_hashes()
    assert project.summary()["content_hash"] != base


@pytest.mark.parametrize(
    ("epsg", "code"), [(4326, "project.crs_not_metric"), (999999, "project.crs_unknown")]
)
def test_crs_must_be_projected_in_metres(epsg: int, code: str) -> None:
    with pytest.raises(ProjectError) as exc:
        crs_name(epsg)
    assert exc.value.code == code


def test_default_crs_is_rdn2008_utm32() -> None:
    assert "RDN2008" in crs_name(7791) and "32N" in crs_name(7791)
