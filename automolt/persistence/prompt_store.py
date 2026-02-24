"""File I/O for automation prompt files (FILTER.md, BEHAVIOR.md).

Handles reading and writing LLM instruction files stored alongside
agent.json in the agent's directory.
"""

import tempfile
from pathlib import Path


def get_prompt_path(base_path: Path, handle: str, prompt_name: str) -> Path:
    """Return the path to a prompt file.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: The prompt name, e.g. 'filter' or 'behavior'.

    Returns:
        The path to the prompt markdown file.
    """
    return base_path / ".agents" / handle / f"{prompt_name.upper()}.md"


def prompt_exists(base_path: Path, handle: str, prompt_name: str) -> bool:
    """Check whether a prompt file exists.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: The prompt name, e.g. 'filter' or 'behavior'.

    Returns:
        True if the prompt file exists.
    """
    return get_prompt_path(base_path, handle, prompt_name).is_file()


def read_prompt(base_path: Path, handle: str, prompt_name: str) -> str:
    """Read and return the contents of a prompt file.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: The prompt name, e.g. 'filter' or 'behavior'.

    Returns:
        The file contents as a string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompt_path = get_prompt_path(base_path, handle, prompt_name)
    return prompt_path.read_text(encoding="utf-8")


def read_prompt_source_file(source_path: Path) -> tuple[Path, str]:
    """Read and validate a source file used to populate a prompt.

    Args:
        source_path: User-provided source file path.

    Returns:
        Tuple of the resolved source path and file content.

    Raises:
        FileNotFoundError: If the source file does not exist.
        OSError: If the source file cannot be read.
        ValueError: If the source file has no non-whitespace content.
    """
    resolved_source_path = source_path.expanduser().resolve()
    if not resolved_source_path.is_file():
        raise FileNotFoundError(f"File not found: {resolved_source_path}")

    try:
        content = resolved_source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot read file: {exc}") from exc

    if not content.strip():
        raise ValueError("Source file is empty.")

    return resolved_source_path, content


def write_prompt(base_path: Path, handle: str, prompt_name: str, content: str) -> Path:
    """Write content to a prompt file using atomic write.

    Creates the file if it does not exist. Uses a temporary file and rename
    to prevent corruption if interrupted mid-write, consistent with
    agent_store.py.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: The prompt name, e.g. 'filter' or 'behavior'.
        content: The content to write.

    Returns:
        The path to the written file.
    """
    prompt_path = get_prompt_path(base_path, handle, prompt_name)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=prompt_path.parent, suffix=".tmp", prefix=f"{prompt_name}_")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(prompt_path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return prompt_path


def ensure_prompt_file(base_path: Path, handle: str, prompt_name: str) -> Path:
    """Create the prompt file with empty content if it does not exist.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        prompt_name: The prompt name, e.g. 'filter' or 'behavior'.

    Returns:
        The path to the file (existing or newly created).
    """
    prompt_path = get_prompt_path(base_path, handle, prompt_name)
    if not prompt_path.is_file():
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text("", encoding="utf-8")
    return prompt_path
