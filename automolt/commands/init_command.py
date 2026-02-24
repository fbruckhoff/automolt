"""Command handler for the 'init' command.

Initializes the automolt client directory by creating the .agents/ folder,
the .sessions/ folder, and client.json configuration file.
"""

from pathlib import Path

import click
from rich.console import Console

from automolt.models.client import ClientConfig
from automolt.persistence import system_prompt_store
from automolt.persistence.client_store import save_client_config

CLIENT_CONFIG_FILENAME = "client.json"
AGENTS_DIR_NAME = ".agents"
SESSIONS_DIR_NAME = ".sessions"

DEFAULT_CLIENT_CONFIG = ClientConfig()


@click.command("init")
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new Automolt client in the current directory."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]

    console.print()
    console.print(f"[bold]Initialize Automolt client in:[/bold] {base_path}")
    console.print()

    if not click.confirm("Is this the directory where you want to initialize your client?"):
        console.print()
        console.print("[yellow]Initialization cancelled.[/yellow] Please cd into your desired client directory and run [bold]automolt init[/bold] again.")
        return

    # Check if already initialized
    client_config_path = base_path / CLIENT_CONFIG_FILENAME
    agents_dir = base_path / AGENTS_DIR_NAME
    sessions_dir = base_path / SESSIONS_DIR_NAME

    if client_config_path.exists():
        ensured_system_prompt_paths = system_prompt_store.ensure_system_prompt_files(base_path)
        console.print()
        console.print("[yellow]This directory is already initialized as a Automolt client.[/yellow]")
        console.print("[dim]Verified required client-root system prompt files:[/dim]")
        for system_prompt_path in ensured_system_prompt_paths:
            console.print(f"  [cyan]{system_prompt_path.name}[/cyan]")
        return

    # Create .agents/ and .sessions/ directories
    agents_dir.mkdir(exist_ok=True)
    sessions_dir.mkdir(exist_ok=True)

    # Create client.json and required system prompt files
    save_client_config(base_path, DEFAULT_CLIENT_CONFIG)
    created_system_prompt_paths = system_prompt_store.ensure_system_prompt_files(base_path)

    console.print()
    console.print("[bold green]Automolt client initialized successfully![/bold green]")
    console.print(f"  Created [cyan]{AGENTS_DIR_NAME}/[/cyan] directory")
    console.print(f"  Created [cyan]{SESSIONS_DIR_NAME}/[/cyan] directory")
    console.print(f"  Created [cyan]{CLIENT_CONFIG_FILENAME}[/cyan]")
    for system_prompt_path in created_system_prompt_paths:
        console.print(f"  Created [cyan]{system_prompt_path.name}[/cyan]")
    console.print()
    console.print("Run [bold]automolt signup[/bold] to register a new agent.")
