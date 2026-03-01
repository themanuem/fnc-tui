"""SQLite cache for AI responses."""

import json
import sqlite3
from pathlib import Path

from finance_tui.config import CACHE_DIR


def _get_db_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "cache.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_get_db_path()))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def cache_get(key: str) -> dict | None:
    """Get a cached value by key."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT value FROM ai_cache WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
        return None
    finally:
        conn.close()


def cache_set(key: str, value: dict) -> None:
    """Set a cached value."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
        conn.commit()
    finally:
        conn.close()


def cache_clear() -> None:
    """Clear all cached values."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM ai_cache")
        conn.commit()
    finally:
        conn.close()
