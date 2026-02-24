"""Command handler for the 'upvote' command.

Upvotes a Moltbook post or comment by ID or URL.
"""

from pathlib import Path
from urllib.parse import ParseResult, unquote, urlparse

import click
from rich.console import Console

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.persistence.agent_store import load_agent_config
from automolt.services.post_service import PostService

VALID_TARGET_TYPES = ("auto", "post", "comment")
SUPPORTED_MOLTBOOK_HOSTS = {"www.moltbook.com", "moltbook.com"}
COMMENT_FRAGMENT_PREFIX = "comment-"
SUPPORTED_POST_PATH_SEGMENTS = {"post", "posts"}


@click.command("upvote")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to use. Defaults to session active agent.",
)
@click.option(
    "--type",
    "target_type",
    type=click.Choice(VALID_TARGET_TYPES),
    default="auto",
    help="Target type: auto, post, or comment.",
)
@click.argument("target")
@click.pass_context
def upvote(ctx: click.Context, handle: str | None, target_type: str, target: str) -> None:
    """Upvote a post/comment by Moltbook URL or raw ID."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    post_service: PostService = ctx.obj["post_service"]

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

    # Load agent config to get API key.
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
        console.print("[red]Agent must be claimed before upvoting.[/red]")
        ctx.exit(1)
        return

    try:
        resolved_type, resolved_id = _parse_upvote_target(target=target, target_type=target_type)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return

    response_message: str | None = None
    with console.status("Submitting upvote..."):
        try:
            response = post_service.upvote_target(config.agent.api_key, resolved_type, resolved_id)
            response_message = post_service.evaluate_upvote_response(response)
        except (MoltbookAPIError, ValueError) as exc:
            if isinstance(exc, MoltbookAPIError):
                console.print(f"[bold red]Failed to upvote:[/bold red] {exc.message}")
                if exc.hint:
                    console.print(f"[dim]Hint: {exc.hint}[/dim]")
            else:
                console.print(f"[red]{exc}[/red]")
            ctx.exit(1)
            return

    console.print()
    console.print("[bold green]Upvote accepted by API.[/bold green]")
    console.print(f"[bold]Handle:[/bold] {active_handle}")
    console.print(f"[bold]Target Type:[/bold] {resolved_type}")
    console.print(f"[bold]Target ID:[/bold] {resolved_id}")

    if response_message:
        console.print(f"[bold]Message:[/bold] {response_message}")


def _parse_upvote_target(*, target: str, target_type: str) -> tuple[str, str]:
    """Parse target input and return normalized `(target_type, target_id)` tuple."""
    normalized_target = target.strip()
    if not normalized_target:
        raise ValueError("Target cannot be empty.")

    parsed_url = _parse_target_as_url(normalized_target)
    if parsed_url is not None:
        return _parse_moltbook_url_target(parsed_url, target_type)

    if target_type in {"post", "comment"}:
        return target_type, normalized_target

    if normalized_target.lower().startswith("comment_"):
        return "comment", normalized_target

    raise ValueError("Could not infer target type from ID. Use --type post or --type comment.")


def _parse_target_as_url(target: str) -> ParseResult | None:
    """Return a parsed URL when target looks URL-like; otherwise return None."""
    candidate = target
    if "://" not in candidate:
        if candidate.startswith("www.moltbook.com/") or candidate.startswith("automolt.com/"):
            candidate = f"https://{candidate}"
        elif candidate.startswith("/"):
            candidate = f"https://www.moltbook.com{candidate}"
        elif candidate.startswith("post/") or candidate.startswith("posts/"):
            candidate = f"https://www.moltbook.com/{candidate}"
        else:
            return None

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return None

    return parsed


def _parse_moltbook_url_target(parsed_url: ParseResult, explicit_type: str) -> tuple[str, str]:
    """Parse supported Moltbook post/comment URLs into an upvote target tuple."""
    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("Unsupported URL scheme. Use http or https Moltbook URLs.")

    host = parsed_url.netloc.split("@")[-1].split(":")[0].lower()
    if host not in SUPPORTED_MOLTBOOK_HOSTS:
        raise ValueError("Only Moltbook URLs are supported for URL targets.")

    path_parts = [part for part in parsed_url.path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0] not in SUPPORTED_POST_PATH_SEGMENTS:
        raise ValueError("Unsupported Moltbook URL path. Expected /post/<post_id> or /posts/<post_id>.")

    post_id = unquote(path_parts[1]).strip()
    if not post_id:
        raise ValueError("Post URL must include a post ID.")

    fragment = unquote(parsed_url.fragment).strip()
    comment_id: str | None = None
    if fragment:
        if not fragment.startswith(COMMENT_FRAGMENT_PREFIX):
            raise ValueError("Unsupported Moltbook URL fragment. Expected #comment-<comment_id>.")

        comment_id = fragment.removeprefix(COMMENT_FRAGMENT_PREFIX).strip()
        if not comment_id:
            raise ValueError("Comment URL fragment must include a comment ID.")

    resolved_type = "comment" if comment_id else "post"
    resolved_id = comment_id if comment_id else post_id

    if explicit_type != "auto" and explicit_type != resolved_type:
        raise ValueError(f"Target URL resolves to a {resolved_type}. Use --type {resolved_type} or provide a matching target.")

    return resolved_type, resolved_id
