"""File I/O for client-root automation system prompt files.

System prompt files live in the initialized client workspace root (next to
`client.json`) and define stage-level response contracts and guardrails.
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT_FILENAMES: dict[str, str] = {
    "filter": "FILTER_SYS.md",
    "action": "ACTION_SYS.md",
    "submolt_planner": "SUBMOLT_PLANNER_SYS.md",
}

DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "filter": (
        "You are an analysis classifier. Return ONLY valid minified JSON with keys: is_relevant (boolean), relevance_rationale (string). relevance_rationale must be at most 120 characters. Do NOT use markdown fences (```) and do not include any prose."
    ),
    "action": (
        "You are an action planner for social replies. Return ONLY valid minified JSON with keys: "
        "reply_text (string), upvote (boolean), promote_to_submolt (boolean), promotion_topic (string|null). "
        "Set upvote=true only when you want to upvote the same item you are replying to. "
        "Set promote_to_submolt=true only when this item should trigger reactive submolt planning. "
        "Never request downvotes. Do NOT use markdown fences (```) and do not include any prose."
    ),
    "submolt_planner": (
        "You are a planner for autonomous submolt operations. Return ONLY valid minified JSON with keys: "
        "should_create_submolt (boolean), submolt_name (string|null), display_name (string|null), "
        "description (string|null), allow_crypto (boolean), should_post (boolean), "
        "post_title (string|null), post_content (string|null), post_url (string|null), "
        "should_link_in_followup_reply (boolean), followup_reply_text (string|null), "
        "decision_rationale (string). Avoid duplicate or near-duplicate submolt ideas, treat crypto as disallowed by default, "
        "and only set allow_crypto=true when behavior policy explicitly allows it. "
        "Do NOT use markdown fences (```) and do not include any prose."
    ),
}


def _normalize_prompt_name(prompt_name: str) -> str:
    """Normalize and validate one system prompt selector."""
    normalized = prompt_name.strip().lower()
    if normalized not in SYSTEM_PROMPT_FILENAMES:
        supported = ", ".join(sorted(SYSTEM_PROMPT_FILENAMES))
        raise ValueError(f"Unsupported system prompt '{prompt_name}'. Supported: {supported}.")

    return normalized


def get_system_prompt_filename(prompt_name: str) -> str:
    """Return the filename for one system prompt selector."""
    normalized = _normalize_prompt_name(prompt_name)
    return SYSTEM_PROMPT_FILENAMES[normalized]


def get_system_prompt_path(base_path: Path, prompt_name: str) -> Path:
    """Return absolute path for one client-root system prompt file."""
    return base_path / get_system_prompt_filename(prompt_name)


def read_system_prompt(base_path: Path, prompt_name: str) -> str:
    """Read one system prompt file from client root."""
    return get_system_prompt_path(base_path, prompt_name).read_text(encoding="utf-8")


def ensure_system_prompt_file(base_path: Path, prompt_name: str) -> Path:
    """Ensure one client-root system prompt file exists with default content."""
    normalized = _normalize_prompt_name(prompt_name)
    prompt_path = get_system_prompt_path(base_path, normalized)
    if not prompt_path.is_file():
        prompt_path.write_text(DEFAULT_SYSTEM_PROMPTS[normalized].strip() + "\n", encoding="utf-8")

    return prompt_path


def ensure_system_prompt_files(base_path: Path) -> list[Path]:
    """Ensure all required client-root system prompt files exist."""
    return [ensure_system_prompt_file(base_path, prompt_name) for prompt_name in SYSTEM_PROMPT_FILENAMES]
