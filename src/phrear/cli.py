"""Command line interface of the Phrear core.

Subcommands (new, check, grid, build, run, ...) are added milestone by milestone,
following docs/SPEC.md, section 5.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from phrear import __version__


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="phrear",
        description="Groundwater modelling platform built on MODFLOW 6.",
    )
    parser.add_argument("--version", action="version", version=f"phrear {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
