"""Command handler for the 'automation' command group.

Provides subcommands for configuring and managing automation.
"""

from __future__ import annotations

import click

from automolt.commands.automation.list_command import list_command
from automolt.commands.automation.reload_command import reload_command
from automolt.commands.automation.scheduler_command import monitor, start, status, stop, tick
from automolt.commands.automation.setup_command import setup


@click.group("automation")
def automation() -> None:
    """Configure and manage automation for one target agent."""


automation.add_command(setup)
automation.add_command(list_command)
automation.add_command(reload_command)
automation.add_command(tick)
automation.add_command(start)
automation.add_command(stop)
automation.add_command(status)
automation.add_command(monitor)
