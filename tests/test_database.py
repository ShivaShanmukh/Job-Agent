"""tests/test_database.py — Unit tests for the SQLite history log."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os

# Point database to a temp file for testing
import config
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
config.DB_PATH = Path(_tmp.name)
_tmp.close()

import database


SAMPLE_JOB = {
    "Job_ID": "001",
    "Company": "Acme Corp",
    "Position": "Software Engineer",
    "platform": "linkedin",
}

SAMPLE_RESULT = {
    "status": "Applied",
    "application_id": "AUTO_20260219",
    "notes": "Submitted via LinkedIn Easy Apply",
    "applied_date": "2026-02-19",
}


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-init the DB before each test."""
    database.init_db()
    yield
    # Clean up rows
    import sqlite3
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("DELETE FROM applications")
        conn.execute("DELETE FROM status_changes")
        conn.commit()


def test_log_application():
    database.log_application(SAMPLE_JOB, SAMPLE_RESULT)
    records = database.get_all_applications()
    assert len(records) == 1
    assert records[0]["company"] == "Acme Corp"
    assert records[0]["status"] == "Applied"


def test_log_status_change():
    database.log_status_change(SAMPLE_JOB, "Applied", "Under Review")
    with database.get_connection() as conn:
        rows = conn.execute("SELECT * FROM status_changes").fetchall()
    assert len(rows) == 1
    assert rows[0]["old_status"] == "Applied"
    assert rows[0]["new_status"] == "Under Review"


def test_multiple_applications():
    database.log_application(SAMPLE_JOB, SAMPLE_RESULT)
    database.log_application({**SAMPLE_JOB, "Company": "Beta Ltd"}, SAMPLE_RESULT)
    records = database.get_all_applications()
    assert len(records) == 2
