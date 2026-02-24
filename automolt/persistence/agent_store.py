"""File I/O for agent.json configuration files.

Handles creating agent directories under .agents/<handle> and
reading/writing AgentConfig models to disk.
"""

import json
import tempfile
from pathlib import Path

from automolt.models.agent import AgentConfig


def get_agents_dir(base_path: Path) -> Path:
    """Return the .agents/ directory path within the given base path."""
    return base_path / ".agents"


def get_agent_dir(base_path: Path, handle: str) -> Path:
    """Return the directory path for a specific agent."""
    return get_agents_dir(base_path) / handle


def get_agent_config_path(base_path: Path, handle: str) -> Path:
    """Return the path to an agent's agent.json file."""
    return get_agent_dir(base_path, handle) / "agent.json"


def agent_exists_locally(base_path: Path, handle: str) -> bool:
    """Check whether an agent directory with agent.json exists locally."""
    return get_agent_config_path(base_path, handle).is_file()


def save_agent_config(base_path: Path, config: AgentConfig) -> Path:
    """Write an AgentConfig to .agents/<handle>/agent.json atomically.

    Creates the agent directory if it does not exist. Writes to a temporary
    file first, then renames to prevent corruption if interrupted mid-write.

    Args:
        base_path: The root directory of the automolt client.
        config: The AgentConfig model to persist.

    Returns:
        The path to the written agent.json file.
    """
    agent_dir = get_agent_dir(base_path, config.agent.handle)
    agent_dir.mkdir(parents=True, exist_ok=True)

    config_path = agent_dir / "agent.json"
    content = json.dumps(config.model_dump(mode="json"), indent=2) + "\n"

    # Atomic write: write to temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(dir=agent_dir, suffix=".tmp", prefix="agent_")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(config_path)
        _harden_permissions(config_path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return config_path


def load_agent_config(base_path: Path, handle: str) -> AgentConfig:
    """Load an AgentConfig from .agents/<handle>/agent.json.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle (username).

    Returns:
        The parsed AgentConfig model.

    Raises:
        FileNotFoundError: If the agent.json file does not exist.
        ValueError: If the file contains invalid JSON or does not match the schema.
    """
    config_path = get_agent_config_path(base_path, handle)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        return AgentConfig.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Corrupted agent config for '{handle}': {exc}") from exc


def _harden_permissions(config_path: Path) -> None:
    """Apply restrictive file permissions for agent.json when supported.

    Args:
        config_path: Path to the agent configuration file.
    """
    try:
        config_path.chmod(0o600)
    except OSError:
        # Ignore platforms/filesystems where chmod semantics are unavailable.
        return
