"""Business logic for automation configuration and heartbeat execution.

Handles setting up automation for an agent, executing heartbeat cycles
that search for content, and managing the automation queue.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.constants import CLI_NAME
from automolt.models.agent import AgentConfig, AutomationLLM, AutomationStage, StageLLMConfig
from automolt.models.automation import QueueItem
from automolt.models.llm import ActionPlan, AnalysisDecision, SubmoltPlannerPlan
from automolt.models.llm_provider import LLMProvider, LLMProviderConfig
from automolt.persistence import agent_store, automation_log_store, automation_store, prompt_store, system_prompt_store
from automolt.persistence.automation_log_store import AutomationEventStatus
from automolt.persistence.client_store import load_client_config
from automolt.services.base_llm_client import LLMClientError
from automolt.services.llm_execution_service import LLMExecutionService
from automolt.services.llm_provider_service import LLMProviderService
from automolt.services.post_service import PostService
from automolt.services.search_service import MIN_SEARCH_QUERY_LENGTH, SearchService
from automolt.services.submolt_service import SubmoltService

logger = logging.getLogger(__name__)

SUPPORTED_QUEUE_ITEM_TYPES = {"post", "comment"}
MAX_ACTION_REPLY_CHARACTERS = 1000
DRY_RUN_REPLIED_ITEM_ID = "--dry"
MOLTBOOK_WEB_BASE_URL = "https://www.moltbook.com"
MIN_REQUIRED_PROMPT_CHARACTERS = 10
ANALYSIS_SYSTEM_PROMPT_NAME = "filter"
ACTION_SYSTEM_PROMPT_NAME = "action"
SUBMOLT_SYSTEM_PROMPT_NAME = "submolt_planner"
BEHAVIOR_SUBMOLT_PROMPT_NAME = "behavior_submolt"

DEFAULT_SUBMOLT_CREATE_INTERVAL_HOURS = 24
DEFAULT_SUBMOLT_MAX_CREATIONS_PER_DAY = 1
MAX_SUBMOLT_POLICY_TOPIC_LENGTH = 200
MAX_SUBMOLT_SOURCE_SUMMARY_LENGTH = 240
RECENT_SUBMOLT_HISTORY_LIMIT = 10
SUBMOLT_NAME_MIN_LENGTH = 2
SUBMOLT_NAME_MAX_LENGTH = 30
SUBMOLT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RETRYABLE_SUBMOLT_ERROR_TOKENS = ("bad request", "already", "exists", "taken", "duplicate")
CADENCE_EVERY_HOURS_PATTERN = re.compile(r"\bevery\s+(\d+)\s+hours?\b")
CADENCE_EVERY_DAYS_PATTERN = re.compile(r"\bevery\s+(\d+)\s+days?\b")
CADENCE_EVERY_WEEKS_PATTERN = re.compile(r"\bevery\s+(\d+)\s+weeks?\b")


class ItemProcessingOutcome(str, Enum):
    """Per-item processing outcomes used by the heartbeat scan loop."""

    IRRELEVANT = "irrelevant"
    RELEVANT_NOT_ACTED = "relevant_not_acted"
    ACTED = "acted"


class HeartbeatEventType(str, Enum):
    """Observable heartbeat events emitted during cycle execution."""

    SEARCH_STARTED = "search_started"
    SEARCH_COMPLETED = "search_completed"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ACTION_DRY_RUN = "action_dry_run"
    ACTION_POSTED = "action_posted"
    PLANNER_EVALUATED = "planner_evaluated"
    PLANNER_SKIPPED = "planner_skipped"
    PLANNER_ACTED = "planner_acted"
    PLANNER_FAILED = "planner_failed"


@dataclass(frozen=True)
class HeartbeatEvent:
    """Structured event payload for CLI monitoring output."""

    event_type: HeartbeatEventType
    handle: str
    search_query: str | None = None
    search_results_total: int = 0
    discovered_posts: int = 0
    discovered_comments: int = 0
    skipped_self_authored_count: int = 0
    item_id: str | None = None
    item_type: str | None = None
    is_relevant: bool | None = None
    relevance_rationale: str | None = None
    response_text: str | None = None
    target_url: str | None = None
    upvote_requested: bool = False
    upvote_target_type: str | None = None
    upvote_target_id: str | None = None
    upvote_message: str | None = None
    planner_status: str | None = None
    planner_reason: str | None = None
    planner_trigger: str | None = None
    planner_submolt_name: str | None = None
    planner_post_id: str | None = None
    dry_run: bool = False


HeartbeatObserver = Callable[[HeartbeatEvent], None]


@dataclass(frozen=True)
class HeartbeatExecutionOptions:
    """Runtime options controlling one heartbeat cycle execution."""

    dry_run_actions: bool = False
    observer: HeartbeatObserver | None = None


@dataclass(frozen=True)
class SubmoltPlannerPolicy:
    """Parsed BEHAVIOR_SUBMOLT policy controls used by deterministic guards."""

    enabled: bool
    interval_hours: int
    max_creations_per_day: int
    topic_policy: str | None
    allowed_topics: tuple[str, ...]
    name_prefix: str | None
    allow_crypto: bool
    policy_body: str


@dataclass(frozen=True)
class SubmoltPlannerContext:
    """Runtime metadata included in planner prompt payloads."""

    source_trigger: str
    current_utc: datetime
    last_submolt_created_at_utc: datetime | None
    hours_since_last_submolt_creation: float | None
    recent_submolt_titles: tuple[str, ...]
    source_item_id: str | None = None
    source_item_type: str | None = None
    source_post_id: str | None = None
    source_submolt_name: str | None = None
    source_item_summary: str | None = None


@dataclass(frozen=True)
class SubmoltPlannerEvaluationResult:
    """Planner stage evaluation result for one heartbeat cycle."""

    acted: bool
    status: str
    reason: str


class AutomationService:
    """Service for automation setup and heartbeat cycle execution."""

    def __init__(self, api_client: MoltbookClient, base_path: Path):
        self._api = api_client
        self._base_path = base_path
        self._post_service = PostService(api_client=api_client)
        self._submolt_service = SubmoltService(api_client=api_client)
        self._llm_provider_service = LLMProviderService()
        self._llm_execution_service = LLMExecutionService()

    def setup_automation(self, handle: str, search_query: str, cutoff_days: int, llm_config: AutomationLLM) -> AgentConfig:
        """Configure automation for an agent.

        1. Load the agent's AgentConfig from disk.
        2. Set automation.search_query and automation.cutoff_days.
        3. Validate stage provider/model selections and required global provider config.
        4. Set automation.llm.
        5. Set automation.enabled = True.
        6. Save the updated AgentConfig to disk.
        7. Initialize the automation database (create tables if needed).
        8. Return the updated AgentConfig.

        Args:
            handle: The agent's handle.
            search_query: The Moltbook search query for finding discussions.
            cutoff_days: Days before un-acted items are pruned.
            llm_config: LLM provider/model settings captured during setup.

        Returns:
            The updated AgentConfig.

        Raises:
            FileNotFoundError: If the agent config does not exist locally.
            ValueError: If search_query is empty, shorter than 3 chars, or cutoff_days < 1.
        """
        normalized_query = search_query.strip()
        if not normalized_query:
            raise ValueError("Search query cannot be empty.")
        if len(normalized_query) < MIN_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Search query must be at least {MIN_SEARCH_QUERY_LENGTH} characters.")
        if cutoff_days < 1:
            raise ValueError("Cutoff days must be at least 1.")
        self.validate_llm_config(llm_config)
        provider_config = self._load_global_provider_config()
        self._validate_required_provider_config(
            required_providers=self._collect_required_providers(llm_config),
            provider_config=provider_config,
        )

        config = agent_store.load_agent_config(self._base_path, handle)

        config.automation.search_query = normalized_query
        config.automation.cutoff_days = cutoff_days
        config.automation.llm = llm_config
        config.automation.enabled = True

        agent_store.save_agent_config(self._base_path, config)
        automation_store.init_db(self._base_path, handle)

        return config

    def validate_llm_config(self, llm_config: AutomationLLM) -> None:
        """Validate stage provider/model selections.

        Args:
            llm_config: LLM settings to validate.

        Raises:
            ValueError: If stage model/provider selections are invalid.
        """

        self._validate_stage_selection(AutomationStage.ANALYSIS, llm_config.analysis)

        self._validate_stage_selection(AutomationStage.ACTION, llm_config.action)
        self._validate_stage_selection(AutomationStage.SUBMOLT_PLANNER, llm_config.submolt_planner)

    def validate_runtime_llm_prerequisites(self, config: AgentConfig) -> None:
        """Validate persisted LLM settings for runtime scheduler prerequisites.

        Args:
            config: Agent config loaded from disk.

        Raises:
            ValueError: If LLM settings are incomplete for runtime execution.
        """
        llm_config = config.automation.llm
        self.validate_llm_config(llm_config)

        provider_config = self._load_global_provider_config()
        self._validate_required_provider_config(
            required_providers=self._collect_required_providers(llm_config),
            provider_config=provider_config,
        )
        self._validate_required_prompt_files(config.agent.handle)

    def list_items(self, handle: str, status_filter: str, limit: int | None) -> list[QueueItem]:
        """List automation queue items for a given status.

        Args:
            handle: The agent's handle.
            status_filter: One of pending-analysis, pending-action, or acted.
            limit: Maximum number of items to return, or None for no limit.

        Returns:
            Queue items matching the requested status.

        Raises:
            ValueError: If status_filter is invalid or limit is less than 1.
        """
        return automation_store.list_items(self._base_path, handle, status_filter, limit)

    def execute_heartbeat_cycle(self, handle: str, options: HeartbeatExecutionOptions | None = None) -> None:
        """Execute one heartbeat cycle for the given agent.

        This is the core automation loop, called by the scheduler.

        Steps:
            1. Load AgentConfig; return if disabled or no api_key.
            2. Init DB (idempotent).
            3. Prune old items.
            4. Run search + enqueue (deduped) every cycle.
            5. Scan unanalyzed items oldest-first in the same cycle.
            6. If search inserted zero rows and no item was acted: retry pending-action backlog.
            7. Stop scan on first acted item, or backlog exhaustion.
            8. Persist heartbeat timestamp once at cycle completion.

        Args:
            handle: The agent's handle.
            options: Optional execution controls for dry-action mode and monitoring.
        """
        execution_options = options or HeartbeatExecutionOptions()
        config = agent_store.load_agent_config(self._base_path, handle)

        if not config.automation.enabled:
            logger.debug("Automation disabled for '%s', skipping cycle.", handle)
            return

        if not config.agent.api_key:
            logger.debug("No API key for '%s', skipping cycle.", handle)
            return

        self.validate_runtime_llm_prerequisites(config)

        automation_store.init_db(self._base_path, handle)
        pruned = automation_store.prune_old_items(self._base_path, handle, config.automation.cutoff_days)
        if pruned > 0:
            logger.info("Pruned %d old items for '%s'.", pruned, handle)

        provider_config = self._load_global_provider_config()
        planner_evaluation = self._evaluate_submolt_planner_for_cycle(
            handle=handle,
            config=config,
            provider_config=provider_config,
            execution_options=execution_options,
        )
        acted_this_cycle = planner_evaluation.acted
        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.SEARCH_STARTED,
                handle=handle,
                search_query=config.automation.search_query,
                dry_run=execution_options.dry_run_actions,
            ),
        )
        search_inserted = self._search_and_enqueue(handle, config)
        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.SEARCH_COMPLETED,
                handle=handle,
                search_query=config.automation.search_query,
                discovered_posts=search_inserted.posts,
                discovered_comments=search_inserted.comments,
                search_results_total=search_inserted.total,
                dry_run=execution_options.dry_run_actions,
            ),
        )

        filter_prompt: str | None = None
        behavior_prompt: str | None = None
        analysis_system_prompt: str | None = None
        action_system_prompt: str | None = None

        if not acted_this_cycle:
            while True:
                next_item = automation_store.get_next_unanalyzed(self._base_path, handle)
                if next_item is None:
                    break

                if filter_prompt is None:
                    filter_prompt = self._load_required_prompt(handle, "filter")
                    behavior_prompt = self._load_required_prompt(handle, "behavior")
                    analysis_system_prompt = self._load_required_system_prompt(ANALYSIS_SYSTEM_PROMPT_NAME)
                    action_system_prompt = self._load_required_system_prompt(ACTION_SYSTEM_PROMPT_NAME)

                outcome = self._analyze_item(
                    handle,
                    config,
                    next_item,
                    provider_config=provider_config,
                    filter_prompt=filter_prompt,
                    behavior_prompt=behavior_prompt,
                    analysis_system_prompt=analysis_system_prompt,
                    action_system_prompt=action_system_prompt,
                    execution_options=execution_options,
                )
                if outcome == ItemProcessingOutcome.ACTED:
                    acted_this_cycle = True
                    break

        should_retry_pending_action = not acted_this_cycle and search_inserted.total == 0
        if should_retry_pending_action:
            if behavior_prompt is None:
                behavior_prompt = self._load_required_prompt(handle, "behavior")
                action_system_prompt = self._load_required_system_prompt(ACTION_SYSTEM_PROMPT_NAME)

            pending_acted = self._process_pending_action_backlog(
                handle=handle,
                config=config,
                provider_config=provider_config,
                behavior_prompt=behavior_prompt,
                action_system_prompt=action_system_prompt,
                execution_options=execution_options,
            )
            if pending_acted:
                logger.info("Pending-action retry acted on at least one item for '%s'.", handle)

        self._persist_heartbeat_timestamp(config)

    def reload_submolt_policy(self, handle: str) -> SubmoltPlannerPolicy:
        """Force re-parse and persistence refresh for BEHAVIOR_SUBMOLT policy."""
        policy, parse_warning = self._refresh_submolt_policy(handle, force_reload=True)
        if parse_warning:
            raise ValueError(parse_warning)
        if policy is None:
            raise ValueError("BEHAVIOR_SUBMOLT.md is missing or contains no usable policy.")
        return policy

    def _evaluate_submolt_planner_for_cycle(
        self,
        *,
        handle: str,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        execution_options: HeartbeatExecutionOptions,
    ) -> SubmoltPlannerEvaluationResult:
        """Evaluate and optionally execute planner-first submolt automation for one cycle."""
        policy, parse_warning = self._refresh_submolt_policy(handle)
        if parse_warning:
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_FAILED,
                    handle=handle,
                    planner_status=AutomationEventStatus.FAILED.value,
                    planner_reason=parse_warning,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_policy_error",
                source_trigger="scheduled",
                status=AutomationEventStatus.FAILED,
                error_summary=parse_warning,
            )

        if policy is None:
            reason = "behavior-submolt-unavailable"
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=reason,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.SKIPPED.value, reason=reason)

        if not policy.enabled:
            reason = "planner-disabled-by-policy"
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=reason,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_skip",
                source_trigger="scheduled",
                status=AutomationEventStatus.SKIPPED,
                error_summary=reason,
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.SKIPPED.value, reason=reason)

        planner_context = self._build_submolt_planner_context(handle=handle, source_trigger="scheduled")
        guard_failure_reason = self._evaluate_submolt_runtime_guards(
            handle=handle,
            policy=policy,
            planner_context=planner_context,
            requested_submolt_name=None,
        )
        if guard_failure_reason is not None:
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=guard_failure_reason,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_skip",
                source_trigger="scheduled",
                status=AutomationEventStatus.SKIPPED,
                error_summary=guard_failure_reason,
            )
            return SubmoltPlannerEvaluationResult(
                acted=False,
                status=AutomationEventStatus.SKIPPED.value,
                reason=guard_failure_reason,
            )

        planner_system_prompt = self._load_required_system_prompt(SUBMOLT_SYSTEM_PROMPT_NAME)
        planner_behavior_prompt = self._load_required_prompt(handle, BEHAVIOR_SUBMOLT_PROMPT_NAME)
        if planner_system_prompt is None or planner_behavior_prompt is None:
            reason = "planner-prompts-unavailable"
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=reason,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.SKIPPED.value, reason=reason)

        planner_plan = self._run_submolt_planner_stage(
            config=config,
            provider_config=provider_config,
            handle=handle,
            planner_context=planner_context,
            policy=policy,
            behavior_prompt=planner_behavior_prompt,
            system_prompt=planner_system_prompt,
        )
        if planner_plan is None:
            reason = "planner-stage-failed"
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_FAILED,
                    handle=handle,
                    planner_status=AutomationEventStatus.FAILED.value,
                    planner_reason=reason,
                    planner_trigger="scheduled",
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_failed",
                source_trigger="scheduled",
                status=AutomationEventStatus.FAILED,
                error_summary=reason,
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.FAILED.value, reason=reason)

        return self._execute_submolt_planner_plan(
            handle=handle,
            config=config,
            policy=policy,
            planner_context=planner_context,
            planner_plan=planner_plan,
            source_trigger="scheduled",
            execution_options=execution_options,
        )

    def _refresh_submolt_policy(
        self,
        handle: str,
        *,
        force_reload: bool = False,
    ) -> tuple[SubmoltPlannerPolicy | None, str | None]:
        """Refresh cached planner policy when file fingerprint changes or reload is requested."""
        runtime_state = automation_store.load_behavior_submolt_runtime_state(self._base_path, handle)
        behavior_path = prompt_store.get_prompt_path(self._base_path, handle, BEHAVIOR_SUBMOLT_PROMPT_NAME)
        if not behavior_path.is_file():
            if force_reload:
                return None, "BEHAVIOR_SUBMOLT.md not found."
            if runtime_state.behavior_submolt_policy_json:
                return self._policy_from_json(runtime_state.behavior_submolt_policy_json), None
            return None, None

        current_stat = os.stat(behavior_path)
        fingerprint_changed = (
            runtime_state.behavior_submolt_mtime_ns != current_stat.st_mtime_ns
            or runtime_state.behavior_submolt_size != current_stat.st_size
        )
        if not force_reload and not fingerprint_changed and runtime_state.behavior_submolt_policy_json:
            return self._policy_from_json(runtime_state.behavior_submolt_policy_json), None

        try:
            policy_text = prompt_store.read_prompt(self._base_path, handle, BEHAVIOR_SUBMOLT_PROMPT_NAME)
            parsed_policy = self._parse_submolt_policy_prompt(policy_text)
        except (OSError, ValueError) as exc:
            if runtime_state.behavior_submolt_policy_json:
                return self._policy_from_json(runtime_state.behavior_submolt_policy_json), f"Failed to parse BEHAVIOR_SUBMOLT.md: {exc}"
            return None, f"Failed to parse BEHAVIOR_SUBMOLT.md: {exc}"

        automation_store.save_behavior_submolt_runtime_state(
            self._base_path,
            handle,
            automation_store.BehaviorSubmoltRuntimeState(
                behavior_submolt_mtime_ns=current_stat.st_mtime_ns,
                behavior_submolt_size=current_stat.st_size,
                behavior_submolt_policy_json=self._policy_to_json(parsed_policy),
                behavior_submolt_loaded_at_utc=datetime.now(timezone.utc).isoformat(),
            ),
        )
        return parsed_policy, None

    def _policy_to_json(self, policy: SubmoltPlannerPolicy) -> str:
        """Serialize planner policy to JSON for runtime-state persistence."""
        payload = {
            "enabled": policy.enabled,
            "interval_hours": policy.interval_hours,
            "max_creations_per_day": policy.max_creations_per_day,
            "topic_policy": policy.topic_policy,
            "allowed_topics": list(policy.allowed_topics),
            "name_prefix": policy.name_prefix,
            "allow_crypto": policy.allow_crypto,
            "policy_body": policy.policy_body,
        }
        return json.dumps(payload, separators=(",", ":"))

    def _policy_from_json(self, policy_json: str) -> SubmoltPlannerPolicy:
        """Deserialize planner policy from runtime-state persistence."""
        payload = json.loads(policy_json)
        return SubmoltPlannerPolicy(
            enabled=bool(payload.get("enabled", False)),
            interval_hours=max(int(payload.get("interval_hours", DEFAULT_SUBMOLT_CREATE_INTERVAL_HOURS)), 1),
            max_creations_per_day=max(int(payload.get("max_creations_per_day", DEFAULT_SUBMOLT_MAX_CREATIONS_PER_DAY)), 1),
            topic_policy=payload.get("topic_policy"),
            allowed_topics=tuple(payload.get("allowed_topics", [])),
            name_prefix=payload.get("name_prefix"),
            allow_crypto=bool(payload.get("allow_crypto", False)),
            policy_body=str(payload.get("policy_body", "")).strip(),
        )

    def _parse_submolt_policy_prompt(self, prompt_text: str) -> SubmoltPlannerPolicy:
        """Parse BEHAVIOR_SUBMOLT.md text into deterministic policy controls."""
        normalized_prompt = prompt_text.strip()
        if len(normalized_prompt) < MIN_REQUIRED_PROMPT_CHARACTERS:
            raise ValueError("BEHAVIOR_SUBMOLT.md must contain at least 10 non-whitespace characters.")

        frontmatter, policy_body = self._extract_policy_frontmatter(normalized_prompt)

        enabled = self._parse_policy_bool(frontmatter.get("submolt_enabled"), default=True)
        raw_interval_hours = frontmatter.get("submolt_create_interval_hours")
        if raw_interval_hours is not None:
            interval_hours = self._parse_policy_int(raw_interval_hours, default=DEFAULT_SUBMOLT_CREATE_INTERVAL_HOURS, minimum=1)
        else:
            interval_hours = self._parse_interval_hours_from_policy_body(policy_body)
            if interval_hours is None:
                interval_hours = DEFAULT_SUBMOLT_CREATE_INTERVAL_HOURS
        max_creations_per_day = self._parse_policy_int(
            frontmatter.get("submolt_max_creations_per_day"),
            default=DEFAULT_SUBMOLT_MAX_CREATIONS_PER_DAY,
            minimum=1,
        )
        topic_policy = self._normalize_optional_policy_text(frontmatter.get("submolt_topic_policy"), MAX_SUBMOLT_POLICY_TOPIC_LENGTH)
        name_prefix = self._normalize_optional_policy_text(frontmatter.get("submolt_name_prefix"), 40)
        allowed_topics = self._parse_allowed_topics(frontmatter.get("submolt_allowed_topics"))
        allow_crypto = self._parse_policy_bool(frontmatter.get("submolt_allow_crypto"), default=False)

        return SubmoltPlannerPolicy(
            enabled=enabled,
            interval_hours=interval_hours,
            max_creations_per_day=max_creations_per_day,
            topic_policy=topic_policy,
            allowed_topics=allowed_topics,
            name_prefix=name_prefix,
            allow_crypto=allow_crypto,
            policy_body=policy_body,
        )

    def _parse_interval_hours_from_policy_body(self, policy_body: str) -> int | None:
        """Parse constrained natural-language cadence hints from BEHAVIOR_SUBMOLT body text."""
        body_text = policy_body.strip().lower()
        if not body_text:
            return None

        if "once per week" in body_text or "weekly" in body_text:
            return 24 * 7
        if "once per day" in body_text or "daily" in body_text:
            return 24

        weeks_match = CADENCE_EVERY_WEEKS_PATTERN.search(body_text)
        if weeks_match:
            return max(int(weeks_match.group(1)), 1) * 24 * 7

        days_match = CADENCE_EVERY_DAYS_PATTERN.search(body_text)
        if days_match:
            return max(int(days_match.group(1)), 1) * 24

        hours_match = CADENCE_EVERY_HOURS_PATTERN.search(body_text)
        if hours_match:
            return max(int(hours_match.group(1)), 1)

        cadence_keywords_present = any(
            token in body_text for token in ("once per", "every", "daily", "weekly", "hour", "day", "week")
        )
        if cadence_keywords_present:
            raise ValueError("Unable to parse cadence from BEHAVIOR_SUBMOLT.md body text.")

        return None

    def _extract_policy_frontmatter(self, prompt_text: str) -> tuple[dict[str, str], str]:
        """Extract optional YAML-like frontmatter and return remaining body text."""
        if not prompt_text.startswith("---"):
            return {}, prompt_text

        lines = prompt_text.splitlines()
        if not lines:
            return {}, prompt_text

        frontmatter_lines: list[str] = []
        body_start = 1
        found_closing = False
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = index + 1
                found_closing = True
                break
            frontmatter_lines.append(line)

        if not found_closing:
            return {}, prompt_text

        frontmatter: dict[str, str] = {}
        for line in frontmatter_lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip().lower()
            if not normalized_key:
                continue
            frontmatter[normalized_key] = value.strip().strip('"').strip("'")

        policy_body = "\n".join(lines[body_start:]).strip()
        return frontmatter, policy_body

    def _parse_policy_bool(self, raw_value: str | None, *, default: bool) -> bool:
        """Parse a bool-like policy value with safe defaults."""
        if raw_value is None:
            return default
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Invalid boolean policy value '{raw_value}'.")

    def _parse_policy_int(self, raw_value: str | None, *, default: int, minimum: int) -> int:
        """Parse and clamp integer policy values."""
        if raw_value is None:
            return default
        parsed_value = int(raw_value.strip())
        if parsed_value < minimum:
            raise ValueError(f"Policy value must be >= {minimum}.")
        return parsed_value

    def _parse_allowed_topics(self, raw_value: str | None) -> tuple[str, ...]:
        """Parse optional comma-separated allowed topics."""
        if raw_value is None:
            return ()
        normalized_topics = []
        for entry in raw_value.split(","):
            topic = entry.strip()
            if not topic:
                continue
            normalized_topics.append(topic[:80])
        return tuple(normalized_topics)

    def _normalize_optional_policy_text(self, raw_value: str | None, max_length: int) -> str | None:
        """Normalize and bound optional policy string fields."""
        if raw_value is None:
            return None
        normalized = raw_value.strip()
        if not normalized:
            return None
        return normalized[:max_length]

    def _build_submolt_planner_context(
        self,
        *,
        handle: str,
        source_trigger: str,
        source_item: QueueItem | None = None,
        source_item_summary: str | None = None,
    ) -> SubmoltPlannerContext:
        """Build deterministic planner context from persisted successful events."""
        now_utc = datetime.now(timezone.utc)
        recent_create_events = automation_log_store.list_recent_successful_submolt_creations(
            self._base_path,
            handle,
            limit=RECENT_SUBMOLT_HISTORY_LIMIT,
        )
        last_create_event = recent_create_events[0] if recent_create_events else None
        if last_create_event is None:
            last_created_at = None
            elapsed_hours = None
        else:
            last_created_at = last_create_event.created_at_utc
            if last_created_at.tzinfo is None:
                last_created_at = last_created_at.replace(tzinfo=timezone.utc)
            elapsed_hours = max((now_utc - last_created_at).total_seconds() / 3600.0, 0.0)

        return SubmoltPlannerContext(
            source_trigger=source_trigger,
            current_utc=now_utc,
            last_submolt_created_at_utc=last_created_at,
            hours_since_last_submolt_creation=elapsed_hours,
            recent_submolt_titles=self._extract_recent_submolt_titles(recent_create_events),
            source_item_id=source_item.item_id if source_item else None,
            source_item_type=source_item.item_type if source_item else None,
            source_post_id=self._resolve_post_id(source_item) if source_item else None,
            source_submolt_name=source_item.submolt_name if source_item else None,
            source_item_summary=self._truncate_source_summary(source_item_summary),
        )

    def _extract_recent_submolt_titles(self, events: list[automation_log_store.AutomationEvent]) -> tuple[str, ...]:
        """Build newest-first display titles from recent successful create events."""
        titles: list[str] = []
        for event in events:
            candidate_title = (event.submolt_display_name or "").strip()
            if not candidate_title:
                candidate_title = (event.submolt_name or "").replace("-", " ").strip().title()
            if not candidate_title:
                continue
            titles.append(candidate_title[:80])
            if len(titles) >= RECENT_SUBMOLT_HISTORY_LIMIT:
                break
        return tuple(titles)

    def _truncate_source_summary(self, value: str | None) -> str | None:
        """Normalize optional source-summary text for planner context payloads."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized[:MAX_SUBMOLT_SOURCE_SUMMARY_LENGTH]

    def _evaluate_submolt_runtime_guards(
        self,
        *,
        handle: str,
        policy: SubmoltPlannerPolicy,
        planner_context: SubmoltPlannerContext,
        requested_submolt_name: str | None,
        requested_display_name: str | None = None,
    ) -> str | None:
        """Return a skip reason when deterministic planner guards fail."""
        if planner_context.hours_since_last_submolt_creation is not None and planner_context.hours_since_last_submolt_creation < policy.interval_hours:
            return "interval-not-elapsed"

        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        creations_today = automation_log_store.count_successful_submolt_creations_since(self._base_path, handle, start_of_day)
        if creations_today >= policy.max_creations_per_day:
            return "max-creations-per-day-reached"

        if requested_submolt_name and automation_log_store.has_successful_submolt_name(self._base_path, handle, requested_submolt_name):
            return "duplicate-submolt-name"

        if self._is_duplicate_or_near_duplicate_submolt(
            requested_submolt_name=requested_submolt_name,
            requested_display_name=requested_display_name,
            recent_titles=planner_context.recent_submolt_titles,
        ):
            return "duplicate-submolt-title"

        return None

    def _is_duplicate_or_near_duplicate_submolt(
        self,
        *,
        requested_submolt_name: str | None,
        requested_display_name: str | None,
        recent_titles: tuple[str, ...],
    ) -> bool:
        """Evaluate duplicate or near-duplicate title/name collisions."""
        candidate_values = [value for value in (requested_submolt_name, requested_display_name) if value and value.strip()]
        if not candidate_values:
            return False

        normalized_candidates = {self._normalize_submolt_title_for_compare(value) for value in candidate_values}
        normalized_candidates.discard("")
        if not normalized_candidates:
            return False

        for recent_title in recent_titles:
            normalized_recent = self._normalize_submolt_title_for_compare(recent_title)
            if not normalized_recent:
                continue

            recent_tokens = set(normalized_recent.split())
            for normalized_candidate in normalized_candidates:
                if normalized_candidate == normalized_recent:
                    return True

                if normalized_candidate.startswith(normalized_recent) or normalized_recent.startswith(normalized_candidate):
                    if len(normalized_candidate) >= 12 or len(normalized_recent) >= 12:
                        return True

                candidate_tokens = set(normalized_candidate.split())
                if not candidate_tokens or not recent_tokens:
                    continue
                overlap = len(candidate_tokens & recent_tokens)
                minimum_tokens = min(len(candidate_tokens), len(recent_tokens))
                if minimum_tokens >= 2 and overlap >= minimum_tokens:
                    return True

        return False

    def _normalize_submolt_title_for_compare(self, value: str) -> str:
        """Normalize title-like text for duplicate detection checks."""
        lowered = value.strip().lower().replace("-", " ")
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        collapsed = re.sub(r"\s+", " ", lowered).strip()
        return collapsed

    def _run_submolt_planner_stage(
        self,
        *,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        handle: str,
        planner_context: SubmoltPlannerContext,
        policy: SubmoltPlannerPolicy,
        behavior_prompt: str,
        system_prompt: str,
    ) -> SubmoltPlannerPlan | None:
        """Execute planner stage and return parsed structured planner output."""
        composed_system_prompt = self._compose_submolt_planner_system_prompt(
            system_prompt=system_prompt,
            policy=policy,
            planner_context=planner_context,
        )
        planner_user_prompt = self._build_submolt_planner_user_prompt(
            planner_context=planner_context,
            policy=policy,
            behavior_prompt=behavior_prompt,
        )
        planner_prompt_payload = self._build_stage_prompt_payload(composed_system_prompt, planner_user_prompt)

        try:
            stage_result = self._llm_execution_service.plan_submolt(
                config=config,
                provider_config=provider_config,
                system_prompt=composed_system_prompt,
                user_prompt=planner_user_prompt,
            )
            self._write_stage_log(
                handle=handle,
                item_id=planner_context.source_item_id or "planner",
                stage="submolt-planner",
                prompt_payload=planner_prompt_payload,
                response_payload=stage_result.raw_response,
            )
            if not isinstance(stage_result.parsed_output, SubmoltPlannerPlan):
                logger.warning("Submolt planner returned unexpected output model for '%s'.", handle)
                return None
            return stage_result.parsed_output
        except LLMClientError as exc:
            self._write_stage_log(
                handle=handle,
                item_id=planner_context.source_item_id or "planner",
                stage="submolt-planner",
                prompt_payload=planner_prompt_payload,
                response_payload=f"LLMClientError: {exc}",
            )
            logger.warning("Submolt planner stage failed for '%s': %s (%s)", handle, exc, exc.reason_code)
            return None

    def _build_submolt_planner_user_prompt(
        self,
        *,
        planner_context: SubmoltPlannerContext,
        policy: SubmoltPlannerPolicy,
        behavior_prompt: str,
    ) -> str:
        """Build deterministic planner user prompt including context and policy controls."""
        context_payload = {
            "source_trigger": planner_context.source_trigger,
            "current_utc": planner_context.current_utc.isoformat(),
            "last_submolt_created_at_utc": planner_context.last_submolt_created_at_utc.isoformat() if planner_context.last_submolt_created_at_utc else None,
            "hours_since_last_submolt_creation": planner_context.hours_since_last_submolt_creation,
            "recent_submolt_titles": list(planner_context.recent_submolt_titles),
            "source_item_id": planner_context.source_item_id,
            "source_item_type": planner_context.source_item_type,
            "source_post_id": planner_context.source_post_id,
            "source_submolt_name": planner_context.source_submolt_name,
            "source_item_summary": planner_context.source_item_summary,
            "policy": {
                "interval_hours": policy.interval_hours,
                "max_creations_per_day": policy.max_creations_per_day,
                "topic_policy": policy.topic_policy,
                "allowed_topics": list(policy.allowed_topics),
                "name_prefix": policy.name_prefix,
                "allow_crypto": policy.allow_crypto,
            },
        }
        return (
            "Submolt planner request.\n"
            f"Context JSON:\n{json.dumps(context_payload, ensure_ascii=True)}\n\n"
            f"Behavior Submolt Prompt:\n{behavior_prompt}\n"
        )

    def _execute_submolt_planner_plan(
        self,
        *,
        handle: str,
        config: AgentConfig,
        policy: SubmoltPlannerPolicy,
        planner_context: SubmoltPlannerContext,
        planner_plan: SubmoltPlannerPlan,
        source_trigger: str,
        execution_options: HeartbeatExecutionOptions,
    ) -> SubmoltPlannerEvaluationResult:
        """Execute planner side effects and persist automation events."""
        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.PLANNER_EVALUATED,
                handle=handle,
                planner_status="evaluated",
                planner_reason=planner_plan.decision_rationale,
                planner_trigger=source_trigger,
                dry_run=execution_options.dry_run_actions,
            ),
        )

        if not planner_plan.should_create_submolt:
            reason = "planner-declined-create"
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_skip",
                source_trigger=source_trigger,
                status=AutomationEventStatus.SKIPPED,
                source_item_id=planner_context.source_item_id,
                error_summary=reason,
            )
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=reason,
                    planner_trigger=source_trigger,
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.SKIPPED.value, reason=reason)

        normalized_submolt_name = self._normalize_planned_submolt_name(planner_plan.submolt_name, policy.name_prefix)
        if not normalized_submolt_name:
            reason = "invalid-submolt-name"
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_failed",
                source_trigger=source_trigger,
                status=AutomationEventStatus.FAILED,
                source_item_id=planner_context.source_item_id,
                error_summary=reason,
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.FAILED.value, reason=reason)

        guard_failure_reason = self._evaluate_submolt_runtime_guards(
            handle=handle,
            policy=policy,
            planner_context=planner_context,
            requested_submolt_name=normalized_submolt_name,
            requested_display_name=planner_plan.display_name,
        )
        if guard_failure_reason is not None:
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_skip",
                source_trigger=source_trigger,
                status=AutomationEventStatus.SKIPPED,
                source_item_id=planner_context.source_item_id,
                error_summary=guard_failure_reason,
            )
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_SKIPPED,
                    handle=handle,
                    planner_status=AutomationEventStatus.SKIPPED.value,
                    planner_reason=guard_failure_reason,
                    planner_trigger=source_trigger,
                    dry_run=execution_options.dry_run_actions,
                ),
            )
            return SubmoltPlannerEvaluationResult(
                acted=False,
                status=AutomationEventStatus.SKIPPED.value,
                reason=guard_failure_reason,
            )

        if execution_options.dry_run_actions:
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_ACTED,
                    handle=handle,
                    planner_status="dry-run",
                    planner_reason=planner_plan.decision_rationale,
                    planner_trigger=source_trigger,
                    planner_submolt_name=normalized_submolt_name,
                    dry_run=True,
                ),
            )
            return SubmoltPlannerEvaluationResult(acted=True, status="dry-run", reason="dry-run")

        display_name = planner_plan.display_name or normalized_submolt_name.replace("-", " ").title()
        description = self._resolve_planned_submolt_description(planner_plan.description, display_name)
        effective_allow_crypto = bool(planner_plan.allow_crypto and policy.allow_crypto)

        created_submolt_name: str | None = None
        created_post_id: str | None = None
        try:
            submolt_response = self._create_planned_submolt_with_retry(
                api_key=config.agent.api_key,
                submolt_name=normalized_submolt_name,
                display_name=display_name,
                description=description,
                allow_crypto=effective_allow_crypto,
            )
            created_submolt_name = submolt_response.name
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="create_submolt",
                source_trigger=source_trigger,
                status=AutomationEventStatus.SUCCESS,
                submolt_name=created_submolt_name,
                submolt_display_name=display_name,
                source_item_id=planner_context.source_item_id,
            )
        except (MoltbookAPIError, ValueError) as exc:
            reason = self._format_submolt_create_failure_reason(exc)
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="create_submolt",
                source_trigger=source_trigger,
                status=AutomationEventStatus.FAILED,
                submolt_name=normalized_submolt_name,
                submolt_display_name=display_name,
                source_item_id=planner_context.source_item_id,
                error_summary=reason,
            )
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.PLANNER_FAILED,
                    handle=handle,
                    planner_status=AutomationEventStatus.FAILED.value,
                    planner_reason=reason,
                    planner_trigger=source_trigger,
                    planner_submolt_name=normalized_submolt_name,
                    dry_run=False,
                ),
            )
            return SubmoltPlannerEvaluationResult(acted=False, status=AutomationEventStatus.FAILED.value, reason=reason)

        target_submolt_name = created_submolt_name or normalized_submolt_name
        if planner_plan.should_post:
            if not planner_plan.post_title:
                reason = "planner-post-missing-title"
                automation_log_store.write_automation_event(
                    self._base_path,
                    handle,
                    event_type="create_post",
                    source_trigger=source_trigger,
                    status=AutomationEventStatus.FAILED,
                    submolt_name=target_submolt_name,
                    source_item_id=planner_context.source_item_id,
                    error_summary=reason,
                )
            else:
                try:
                    post_response = self._post_service.create_post(
                        config.agent.api_key,
                        target_submolt_name,
                        planner_plan.post_title,
                        content=planner_plan.post_content,
                        url=planner_plan.post_url,
                    )
                    created_post_id = post_response.id
                    automation_log_store.write_automation_event(
                        self._base_path,
                        handle,
                        event_type="create_post",
                        source_trigger=source_trigger,
                        status=AutomationEventStatus.SUCCESS,
                        submolt_name=target_submolt_name,
                        post_id=created_post_id,
                        source_item_id=planner_context.source_item_id,
                    )
                except (MoltbookAPIError, ValueError) as exc:
                    automation_log_store.write_automation_event(
                        self._base_path,
                        handle,
                        event_type="create_post",
                        source_trigger=source_trigger,
                        status=AutomationEventStatus.FAILED,
                        submolt_name=target_submolt_name,
                        source_item_id=planner_context.source_item_id,
                        error_summary=f"create-post-failed: {exc}",
                    )

        if (
            source_trigger == "reactive"
            and planner_plan.should_link_in_followup_reply
            and planner_plan.followup_reply_text
            and planner_context.source_post_id
        ):
            self._post_planner_followup_reply(
                api_key=config.agent.api_key,
                planner_context=planner_context,
                planner_plan=planner_plan,
                submolt_name=target_submolt_name,
                created_post_id=created_post_id,
            )

        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.PLANNER_ACTED,
                handle=handle,
                planner_status=AutomationEventStatus.SUCCESS.value,
                planner_reason=planner_plan.decision_rationale,
                planner_trigger=source_trigger,
                planner_submolt_name=target_submolt_name,
                planner_post_id=created_post_id,
                dry_run=False,
            ),
        )
        return SubmoltPlannerEvaluationResult(acted=True, status=AutomationEventStatus.SUCCESS.value, reason="planner-acted")

    def _post_planner_followup_reply(
        self,
        *,
        api_key: str,
        planner_context: SubmoltPlannerContext,
        planner_plan: SubmoltPlannerPlan,
        submolt_name: str,
        created_post_id: str | None,
    ) -> None:
        """Post optional reactive follow-up reply referencing created submolt/post."""
        if planner_context.source_post_id is None or planner_plan.followup_reply_text is None:
            return

        followup_url = f"{MOLTBOOK_WEB_BASE_URL}/s/{submolt_name}"
        if created_post_id:
            followup_url = f"{MOLTBOOK_WEB_BASE_URL}/post/{created_post_id}"

        followup_text = f"{planner_plan.followup_reply_text}\n\n{followup_url}"
        try:
            self._api.add_comment(
                api_key,
                planner_context.source_post_id,
                followup_text[:MAX_ACTION_REPLY_CHARACTERS],
                parent_id=planner_context.source_item_id if planner_context.source_item_type == "comment" else None,
            )
        except MoltbookAPIError:
            logger.warning("Reactive follow-up reply failed for source item '%s'.", planner_context.source_item_id)

    def _normalize_planned_submolt_name(self, raw_name: str | None, name_prefix: str | None) -> str | None:
        """Normalize planner-provided submolt names to API-safe slug format."""
        if raw_name is None:
            return None
        normalized = self._normalize_submolt_slug(raw_name)
        if name_prefix:
            prefix = self._normalize_submolt_slug(name_prefix)
            if prefix and not normalized.startswith(f"{prefix}-"):
                normalized = f"{prefix}-{normalized}" if normalized else prefix

        normalized = normalized[:SUBMOLT_NAME_MAX_LENGTH].strip("-")
        if len(normalized) < SUBMOLT_NAME_MIN_LENGTH:
            return None
        if not SUBMOLT_NAME_PATTERN.match(normalized):
            return None

        return normalized or None

    def _normalize_submolt_slug(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
        return re.sub(r"-{2,}", "-", normalized).strip("-")

    def _resolve_planned_submolt_description(self, raw_description: str | None, display_name: str) -> str:
        if raw_description is not None and raw_description.strip():
            return raw_description.strip()
        return f"A community for {display_name} discussions."

    def _create_planned_submolt_with_retry(
        self,
        *,
        api_key: str,
        submolt_name: str,
        display_name: str,
        description: str,
        allow_crypto: bool,
    ):
        last_error: MoltbookAPIError | None = None
        attempted_names: set[str] = set()
        name_candidates = (submolt_name, self._build_retry_submolt_name(submolt_name))

        for candidate_name in name_candidates:
            if not candidate_name or candidate_name in attempted_names:
                continue
            attempted_names.add(candidate_name)

            try:
                return self._submolt_service.create_submolt(
                    api_key,
                    candidate_name,
                    display_name,
                    description=description,
                    allow_crypto=allow_crypto,
                )
            except MoltbookAPIError as exc:
                last_error = exc
                if candidate_name != submolt_name or not self._is_retryable_submolt_create_error(exc):
                    raise

        if last_error is not None:
            raise last_error
        raise MoltbookAPIError(message="Failed to create submolt.")

    def _build_retry_submolt_name(self, base_name: str) -> str:
        suffix = datetime.now(timezone.utc).strftime("%m%d%H%M")
        max_base_length = SUBMOLT_NAME_MAX_LENGTH - len(suffix) - 1
        trimmed_base = base_name[:max_base_length].strip("-")
        if len(trimmed_base) < SUBMOLT_NAME_MIN_LENGTH:
            trimmed_base = "community"
        return f"{trimmed_base}-{suffix}"

    def _is_retryable_submolt_create_error(self, error: MoltbookAPIError) -> bool:
        if error.status_code in {400, 409}:
            return True

        message = error.message.strip().lower()
        return any(token in message for token in RETRYABLE_SUBMOLT_ERROR_TOKENS)

    def _format_submolt_create_failure_reason(self, error: MoltbookAPIError | ValueError) -> str:
        if isinstance(error, ValueError):
            return f"create-submolt-failed: {error}"

        details = error.message
        if error.hint:
            details = f"{details} (hint: {error.hint})"
        if error.status_code is not None:
            details = f"{details} [status={error.status_code}]"
        return f"create-submolt-failed: {details}"

    def _process_pending_action_backlog(
        self,
        *,
        handle: str,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        behavior_prompt: str | None,
        action_system_prompt: str | None,
        execution_options: HeartbeatExecutionOptions,
    ) -> bool:
        """Retry action execution for persisted pending-action queue items.

        Returns:
            True when at least one pending item was acted on; otherwise False.
        """
        pending_items = automation_store.list_pending_action_items_oldest(self._base_path, handle)
        if not pending_items:
            return False

        search_service = SearchService(api_client=self._api)
        for pending_item in pending_items:
            post_id = self._resolve_post_id(pending_item)
            if post_id is None:
                logger.warning(
                    "Pending-action item '%s' for '%s' is missing post context.",
                    pending_item.item_id,
                    handle,
                )
                continue

            content_text = search_service.get_queue_item_content(
                config.agent.api_key,
                pending_item.item_type,
                pending_item.item_id,
                post_id,
            )
            if content_text is None or not content_text.strip():
                logger.info(
                    "Pending-action item '%s' for '%s' skipped because content is unavailable.",
                    pending_item.item_id,
                    handle,
                )
                continue

            outcome = self._execute_action_for_relevant_item(
                handle=handle,
                config=config,
                item=pending_item,
                post_id=post_id,
                content_text=content_text,
                provider_config=provider_config,
                behavior_prompt=behavior_prompt,
                action_system_prompt=action_system_prompt,
                analysis_rationale=pending_item.relevance_rationale or "pending-action-retry",
                execution_options=execution_options,
            )
            if outcome == ItemProcessingOutcome.ACTED:
                return True

        return False

    def _search_and_enqueue(self, handle: str, config: AgentConfig) -> automation_store.InsertItemsResult:
        """Search for new content and insert into the queue.

        Args:
            handle: The agent's handle.
            config: The loaded AgentConfig.
        """
        search_service = SearchService(api_client=self._api)
        search_query = config.automation.search_query

        if not search_query:
            logger.warning("No search query configured for '%s'.", handle)
            return automation_store.InsertItemsResult(total=0, posts=0, comments=0)

        response = search_service.search(config.agent.api_key, search_query, search_type="all", limit=50)

        now = datetime.now(timezone.utc)
        queue_items: list[QueueItem] = []
        for result in response.results:
            if result.type not in SUPPORTED_QUEUE_ITEM_TYPES:
                continue

            queue_items.append(
                QueueItem(
                    item_id=result.id,
                    item_type=result.type,
                    post_id=result.post_id,
                    submolt_name=result.submolt.name if result.submolt else None,
                    author_name=result.author.name,
                    created_at=now,
                )
            )

        inserted = automation_store.insert_items(self._base_path, handle, queue_items)
        logger.info(
            "Inserted %d new items (posts=%d comments=%d) from %d search results for '%s'.",
            inserted.total,
            inserted.posts,
            inserted.comments,
            len(response.results),
            handle,
        )
        return inserted

    def _analyze_item(
        self,
        handle: str,
        config: AgentConfig,
        item: QueueItem,
        *,
        provider_config: LLMProviderConfig,
        filter_prompt: str | None,
        behavior_prompt: str | None,
        analysis_system_prompt: str | None,
        action_system_prompt: str | None,
        execution_options: HeartbeatExecutionOptions,
    ) -> ItemProcessingOutcome:
        """Analyze a single queue item and update its status.

        Args:
            handle: The agent's handle.
            config: The loaded AgentConfig.
            item: The unanalyzed QueueItem to process.

        Returns:
            Per-item outcome for heartbeat loop control.
        """
        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.ANALYSIS_STARTED,
                handle=handle,
                item_id=item.item_id,
                item_type=item.item_type,
                dry_run=execution_options.dry_run_actions,
            ),
        )

        if item.item_type not in SUPPORTED_QUEUE_ITEM_TYPES:
            rationale = "unsupported-item-type"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            logger.warning(
                "Skipped unsupported queue item type '%s' for '%s' (%s).",
                item.item_type,
                handle,
                item.item_id,
            )
            return ItemProcessingOutcome.IRRELEVANT

        post_id = self._resolve_post_id(item)
        if post_id is None:
            rationale = "missing-post-context"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            logger.warning("Queue item '%s' missing post context for '%s'.", item.item_id, handle)
            return ItemProcessingOutcome.IRRELEVANT

        if filter_prompt is None:
            rationale = "missing-filter-prompt"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            logger.warning("Missing or empty filter prompt for '%s'.", handle)
            return ItemProcessingOutcome.IRRELEVANT

        if analysis_system_prompt is None:
            rationale = "missing-filter-system-prompt"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            logger.warning("Missing or empty FILTER_SYS.md in client root for '%s'.", handle)
            return ItemProcessingOutcome.IRRELEVANT

        search_service = SearchService(api_client=self._api)
        content_text = search_service.get_queue_item_content(
            config.agent.api_key,
            item.item_type,
            item.item_id,
            post_id,
        )
        if content_text is None or not content_text.strip():
            rationale = "content-unavailable"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            logger.info(
                "Item '%s' for '%s' marked not relevant due to unavailable content.",
                item.item_id,
                handle,
            )
            return ItemProcessingOutcome.IRRELEVANT

        analysis_decision = self._run_analysis_stage(
            config=config,
            provider_config=provider_config,
            handle=handle,
            item=item,
            content_text=content_text,
            filter_prompt=filter_prompt,
            system_prompt=analysis_system_prompt,
        )
        if analysis_decision is None:
            rationale = "analysis-stage-failed"
            self._finalize_item(handle, item.item_id, is_relevant=False, relevance_rationale=rationale)
            self._emit_analysis_completion(execution_options, handle, item, is_relevant=False, relevance_rationale=rationale)
            return ItemProcessingOutcome.IRRELEVANT

        if not analysis_decision.is_relevant:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=False,
                relevance_rationale=analysis_decision.relevance_rationale,
            )
            self._emit_analysis_completion(
                execution_options,
                handle,
                item,
                is_relevant=False,
                relevance_rationale=analysis_decision.relevance_rationale,
            )
            logger.info("Item '%s' marked not relevant for '%s'.", item.item_id, handle)
            return ItemProcessingOutcome.IRRELEVANT

        self._emit_analysis_completion(
            execution_options,
            handle,
            item,
            is_relevant=True,
            relevance_rationale=analysis_decision.relevance_rationale,
        )

        return self._execute_action_for_relevant_item(
            handle=handle,
            config=config,
            item=item,
            post_id=post_id,
            content_text=content_text,
            provider_config=provider_config,
            behavior_prompt=behavior_prompt,
            action_system_prompt=action_system_prompt,
            analysis_rationale=analysis_decision.relevance_rationale,
            execution_options=execution_options,
        )

    def _execute_action_for_relevant_item(
        self,
        *,
        handle: str,
        config: AgentConfig,
        item: QueueItem,
        post_id: str,
        content_text: str,
        provider_config: LLMProviderConfig,
        behavior_prompt: str | None,
        action_system_prompt: str | None,
        analysis_rationale: str,
        execution_options: HeartbeatExecutionOptions,
    ) -> ItemProcessingOutcome:
        """Execute action stage for an item already classified as relevant."""
        resolved_author_name = self._resolve_queue_item_author_name(
            api_key=config.agent.api_key,
            item=item,
            post_id=post_id,
        )
        if resolved_author_name is None:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale="author-unresolved",
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=None,
                reply_text=None,
                upvote_requested=False,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=None,
                upvote_target_id=None,
                upvote_error="author-unresolved",
                dry_run=execution_options.dry_run_actions,
            )
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        if self._is_self_authored_target(handle=handle, author_name=resolved_author_name):
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale="self-authored-item",
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=None,
                reply_text=None,
                upvote_requested=False,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=None,
                upvote_target_id=None,
                upvote_error="self-authored-item",
                dry_run=execution_options.dry_run_actions,
            )
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        if behavior_prompt is None:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
            )
            logger.warning("Missing or empty behavior prompt for '%s'.", handle)
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        if action_system_prompt is None:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
            )
            logger.warning("Missing or empty ACTION_SYS.md in client root for '%s'.", handle)
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        action_plan = self._run_action_stage(
            config=config,
            provider_config=provider_config,
            handle=handle,
            item=item,
            content_text=content_text,
            behavior_prompt=behavior_prompt,
            analysis_rationale=analysis_rationale,
            system_prompt=action_system_prompt,
        )
        if action_plan is None:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=None,
                reply_text=None,
                upvote_requested=False,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=None,
                upvote_target_id=None,
                upvote_error="action-stage-failed",
                dry_run=execution_options.dry_run_actions,
            )
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        reply_text = self._normalize_reply_text(action_plan)
        if reply_text is None:
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=None,
                reply_text=None,
                upvote_requested=action_plan.upvote,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=None,
                upvote_target_id=None,
                upvote_error="empty-reply-text",
                dry_run=execution_options.dry_run_actions,
            )
            logger.info("Item '%s' produced empty reply text for '%s'.", item.item_id, handle)
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        parent_id = item.item_id if item.item_type == "comment" else None
        upvote_target = self._resolve_upvote_target(item=item, post_id=post_id)
        upvote_target_type = upvote_target[0] if upvote_target else None
        upvote_target_id = upvote_target[1] if upvote_target else None

        if execution_options.dry_run_actions:
            dry_target_comment_id = item.item_id if item.item_type == "comment" else None
            target_url = self._build_comment_target_url(post_id, dry_target_comment_id)
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
                replied_item_id=DRY_RUN_REPLIED_ITEM_ID,
            )
            self._emit_heartbeat_event(
                execution_options,
                HeartbeatEvent(
                    event_type=HeartbeatEventType.ACTION_DRY_RUN,
                    handle=handle,
                    item_id=item.item_id,
                    item_type=item.item_type,
                    response_text=reply_text,
                    target_url=target_url,
                    upvote_requested=action_plan.upvote,
                    upvote_target_type=upvote_target_type,
                    upvote_target_id=upvote_target_id,
                    dry_run=True,
                ),
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=DRY_RUN_REPLIED_ITEM_ID,
                reply_text=reply_text,
                upvote_requested=action_plan.upvote,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=upvote_target_type,
                upvote_target_id=upvote_target_id,
                upvote_error="dry-run",
                dry_run=True,
            )
            self._maybe_execute_reactive_submolt_planner(
                handle=handle,
                config=config,
                provider_config=provider_config,
                item=item,
                action_plan=action_plan,
                source_item_summary=content_text,
                execution_options=execution_options,
            )
            return ItemProcessingOutcome.ACTED

        try:
            raw_response = self._api.add_comment(
                config.agent.api_key,
                post_id,
                reply_text,
                parent_id=parent_id,
            )
        except MoltbookAPIError as exc:
            logger.exception(
                "Failed to post automation reply for item '%s' on '%s'.",
                item.item_id,
                handle,
            )
            self._finalize_item(
                handle,
                item.item_id,
                is_relevant=True,
                relevance_rationale=analysis_rationale,
            )
            self._write_action_outcome_log(
                handle=handle,
                item_id=item.item_id,
                replied_item_id=None,
                reply_text=reply_text,
                upvote_requested=action_plan.upvote,
                upvote_attempted=False,
                upvote_performed=False,
                upvote_target_type=upvote_target_type,
                upvote_target_id=upvote_target_id,
                upvote_error=f"reply-post-failed: {exc.message}",
                dry_run=False,
            )
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        replied_item_id = self._extract_reply_item_id(raw_response)
        target_url = self._build_comment_target_url(post_id, replied_item_id)
        self._finalize_item(
            handle,
            item.item_id,
            is_relevant=True,
            relevance_rationale=analysis_rationale,
            replied_item_id=replied_item_id,
        )

        upvote_message: str | None = None
        upvote_error: str | None = None
        upvote_attempted = False
        upvote_performed = False
        if action_plan.upvote and upvote_target_type and upvote_target_id:
            upvote_attempted = True
            try:
                upvote_message = self._upvote_acted_item(
                    api_key=config.agent.api_key,
                    target_type=upvote_target_type,
                    target_id=upvote_target_id,
                )
                upvote_performed = True
            except MoltbookAPIError as exc:
                upvote_error = exc.message
                logger.warning(
                    "Failed to upvote automation target for item '%s' on '%s' (target_type=%s, target_id=%s): %s",
                    item.item_id,
                    handle,
                    upvote_target_type,
                    upvote_target_id,
                    exc.message,
                )
        elif action_plan.upvote:
            upvote_error = "target-resolution-failed"
            logger.warning(
                "Skipped automation upvote for item '%s' on '%s' because target resolution failed.",
                item.item_id,
                handle,
            )

        self._write_action_outcome_log(
            handle=handle,
            item_id=item.item_id,
            replied_item_id=replied_item_id,
            reply_text=reply_text,
            upvote_requested=action_plan.upvote,
            upvote_attempted=upvote_attempted,
            upvote_performed=upvote_performed,
            upvote_target_type=upvote_target_type,
            upvote_target_id=upvote_target_id,
            upvote_message=upvote_message,
            upvote_error=upvote_error,
            dry_run=False,
        )

        self._emit_heartbeat_event(
            execution_options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.ACTION_POSTED,
                handle=handle,
                item_id=item.item_id,
                item_type=item.item_type,
                response_text=reply_text,
                target_url=target_url,
                upvote_requested=action_plan.upvote,
                upvote_target_type=upvote_target_type,
                upvote_target_id=upvote_target_id,
                upvote_message=upvote_message,
                dry_run=False,
            ),
        )
        logger.info(
            "Posted automation reply for item '%s' on '%s' (reply=%s).",
            item.item_id,
            handle,
            replied_item_id or "unknown",
        )
        if replied_item_id is None:
            return ItemProcessingOutcome.RELEVANT_NOT_ACTED

        self._maybe_execute_reactive_submolt_planner(
            handle=handle,
            config=config,
            provider_config=provider_config,
            item=item,
            action_plan=action_plan,
            source_item_summary=content_text,
            execution_options=execution_options,
        )

        return ItemProcessingOutcome.ACTED

    def _maybe_execute_reactive_submolt_planner(
        self,
        *,
        handle: str,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        item: QueueItem,
        action_plan: ActionPlan,
        source_item_summary: str,
        execution_options: HeartbeatExecutionOptions,
    ) -> None:
        """Run reactive planner when the action stage requests submolt promotion."""
        if not action_plan.promote_to_submolt:
            return

        policy, parse_warning = self._refresh_submolt_policy(handle)
        if parse_warning:
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_policy_error",
                source_trigger="reactive",
                status=AutomationEventStatus.FAILED,
                source_item_id=item.item_id,
                error_summary=parse_warning,
            )
        if policy is None or not policy.enabled:
            return

        planner_context = self._build_submolt_planner_context(
            handle=handle,
            source_trigger="reactive",
            source_item=item,
            source_item_summary=source_item_summary,
        )
        guard_failure_reason = self._evaluate_submolt_runtime_guards(
            handle=handle,
            policy=policy,
            planner_context=planner_context,
            requested_submolt_name=None,
        )
        if guard_failure_reason is not None:
            automation_log_store.write_automation_event(
                self._base_path,
                handle,
                event_type="planner_skip",
                source_trigger="reactive",
                status=AutomationEventStatus.SKIPPED,
                source_item_id=item.item_id,
                error_summary=guard_failure_reason,
            )
            return

        planner_system_prompt = self._load_required_system_prompt(SUBMOLT_SYSTEM_PROMPT_NAME)
        planner_behavior_prompt = self._load_required_prompt(handle, BEHAVIOR_SUBMOLT_PROMPT_NAME)
        if planner_system_prompt is None or planner_behavior_prompt is None:
            return

        policy_override = policy
        if action_plan.promotion_topic:
            policy_override = SubmoltPlannerPolicy(
                enabled=policy.enabled,
                interval_hours=policy.interval_hours,
                max_creations_per_day=policy.max_creations_per_day,
                topic_policy=action_plan.promotion_topic,
                allowed_topics=policy.allowed_topics,
                name_prefix=policy.name_prefix,
                allow_crypto=policy.allow_crypto,
                policy_body=policy.policy_body,
            )

        planner_plan = self._run_submolt_planner_stage(
            config=config,
            provider_config=provider_config,
            handle=handle,
            planner_context=planner_context,
            policy=policy_override,
            behavior_prompt=planner_behavior_prompt,
            system_prompt=planner_system_prompt,
        )
        if planner_plan is None:
            return

        self._execute_submolt_planner_plan(
            handle=handle,
            config=config,
            policy=policy_override,
            planner_context=planner_context,
            planner_plan=planner_plan,
            source_trigger="reactive",
            execution_options=execution_options,
        )

    def _run_analysis_stage(
        self,
        *,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        handle: str,
        item: QueueItem,
        content_text: str,
        filter_prompt: str,
        system_prompt: str,
    ) -> AnalysisDecision | None:
        """Execute the analysis stage and return the parsed decision.

        Returns None for non-fatal per-item failures.
        """
        analysis_user_prompt = self._build_analysis_user_prompt(item, content_text, filter_prompt)
        analysis_prompt_payload = self._build_stage_prompt_payload(system_prompt, analysis_user_prompt)

        try:
            stage_result = self._llm_execution_service.analyze(
                config=config,
                provider_config=provider_config,
                system_prompt=system_prompt,
                user_prompt=analysis_user_prompt,
            )
            self._write_stage_log(
                handle=handle,
                item_id=item.item_id,
                stage="analysis",
                prompt_payload=analysis_prompt_payload,
                response_payload=stage_result.raw_response,
            )
            if not isinstance(stage_result.parsed_output, AnalysisDecision):
                logger.warning("Analysis stage returned unexpected output model for item '%s'.", item.item_id)
                return None
            return stage_result.parsed_output
        except LLMClientError as exc:
            self._write_stage_log(
                handle=handle,
                item_id=item.item_id,
                stage="analysis",
                prompt_payload=analysis_prompt_payload,
                response_payload=f"LLMClientError: {exc}",
            )
            if exc.reason_code in {"openai-auth-failed", "missing-provider-config", "provider-model-not-supported"}:
                raise ValueError(str(exc)) from exc

            logger.warning(
                "Analysis stage failed for item '%s': %s (%s)",
                item.item_id,
                exc,
                exc.reason_code,
            )
            return None

    def _build_comment_target_url(self, post_id: str, comment_id: str | None) -> str:
        """Build a full Moltbook URL for post/comment targeting display."""
        post_url = f"{MOLTBOOK_WEB_BASE_URL}/post/{post_id}"
        if comment_id:
            return f"{post_url}#comment-{comment_id}"
        return post_url

    def _resolve_upvote_target(self, *, item: QueueItem, post_id: str) -> tuple[str, str] | None:
        """Resolve which target should be upvoted for one action-stage decision."""
        if item.item_type == "post":
            return "post", post_id

        if item.item_type == "comment":
            return "comment", item.item_id

        return None

    def _upvote_acted_item(self, *, api_key: str, target_type: str, target_id: str) -> str | None:
        """Execute one upvote call for an acted item and return API message text when available."""
        response = self._post_service.upvote_target(api_key, target_type, target_id)
        return self._post_service.evaluate_upvote_response(response)

    def _emit_analysis_completion(
        self,
        options: HeartbeatExecutionOptions,
        handle: str,
        item: QueueItem,
        *,
        is_relevant: bool,
        relevance_rationale: str,
    ) -> None:
        """Emit one analysis completion event for monitor rendering."""
        self._emit_heartbeat_event(
            options,
            HeartbeatEvent(
                event_type=HeartbeatEventType.ANALYSIS_COMPLETED,
                handle=handle,
                item_id=item.item_id,
                item_type=item.item_type,
                is_relevant=is_relevant,
                relevance_rationale=relevance_rationale,
                dry_run=options.dry_run_actions,
            ),
        )

    def _emit_heartbeat_event(self, options: HeartbeatExecutionOptions, event: HeartbeatEvent) -> None:
        """Invoke observer callbacks for heartbeat progress when provided."""
        if options.observer is None:
            return

        options.observer(event)

    def _run_action_stage(
        self,
        *,
        config: AgentConfig,
        provider_config: LLMProviderConfig,
        handle: str,
        item: QueueItem,
        content_text: str,
        behavior_prompt: str,
        analysis_rationale: str,
        system_prompt: str,
    ) -> ActionPlan | None:
        """Execute the action stage and return the parsed action plan.

        Returns None for non-fatal per-item failures.
        """
        action_user_prompt = self._build_action_user_prompt(
            item=item,
            content_text=content_text,
            behavior_prompt=behavior_prompt,
            analysis_rationale=analysis_rationale,
        )
        action_prompt_payload = self._build_stage_prompt_payload(system_prompt, action_user_prompt)

        try:
            stage_result = self._llm_execution_service.generate_action(
                config=config,
                provider_config=provider_config,
                system_prompt=system_prompt,
                user_prompt=action_user_prompt,
            )
            self._write_stage_log(
                handle=handle,
                item_id=item.item_id,
                stage="action",
                prompt_payload=action_prompt_payload,
                response_payload=stage_result.raw_response,
            )
            if not isinstance(stage_result.parsed_output, ActionPlan):
                logger.warning("Action stage returned unexpected output model for item '%s'.", item.item_id)
                return None
            return stage_result.parsed_output
        except LLMClientError as exc:
            self._write_stage_log(
                handle=handle,
                item_id=item.item_id,
                stage="action",
                prompt_payload=action_prompt_payload,
                response_payload=f"LLMClientError: {exc}",
            )
            if exc.reason_code in {"openai-auth-failed", "missing-provider-config", "provider-model-not-supported"}:
                raise ValueError(str(exc)) from exc

            logger.warning(
                "Action stage failed for item '%s': %s (%s)",
                item.item_id,
                exc,
                exc.reason_code,
            )
            return None

    def _build_analysis_user_prompt(self, item: QueueItem, content_text: str, filter_prompt: str) -> str:
        """Build deterministic user prompt payload for analysis stage."""
        submolt_name = item.submolt_name or "unknown"
        return f"Automation analysis request.\nItem ID: {item.item_id}\nItem Type: {item.item_type}\nSubmolt: {submolt_name}\n\nFilter Prompt:\n{filter_prompt}\n\nItem Content:\n{content_text}"

    def _build_action_user_prompt(
        self,
        *,
        item: QueueItem,
        content_text: str,
        behavior_prompt: str,
        analysis_rationale: str,
    ) -> str:
        """Build deterministic user prompt payload for action stage."""
        submolt_name = item.submolt_name or "unknown"
        return (
            f"Automation action request.\nItem ID: {item.item_id}\nItem Type: {item.item_type}\nSubmolt: {submolt_name}\n"
            f"Analysis Rationale: {analysis_rationale}\n"
            "If this item should trigger reactive submolt promotion, set promote_to_submolt=true and provide promotion_topic.\n\n"
            f"Behavior Prompt:\n{behavior_prompt}\n\nItem Content:\n{content_text}"
        )

    def _build_stage_prompt_payload(self, system_prompt: str, user_prompt: str) -> str:
        """Serialize the exact stage prompt payload sent to the provider."""
        payload = {
            "instructions": system_prompt,
            "input": user_prompt,
        }
        return json.dumps(payload)

    def _write_stage_log(
        self,
        *,
        handle: str,
        item_id: str,
        stage: str,
        prompt_payload: str,
        response_payload: str,
    ) -> None:
        """Persist one stage prompt/response trace for audit-friendly dry testing."""
        try:
            automation_log_store.write_stage_log(
                self._base_path,
                handle,
                item_id=item_id,
                stage=stage,
                prompt_payload=prompt_payload,
                response_payload=response_payload,
            )
        except OSError:
            logger.exception("Failed to write %s stage log for item '%s' (%s).", stage, item_id, handle)

    def _write_action_outcome_log(
        self,
        *,
        handle: str,
        item_id: str,
        replied_item_id: str | None,
        reply_text: str | None,
        upvote_requested: bool,
        upvote_attempted: bool,
        upvote_performed: bool,
        upvote_target_type: str | None,
        upvote_target_id: str | None,
        upvote_message: str | None = None,
        upvote_error: str | None = None,
        dry_run: bool,
    ) -> None:
        """Persist action execution outcome details including upvote occurrence."""
        payload = {
            "replied_item_id": replied_item_id,
            "reply_text": reply_text,
            "upvote_requested": upvote_requested,
            "upvote_attempted": upvote_attempted,
            "upvote_performed": upvote_performed,
            "upvote_target_type": upvote_target_type,
            "upvote_target_id": upvote_target_id,
            "upvote_message": upvote_message,
            "upvote_error": upvote_error,
            "dry_run": dry_run,
        }
        self._write_stage_log(
            handle=handle,
            item_id=item_id,
            stage="action-outcome",
            prompt_payload=json.dumps({"source": "action-stage-outcome"}),
            response_payload=json.dumps(payload),
        )

    def _normalize_reply_text(self, action_plan: ActionPlan) -> str | None:
        """Normalize and bound action-stage reply text."""
        if not action_plan.reply_text:
            return None

        normalized = action_plan.reply_text.strip()
        if not normalized:
            return None

        return normalized[:MAX_ACTION_REPLY_CHARACTERS]

    def _compose_submolt_planner_system_prompt(
        self,
        *,
        system_prompt: str,
        policy: SubmoltPlannerPolicy,
        planner_context: SubmoltPlannerContext,
    ) -> str:
        """Compose runtime planner guardrail instructions with immutable constraints."""
        try:
            runtime_guardrail = (
                "\n\nRUNTIME GUARDRAILS (NON-OVERRIDABLE):\n"
                "- Treat this as strict policy.\n"
                "- Never propose duplicate or near-duplicate submolts.\n"
                "- Compare your proposal to recent_submolt_titles in Context JSON and decline duplicates.\n"
                "- Default allow_crypto to false.\n"
                f"- Policy allow_crypto is currently {str(policy.allow_crypto).lower()}; set allow_crypto=true only when this value is true and the plan explicitly requires it.\n"
                "- If cadence is not satisfied or confidence is low, set should_create_submolt=false.\n"
                f"- Recent submolt titles count: {len(planner_context.recent_submolt_titles)}.\n"
            )
            return f"{system_prompt.strip()}{runtime_guardrail}"
        except Exception:
            logger.warning("Failed to compose runtime submolt planner guardrails; using base system prompt.")
            return system_prompt

    def _resolve_queue_item_author_name(self, *, api_key: str, item: QueueItem, post_id: str) -> str | None:
        """Resolve queue-item author with persisted metadata first and API fallback second."""
        if item.author_name and item.author_name.strip():
            return item.author_name.strip()

        search_service = SearchService(api_client=self._api)
        return search_service.get_queue_item_author_name(api_key, item.item_type, item.item_id, post_id)

    def _is_self_authored_target(self, *, handle: str, author_name: str) -> bool:
        """Return True when a target author resolves to the current handle."""
        return handle.strip().lower() == author_name.strip().lower()

    def _extract_reply_item_id(self, response: dict[str, object]) -> str | None:
        """Extract reply item ID from Moltbook add-comment response payload."""
        comment_payload = response.get("comment", response)
        if isinstance(comment_payload, dict):
            raw_id = comment_payload.get("id")
            if isinstance(raw_id, str) and raw_id.strip():
                return raw_id.strip()
        return None

    def _resolve_post_id(self, item: QueueItem) -> str | None:
        """Resolve canonical post_id for queue item processing."""
        if item.item_type == "post":
            return item.post_id or item.item_id

        if item.item_type == "comment":
            return item.post_id

        return None

    def _load_required_prompt(self, handle: str, prompt_name: str) -> str | None:
        """Load a required prompt file and return None when unavailable/empty."""
        try:
            prompt_text = prompt_store.read_prompt(self._base_path, handle, prompt_name)
        except FileNotFoundError:
            return None

        normalized = prompt_text.strip()
        if len(normalized) < MIN_REQUIRED_PROMPT_CHARACTERS:
            return None

        return normalized

    def _load_required_system_prompt(self, prompt_name: str) -> str | None:
        """Load a required client-root system prompt and return None when unavailable/empty."""
        try:
            prompt_text = system_prompt_store.read_system_prompt(self._base_path, prompt_name)
        except FileNotFoundError:
            return None

        normalized = prompt_text.strip()
        if len(normalized) < MIN_REQUIRED_PROMPT_CHARACTERS:
            return None

        return normalized

    def _finalize_item(
        self,
        handle: str,
        item_id: str,
        *,
        is_relevant: bool,
        relevance_rationale: str | None = None,
        replied_item_id: str | None = None,
    ) -> None:
        """Persist queue outcome for one processed item."""
        automation_store.update_item_analysis(
            self._base_path,
            handle,
            item_id,
            is_relevant=is_relevant,
            relevance_rationale=relevance_rationale,
            replied_item_id=replied_item_id,
        )

    def _persist_heartbeat_timestamp(self, config: AgentConfig) -> None:
        """Persist heartbeat completion timestamp for one cycle."""
        config.automation.last_heartbeat_at = datetime.now(timezone.utc)
        agent_store.save_agent_config(self._base_path, config)

    def _validate_stage_selection(self, stage: AutomationStage, stage_config: StageLLMConfig) -> None:
        """Validate one stage's provider/model selection.

        Args:
            stage: Stage being validated.
            stage_config: Selected provider and model for the stage.

        Raises:
            ValueError: If model/provider selection is invalid.
        """
        try:
            self._llm_provider_service.validate_stage_model(stage_config.provider, stage_config.model)
        except ValueError as exc:
            raise ValueError(f"Invalid LLM setup for {stage.value} stage: {exc}") from exc

    def _collect_required_providers(self, llm_config: AutomationLLM) -> set[LLMProvider]:
        """Collect the distinct providers required by configured automation stages."""
        return {
            llm_config.analysis.provider,
            llm_config.action.provider,
            llm_config.submolt_planner.provider,
        }

    def _validate_required_provider_config(
        self,
        required_providers: set[LLMProvider],
        provider_config: LLMProviderConfig,
    ) -> None:
        """Validate that required providers have usable global config."""
        if LLMProvider.OPENAI in required_providers and not provider_config.openai.api_key:
            raise ValueError(f"OpenAI API key is required for the selected LLM stage provider. Run '{CLI_NAME} automation setup' to complete automation setup.")

        if LLMProvider.OPENAI in required_providers and provider_config.openai.max_output_tokens < 1:
            raise ValueError(f"OpenAI max output tokens must be > 0. Run '{CLI_NAME} automation setup' to complete automation setup.")

    def _load_global_provider_config(self) -> LLMProviderConfig:
        """Load global provider config from client.json."""
        try:
            client_config = load_client_config(self._base_path)
        except FileNotFoundError as exc:
            raise ValueError(f"No client.json found. Run '{CLI_NAME} init' first.") from exc
        except ValueError as exc:
            raise ValueError(f"client.json is corrupted. Fix it or rerun '{CLI_NAME} init'.") from exc

        return client_config.llm_provider_config

    def _validate_required_prompt_files(self, handle: str) -> None:
        """Validate required client-root and per-agent prompt files."""
        missing_or_short: list[str] = []

        for prompt_name in (ANALYSIS_SYSTEM_PROMPT_NAME, ACTION_SYSTEM_PROMPT_NAME):
            prompt_filename = system_prompt_store.get_system_prompt_filename(prompt_name)
            try:
                system_prompt_text = system_prompt_store.read_system_prompt(self._base_path, prompt_name)
            except FileNotFoundError:
                missing_or_short.append(prompt_filename)
                continue

            if len(system_prompt_text.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
                missing_or_short.append(prompt_filename)

        for prompt_name in ("filter", "behavior"):
            try:
                content = prompt_store.read_prompt(self._base_path, handle, prompt_name)
            except FileNotFoundError:
                missing_or_short.append(f"{prompt_name}.md")
                continue

            if len(content.strip()) < MIN_REQUIRED_PROMPT_CHARACTERS:
                missing_or_short.append(f"{prompt_name}.md")

        if missing_or_short:
            file_list = ", ".join(missing_or_short)
            raise ValueError(
                "Automation configuration is incomplete for "
                f"'{handle}': {file_list} must each contain at least "
                f"{MIN_REQUIRED_PROMPT_CHARACTERS} characters. "
                f"Run '{CLI_NAME} init' to restore FILTER_SYS.md/ACTION_SYS.md and "
                f"run '{CLI_NAME} automation setup' to complete per-agent prompts."
            )
