"""SQLite storage for sessions, messages, feedback and test results.

The domain knowledge lives in knowledge/knowledge.md; this database only holds logs.
"""
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    role        TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content     TEXT NOT NULL,
    latency_ms  INTEGER,
    tokens_used INTEGER,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, message_id);
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL UNIQUE REFERENCES messages(message_id),
    rating      INTEGER NOT NULL CHECK (rating IN (1, -1)),
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS test_results (
    test_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT NOT NULL,
    category    TEXT,
    query       TEXT NOT NULL,
    expected    TEXT NOT NULL,
    actual      TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    latency_ms  INTEGER
);
"""

# Personal data must not be stored (privacy requirement), so obvious identifiers are masked before logging.
_REDACTIONS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email removed]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone removed]"),
    (re.compile(r"\b\d[A-Z]{2}\d{2}[A-Z]{2}\d{3}\b", re.IGNORECASE), "[USN removed]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def ensure_session(session_id: str | None) -> str:
    """Return a valid session id, creating the session row if needed."""
    try:
        session_id = str(uuid.UUID(session_id)) if session_id else str(uuid.uuid4())
    except ValueError:
        session_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)", (session_id, now()))
    return session_id


def add_message(session_id: str, role: str, content: str, latency_ms: int | None = None, tokens_used: int | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, latency_ms, tokens_used, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, redact(content), latency_ms, tokens_used, now()),
        )
        return cur.lastrowid


def get_history(session_id: str, limit: int | None = None) -> list[dict]:
    """Messages of a session, oldest first. With limit, only the most recent ones."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT message_id, role, content, latency_ms, tokens_used, created_at FROM messages "
            "WHERE session_id = ? ORDER BY message_id DESC LIMIT ?",
            (session_id, limit if limit else -1),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def message_exists(message_id: int) -> bool:
    with connect() as conn:
        return conn.execute("SELECT 1 FROM messages WHERE message_id = ? AND role = 'bot'", (message_id,)).fetchone() is not None


def save_feedback(message_id: int, rating: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO feedback (message_id, rating, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(message_id) DO UPDATE SET rating = excluded.rating, created_at = excluded.created_at",
            (message_id, rating, now()),
        )


def save_test_result(category: str, query: str, expected: str, actual: str, correct: bool, latency_ms: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO test_results (run_at, category, query, expected, actual, correct, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now(), category, query, expected, actual, int(correct), latency_ms),
        )
