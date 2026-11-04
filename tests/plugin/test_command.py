"""Command line and environment of the core as started by the plugin."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import plugin_package
from phrear_qgis.client.command import (
    CoreLocation,
    clean_environment,
    core_command,
    default_core_dir,
    find_pixi,
    is_core_dir,
    location_problems,
)
from phrear_qgis.client.events import EventStream, collect

from .conftest import PLUGIN, REPO


def test_qgis_variables_are_removed_whatever_their_case() -> None:
    env = {"PYTHONHOME": "q", "pythonpath": "q", "GDAL_DATA": "q", "Proj_Lib": "q", "HOME": "h"}
    assert clean_environment(env) == {"HOME": "h"}


def test_qgis_folders_leave_path(tmp_path: Path) -> None:
    qgis = tmp_path / "QGIS 4.2"
    keep = tmp_path / "Windows" / "system32"
    for folder in (qgis / "bin", qgis / "apps" / "qgis" / "bin", keep):
        folder.mkdir(parents=True)
    path = os.pathsep.join([str(qgis / "bin"), str(keep), str(qgis / "apps" / "qgis" / "bin")])
    cleaned = clean_environment({"PATH": path, "X": "1"}, [qgis])
    assert cleaned == {"PATH": str(keep), "X": "1"}


def test_pixi_on_path_or_in_its_default_folder(tmp_path: Path) -> None:
    on_path = tmp_path / "bin"
    on_path.mkdir()
    exe = on_path / ("pixi.exe" if sys.platform == "win32" else "pixi")
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    assert find_pixi({"PATH": str(on_path)}, tmp_path / "home") == exe
    home = tmp_path / "home"
    default = home / ".pixi" / "bin" / "pixi.exe"
    default.parent.mkdir(parents=True)
    default.write_text("", encoding="utf-8")
    assert find_pixi({"PATH": ""}, home) == default
    assert find_pixi({"PATH": ""}, tmp_path / "nobody") is None


def test_the_repository_is_found_from_the_plugin_folder(tmp_path: Path) -> None:
    assert default_core_dir(PLUGIN) == REPO
    link = plugin_package.link(tmp_path / "plugins")  # junction on Windows, symlink elsewhere
    assert default_core_dir(link) == REPO  # installed with the development link
    assert default_core_dir(tmp_path) is None
    assert is_core_dir(REPO) and not is_core_dir(tmp_path)


def test_location_problems(tmp_path: Path) -> None:
    pixi = tmp_path / "pixi"
    pixi.write_text("", encoding="utf-8")
    assert location_problems(CoreLocation(REPO, pixi)) == []
    assert location_problems(CoreLocation(tmp_path, tmp_path / "none")) == [
        "pixi_missing",
        "core_dir_invalid",
    ]


def test_core_command() -> None:
    command = core_command(CoreLocation(REPO, Path("pixi")), ["check", "C:/p"], "it")
    assert command == [
        "pixi", "run", "--manifest-path", str(REPO / "pixi.toml"), "--frozen",
        "phrear", "--json", "--lang", "it", "check", "C:/p",
    ]  # fmt: skip
    assert core_command(CoreLocation(REPO, Path("pixi")), ["env"], "de")[8] == "en"


@pytest.mark.engine
def test_the_core_answers_through_pixi_with_a_clean_environment() -> None:
    pixi = find_pixi(os.environ, Path.home())
    if pixi is None:
        pytest.skip("pixi not on PATH")
    location = CoreLocation(REPO, pixi)
    environment = clean_environment({**os.environ, "PYTHONPATH": "/broken", "GDAL_DATA": "/x"})
    completed = subprocess.run(
        core_command(location, ["env"], "en"),
        capture_output=True,
        env=environment,
        cwd=REPO,
        check=False,
        timeout=300,
    )
    stream = EventStream()
    events = stream.feed(completed.stdout) + stream.finish()
    outcome = collect("env", events, completed.returncode, stream, completed.stderr.decode())
    assert outcome.ok, outcome.output
    assert outcome.result is not None and outcome.result["mf6"]["version"] == "6.8.1"
