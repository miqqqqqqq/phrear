"""Events of the core read from its output, and the outcome of a command.

The core writes one JSON object per line in UTF-8 (protocol version 1, ADR 0006
of the core). Output arrives in chunks that may split lines; lines that are not
JSON (for example from pixi) are kept as text for the log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "1"
EXIT_OK, EXIT_INPUT, EXIT_USAGE, EXIT_INTERNAL = 0, 1, 2, 3


class EventStream:
    """Splits the bytes of stdout into events."""

    def __init__(self) -> None:
        self._buffer = b""
        self.text: list[str] = []
        """Lines that are not events."""
        self.wrong_schema: set[str] = set()

    def _parse(self, line: bytes) -> dict[str, Any] | None:
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            self.text.append(text)
            return None
        if not isinstance(event, dict) or "event" not in event:
            self.text.append(text)
            return None
        if event.get("schema") != SCHEMA:
            self.wrong_schema.add(str(event.get("schema")))
        return event

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        self._buffer += chunk
        *lines, self._buffer = self._buffer.split(b"\n")
        return [e for e in (self._parse(line) for line in lines) if e is not None]

    def finish(self) -> list[dict[str, Any]]:
        rest, self._buffer = self._buffer, b""
        event = self._parse(rest)
        return [event] if event is not None else []


@dataclass
class Outcome:
    command: str
    exit_code: int | None
    """None when the process did not start or was cancelled."""
    result: dict[str, Any] | None = None
    """``data`` of the result event."""
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    failure: dict[str, Any] | None = None
    """Problem of command_failed."""
    output: str = ""
    """Text from stderr and non-event lines, for the log."""
    cancelled: bool = False
    start_error: str | None = None
    wrong_schema: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK and not self.cancelled and not self.wrong_schema

    def failure_text(self, lang: str) -> str:
        """The message of the failure, in the language of the interface."""
        if self.failure is None:
            return ""
        message = self.failure.get("message", {})
        hint = self.failure.get("hint", {})
        parts = [message.get(lang) or message.get("en", ""), hint.get(lang) or hint.get("en", "")]
        return "\n".join(p for p in parts if p)


def collect(
    command: str,
    events: list[dict[str, Any]],
    exit_code: int | None,
    stream: EventStream,
    stderr: str = "",
    *,
    cancelled: bool = False,
    start_error: str | None = None,
) -> Outcome:
    outcome = Outcome(
        command=command,
        exit_code=exit_code,
        cancelled=cancelled,
        start_error=start_error,
        wrong_schema=tuple(sorted(stream.wrong_schema)),
    )
    for event in events:
        kind = event.get("event")
        if kind == "result":
            outcome.result = event.get("data")
        elif kind == "warning":
            outcome.warnings.append(event.get("problem", {}))
        elif kind == "error":
            outcome.errors.append(event.get("problem", {}))
        elif kind in ("command_failed", "run_failed"):
            outcome.failure = event.get("error")
    outcome.output = "\n".join([*stream.text, stderr.strip()]).strip()
    return outcome
