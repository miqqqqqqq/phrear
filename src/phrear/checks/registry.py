"""Registry of the model checks."""

from __future__ import annotations

from phrear.checks import model_checks
from phrear.checks.base import Check

#: Registered checks, in the order they run.
CHECKS: dict[str, Check] = {c.name: c for c in model_checks.CHECKS}


def register(check: Check) -> None:
    """Add a check (used by later milestones and extensions)."""
    if check.name in CHECKS:
        raise ValueError(f"check {check.name!r} already registered")
    CHECKS[check.name] = check
