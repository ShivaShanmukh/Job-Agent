"""tests/test_sheets.py — Unit tests for Google Sheets integration (mocked)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch


MOCK_SHEET_VALUES = {
    "values": [
        ["Job_ID", "Company", "Position", "Status", "Applied_Date", "Last_Checked", "Application_ID", "Notes", "Job_URL", "Priority"],
        ["001", "Acme Corp", "Software Engineer", "Not Applied", "", "", "", "", "https://linkedin.com/jobs/1", "High"],
        ["002", "Beta Ltd",  "Product Manager",   "Applied",      "2026-02-18", "2026-02-18", "APP123", "", "https://indeed.com/j/2", "Medium"],
    ]
}


@pytest.fixture
def mock_service(monkeypatch):
    mock = MagicMock()
    mock.spreadsheets().values().get().execute.return_value = MOCK_SHEET_VALUES
    mock.spreadsheets().values().update().execute.return_value = {}
    monkeypatch.setattr("sheets._service", mock)
    return mock


def test_read_jobs_all(mock_service):
    import sheets
    jobs = sheets.read_jobs()
    assert len(jobs) == 2
    assert jobs[0]["Company"] == "Acme Corp"


def test_read_jobs_filtered(mock_service):
    import sheets
    pending = sheets.read_jobs(status_filter="Not Applied")
    assert len(pending) == 1
    assert pending[0]["Job_ID"] == "001"


def test_read_jobs_applied(mock_service):
    import sheets
    applied = sheets.read_jobs(status_filter="Applied")
    assert len(applied) == 1
    assert applied[0]["Company"] == "Beta Ltd"


def test_row_index_attached(mock_service):
    import sheets
    jobs = sheets.read_jobs()
    # First data row = row 2 (1 header + 1 data)
    assert jobs[0]["_row_index"] == 2
    assert jobs[1]["_row_index"] == 3


def test_dry_run_skips_update(monkeypatch):
    import config
    import sheets
    monkeypatch.setattr(config, "DRY_RUN", True)
    mock = MagicMock()
    monkeypatch.setattr("sheets._service", mock)
    sheets.update_job_row(2, {"D": "Applied"})
    mock.spreadsheets().values().update.assert_not_called()
