"""Environment command: env, the versions the core runs with (used by the plugin)."""

from __future__ import annotations

import argparse
import platform
import sys
from importlib.metadata import version
from typing import Any

import phrear
from phrear.commands.base import CommandSpec, Context
from phrear.errors import PhrearError
from phrear.events import SCHEMA_VERSION, Problem
from phrear.modflow.engine import engine_version, mf6_executable


def _data(ctx: Context) -> dict[str, Any]:
    import pyogrio
    import pyproj

    data: dict[str, Any] = {
        "phrear": phrear.__version__,
        "event_schema": SCHEMA_VERSION,
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "flopy": version("flopy"),
        "gdal": pyogrio.__gdal_version_string__,
        "proj": pyproj.proj_version_str,
        "mf6": None,
    }
    try:
        exe = mf6_executable()
        data["mf6"] = {"version": engine_version(exe), "executable": str(exe)}
    except PhrearError as exc:
        ctx.warn(Problem.from_error(exc))
    return data


def _text(data: dict[str, Any], lang: str) -> str:
    mf6 = data["mf6"]
    engine = f"{mf6['version']} ({mf6['executable']})" if mf6 else "-"
    rows = [
        ("phrear", data["phrear"]),
        ("MODFLOW 6", engine),
        ("Python", f"{data['python']} ({data['executable']})"),
        ("FloPy", data["flopy"]),
        ("GDAL", data["gdal"]),
        ("PROJ", data["proj"]),
        ("Sistema" if lang == "it" else "System", data["platform"]),
    ]
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k.ljust(width)}  {v}" for k, v in rows)


def _configure(parser: argparse.ArgumentParser) -> None:
    del parser


def _env(args: argparse.Namespace, ctx: Context) -> int:
    del args
    data = _data(ctx)
    ctx.result("env", data, _text(data, ctx.lang))
    return 0


COMMANDS = [CommandSpec("env", "versions of phrear, MODFLOW 6 and libraries", _configure, _env)]
