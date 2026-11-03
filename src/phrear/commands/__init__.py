"""Subcommands of the CLI, collected in :data:`COMMANDS` (docs/SPEC.md, section 5)."""

from phrear.commands import (
    bc_commands,
    check_commands,
    grid_commands,
    params_commands,
    project_commands,
    results_commands,
    run_commands,
    time_commands,
)
from phrear.commands.base import CommandSpec, Configure, Context, Handler

#: Registered subcommands, in the order shown by ``--help``.
COMMANDS: list[CommandSpec] = [
    *project_commands.COMMANDS,
    *time_commands.COMMANDS,
    *grid_commands.COMMANDS,
    *params_commands.COMMANDS,
    *bc_commands.COMMANDS,
    *check_commands.COMMANDS,
    *run_commands.COMMANDS,
    *results_commands.COMMANDS,
]

__all__ = ["COMMANDS", "CommandSpec", "Configure", "Context", "Handler"]
