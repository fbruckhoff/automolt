"""Business logic for automation configuration and heartbeat execution.

Handles setting up automation for an agent, executing heartbeat cycles
that search for content, and managing the automation queue.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.constants import CLI_NAME
from automolt.models.agent import AgentConfig, AutomationLLM, AutomationStage, StageLLMConfig
from automolt.models.automation import QueueItem
from automolt.models.llm import ActionPlan, AnalysisDecision
from automolt.models.llm_provider import LLMProvider, LLMProviderConfig
from automolt.persistence import agent_store, automation_log_store, automation_store, prompt_store, system_prompt_store
from automolt.persistence.client_store import load_client_config
from automolt.services.base_llm_client import LLMClientError
from automolt.services.llm_execution_service import LLMExecutionService
from automolt.services.llm_provider_service import LLMProviderService
from automolt.services.post_service import PostService
from automolt.services.search_service import SearchService

logger = logging.getLogger(__name__)

SUPPORTED_QUEUE_ITEM_TYPES = {"post", "comment"}
MAX_ACTION_REPLY_CHARACTERS = 1000
DRY_RUN_REPLIED_ITEM_ID = "--dry"
MOLTBOOK_WEB_BASE_URL = "https://www.moltbook.com"
MIN_REQUIRED_PROMPT_CHARACTERS = 10
ANALYSIS_SYSTEM_PROMPT_NAME = "filter"
ACTION_SYSTEM_PROMPT_NAME = "action"


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


@dataclass(frozen=True)
class HeartbeatEvent:
    """Structured event payload for CLI monitoring output."""

    event_type: HeartbeatEventType
    handle: str
    search_query: str | None = None
    discovered_posts: int = 0
    discovered_comments: int = 0
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
    dry_run: bool = False


HeartbeatObserver = Callable[[HeartbeatEvent], None]


@dataclass(frozen=True)
class HeartbeatExecutionOptions:
    """Runtime options controlling one heartbeat cycle execution."""

    dry_run_actions: bool = False
    observer: HeartbeatObserver | None = None


class AutomationService:
    """Service for automation setup and heartbeat cycle execution."""

    def __init__(self, api_client: MoltbookClient, base_path: Path):
        self._api = api_client
        self._base_path = base_path
        self._post_service = PostService(api_client=api_client)
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
            ValueError: If search_query is empty or cutoff_days < 1.
        """
        if not search_query or not search_query.strip():
            raise ValueError("Search query cannot be empty.")
        if cutoff_days < 1:
            raise ValueError("Cutoff days must be at least 1.")
        self.validate_llm_config(llm_config)
        provider_config = self._load_global_provider_config()
        self._validate_required_provider_config(
            required_providers=self._collect_required_providers(llm_config),
            provider_config=provider_config,
        )

        config = agent_store.load_agent_config(self._base_path, handle)

        config.automation.search_query = search_query.strip()
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
            4. If no unanalyzed items exist: search + enqueue (deduped).
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

        search_inserted: automation_store.InsertItemsResult | None = None
        acted_this_cycle = False

        if not automation_store.has_unanalyzed(self._base_path, handle):
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
                    dry_run=execution_options.dry_run_actions,
                ),
            )

        provider_config: LLMProviderConfig | None = None
        filter_prompt: str | None = None
        behavior_prompt: str | None = None
        analysis_system_prompt: str | None = None
        action_system_prompt: str | None = None

        while True:
            next_item = automation_store.get_next_unanalyzed(self._base_path, handle)
            if next_item is None:
                break

            if provider_config is None:
                provider_config = self._load_global_provider_config()
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

        should_retry_pending_action = not acted_this_cycle and search_inserted is not None and search_inserted.total == 0
        if should_retry_pending_action:
            if provider_config is None:
                provider_config = self._load_global_provider_config()
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
                    created_at=now,
                )
            )

        inserted = automation_store.insert_items(self._base_path, handle, queue_items)
        logger.info(
            "Inserted %d new items (of %d search results) for '%s'.",
            inserted.total,
            len(queue_items),
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

        return ItemProcessingOutcome.ACTED

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
        return f"Automation action request.\nItem ID: {item.item_id}\nItem Type: {item.item_type}\nSubmolt: {submolt_name}\nAnalysis Rationale: {analysis_rationale}\n\nBehavior Prompt:\n{behavior_prompt}\n\nItem Content:\n{content_text}"

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
