"""SQLite-backed persistence for the automation queue.

Manages the automation.db database per agent, tracking posts and comments
discovered via search for analysis and potential replies.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automolt.models.automation import QueueItem

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL,
    post_id TEXT,
    submolt_name TEXT,
    analyzed INTEGER NOT NULL DEFAULT 0,
    is_relevant INTEGER NOT NULL DEFAULT 0,
    relevance_rationale TEXT,
    replied_item_id TEXT,
    created_at TEXT NOT NULL
)
"""

POST_ID_COLUMN_NAME = "post_id"
RELEVANCE_RATIONALE_COLUMN_NAME = "relevance_rationale"


@dataclass(frozen=True)
class InsertItemsResult:
    """Breakdown of queue rows inserted during one search refill."""

    total: int
    posts: int
    comments: int


CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_items_analyzed
ON items (analyzed) WHERE analyzed = 0
"""

LIST_STATUS_WHERE_CLAUSES = {
    "pending-analysis": "WHERE analyzed = 0",
    "pending-action": "WHERE analyzed = 1 AND is_relevant = 1 AND replied_item_id IS NULL",
    "acted": "WHERE replied_item_id IS NOT NULL",
}

LIST_STATUS_QUERIES_WITH_LIMIT = {status: f"SELECT * FROM items {where_clause} ORDER BY created_at DESC LIMIT ?" for status, where_clause in LIST_STATUS_WHERE_CLAUSES.items()}

LIST_STATUS_QUERIES_NO_LIMIT = {status: f"SELECT * FROM items {where_clause} ORDER BY created_at DESC" for status, where_clause in LIST_STATUS_WHERE_CLAUSES.items()}


def get_db_path(base_path: Path, handle: str) -> Path:
    """Return the path to the automation SQLite database for an agent."""
    return base_path / ".agents" / handle / "automation.db"


def init_db(base_path: Path, handle: str) -> None:
    """Create the automation.db file and the items table + index if they do not exist.

    Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
    Must be called before any other store method for a given agent.
    """
    db_path = get_db_path(base_path, handle)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TABLE_SQL)
        _ensure_items_table_schema(conn)
        conn.execute(CREATE_INDEX_SQL)


def _ensure_items_table_schema(conn: sqlite3.Connection) -> None:
    """Apply lightweight schema migrations for the automation items table."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}

    if POST_ID_COLUMN_NAME not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN post_id TEXT")
        conn.execute("UPDATE items SET post_id = item_id WHERE item_type = 'post'")

    if RELEVANCE_RATIONALE_COLUMN_NAME not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN relevance_rationale TEXT")


def prune_old_items(base_path: Path, handle: str, cutoff_days: int) -> int:
    """Delete items older than cutoff_days that we did NOT act upon.

    Deletes items where replied_item_id IS NULL and created_at is older than
    the cutoff. This includes items analyzed as irrelevant. If the search API
    returns them again in a future cycle, they will be re-inserted and
    re-analyzed.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        cutoff_days: Number of days before un-acted items are pruned.

    Returns:
        The number of rows deleted.
    """
    db_path = get_db_path(base_path, handle)
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    cutoff_iso = cutoff.isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM items WHERE created_at < ? AND replied_item_id IS NULL",
            (cutoff_iso,),
        )
        return cursor.rowcount


def insert_items(base_path: Path, handle: str, items: list[QueueItem]) -> InsertItemsResult:
    """Bulk insert items, ignoring rows whose item_id already exists.

    Uses INSERT OR IGNORE to handle deduplication via the item_id primary key.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        items: List of QueueItem instances to insert.

    Returns:
        Inserted row counts, including a per-type breakdown.
    """
    if not items:
        return InsertItemsResult(total=0, posts=0, comments=0)

    db_path = get_db_path(base_path, handle)
    inserted_posts = 0
    inserted_comments = 0

    with sqlite3.connect(db_path) as conn:
        for item in items:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO items (item_id, item_type, post_id, submolt_name, analyzed, is_relevant, relevance_rationale, replied_item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.item_id,
                    item.item_type,
                    item.post_id,
                    item.submolt_name,
                    int(item.analyzed),
                    int(item.is_relevant),
                    item.relevance_rationale,
                    item.replied_item_id,
                    item.created_at.isoformat(),
                ),
            )
            if cursor.rowcount == 1:
                if item.item_type == "post":
                    inserted_posts += 1
                elif item.item_type == "comment":
                    inserted_comments += 1

    inserted_total = inserted_posts + inserted_comments
    return InsertItemsResult(total=inserted_total, posts=inserted_posts, comments=inserted_comments)


