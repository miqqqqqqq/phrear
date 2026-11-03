"""Subcommands of the CLI, collected in :data:`COMMANDS` (docs/SPEC.md, section 5)."""

from phrear.commands import project_commands, time_commands
from phrear.commands.base import CommandSpec, Configure, Context, Handler

#: Registered subcommands, in the order shown by ``--help``.
COMMANDS: list[CommandSpec] = [*project_commands.COMMANDS, *time_commands.COMMANDS]

__all__ = ["COMMANDS", "CommandSpec", "Configure", "Context", "Handler"]
