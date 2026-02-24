"""File I/O for client.json configuration files.

Handles client-level configuration like the remembered last-active agent setting,
API timeout, and global LLM provider config.
"""

import json
import os
import tempfile
from pathlib import Path

from automolt.models.client import ClientConfig


def get_client_config_path(base_path: Path) -> Path:
    """Return the path to the client.json file."""
    return base_path / "client.json"


def load_client_config(base_path: Path) -> ClientConfig:
    """Load the client.json configuration.

    Args:
        base_path: The root directory of the automolt client.

    Returns:
        The parsed ClientConfig model.

    Raises:
        FileNotFoundError: If the client.json file does not exist.
        ValueError: If the file contains invalid JSON or does not match the schema.
    """
    config_path = get_client_config_path(base_path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        return ClientConfig.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Corrupted client config at '{config_path}': {exc}") from exc


def save_client_config(base_path: Path, config: ClientConfig) -> Path:
    """Write the client configuration to client.json atomically.

    Writes to a temporary file first, then renames to prevent corruption
    if the process is interrupted mid-write.

    Args:
        base_path: The root directory of the automolt client.
        config: The ClientConfig model to persist.

    Returns:
        The path to the written client.json file.
    """
    config_path = get_client_config_path(base_path)
    content = json.dumps(config.model_dump(mode="json", by_alias=True), indent=2) + "\n"

    # Atomic write: write to temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".tmp", prefix="client_")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(config_path)
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            # Best effort on platforms/filesystems that may not support chmod.
            pass
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return config_path


def set_last_active_agent(base_path: Path, handle: str) -> None:
    """Set the remembered last-active agent in client.json.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent handle to remember as last active.
    """
    try:
        config = load_client_config(base_path)
    except FileNotFoundError:
        # If client.json doesn't exist, create a default one
        config = ClientConfig()

    config.last_active_agent = handle
    save_client_config(base_path, config)


def get_last_active_agent(base_path: Path) -> str | None:
    """Get the remembered last-active agent from client.json.

    Args:
        base_path: The root directory of the automolt client.

    Returns:
        The remembered last-active agent handle, or None if not set.

    Raises:
        FileNotFoundError: If the client.json file does not exist.
    """
    config = load_client_config(base_path)
    return config.last_active_agent