def has_unanalyzed(base_path: Path, handle: str) -> bool:
    """Return True when at least one unanalyzed row exists in the queue.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.

    Returns:
        True if at least one row has analyzed = 0, otherwise False.
    """
    db_path = get_db_path(base_path, handle)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM items WHERE analyzed = 0 LIMIT 1").fetchone()

    return row is not None


def get_next_unanalyzed(base_path: Path, handle: str) -> QueueItem | None:
    """Return one item where analyzed = 0, ordered by created_at ASC (oldest first).

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.

    Returns:
        A QueueItem instance, or None if no unanalyzed items exist.
    """
    db_path = get_db_path(base_path, handle)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM items WHERE analyzed = 0 ORDER BY created_at ASC LIMIT 1").fetchone()

    if row is None:
        return None

    return _row_to_queue_item(row)


def update_item_analysis(
    base_path: Path,
    handle: str,
    item_id: str,
    is_relevant: bool,
    relevance_rationale: str | None = None,
    replied_item_id: str | None = None,
) -> None:
    """Mark an item as analyzed and optionally record the reply.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        item_id: The ID of the item to update.
        is_relevant: Whether the item was determined to be relevant.
        relevance_rationale: Short rationale recorded from filter analysis.
        replied_item_id: The ID of the reply comment, if one was posted.

    Raises:
        ValueError: If item_id does not exist in the table.
    """
    db_path = get_db_path(base_path, handle)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE items SET analyzed = 1, is_relevant = ?, relevance_rationale = ?, replied_item_id = ? WHERE item_id = ?",
            (int(is_relevant), relevance_rationale, replied_item_id, item_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Item '{item_id}' not found in automation queue.")


def list_items(base_path: Path, handle: str, status_filter: str, limit: int | None) -> list[QueueItem]:
    """List queue items for a given status filter.

    Args:
        base_path: The root directory of the automolt client.
        handle: The agent's handle.
        status_filter: One of pending-analysis, pending-action, or acted.
        limit: Maximum number of rows to return, or None for no limit.

    Returns:
        Queue items matching the requested status.

    Raises:
        ValueError: If the status_filter is invalid or limit is less than 1.
    """
    if limit is not None and limit < 1:
        raise ValueError("Limit must be at least 1.")

    query = _resolve_list_query(status_filter, apply_limit=limit is not None)
    db_path = get_db_path(base_path, handle)

    if not db_path.exists():
        return []

    init_db(base_path, handle)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if limit is None:
            rows = conn.execute(query).fetchall()
        else:
            rows = conn.execute(query, (limit,)).fetchall()

    return [_row_to_queue_item(row) for row in rows]


def _resolve_list_query(status_filter: str, apply_limit: bool) -> str:
    """Return the SQL query for a list status filter."""
    query_map = LIST_STATUS_QUERIES_WITH_LIMIT if apply_limit else LIST_STATUS_QUERIES_NO_LIMIT

    try:
        return query_map[status_filter]
    except KeyError as exc:
        valid_statuses = ", ".join(LIST_STATUS_WHERE_CLAUSES)
        raise ValueError(f"Invalid status filter '{status_filter}'. Expected one of: {valid_statuses}.") from exc


def _row_to_queue_item(row: sqlite3.Row) -> QueueItem:
    """Convert a SQLite Row to a QueueItem model instance."""
    post_id = row["post_id"] if "post_id" in row.keys() else None
    return QueueItem(
        item_id=row["item_id"],
        item_type=row["item_type"],
        post_id=post_id,
        submolt_name=row["submolt_name"],
        analyzed=bool(row["analyzed"]),
        is_relevant=bool(row["is_relevant"]),
        relevance_rationale=row["relevance_rationale"] if "relevance_rationale" in row.keys() else None,
        replied_item_id=row["replied_item_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
