"""Packaging and development install of the QGIS plugin.

    pixi run plugin-zip     dist/phrear_qgis-<version>.zip, for "Install from ZIP"
    pixi run plugin-link    link the plugin folder into the QGIS 4 profile

The link is a directory junction on Windows (no administrator rights needed) and
a symbolic link elsewhere, so QGIS loads the plugin straight from the repository.
An existing folder or link with the same name is never replaced.
"""

from __future__ import annotations

import argparse
import configparser
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "qgis_plugin" / "phrear_qgis"
NAME = PLUGIN.name
EXCLUDED_SUFFIXES = {".pyc", ".ts"}


def version(plugin: Path = PLUGIN) -> str:
    parser = configparser.ConfigParser()
    parser.read(plugin / "metadata.txt", encoding="utf-8")
    return parser["general"]["version"]


def plugin_files(plugin: Path = PLUGIN) -> list[Path]:
    return sorted(
        p
        for p in plugin.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in EXCLUDED_SUFFIXES
    )


def build_zip(target_dir: Path, plugin: Path = PLUGIN) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{NAME}-{version(plugin)}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in plugin_files(plugin):
            archive.write(path, f"{NAME}/{path.relative_to(plugin).as_posix()}")
    return target


def profile_plugins_dir() -> Path:
    """python/plugins of the default QGIS 4 profile (QGIS 3 as a fallback)."""
    if sys.platform == "win32":
        base = Path(os.environ["APPDATA"]) / "QGIS"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "QGIS"
    else:
        base = Path.home() / ".local" / "share" / "QGIS"
    for version_dir in ("QGIS4", "QGIS3"):
        profile = base / version_dir / "profiles" / "default"
        if profile.is_dir():
            return profile / "python" / "plugins"
    raise SystemExit(
        f"No QGIS profile found under {base}. Start QGIS once, or pass --plugins-dir "
        "(QGIS: Settings > User Profiles > Open Active Profile Folder, then python/plugins)."
    )


def link(plugins_dir: Path, plugin: Path = PLUGIN) -> Path:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    target = plugins_dir / NAME
    if target.exists() or target.is_symlink():
        if os.path.realpath(target) == os.path.realpath(plugin):
            return target
        raise SystemExit(f"{target} already exists and is not this plugin: move it away first")
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(plugin), str(target))
    else:
        target.symlink_to(plugin, target_is_directory=True)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    zip_parser = sub.add_parser("zip", help="build the plugin ZIP")
    zip_parser.add_argument("--output", type=Path, default=REPO / "dist")
    link_parser = sub.add_parser("link", help="link the plugin into the QGIS profile")
    link_parser.add_argument("--plugins-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.action == "zip":
        print(build_zip(args.output))
    else:
        target = link(args.plugins_dir or profile_plugins_dir())
        print(f"{target} -> {PLUGIN}")
        print("Restart QGIS and enable Phrear in Plugins > Manage and Install Plugins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
