"""Command line of the core, and the environment it runs in.

The plugin runs the core with ``pixi run`` in the environment of the phrear
repository, which activates GDAL, PROJ and MODFLOW 6 of that environment. QGIS
sets variables for its own Python and GDAL (PYTHONHOME, PYTHONPATH, GDAL_DATA,
PROJ_LIB, ...) and puts its folders on PATH: inherited by the core, they would
make its Python load the wrong libraries, so they are removed before the start.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

MANIFEST = "pixi.toml"

#: Variables set by QGIS (and OSGeo4W) for its own Python, Qt and GDAL.
QGIS_VARIABLES = frozenset(
    {
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
        "PYTHONNOUSERSITE",
        "GDAL_DATA",
        "GDAL_DRIVER_PATH",
        "GDAL_FILENAME_IS_UTF8",
        "PROJ_LIB",
        "PROJ_DATA",
        "PROJ_NETWORK",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QGIS_PREFIX_PATH",
        "QGIS_PLUGINPATH",
        "OSGEO4W_ROOT",
        "O4W_QT_PREFIX",
        "O4W_QT_BIN",
        "O4W_QT_PLUGINS",
        "O4W_QT_TRANSLATIONS",
        "O4W_QT_HEADERS",
        "O4W_QT_DOC",
        "VSI_CACHE",
        "VSI_CACHE_SIZE",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "CONDA_SHLVL",
        "PIXI_PROJECT_ROOT",
        "PIXI_ENVIRONMENT_NAME",
    }
)


@dataclass(frozen=True)
class CoreLocation:
    """Where the core is: the phrear repository and the pixi executable."""

    core_dir: Path
    pixi: Path

    @property
    def manifest(self) -> Path:
        return self.core_dir / MANIFEST


def _inside(path: str, roots: Sequence[Path]) -> bool:
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return False
    return any(resolved == root or root in resolved.parents for root in roots)


def clean_environment(
    environment: Mapping[str, str], qgis_roots: Sequence[str | Path] = ()
) -> dict[str, str]:
    """The environment for the core: QGIS variables removed, QGIS folders off PATH.

    Names are compared without case, as Windows does.
    """
    roots = [Path(r).resolve() for r in qgis_roots if r]
    cleaned: dict[str, str] = {}
    for name, value in environment.items():
        if name.upper() in QGIS_VARIABLES:
            continue
        if name.upper() == "PATH" and roots:
            parts = [p for p in value.split(os.pathsep) if p and not _inside(p, roots)]
            value = os.pathsep.join(parts)
        cleaned[name] = value
    return cleaned


def find_pixi(environment: Mapping[str, str], home: Path) -> Path | None:
    """pixi on PATH, or in its default install folder ~/.pixi/bin."""
    path = next((v for k, v in environment.items() if k.upper() == "PATH"), "")
    for name in ("pixi.exe", "pixi"):
        found = shutil.which(name, path=path)
        if found:
            return Path(found)
    for candidate in (home / ".pixi" / "bin" / "pixi.exe", home / ".pixi" / "bin" / "pixi"):
        if candidate.is_file():
            return candidate
    return None


def is_core_dir(folder: Path) -> bool:
    return (folder / MANIFEST).is_file() and (folder / "src" / "phrear" / "__init__.py").is_file()


def default_core_dir(plugin_dir: Path) -> Path | None:
    """The repository the plugin folder belongs to, when installed with the dev link."""
    real = Path(os.path.realpath(plugin_dir))
    for candidate in (real.parent.parent, real.parent):
        if is_core_dir(candidate):
            return candidate
    return None


def location_problems(location: CoreLocation) -> list[str]:
    """Keys of the messages that explain why the location cannot work."""
    problems: list[str] = []
    if not location.pixi.is_file():
        problems.append("pixi_missing")
    if not is_core_dir(location.core_dir):
        problems.append("core_dir_invalid")
    return problems


def core_command(location: CoreLocation, args: Sequence[str], lang: str) -> list[str]:
    """Program and arguments that run ``phrear --json --lang <lang> <args>``."""
    return [
        str(location.pixi),
        "run",
        "--manifest-path",
        str(location.manifest),
        "--frozen",
        "phrear",
        "--json",
        "--lang",
        "it" if lang == "it" else "en",
        *args,
    ]
