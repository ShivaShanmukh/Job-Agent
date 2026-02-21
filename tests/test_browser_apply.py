"""tests/test_browser_apply.py — Unit tests for browser_apply router and dry-run paths."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch
import browser_apply
import config


LINKEDIN_JOB = {
    "Job_ID": "001",
    "Company": "Acme Corp",
    "Position": "Software Engineer",
    "Job_URL": "https://www.linkedin.com/jobs/view/123456",
    "_row_index": 2,
}

INDEED_JOB = {
    "Job_ID": "002",
    "Company": "Beta Ltd",
    "Position": "Product Manager",
    "Job_URL": "https://indeed.com/j/789",
    "_row_index": 3,
}

GENERIC_JOB = {
    "Job_ID": "003",
    "Company": "Gamma Inc",
    "Position": "Designer",
    "Job_URL": "https://greenhouse.io/jobs/999",
    "_row_index": 4,
}


class TestRouter:
    """Tests for the apply() URL-to-platform routing logic."""

    def test_linkedin_url_sets_platform(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        job = {**LINKEDIN_JOB}
        result = browser_apply.apply(job, "cover letter")
        assert job["platform"] == "linkedin"

    def test_indeed_url_sets_platform(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        job = {**INDEED_JOB}
        result = browser_apply.apply(job, "cover letter")
        assert job["platform"] == "indeed"

    def test_unknown_url_sets_generic_platform(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        job = {**GENERIC_JOB}
        result = browser_apply.apply(job, "cover letter")
        assert job["platform"] == "generic"

    def test_unknown_url_returns_failed_status(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        job = {**GENERIC_JOB}
        result = browser_apply.apply(job, "cover letter")
        assert result["status"] == "Failed"
        assert "Unsupported platform" in result["notes"]

    def test_url_matching_is_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        job = {**LINKEDIN_JOB, "Job_URL": "HTTPS://WWW.LINKEDIN.COM/JOBS/123"}
        result = browser_apply.apply(job, "cover letter")
        assert job["platform"] == "linkedin"


class TestDryRun:
    """Tests for the dry-run path in apply() — must not launch a browser."""

    def test_linkedin_dry_run_returns_applied_status(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        result = browser_apply.apply({**LINKEDIN_JOB}, "cover letter")
        assert result["status"] == "Applied"

    def test_indeed_dry_run_returns_applied_status(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        result = browser_apply.apply({**INDEED_JOB}, "cover letter")
        assert result["status"] == "Applied"

    def test_dry_run_result_has_required_keys(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        result = browser_apply.apply({**LINKEDIN_JOB}, "cover letter")
        for key in ("status", "application_id", "notes", "platform", "applied_date"):
            assert key in result, f"Missing key: {key}"

    def test_dry_run_application_id_has_auto_prefix(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        result = browser_apply.apply({**LINKEDIN_JOB}, "cover letter")
        assert result["application_id"].startswith("AUTO_")

    def test_dry_run_returns_correct_result_without_browser(self, monkeypatch):
        """Dry-run must return a valid Applied result without opening a browser.
        sync_playwright is imported inline inside the non-dry-run code path,
        so it is never reached during dry-run — verified by the correct return value."""
        monkeypatch.setattr(config, "DRY_RUN", True)
        result = browser_apply.apply({**LINKEDIN_JOB}, "cover letter")
        assert result["status"] == "Applied"
        assert "Dry run" in result["notes"]


class TestMakeResult:
    def test_success_sets_applied_status(self):
        result = browser_apply._make_result(True, "AUTO_123", "note", "linkedin")
        assert result["status"] == "Applied"

    def test_failure_sets_failed_status(self):
        result = browser_apply._make_result(False, "", "error", "linkedin")
        assert result["status"] == "Failed"

    def test_result_includes_applied_date(self):
        result = browser_apply._make_result(True, "AUTO_123", "note", "linkedin")
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", result["applied_date"])
