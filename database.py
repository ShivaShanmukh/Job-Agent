"""
database.py — SQLite local history log.
Keeps a permanent record of every application attempt and status change.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
import config

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          TEXT NOT NULL,
                company         TEXT NOT NULL,
                position        TEXT NOT NULL,
                platform        TEXT,
                status          TEXT NOT NULL,
                application_id  TEXT,
                notes           TEXT,
                applied_at      TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS status_changes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                company     TEXT NOT NULL,
                position    TEXT NOT NULL,
                old_status  TEXT NOT NULL,
                new_status  TEXT NOT NULL,
                changed_at  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    logger.info("Database initialised at %s", config.DB_PATH)


def log_application(job: dict, result: dict) -> None:
    """Record a job application attempt."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO applications
                (job_id, company, position, platform, status, application_id, notes, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("Job_ID", ""),
                job.get("Company", ""),
                job.get("Position", ""),
                job.get("platform", ""),
                result.get("status", "Unknown"),
                result.get("application_id", ""),
                result.get("notes", ""),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    logger.info("Logged application for %s @ %s", job.get("Position"), job.get("Company"))


def log_status_change(job: dict, old_status: str, new_status: str) -> None:
    """Record a status change detected during tracking."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO status_changes
                (job_id, company, position, old_status, new_status, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("Job_ID", ""),
                job.get("Company", ""),
                job.get("Position", ""),
                old_status,
                new_status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    logger.info(
        "Status change logged for %s @ %s: %s → %s",
        job.get("Position"),
        job.get("Company"),
        old_status,
        new_status,
    )


def get_all_applications(limit: int = 100) -> list[dict]:
    """
    Return application records ordered by most recent first.

    Args:
        limit: Maximum number of records to return (default 100).
               Pass None to fetch all records (use with care on large DBs).
    """
    with get_connection() as conn:
        if limit is None:
            rows = conn.execute("SELECT * FROM applications ORDER BY applied_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY applied_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
