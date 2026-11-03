"""A Phrear project: a folder with project.toml, model.gpkg and rasters (section 8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyproj
from pyproj.exceptions import CRSError

from phrear import __version__
from phrear.errors import ProjectError
from phrear.project import gpkg, hashing
from phrear.project.config import ModelTime, ProjectConfig, read_config, write_config
from phrear.project.migrations import MIGRATIONS, MigrationReport, backup_project, pending
from phrear.project.schema import SCHEMA_VERSION, TABLES

PROJECT_FILE = "project.toml"
GPKG_FILE = "model.gpkg"
RASTERS_DIR = "rasters"
RUNS_DIR = "runs"
EXPORTS_DIR = "exports"
DEFAULT_EPSG = 7791  # RDN2008 / UTM zone 32N, axes east-north


def crs_name(epsg: int) -> str:
    """Name of a projected CRS in metres; raise :class:`ProjectError` otherwise."""
    try:
        crs = pyproj.CRS.from_epsg(epsg)
    except CRSError as exc:
        raise ProjectError("project.crs_unknown", epsg=epsg, detail=str(exc)) from exc
    units = {axis.unit_name for axis in crs.axis_info}
    if not crs.is_projected or not units <= {"metre", "meter"}:
        raise ProjectError(
            "project.crs_not_metric", epsg=epsg, crs_name=crs.name, detail=f"units {units}"
        )
    return str(crs.name)


def _log_change(path: Path, action: str, detail: str) -> None:
    with gpkg.connect(path) as conn:
        conn.execute(
            'INSERT INTO "change_log" ("time", "action", "detail", "software_version") '
            "VALUES (?, ?, ?, ?)",
            (datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), action, detail, __version__),
        )


@dataclass
class Project:
    root: Path
    config: ProjectConfig

    @property
    def config_path(self) -> Path:
        return self.root / PROJECT_FILE

    @property
    def gpkg_path(self) -> Path:
        return self.root / GPKG_FILE

    # --- creation and opening -------------------------------------------------

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        name: str,
        start: datetime,
        end: datetime,
        epsg: int = DEFAULT_EPSG,
    ) -> Project:
        """Create a new project in ``root``, which must not exist or be empty."""
        root = root.resolve()
        if root.exists() and any(root.iterdir()):
            raise ProjectError("project.exists", path=str(root))
        crs_name(epsg)
        config = ProjectConfig(
            schema_version=SCHEMA_VERSION,
            software_version_created=__version__,
            software_version_last_saved=__version__,
            name=name,
            crs=epsg,
            model=ModelTime(start_date=start, end_date=end),
        )
        root.mkdir(parents=True, exist_ok=True)
        for folder in (RASTERS_DIR, RUNS_DIR, EXPORTS_DIR):
            (root / folder).mkdir()
        project = cls(root, config)
        write_config(config, project.config_path)
        gpkg.create_gpkg(project.gpkg_path, epsg)
        _log_change(project.gpkg_path, "create", f"schema {SCHEMA_VERSION}")
        return project

    @classmethod
    def open(cls, path: Path, *, check_schema: bool = True) -> Project:
        """Open the project in ``path`` (the folder or its project.toml)."""
        root = (path.parent if path.name == PROJECT_FILE else path).resolve()
        config_path = root / PROJECT_FILE
        if not config_path.is_file():
            raise ProjectError("project.not_found", path=str(root))
        config = read_config(config_path)
        project = cls(root, config)
        if check_schema:
            project.check_schema_version()
        crs_name(config.crs)
        if not project.gpkg_path.is_file():
            raise ProjectError("project.gpkg_missing", path=str(root))
        missing = gpkg.missing_tables(project.gpkg_path)
        if missing:
            raise ProjectError("project.gpkg_tables_missing", tables=", ".join(missing))
        return project

    def check_schema_version(self) -> None:
        found = self.config.schema_version
        if found > SCHEMA_VERSION:
            raise ProjectError("project.schema_too_new", found=found, supported=SCHEMA_VERSION)
        if found < SCHEMA_VERSION:
            raise ProjectError("project.migration_required", found=found, supported=SCHEMA_VERSION)

    # --- saving and migration ---------------------------------------------------

    def save(self) -> None:
        """Write project.toml, recording the current software version."""
        self.config.software_version_last_saved = __version__
        write_config(self.config, self.config_path)

    @classmethod
    def migrate(cls, path: Path) -> MigrationReport:
        """Bring the project to the current schema, after a backup copy."""
        project = cls.open(path, check_schema=False)
        found = project.config.schema_version
        if found > SCHEMA_VERSION:
            raise ProjectError("project.schema_too_new", found=found, supported=SCHEMA_VERSION)
        steps = pending(found, SCHEMA_VERSION)
        if not steps:
            return MigrationReport(found, found, None)
        backup = backup_project(project.root, (PROJECT_FILE, GPKG_FILE), found)
        for version in steps:
            MIGRATIONS[version](project.root)
            project.config.schema_version = version + 1
            project.save()
            _log_change(project.gpkg_path, "migrate", f"schema {version} -> {version + 1}")
        return MigrationReport(found, SCHEMA_VERSION, backup, steps)

    # --- inspection ---------------------------------------------------------------

    def content_hashes(self) -> dict[str, str]:
        hashes = {PROJECT_FILE: hashing.settings_hash(self.config.model_dump(mode="json"))}
        hashes |= hashing.gpkg_hashes(self.gpkg_path)
        hashes |= hashing.raster_hashes(self.root)
        return hashes

    def summary(self) -> dict[str, Any]:
        """Data shown by ``phrear info``."""
        cfg = self.config
        hashes = self.content_hashes()
        return {
            "name": cfg.name,
            "path": str(self.root),
            "schema_version": cfg.schema_version,
            "software_version_created": cfg.software_version_created,
            "software_version_last_saved": cfg.software_version_last_saved,
            "crs": {"epsg": cfg.crs, "name": crs_name(cfg.crs)},
            "model": {
                "start_date": cfg.model.start_date.isoformat(),
                "end_date": cfg.model.end_date.isoformat(),
                "steady_initial": cfg.model.steady_initial,
            },
            "tables": gpkg.row_counts(self.gpkg_path, TABLES),
            "content_hash": hashing.combined_hash(hashes),
        }
