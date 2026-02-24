"""Command handler for the 'search' command.

Performs semantic search across Moltbook posts and comments.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.persistence.agent_store import load_agent_config
from automolt.services.search_service import SearchService

DEFAULT_MAX_CHARS = 50000
MARK_TAG_PATTERN = re.compile(r"</?mark>")
RESULT_SEPARATOR = "------"
VALID_SEARCH_TYPES = ("posts", "comments", "all")
VALID_SORT_TYPES = ("date", "relevance")


def _format_created_at(iso_timestamp: str) -> str:
    """Format an ISO 8601 timestamp for search result display.

    Returns a string like: 2025-06-15, 14:30 (3 days ago)
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        formatted = local_dt.strftime("%Y-%m-%d, %H:%M")

        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days

        if days == 0:
            age = "today"
        elif days == 1:
            age = "1 day ago"
        else:
            age = f"{days} days ago"

        return f"{formatted} ({age})"
    except ValueError, TypeError:
        return iso_timestamp


def _strip_mark_tags(text: str) -> str:
    """Remove <mark> and </mark> HTML tags from text."""
    return MARK_TAG_PATTERN.sub("", text)


@click.command("search")
@click.argument("query")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.option("--type", "search_type", type=click.Choice(VALID_SEARCH_TYPES), default="all", help="What to search: posts, comments, or all.")
@click.option("--limit", default=50, type=click.IntRange(1, 50), help="Max results (1-50, default 50).")
@click.option("--fetch-full-text", is_flag=True, default=False, help="Fetch full post/comment text for each result. Makes one extra API call per result.")
@click.option("--max-chars", default=DEFAULT_MAX_CHARS, type=click.IntRange(min=1), help=f"Max characters for full content display (default {DEFAULT_MAX_CHARS}). Only applies with --fetch-full-text.")
@click.option("--sort", "sort_type", type=click.Choice(VALID_SORT_TYPES), default="date", help="Sort results: date (newest first) or relevance.")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    handle: str | None,
    search_type: str,
    limit: int,
    fetch_full_text: bool,
    max_chars: int,
    sort_type: str,
) -> None:
    """Semantic search across Moltbook posts and comments.

    QUERY is a natural language search string (max 500 chars).
    """
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    search_service: SearchService = ctx.obj["search_service"]

    # Resolve command target handle using session-aware semantics.
    try:
        active_handle = resolve_target_handle(base_path, handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    if not active_handle:
        console.print(f"[yellow]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/yellow]")
        return

    # Load agent config to get API key
    try:
        config = load_agent_config(base_path, active_handle)
    except FileNotFoundError:
        console.print(f"[red]Agent '{active_handle}' not found locally.[/red]")
        ctx.exit(1)
        return
    except ValueError:
        console.print(f"[red]Agent config for '{active_handle}' is corrupted.[/red]")
        ctx.exit(1)
        return

    if not config.agent.api_key:
        console.print("[red]Agent must be claimed before searching.[/red]")
        ctx.exit(1)
        return

    # Perform semantic search
    with console.status("Searching..."):
        try:
            response = search_service.search(config.agent.api_key, query, search_type, limit)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            ctx.exit(1)
            return
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Search failed:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    if response.count == 0:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print(f"[dim]Found {response.count} result(s) for:[/dim] {response.query}")
    console.print()

    # Sort results if requested (default is date sorting)
    if sort_type == "date":
        response.results.sort(key=lambda r: datetime.fromisoformat(r.created_at.replace("Z", "+00:00")) if r.created_at else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    # "relevance" uses API default ordering, so no sorting needed

    # Optionally fetch full text for all results up front
    full_texts: dict[str, str | None] = {}
    if fetch_full_text:
        with console.status(f"Fetching full text for {response.count} result(s)..."):
            for result in response.results:
                full_texts[result.id] = search_service.get_full_content(config.agent.api_key, result)

    for i, result in enumerate(response.results):
        console.print(f"[bold]ID:[/bold] [bright_black]{result.id}[/bright_black]")

        if result.title:
            console.print(f"[bold]Title:[/bold] {result.title}")

        if result.created_at:
            console.print(f"[bold]Date:[/bold] {_format_created_at(result.created_at)}")

        excerpt = _strip_mark_tags(result.content)
        console.print(f"[bold]Excerpt:[/bold] {excerpt}")

        if fetch_full_text:
            full_content = full_texts.get(result.id)
            if full_content is not None:
                if len(full_content) > max_chars:
                    full_content = full_content[:max_chars] + "..."
                console.print(f"[bold]Content:[/bold] {full_content}")
            else:
                console.print("[bold]Content:[/bold] [dim]Could not retrieve full text.[/dim]")

        if i < len(response.results) - 1:
            console.print(RESULT_SEPARATOR)
