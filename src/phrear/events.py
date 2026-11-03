"""Events emitted by the core (docs/SPEC.md, sections 5 and 16; docs/adr/0006).

Protocol
--------
- JSON Lines: one event per line, UTF-8, ``\\n`` terminated, flushed after each line.
  The stream is binary, so the encoding does not depend on the Windows console.
- Every event carries ``schema`` (protocol version, currently ``"1"``), ``event``
  (its type) and ``time`` (UTC, ISO 8601).
- User-facing texts are carried in both languages; the client chooses.
- Quantities in field names carry their unit: ``_m``, ``_d``, ``_s``, ``_m3d``, ``_pct``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, BinaryIO, Final, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

from phrear.errors import FieldValue, ObjectRef, PhrearError, render

SCHEMA_VERSION: Final = "1"


def _now() -> datetime:
    return datetime.now(UTC)


class Text(BaseModel):
    """A user-facing text in Italian and English."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    it: str
    en: str


class Problem(BaseModel):
    """Payload of an error or warning: what happened, where, how to fix it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: Text
    hint: Text
    detail: str = ""
    ref: ObjectRef | None = None

    @classmethod
    def from_code(
        cls,
        code: str,
        fields: dict[str, FieldValue] | None = None,
        *,
        detail: str = "",
        ref: ObjectRef | None = None,
    ) -> Problem:
        values = fields or {}
        return cls(
            code=code,
            message=Text(it=render(code, "it", values), en=render(code, "en", values)),
            hint=Text(
                it=render(code, "it", values, hint=True), en=render(code, "en", values, hint=True)
            ),
            detail=detail,
            ref=ref,
        )

    @classmethod
    def from_error(cls, error: PhrearError) -> Problem:
        return cls.from_code(error.code, error.fields, detail=error.detail, ref=error.ref)


class _EventBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_: Literal["1"] = Field(default=SCHEMA_VERSION, alias="schema")
    time: AwareDatetime = Field(default_factory=_now)


# --- command life cycle -------------------------------------------------------


class CommandStarted(_EventBase):
    event: Literal["command_started"] = "command_started"
    command: str


class CommandCompleted(_EventBase):
    event: Literal["command_completed"] = "command_completed"
    command: str
    duration_s: float


class CommandFailed(_EventBase):
    event: Literal["command_failed"] = "command_failed"
    command: str
    error: Problem


class Progress(_EventBase):
    event: Literal["progress"] = "progress"
    stage: str
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    message: Text | None = None


class WarningEvent(_EventBase):
    event: Literal["warning"] = "warning"
    problem: Problem


class ErrorEvent(_EventBase):
    event: Literal["error"] = "error"
    problem: Problem


# --- simulation run (section 16) ----------------------------------------------


class RunStarted(_EventBase):
    event: Literal["run_started"] = "run_started"
    run_id: str
    engine_version: str


class PeriodStarted(_EventBase):
    event: Literal["period_started"] = "period_started"
    run_id: str
    period: int = Field(ge=1)
    start_date: datetime


class TimestepCompleted(_EventBase):
    event: Literal["timestep_completed"] = "timestep_completed"
    run_id: str
    period: int = Field(ge=1)
    step: int = Field(ge=1)
    time_d: float
    iterations: int = Field(ge=0)
    max_head_change_m: float
    budget_error_pct: float


class SnapshotWritten(_EventBase):
    event: Literal["snapshot_written"] = "snapshot_written"
    run_id: str
    period: int = Field(ge=1)
    step: int = Field(ge=1)
    path: str


class FlowReduced(_EventBase):
    event: Literal["flow_reduced"] = "flow_reduced"
    run_id: str
    period: int = Field(ge=1)
    step: int = Field(ge=1)
    well: ObjectRef
    design_rate_m3d: float
    actual_rate_m3d: float


class RunCompleted(_EventBase):
    event: Literal["run_completed"] = "run_completed"
    run_id: str
    duration_s: float


class RunFailed(_EventBase):
    event: Literal["run_failed"] = "run_failed"
    run_id: str
    error: Problem


AnyEvent = (
    CommandStarted
    | CommandCompleted
    | CommandFailed
    | Progress
    | WarningEvent
    | ErrorEvent
    | RunStarted
    | PeriodStarted
    | TimestepCompleted
    | SnapshotWritten
    | FlowReduced
    | RunCompleted
    | RunFailed
)
Event = Annotated[AnyEvent, Field(discriminator="event")]
EVENT_ADAPTER: TypeAdapter[AnyEvent] = TypeAdapter(Event)


def dump_event(event: AnyEvent) -> bytes:
    """Serialise one event as a UTF-8 JSON line (without the newline)."""
    return event.model_dump_json(by_alias=True).encode("utf-8")


def parse_event(line: str | bytes) -> AnyEvent:
    """Parse one JSON line into the matching event model."""
    return EVENT_ADAPTER.validate_json(line)


def event_json_schema() -> dict[str, Any]:
    """JSON Schema of protocol version 1, for clients such as the QGIS plugin."""
    return EVENT_ADAPTER.json_schema(by_alias=True)


class EventSink(Protocol):
    """Destination of events."""

    def emit(self, event: AnyEvent) -> None: ...


class JsonLinesSink:
    """Writes events as UTF-8 JSON Lines on a binary stream, flushing each line."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream

    def emit(self, event: AnyEvent) -> None:
        self._stream.write(dump_event(event) + b"\n")
        self._stream.flush()


class MemorySink:
    """Keeps events in memory; used by tests and by in-process callers."""

    def __init__(self) -> None:
        self.events: list[AnyEvent] = []

    def emit(self, event: AnyEvent) -> None:
        self.events.append(event)
