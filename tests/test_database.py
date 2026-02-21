"""tests/test_database.py — Unit tests for the SQLite history log."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest
import database
import config


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
    """Re-init the DB and wipe rows before each test."""
    database.init_db()
    yield
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("DELETE FROM applications")
        conn.execute("DELETE FROM status_changes")
        conn.commit()


def test_log_application():
    database.log_application(SAMPLE_JOB, SAMPLE_RESULT)
    records = database.get_all_applications(limit=None)
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
    records = database.get_all_applications(limit=None)
    assert len(records) == 2


def test_get_all_applications_default_limit():
    """Default limit of 100 should return records (up to 100)."""
    for i in range(5):
        database.log_application({**SAMPLE_JOB, "Job_ID": str(i)}, SAMPLE_RESULT)
    records = database.get_all_applications()  # default limit=100
    assert len(records) == 5


def test_get_all_applications_respects_limit():
    """Explicit limit should cap the number of records returned."""
    for i in range(5):
        database.log_application({**SAMPLE_JOB, "Job_ID": str(i)}, SAMPLE_RESULT)
    records = database.get_all_applications(limit=3)
    assert len(records) == 3
