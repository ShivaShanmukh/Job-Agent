"""tests/test_gmail_notify.py — Unit tests for Gmail notification functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
import gmail_notify
import config


SAMPLE_JOB = {
    "Company": "Acme Corp",
    "Position": "Software Engineer",
    "platform": "linkedin",
}

SAMPLE_JOB_SPECIAL_CHARS = {
    "Company": "Smith & Jones <LLC>",
    "Position": "Dev \"Lead\"",
    "platform": "linkedin",
}

SAMPLE_RESULT_APPLIED = {
    "status": "Applied",
    "application_id": "AUTO_20260219",
    "notes": "Submitted via LinkedIn Easy Apply",
    "applied_date": "2026-02-19",
}

SAMPLE_RESULT_FAILED = {
    "status": "Failed",
    "application_id": "",
    "notes": "Timeout error",
    "applied_date": "2026-02-19",
}


class TestDryRun:
    def test_send_does_not_call_gmail_api_in_dry_run(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        mock_service = MagicMock()
        monkeypatch.setattr(gmail_notify, "_gmail_service", mock_service)

        gmail_notify.send_application_email(SAMPLE_JOB, SAMPLE_RESULT_APPLIED)

        mock_service.users().messages().send.assert_not_called()

    def test_send_status_update_does_not_call_gmail_api_in_dry_run(self, monkeypatch):
        monkeypatch.setattr(config, "DRY_RUN", True)
        mock_service = MagicMock()
        monkeypatch.setattr(gmail_notify, "_gmail_service", mock_service)

        gmail_notify.send_status_update_email(SAMPLE_JOB, "Applied", "Rejected", "2026-02-21")

        mock_service.users().messages().send.assert_not_called()


class TestApplicationEmail:
    def _capture_html(self, monkeypatch, job, result):
        """Helper: capture the HTML body passed to _send()."""
        captured = {}

        def fake_send(subject, html_body):
            captured["subject"] = subject
            captured["html"] = html_body

        monkeypatch.setattr(gmail_notify, "_send", fake_send)
        gmail_notify.send_application_email(job, result)
        return captured

    def test_subject_contains_company_and_position(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, SAMPLE_RESULT_APPLIED)
        assert "Acme Corp" in captured["subject"]
        assert "Software Engineer" in captured["subject"]

    def test_html_contains_all_fields(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, SAMPLE_RESULT_APPLIED)
        html_body = captured["html"]
        assert "Acme Corp" in html_body
        assert "Software Engineer" in html_body
        assert "AUTO_20260219" in html_body
        assert "2026-02-19" in html_body

    def test_applied_status_uses_green_color(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, SAMPLE_RESULT_APPLIED)
        assert "#27ae60" in captured["html"]

    def test_failed_status_uses_red_color(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, SAMPLE_RESULT_FAILED)
        assert "#e74c3c" in captured["html"]

    def test_special_characters_are_escaped(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB_SPECIAL_CHARS, SAMPLE_RESULT_APPLIED)
        html_body = captured["html"]
        # Raw special chars must not appear unescaped inside HTML tags
        assert "Smith &amp; Jones" in html_body
        assert "&lt;LLC&gt;" in html_body
        # The raw versions should not appear in the HTML body
        assert "Smith & Jones <LLC>" not in html_body


class TestStatusUpdateEmail:
    def _capture_html(self, monkeypatch, job, old_status, new_status):
        captured = {}

        def fake_send(subject, html_body):
            captured["subject"] = subject
            captured["html"] = html_body

        monkeypatch.setattr(gmail_notify, "_send", fake_send)
        gmail_notify.send_status_update_email(job, old_status, new_status, "2026-02-21")
        return captured

    def test_html_contains_old_and_new_status(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, "Applied", "Rejected")
        assert "Applied" in captured["html"]
        assert "Rejected" in captured["html"]

    def test_interview_uses_green_color(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, "Applied", "Interview Scheduled")
        assert "#27ae60" in captured["html"]

    def test_offer_uses_purple_color(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, "Applied", "Offer Received")
        assert "#8e44ad" in captured["html"]

    def test_rejected_uses_red_color(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, "Applied", "Rejected")
        assert "#e74c3c" in captured["html"]

    def test_unknown_status_uses_default_blue(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB, "Applied", "Pending Review")
        assert "#2980b9" in captured["html"]

    def test_special_chars_escaped_in_status(self, monkeypatch):
        captured = self._capture_html(monkeypatch, SAMPLE_JOB_SPECIAL_CHARS, "Applied", "Rejected")
        html_body = captured["html"]
        assert "Smith &amp; Jones" in html_body
        assert "Smith & Jones" not in html_body
