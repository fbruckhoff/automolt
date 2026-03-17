"""Command handler for the 'automation setup' command.

Guides the user through configuring automation for the active agent:
search query, cutoff days, prompt files, and LLM provider settings.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from automolt.api.client import MoltbookAPIError
from automolt.commands.agent_targeting import resolve_target_handle
from automolt.constants import CLI_NAME
from automolt.models.agent import (
    AgentConfig,
    AutomationLLM,
    AutomationStage,
    StageLLMConfig,
    VerificationStatus,
)
from automolt.models.client import ClientConfig
from automolt.models.llm_provider import (
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    LLMProvider,
    LLMProviderConfig,
    OpenAIProviderConfig,
)
from automolt.persistence import agent_store, prompt_store, system_prompt_store
from automolt.persistence.client_store import load_client_config, save_client_config
from automolt.services.automation_service import AutomationService
from automolt.services.llm_provider_service import LLMProviderService

SEARCH_QUERY_MAX_LENGTH = 500
OPENAI_API_KEY_PREFIX = "sk-"
MIN_REQUIRED_PROMPT_CHARACTERS = 10

STAGE_TITLES = {
    AutomationStage.ANALYSIS: "analysis",
    AutomationStage.ACTION: "action",
    AutomationStage.SUBMOLT_PLANNER: "submolt planner",
}

PROMPT_DESCRIPTIONS = {
    "filter": (
        "The [bold]filter prompt[/bold] tells the LLM how to decide if a post/comment is relevant to your agent. Write criteria like: [italic]'This post is relevant if it discusses AI agent development, LLM tooling, or autonomous systems.'[/italic]"
    ),
    "behavior": (
        "The [bold]behavior prompt[/bold] tells the LLM how to write replies and when to upvote acted-on content. "
        "Describe posting/commenting tone, style, and constraints, plus clear upvote circumstances for items the agent actively replies to. "
        "Automation does not perform downvotes. Example: [italic]'Reply in a friendly, concise tone. Focus on adding value. Upvote only when the acted-on post/comment is clearly helpful.'[/italic]"
    ),
    "behavior_submolt": (
        "The [bold]submolt behavior prompt[/bold] guides planner cadence and policy in `BEHAVIOR_SUBMOLT.md`. "
        "Define when planner-driven submolt creation is appropriate, what topics are allowed, and any posting constraints."
    ),
}


@click.command("setup")
@click.option(
    "--handle",
    type=str,
    default=None,
    help="Agent handle to configure. Defaults to session active agent.",
)
@click.option(
    "--provider",
    type=str,
    default=None,
    help="Set the targeted LLM provider for analysis and action stages.",
)
@click.option(
    "--api-key",
    type=str,
    default=None,
    help="Set the API key for the chosen provider.",
)
@click.option(
    "--max-output-tokens",
    type=int,
    default=None,
    help="Set OpenAI max output tokens.",
)
@click.option(
    "--filter-md",
    type=str,
    default=None,
    flag_value="",
    help="Open or create filter prompt markdown in the default prompt file path.",
)
@click.option(
    "--behavior-md",
    type=str,
    default=None,
    flag_value="",
    help="Open or create behavior prompt markdown in the default prompt file path.",
)
@click.option(
    "--behavior-submolt-md",
    type=str,
    default=None,
    flag_value="",
    help="Open or create submolt behavior prompt markdown in the default prompt file path.",
)
@click.pass_context
def setup(
    ctx: click.Context,
    handle: str | None,
    provider: str | None,
    api_key: str | None,
    max_output_tokens: int | None,
    filter_md: str | None,
    behavior_md: str | None,
    behavior_submolt_md: str | None,
) -> None:
    """Set up automation for a target agent."""
    console: Console = ctx.obj["console"]
    base_path: Path = ctx.obj["base_path"]
    automation_service: AutomationService = ctx.obj["automation_service"]
    llm_provider_service: LLMProviderService = ctx.obj["llm_provider_service"]

    # Step 1: Resolve command target handle.
    target_handle = _resolve_target_handle(base_path, console, ctx, handle)
    if target_handle is None:
        return

    config = _load_and_validate_agent(base_path, target_handle, console, ctx)
    if config is None:
        return

    client_config = _load_client_config(base_path, console, ctx)
    if client_config is None:
        return

    _validate_system_prompt_files(base_path, console, ctx)

    is_atomic_mode = any(
        option is not None
        for option in (
            provider,
            api_key,
            max_output_tokens,
            filter_md,
            behavior_md,
            behavior_submolt_md,
        )
    )

    if is_atomic_mode:
        _run_atomic_setup(
            base_path=base_path,
            handle=target_handle,
            existing_config=config,
            client_config=client_config,
            provider=provider,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
            filter_md=filter_md,
            behavior_md=behavior_md,
            behavior_submolt_md=behavior_submolt_md,
            llm_provider_service=llm_provider_service,
            automation_service=automation_service,
            console=console,
            ctx=ctx,
        )
        return

    console.print()
    console.print("[bold]Automation Setup (Interactive)[/bold]")
    console.print()

    search_query = _prompt_search_query(
        console,
        default_query=config.automation.search_query,
    )
    cutoff_days = _prompt_cutoff_days(
        console,
        default_cutoff_days=config.automation.cutoff_days,
    )

    _collect_prompt_file(base_path, target_handle, "filter", console)
    _collect_prompt_file(base_path, target_handle, "behavior", console)
    _collect_prompt_file(base_path, target_handle, "behavior_submolt", console)
    _validate_prompt_files(base_path, target_handle, console)

    llm_config, provider_config = _collect_llm_configuration(
        console=console,
        existing_config=config,
        existing_provider_config=client_config.llm_provider_config,
        llm_provider_service=llm_provider_service,
    )

    console.print()
    with console.status("Configuring automation..."):
        try:
            client_config.llm_provider_config = provider_config
            save_client_config(base_path, client_config)

            updated_config = automation_service.setup_automation(
                handle=target_handle,
                search_query=search_query,
                cutoff_days=cutoff_days,
                llm_config=llm_config,
            )
        except (OSError, ValueError, FileNotFoundError) as exc:
            console.print(f"[bold red]Setup failed:[/bold red] {exc}")
            ctx.exit(1)
            return
        except MoltbookAPIError as exc:
            console.print(f"[bold red]Setup failed:[/bold red] {exc.message}")
            if exc.hint:
                console.print(f"[dim]Hint: {exc.hint}[/dim]")
            ctx.exit(1)
            return

    _display_success(base_path, target_handle, updated_config, client_config.llm_provider_config, console)


def _resolve_target_handle(
    base_path: Path,
    console: Console,
    ctx: click.Context,
    explicit_handle: str | None,
) -> str | None:
    """Resolve target handle from --handle, session state, or last_active_agent.

    Returns:
        The resolved handle, or None if resolution fails.
    """
    try:
        target_handle = resolve_target_handle(base_path, explicit_handle)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        ctx.exit(1)
        return None

    if not target_handle:
        console.print(f"[yellow]No target agent selected. Use '{CLI_NAME} agents', run '{CLI_NAME} signup', or pass --handle.[/yellow]")
        return None

    return target_handle


def _load_client_config(base_path: Path, console: Console, ctx: click.Context) -> ClientConfig | None:
    """Load and validate client.json for setup state updates.

    Returns:
        The parsed client configuration, or None when setup cannot proceed.
    """
    try:
        return load_client_config(base_path)
    except FileNotFoundError:
        console.print(f"[red]No client.json found. Run '{CLI_NAME} init' first.[/red]")
        ctx.exit(1)
        return None
    except ValueError:
        console.print(f"[red]client.json is corrupted. Fix it or rerun '{CLI_NAME} init'.[/red]")
        ctx.exit(1)
        return None


def _load_and_validate_agent(base_path: Path, handle: str, console: Console, ctx: click.Context) -> AgentConfig | None:
    """Load agent config and validate preconditions for automation setup.

    Returns:
        The AgentConfig, or None if validation fails.
    """
    try:
        config = agent_store.load_agent_config(base_path, handle)
    except FileNotFoundError:
        console.print(f"[red]Agent '{handle}' not found locally.[/red]")
        ctx.exit(1)
        return None
    except ValueError:
        console.print(f"[red]Agent config for '{handle}' is corrupted.[/red]")
        ctx.exit(1)
        return None

    if config.agent.verification_status != VerificationStatus.VERIFIED:
        console.print(f"[red]Agent must be verified first. Run '{CLI_NAME} profile' to check verification status.[/red]")
        ctx.exit(1)
        return None

    if config.agent.is_active is False:
        console.print("[red]Agent account deactivated.[/red]")
        ctx.exit(1)
        return None

    return config


def _run_atomic_setup(
    *,
    base_path: Path,
    handle: str,
    existing_config: AgentConfig,
    client_config: ClientConfig,
    provider: str | None,
    api_key: str | None,
    max_output_tokens: int | None,
    filter_md: str | None,
    behavior_md: str | None,
    behavior_submolt_md: str | None,
    llm_provider_service: LLMProviderService,
    automation_service: AutomationService,
    console: Console,
    ctx: click.Context,
) -> None:
    """Apply atomic setup updates without prompting for unrelated fields."""
    updated_agent_config = existing_config.model_copy(deep=True)
    updated_llm_config = updated_agent_config.automation.llm.model_copy(deep=True)
    updated_provider_config = client_config.llm_provider_config.model_copy(deep=True)

    status_lines: list[str] = []

    try:
        provider_override: LLMProvider | None = None
        if provider is not None:
            provider_override = _normalize_provider_value(provider, llm_provider_service)
            updated_llm_config.analysis.provider = provider_override
            updated_llm_config.action.provider = provider_override
            updated_llm_config.submolt_planner.provider = provider_override
            updated_llm_config.analysis.model = _resolve_default_model(
                llm_provider_service,
                AutomationStage.ANALYSIS,
                provider_override,
                existing_config.automation.llm.analysis,
            )
            updated_llm_config.action.model = _resolve_default_model(
                llm_provider_service,
                AutomationStage.ACTION,
                provider_override,
                existing_config.automation.llm.action,
            )
            updated_llm_config.submolt_planner.model = _resolve_default_model(
                llm_provider_service,
                AutomationStage.SUBMOLT_PLANNER,
                provider_override,
                existing_config.automation.llm.submolt_planner,
            )
            status_lines.append(f"[green]--provider[/green]: set all stages to '{provider_override.value}'.")

        target_provider = provider_override or updated_llm_config.analysis.provider

        if target_provider != LLMProvider.OPENAI and (api_key is not None or max_output_tokens is not None):
            raise ValueError("--api-key and --max-output-tokens currently support only provider 'openai'. Run interactive setup to choose a supported provider/model combination.")

        if api_key is not None:
            updated_provider_config.openai.api_key = _validate_openai_api_key(api_key)
            status_lines.append("[green]--api-key[/green]: updated OpenAI API key.")

        if max_output_tokens is not None:
            if max_output_tokens < 1:
                raise ValueError("--max-output-tokens must be at least 1.")
            updated_provider_config.openai.max_output_tokens = max_output_tokens
            status_lines.append(f"[green]--max-output-tokens[/green]: set max_output_tokens={max_output_tokens}.")

        if filter_md is not None:
            filter_success, filter_message = _apply_atomic_prompt_update(
                base_path=base_path,
                handle=handle,
                prompt_name="filter",
                option_value=filter_md,
                console=console,
            )
            status_color = "green" if filter_success else "red"
            status_lines.append(f"[{status_color}]--filter-md[/{status_color}]: {filter_message}")

        if behavior_md is not None:
            behavior_success, behavior_message = _apply_atomic_prompt_update(
                base_path=base_path,
                handle=handle,
                prompt_name="behavior",
                option_value=behavior_md,
                console=console,
            )
            status_color = "green" if behavior_success else "red"
            status_lines.append(f"[{status_color}]--behavior-md[/{status_color}]: {behavior_message}")

        if behavior_submolt_md is not None:
            behavior_submolt_success, behavior_submolt_message = _apply_atomic_prompt_update(
                base_path=base_path,
                handle=handle,
                prompt_name="behavior_submolt",
                option_value=behavior_submolt_md,
                console=console,
            )
            status_color = "green" if behavior_submolt_success else "red"
            status_lines.append(f"[{status_color}]--behavior-submolt-md[/{status_color}]: {behavior_submolt_message}")

        updated_agent_config.automation.llm = updated_llm_config
        client_config.llm_provider_config = updated_provider_config

        save_client_config(base_path, client_config)
        agent_store.save_agent_config(base_path, updated_agent_config)

        missing_requirements = _collect_missing_setup_requirements(
            base_path=base_path,
            handle=handle,
            config=updated_agent_config,
            provider_config=updated_provider_config,
        )

        updated_config_for_display = updated_agent_config
        if not missing_requirements:
            updated_config_for_display = automation_service.setup_automation(
                handle=handle,
                search_query=updated_agent_config.automation.search_query or "",
                cutoff_days=updated_agent_config.automation.cutoff_days,
                llm_config=updated_llm_config,
            )

        console.print()
        console.print("[bold]Automation Setup (Atomic)[/bold]")
        for line in status_lines:
            console.print(f"- {line}")

        if missing_requirements:
            console.print()
            console.print("[yellow]Atomic updates were stored, but automation setup is still incomplete.[/yellow]")
            for missing_item in missing_requirements:
                console.print(f"  - {missing_item}")
            console.print(f"[dim]Provide missing values using the corresponding flags, or run '{CLI_NAME} automation setup' without flags to use the interactive wizard.[/dim]")
            return

        _display_success(base_path, handle, updated_config_for_display, updated_provider_config, console)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(f"[bold red]Setup failed:[/bold red] {exc}")
        ctx.exit(1)
    except MoltbookAPIError as exc:
        console.print(f"[bold red]Setup failed:[/bold red] {exc.message}")
        if exc.hint:
            console.print(f"[dim]Hint: {exc.hint}[/dim]")
        ctx.exit(1)


def _normalize_provider_value(raw_provider: str, llm_provider_service: LLMProviderService) -> LLMProvider:
    """Normalize and validate a provider value from CLI flags."""
    normalized = raw_provider.strip().lower()
    if not normalized:
        raise ValueError("--provider cannot be empty.")

    provider_values = llm_provider_service.list_provider_values()
    if normalized not in provider_values:
        raise ValueError(f"Unsupported provider '{raw_provider}'. Supported values: {', '.join(provider_values)}.")

    return LLMProvider(normalized)


def _collect_missing_setup_requirements(
    *,
    base_path: Path,
    handle: str,
    config: AgentConfig,
    provider_config: LLMProviderConfig,
) -> list[str]:
    """Collect missing setup requirements for partial atomic updates."""
    missing: list[str] = []

    search_query = (config.automation.search_query or "").strip()
    if not search_query:
        missing.append("search query is missing (run interactive setup).")

    if config.automation.cutoff_days < 1:
        missing.append("cutoff days must be at least 1 (run interactive setup).")

    required_providers = {
        config.automation.llm.analysis.provider,
        config.automation.llm.action.provider,
    }
    if LLMProvider.OPENAI in required_providers and not provider_config.openai.api_key:
        missing.append("OpenAI API key is missing (use --api-key).")

    if LLMProvider.OPENAI in required_providers and provider_config.openai.max_output_tokens < 1:
        missing.append("OpenAI max output tokens must be > 0 (use --max-output-tokens).")

    for prompt_name in ("filter", "action"):
        system_prompt_filename = system_prompt_store.get_system_prompt_filename(prompt_name)
        system_prompt_path = system_prompt_store.get_system_prompt_path(base_path, prompt_name)
        if not system_prompt_path.is_file():
            missing.append(f"{system_prompt_filename} is missing (run '{CLI_NAME} init' in this client directory to restore defaults).")
            continue

        system_prompt_text = system_prompt_path.read_text(encoding="utf-8").strip()
        if len(system_prompt_text) < MIN_REQUIRED_PROMPT_CHARACTERS:
            missing.append(f"{system_prompt_filename} must contain at least {MIN_REQUIRED_PROMPT_CHARACTERS} characters.")

    for prompt_name in ("filter", "behavior"):
        prompt_path = prompt_store.get_prompt_path(base_path, handle, prompt_name)
        if not prompt_path.is_file():
            missing.append(f"{prompt_name}.md is missing (use --{prompt_name}-md).")
            continue

        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        if len(prompt_text) < MIN_REQUIRED_PROMPT_CHARACTERS:
            missing.append(f"{prompt_name}.md must contain at least {MIN_REQUIRED_PROMPT_CHARACTERS} characters (use --{prompt_name}-md).")

    return missing


def _apply_atomic_prompt_update(
    *,
    base_path: Path,
    handle: str,
    prompt_name: str,
    option_value: str,
    console: Console,
) -> tuple[bool, str]:
    """Apply one atomic prompt update via editor and sync to default prompt path."""
    default_prompt_path = prompt_store.ensure_prompt_file(base_path, handle, prompt_name)

    if option_value == "":
        editor_path = default_prompt_path
    else:
        editor_path = Path(option_value).expanduser().resolve()
        editor_path.parent.mkdir(parents=True, exist_ok=True)
        if not editor_path.exists():
            editor_path.write_text("", encoding="utf-8")

    success, content = _open_editor_and_collect_content(
        file_path=editor_path,
        prompt_name=prompt_name,
        console=console,
    )
    if not success:
        return (
            False,
            f"edited file is below {MIN_REQUIRED_PROMPT_CHARACTERS} characters; no update applied.",
        )

    prompt_store.write_prompt(base_path, handle, prompt_name, content)
    return True, f"saved {len(content)} characters."


def _prompt_search_query(console: Console, default_query: str | None = None) -> str:
    """Prompt the user for a Moltbook semantic search query.

    Returns:
        A validated, non-empty search query string.
    """
    normalized_default = (default_query or "").strip() or None

    while True:
        query = click.prompt(
            "Enter the Moltbook semantic search query to find potentially relevant discussions",
            default=normalized_default,
            show_default=normalized_default is not None,
        ).strip()

        if not query:
            console.print("[red]Search query cannot be empty.[/red]")
            continue

        if len(query) > SEARCH_QUERY_MAX_LENGTH:
            console.print(f"[red]Query must be {SEARCH_QUERY_MAX_LENGTH} characters or fewer (currently {len(query)}).[/red]")
            continue

        return query


def _prompt_cutoff_days(console: Console, default_cutoff_days: int | None = None) -> int:
    """Prompt the user for the cutoff window in days.

    Returns:
        A validated integer >= 1.
    """
    resolved_default = default_cutoff_days if default_cutoff_days and default_cutoff_days >= 1 else 90

    while True:
        value = click.prompt(
            "Enter the cutoff window in days (must be >= 1)",
            type=int,
            default=resolved_default,
            show_default=True,
        )

        if value < 1:
            console.print("[red]Cutoff days must be at least 1.[/red]")
            continue

        return value


def _collect_prompt_file(base_path: Path, handle: str, prompt_name: str, console: Console) -> None:
    """Collect content for a prompt file (for example FILTER.md or BEHAVIOR.md).

    Offers the user two options: edit in default editor, or copy from a file path.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: Prompt key such as 'filter', 'behavior', or 'behavior_submolt'.
        console: Rich console for output.
    """
    console.print()
    console.print(PROMPT_DESCRIPTIONS[prompt_name])
    console.print()

    # Check if file already exists with content
    if prompt_store.prompt_exists(base_path, handle, prompt_name):
        existing = prompt_store.read_prompt(base_path, handle, prompt_name)
        if existing.strip():
            console.print(f"[dim]Existing {prompt_name}.md found ({len(existing)} characters).[/dim]")
            if not click.confirm(f"Overwrite existing {prompt_name}.md?", default=False):
                console.print(f"[dim]Keeping existing {prompt_name}.md.[/dim]")
                return

    while True:
        choice = click.prompt(
            f"How would you like to provide {prompt_name}.md?\n  (a) Edit in default editor\n  (b) Provide a file path to copy from\nChoose",
            type=click.Choice(["a", "b"], case_sensitive=False),
        )

        if choice.lower() == "a":
            success = _collect_via_editor(base_path, handle, prompt_name, console)
        else:
            success = _collect_via_file_path(base_path, handle, prompt_name, console)

        if success:
            return

        if not click.confirm("Would you like to try again?", default=True):
            console.print(f"[yellow]Skipping {prompt_name}.md. You can edit it manually later.[/yellow]")
            return


def _collect_via_editor(base_path: Path, handle: str, prompt_name: str, console: Console) -> bool:
    """Open the prompt file in the default editor for the user to fill in.

    Returns:
        True if the file was written with content, False otherwise.
    """
    file_path = prompt_store.ensure_prompt_file(base_path, handle, prompt_name)
    success, _ = _open_editor_and_collect_content(
        file_path=file_path,
        prompt_name=prompt_name,
        console=console,
    )
    if not success:
        return False

    return True


def _open_editor_and_collect_content(
    *,
    file_path: Path,
    prompt_name: str,
    console: Console,
) -> tuple[bool, str]:
    """Open a markdown file in editor and return validation status and content."""
    console.print(f"[dim]Opening '{prompt_name}.md' in your default editor...[/dim]")
    click.launch(str(file_path))
    click.pause(info="Save the file, then press any key to continue...")

    content = file_path.read_text(encoding="utf-8")
    char_count = len(content)
    console.print(f"[dim]{prompt_name}.md current length: {char_count} characters.[/dim]")
    if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
        console.print(f"[yellow]{prompt_name}.md must contain at least {MIN_REQUIRED_PROMPT_CHARACTERS} characters.[/yellow]")
        return False, content

    return True, content


def _collect_via_file_path(base_path: Path, handle: str, prompt_name: str, console: Console) -> bool:
    """Copy content from a user-provided file path into the prompt file.

    Returns:
        True if the file was written with content, False otherwise.
    """
    raw_path = click.prompt("Enter file path").strip()

    try:
        source_path, content = prompt_store.read_prompt_source_file(Path(raw_path))
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return False
    except OSError as exc:
        console.print(f"[red]{exc}[/red]")
        return False
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        return False

    prompt_store.write_prompt(base_path, handle, prompt_name, content)
    console.print(f"[green]{prompt_name}.md saved ({len(content)} characters). Contents copied from {source_path}.[/green]")
    return True


def _validate_prompt_files(base_path: Path, handle: str, console: Console) -> None:
    """Validate that both prompt files have usable content. Warn if not.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        console: Rich console for output.
    """
    incomplete_prompts = []
    for name in ("filter", "behavior"):
        if not prompt_store.prompt_exists(base_path, handle, name):
            incomplete_prompts.append(f"{name}.md")
        else:
            content = prompt_store.read_prompt(base_path, handle, name)
            if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
                incomplete_prompts.append(f"{name}.md")

    if incomplete_prompts:
        console.print()
        console.print(f"[yellow]Warning: {', '.join(incomplete_prompts)} must each contain at least {MIN_REQUIRED_PROMPT_CHARACTERS} characters. Automation will fail until fixed.[/yellow]")
        if not click.confirm("Continue with setup anyway?", default=True):
            raise click.Abort()


def _validate_system_prompt_files(base_path: Path, console: Console, ctx: click.Context) -> None:
    """Fail setup early when client-root system prompt files are missing/invalid."""
    incomplete_system_prompts: list[str] = []

    for prompt_name in ("filter", "action"):
        filename = system_prompt_store.get_system_prompt_filename(prompt_name)
        prompt_path = system_prompt_store.get_system_prompt_path(base_path, prompt_name)
        if not prompt_path.is_file():
            incomplete_system_prompts.append(filename)
            continue

        content = prompt_path.read_text(encoding="utf-8")
        if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
            incomplete_system_prompts.append(filename)

    if not incomplete_system_prompts:
        return

    console.print(f"[red]Automation setup cannot continue: {', '.join(incomplete_system_prompts)} must each contain at least {MIN_REQUIRED_PROMPT_CHARACTERS} characters in the client root (next to client.json).[/red]")
    console.print(f"[dim]Run '{CLI_NAME} init' in this client directory to restore missing defaults, then retry setup.[/dim]")
    ctx.exit(1)


def _collect_llm_configuration(
    console: Console,
    existing_config: AgentConfig,
    existing_provider_config: LLMProviderConfig,
    llm_provider_service: LLMProviderService,
) -> tuple[AutomationLLM, LLMProviderConfig]:
    """Collect stage routing and required global provider config.

    Returns:
        A tuple containing per-agent stage configuration and updated global
        provider config storage.
    """
    console.print()
    console.print("[bold]LLM Provider Setup[/bold]")
    console.print("[dim]Choose provider + model for each stage. OpenAI is currently supported.[/dim]")
    console.print()

    provider_config = existing_provider_config.model_copy(deep=True)
    prompted_provider_configs: set[LLMProvider] = set()

    analysis_stage_config = _prompt_stage_llm_config(
        console,
        llm_provider_service,
        AutomationStage.ANALYSIS,
        existing_config.automation.llm.analysis,
        provider_config,
        prompted_provider_configs,
    )
    action_stage_config = _prompt_stage_llm_config(
        console,
        llm_provider_service,
        AutomationStage.ACTION,
        existing_config.automation.llm.action,
        provider_config,
        prompted_provider_configs,
    )
    submolt_planner_stage_config = _prompt_stage_llm_config(
        console,
        llm_provider_service,
        AutomationStage.SUBMOLT_PLANNER,
        existing_config.automation.llm.submolt_planner,
        provider_config,
        prompted_provider_configs,
    )

    return (
        AutomationLLM(
            analysis=analysis_stage_config,
            action=action_stage_config,
            submolt_planner=submolt_planner_stage_config,
        ),
        provider_config,
    )


def _prompt_provider_config(
    console: Console,
    provider: LLMProvider,
    provider_config: LLMProviderConfig,
) -> None:
    """Prompt for missing config for one selected provider."""
    if provider == LLMProvider.OPENAI:
        provider_config.openai = _prompt_openai_provider_config(
            console,
            provider_config.openai,
        )
        return

    raise ValueError(f"Unsupported provider '{provider.value}'.")


def _prompt_openai_provider_config(
    console: Console,
    existing_config: OpenAIProviderConfig,
) -> OpenAIProviderConfig:
    """Prompt for OpenAI provider config once for the selected provider."""
    api_key = _prompt_openai_api_key(console, existing_config.api_key)
    max_output_tokens = _prompt_openai_max_output_tokens(
        console,
        existing_config.max_output_tokens,
    )
    return OpenAIProviderConfig(
        api_key=api_key,
        max_output_tokens=max_output_tokens,
    )


def _prompt_stage_llm_config(
    console: Console,
    llm_provider_service: LLMProviderService,
    stage: AutomationStage,
    existing_stage_config: StageLLMConfig,
    provider_config: LLMProviderConfig,
    prompted_provider_configs: set[LLMProvider],
) -> StageLLMConfig:
    """Prompt for provider and model selection for one automation stage."""
    stage_title = STAGE_TITLES[stage]

    supported_providers = llm_provider_service.list_supported_providers()
    selected_provider = _prompt_provider_selection(
        console,
        stage_title,
        supported_providers,
        existing_stage_config.provider,
    )

    if selected_provider not in prompted_provider_configs:
        _prompt_provider_config(console, selected_provider, provider_config)
        prompted_provider_configs.add(selected_provider)

    model_choices = _resolve_stage_model_choices(
        console=console,
        llm_provider_service=llm_provider_service,
        provider=selected_provider,
        provider_config=provider_config,
    )
    default_model = _resolve_default_model_for_choices(
        llm_provider_service,
        stage,
        selected_provider,
        existing_stage_config,
        model_choices,
    )

    selected_model = _prompt_radio_choice(
        console=console,
        title=f"Model for {stage_title} stage",
        options=model_choices,
        default_value=default_model,
    )

    return StageLLMConfig(provider=selected_provider, model=selected_model)


def _prompt_provider_selection(
    console: Console,
    stage_title: str,
    providers: tuple[LLMProvider, ...],
    default_provider: LLMProvider,
) -> LLMProvider:
    """Render and prompt a Rich radio-style provider selector for one stage."""
    provider_values = [provider.value for provider in providers]
    default_value = default_provider.value if default_provider in providers else provider_values[0]
    selected_value = _prompt_radio_choice(
        console=console,
        title=f"LLM provider for {stage_title} stage",
        options=provider_values,
        default_value=default_value,
    )
    return LLMProvider(selected_value)


def _resolve_stage_model_choices(
    *,
    console: Console,
    llm_provider_service: LLMProviderService,
    provider: LLMProvider,
    provider_config: LLMProviderConfig,
) -> tuple[str, ...]:
    """Resolve available model choices for one provider during setup."""
    if provider == LLMProvider.OPENAI:
        api_key = provider_config.openai.api_key
        if not api_key:
            raise ValueError("OpenAI API key is required before selecting a model.")

        model_choices = tuple(llm_provider_service.fetch_available_models(api_key))
        warning = llm_provider_service.consume_last_model_fetch_warning()
        if warning:
            console.print()
            console.print(
                Panel(
                    f"[yellow]{warning}[/yellow]",
                    title="Model Catalog Fallback",
                    border_style="yellow",
                )
            )
            console.print()
        return model_choices

    return llm_provider_service.list_models_for_provider(provider)


def _prompt_radio_choice(
    *,
    console: Console,
    title: str,
    options: tuple[str, ...] | list[str],
    default_value: str,
) -> str:
    """Render simple numbered radio options and return one selected value."""
    normalized_options = [option.strip() for option in options if option.strip()]
    if not normalized_options:
        raise ValueError(f"No options available for selection: {title}.")

    if default_value not in normalized_options:
        default_value = normalized_options[0]

    default_index = normalized_options.index(default_value)

    while True:
        console.print(f"[bold]{title}[/bold]")
        for index, option in enumerate(normalized_options, start=1):
            is_default = index - 1 == default_index
            marker = "(*)" if is_default else "( )"
            default_suffix = " [dim](default)[/dim]" if is_default else ""
            console.print(f"  {marker} [{index}] {option}{default_suffix}")

        raw_choice = click.prompt(
            "Select number",
            default=str(default_index + 1),
            show_default=True,
        ).strip()

        if raw_choice.isdigit():
            selected_index = int(raw_choice)
            if 1 <= selected_index <= len(normalized_options):
                console.print()
                return normalized_options[selected_index - 1]

        console.print(f"[red]Invalid selection '{raw_choice}'. Enter a number between 1 and {len(normalized_options)}.[/red]")
        console.print()


def _resolve_default_model_for_choices(
    llm_provider_service: LLMProviderService,
    stage: AutomationStage,
    provider: LLMProvider,
    existing_stage_config: StageLLMConfig,
    model_choices: tuple[str, ...],
) -> str:
    """Resolve default model for dynamic model-choice lists."""
    if existing_stage_config.provider == provider and existing_stage_config.model in model_choices:
        return existing_stage_config.model

    fallback_default = llm_provider_service.default_model_for_stage(stage, provider)
    if fallback_default in model_choices:
        return fallback_default

    return model_choices[0]


def _resolve_default_model(
    llm_provider_service: LLMProviderService,
    stage: AutomationStage,
    provider: LLMProvider,
    existing_stage_config: StageLLMConfig,
) -> str:
    """Resolve default stage model while preserving a valid existing choice."""
    models = llm_provider_service.list_models_for_provider(provider)
    if existing_stage_config.provider == provider and existing_stage_config.model in models:
        return existing_stage_config.model

    return llm_provider_service.default_model_for_stage(stage, provider)


def _prompt_openai_api_key(console: Console, existing_api_key: str | None) -> str:
    """Prompt for OpenAI API key using hidden input and optional key reuse."""
    if existing_api_key:
        console.print("[dim]A global OpenAI API key is already stored for this client.[/dim]")
        if click.confirm("Reuse global OpenAI API key for all agents?", default=True):
            return existing_api_key

    while True:
        api_key = click.prompt(
            "Enter OpenAI API key",
            hide_input=True,
            confirmation_prompt=True,
        ).strip()

        try:
            validated_key = _validate_openai_api_key(api_key)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            continue

        console.print("[green]Stored OpenAI API key for all local agents.[/green]")
        return validated_key


def _validate_openai_api_key(api_key: str) -> str:
    """Validate and normalize OpenAI API key values."""
    normalized = api_key.strip()
    if not normalized:
        raise ValueError("OpenAI API key cannot be empty.")

    if not normalized.startswith(OPENAI_API_KEY_PREFIX):
        raise ValueError("OpenAI API keys should start with 'sk-'. Please verify and try again.")

    return normalized


def _prompt_openai_max_output_tokens(console: Console, existing_value: int | None) -> int:
    """Prompt for OpenAI max_output_tokens with hard-cutoff guidance."""
    default_value = existing_value if existing_value and existing_value >= 1 else DEFAULT_OPENAI_MAX_OUTPUT_TOKENS
    console.print("[dim]OpenAI max output tokens is a hard cutoff. Set this slightly above your desired output length.[/dim]")

    while True:
        value = click.prompt(
            "Enter OpenAI max output tokens (max_output_tokens)",
            type=int,
            default=default_value,
            show_default=True,
        )

        if value < 1:
            console.print("[red]Max output tokens must be > 0.[/red]")
            continue

        return value


def _display_success(
    base_path: Path,
    handle: str,
    config: AgentConfig,
    provider_config: LLMProviderConfig,
    console: Console,
) -> None:
    """Display the success panel after automation setup.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        config: The updated AgentConfig.
        provider_config: Global provider config loaded from client.json.
        console: Rich console for output.
    """
    filter_status = _prompt_file_status(base_path, handle, "filter")
    behavior_status = _prompt_file_status(base_path, handle, "behavior")
    behavior_submolt_status = _prompt_file_status(base_path, handle, "behavior_submolt")
    filter_system_status = _system_prompt_file_status(base_path, "filter")
    action_system_status = _system_prompt_file_status(base_path, "action")
    agent_dir = base_path / ".agents" / handle
    llm = config.automation.llm
    openai_key_status = _secret_status(provider_config.openai.api_key)
    openai_max_tokens = provider_config.openai.max_output_tokens

    panel_text = (
        f"[bold]Search Query:[/bold] {config.automation.search_query}\n"
        f"[bold]Cutoff Days:[/bold] {config.automation.cutoff_days}\n"
        f"[bold]FILTER_SYS.md:[/bold] {filter_system_status}\n"
        f"[bold]ACTION_SYS.md:[/bold] {action_system_status}\n"
        f"[bold]FILTER.md:[/bold] {filter_status}\n"
        f"[bold]BEHAVIOR.md:[/bold] {behavior_status}\n"
        f"[bold]BEHAVIOR_SUBMOLT.md:[/bold] {behavior_submolt_status}\n"
        f"[bold]Analysis Stage:[/bold] {llm.analysis.provider.value} / {llm.analysis.model}\n"
        f"[bold]Action Stage:[/bold] {llm.action.provider.value} / {llm.action.model}\n"
        f"[bold]Submolt Planner Stage:[/bold] {llm.submolt_planner.provider.value} / {llm.submolt_planner.model}\n"
        f"[bold]OpenAI API Key (Global):[/bold] {openai_key_status}\n"
        f"[bold]OpenAI max_output_tokens:[/bold] {openai_max_tokens}\n"
        f"[bold]Agent Directory:[/bold] {agent_dir}\n\n"
        "[dim]Automation is now enabled. Start in foreground with "
        f"'{CLI_NAME} automation start' or in background with "
        f"'{CLI_NAME} automation start --background'. Use "
        f"'{CLI_NAME} automation monitor' to watch live progress.[/dim]"
    )

    console.print()
    console.print(
        Panel(
            panel_text,
            title=f"Automation Setup Complete — {handle}",
            border_style="green",
        )
    )


def _prompt_file_status(base_path: Path, handle: str, prompt_name: str) -> str:
    """Return a display string for a prompt file's status.

    Returns:
        A Rich-formatted status string.
    """
    if not prompt_store.prompt_exists(base_path, handle, prompt_name):
        return "[yellow]Not created[/yellow]"

    content = prompt_store.read_prompt(base_path, handle, prompt_name)
    if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
        return f"[yellow]Too short (<{MIN_REQUIRED_PROMPT_CHARACTERS} chars)[/yellow]"

    return f"[green]{len(content)} characters[/green]"


def _system_prompt_file_status(base_path: Path, prompt_name: str) -> str:
    """Return a display string for a client-root system prompt file's status."""
    prompt_path = system_prompt_store.get_system_prompt_path(base_path, prompt_name)
    if not prompt_path.is_file():
        return "[yellow]Missing[/yellow]"

    content = prompt_path.read_text(encoding="utf-8")
    if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
        return f"[yellow]Too short (<{MIN_REQUIRED_PROMPT_CHARACTERS} chars)[/yellow]"

    return f"[green]{len(content)} characters[/green]"


def _secret_status(secret: str | None) -> str:
    """Render a safe display status for a sensitive secret value."""
    if not secret:
        return "[red]Missing[/red]"

    suffix = secret[-4:] if len(secret) >= 4 else "****"
    return f"[green]Stored[/green] (ends with ...{suffix})"
