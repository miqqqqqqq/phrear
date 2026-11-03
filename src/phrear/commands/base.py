"""Building blocks shared by the CLI subcommands."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TextIO

from phrear.errors import Lang
from phrear.events import EventSink, Problem, Result, WarningEvent


@dataclass(frozen=True)
class Context:
    """What a command needs to report its output."""

    sink: EventSink | None
    """Event destination in ``--json`` mode, otherwise ``None``."""
    lang: Lang
    out: TextIO
    """Human-readable output (text mode only)."""

    def result(self, command: str, data: dict[str, Any], text: str) -> None:
        """Report the structured result of a command: an event, or ``text``."""
        if self.sink is not None:
            self.sink.emit(Result(command=command, data=data))
        else:
            self.out.write(text if text.endswith("\n") else text + "\n")

    def warn(self, problem: Problem) -> None:
        """Report a warning: an event, or a line of text."""
        if self.sink is not None:
            self.sink.emit(WarningEvent(problem=problem))
            return
        label = "Avviso" if self.lang == "it" else "Warning"
        message = problem.message.it if self.lang == "it" else problem.message.en
        hint = problem.hint.it if self.lang == "it" else problem.hint.en
        self.out.write(f"{label} [{problem.code}]: {message}\n")
        if hint:
            self.out.write(f"  {hint}\n")


Handler = Callable[[argparse.Namespace, Context], int]
Configure = Callable[[argparse.ArgumentParser], None]


@dataclass(frozen=True)
class CommandSpec:
    """A subcommand: name, one-line help, argument setup and handler."""

    name: str
    help_text: str
    configure: Configure
    handler: Handler
