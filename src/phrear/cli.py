"""Command line interface of the Phrear core (docs/SPEC.md, section 5).

Subcommands (new, check, grid, build, run, ...) are added milestone by milestone.

Global options
--------------
``--json``
    Write the output as JSON Lines events on stdout (docs/adr/0006). Usage errors
    and failures are events too, so a client never has to parse free text.
``--lang {it,en}``
    Language of the human-readable output. JSON events carry both languages.

Exit codes
----------
0 success; 1 error in the input or the project; 2 invalid command line;
3 internal error.
"""

from __future__ import annotations

import argparse
import itertools
import sys
import time
import traceback
from collections.abc import Sequence
from typing import BinaryIO, NoReturn, TextIO

from phrear import __version__
from phrear.commands import COMMANDS, CommandSpec, Context, Handler
from phrear.errors import InternalError, Lang, PhrearError, UsageError
from phrear.events import (
    CommandCompleted,
    CommandFailed,
    CommandStarted,
    ErrorEvent,
    EventSink,
    JsonLinesSink,
    Problem,
)

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

__all__ = ["COMMANDS", "CommandSpec", "Context", "Handler", "build_parser", "main", "run_command"]


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that raises instead of printing and exiting on errors."""

    def error(self, message: str) -> NoReturn:
        raise UsageError("cli.usage", reason=message)


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""
    parser = _Parser(
        prog="phrear",
        description="Groundwater modelling platform built on MODFLOW 6.",
    )
    parser.add_argument("--version", action="version", version=f"phrear {__version__}")
    parser.add_argument(
        "--json", action="store_true", help="write the output as JSON Lines events on stdout"
    )
    parser.add_argument(
        "--lang", choices=["it", "en"], default="it", help="language of the text output"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for spec in COMMANDS:
        spec.configure(subparsers.add_parser(spec.name, help=spec.help_text))
    return parser


def run_command(command: str, handler: Handler, args: argparse.Namespace, ctx: Context) -> int:
    """Run a subcommand handler, wrapping it in command_started/completed events."""
    sink = ctx.sink
    if sink is not None:
        sink.emit(CommandStarted(command=command))
    start = time.perf_counter()
    code = handler(args, ctx)
    if sink is not None:
        sink.emit(CommandCompleted(command=command, duration_s=time.perf_counter() - start))
    return code


def _report(
    error: PhrearError,
    sink: EventSink | None,
    lang: Lang,
    stderr: TextIO,
    command: str | None,
) -> None:
    if sink is not None:
        problem = Problem.from_error(error)
        if command is None:
            sink.emit(ErrorEvent(problem=problem))
        else:
            sink.emit(CommandFailed(command=command, error=problem))
        return
    label = "Errore" if lang == "it" else "Error"
    stderr.write(f"{label} [{error.code}]: {error.message(lang)}\n")
    hint = error.hint(lang)
    if hint:
        stderr.write(f"{hint}\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: BinaryIO | None = None,
    stderr: TextIO | None = None,
    text_stdout: TextIO | None = None,
) -> int:
    """Run the CLI and return the process exit code.

    ``stdout`` receives JSON events (binary); ``text_stdout`` the text output.
    """
    args_list = list(sys.argv[1:] if argv is None else argv)
    out = sys.stdout.buffer if stdout is None else stdout
    text_out = _tolerant(sys.stdout) if text_stdout is None else text_stdout
    err_stream = _tolerant(sys.stderr) if stderr is None else stderr
    # The output mode must be known before parsing, so that usage errors
    # are reported in the right format.
    sink: EventSink | None = JsonLinesSink(out) if "--json" in args_list else None
    lang: Lang = "en" if "--lang=en" in args_list or _follows(args_list, "--lang", "en") else "it"

    parser = build_parser()
    command: str | None = None
    try:
        args = parser.parse_args(args_list)
        command = args.command
        if command is None:
            if sink is None:
                parser.print_help()
            return EXIT_OK
        handler = {spec.name: spec.handler for spec in COMMANDS}[command]
        ctx = Context(sink=sink, lang=lang, out=text_out)
        return run_command(command, handler, args, ctx)
    except UsageError as error:
        _report(error, sink, lang, err_stream, command)
        return EXIT_USAGE
    except PhrearError as error:
        _report(error, sink, lang, err_stream, command)
        return EXIT_INPUT_ERROR
    except Exception:
        internal = InternalError("internal.unexpected", detail=traceback.format_exc())
        _report(internal, sink, lang, err_stream, command)
        return EXIT_INTERNAL


def _tolerant(stream: TextIO) -> TextIO:
    """Avoid UnicodeEncodeError when a redirected Windows console uses cp1252."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
    return stream


def _follows(args: list[str], option: str, value: str) -> bool:
    return any(a == option and b == value for a, b in itertools.pairwise(args))


if __name__ == "__main__":
    raise SystemExit(main())
