"""CLI command router. Defines the main Click group, sets up shared context."""

from pathlib import Path

import click
from rich.console import Console

from automolt.api.client import MoltbookClient
from automolt.commands.agents_command import agents
from automolt.commands.automation.automation_command import automation
from automolt.commands.comment_command import comment
from automolt.commands.init_command import init
from automolt.commands.profile.profile_command import profile
from automolt.commands.search_command import search
from automolt.commands.signup_command import signup
from automolt.commands.submolts.submolt_command import submolt
from automolt.commands.upvote_command import upvote
from automolt.models.client import ClientConfig
from automolt.persistence.client_store import load_client_config
from automolt.services.agent_service import AgentService
from automolt.services.automation_service import AutomationService
from automolt.services.llm_provider_service import LLMProviderService
from automolt.services.post_service import PostService
from automolt.services.scheduler_service import SchedulerService
from automolt.services.search_service import SearchService
from automolt.services.submolt_service import SubmoltService


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Automolt CLI — interact with the Moltbook social network for AI agents"""
    ctx.ensure_object(dict)

    console = Console()
    base_path = Path.cwd()

    # Load client configuration for timeout settings
    try:
        client_config = load_client_config(base_path)
        timeout = client_config.api_timeout_seconds
    except FileNotFoundError:
        # Use default timeout if client.json doesn't exist
        client_config = ClientConfig()
        timeout = client_config.api_timeout_seconds

    api_client = MoltbookClient(timeout=timeout)
    agent_service = AgentService(api_client=api_client, base_path=base_path)

    automation_service = AutomationService(api_client=api_client, base_path=base_path)
    llm_provider_service = LLMProviderService()
    scheduler_service = SchedulerService(automation_service=automation_service, base_path=base_path)
    submolt_service = SubmoltService(api_client=api_client)
    search_service = SearchService(api_client=api_client)
    post_service = PostService(api_client=api_client)

    ctx.obj["console"] = console
    ctx.obj["base_path"] = base_path
    ctx.obj["api_client"] = api_client
    ctx.obj["agent_service"] = agent_service
    ctx.obj["automation_service"] = automation_service
    ctx.obj["llm_provider_service"] = llm_provider_service
    ctx.obj["scheduler_service"] = scheduler_service
    ctx.obj["submolt_service"] = submolt_service
    ctx.obj["search_service"] = search_service
    ctx.obj["post_service"] = post_service

    # Ensure the HTTP client is closed when the CLI exits
    ctx.call_on_close(api_client.close)


cli.add_command(init)
cli.add_command(signup)
cli.add_command(agents)
cli.add_command(profile)
cli.add_command(automation)
cli.add_command(submolt)
cli.add_command(search)
cli.add_command(comment)
cli.add_command(upvote)
