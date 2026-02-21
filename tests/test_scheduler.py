"""tests/test_scheduler.py — Unit tests for the scheduler workflow functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch, call


SAMPLE_JOB_NOT_APPLIED = {
    "Job_ID": "001",
    "Company": "Acme Corp",
    "Position": "Software Engineer",
    "Status": "Not Applied",
    "Job_URL": "https://www.linkedin.com/jobs/view/123",
    "Priority": "High",
    "_row_index": 2,
}

SAMPLE_JOB_APPLIED = {
    "Job_ID": "002",
    "Company": "Beta Ltd",
    "Position": "Product Manager",
    "Status": "Applied",
    "Job_URL": "https://www.linkedin.com/jobs/view/456",
    "_row_index": 3,
}

SAMPLE_RESULT_SUCCESS = {
    "status": "Applied",
    "application_id": "AUTO_20260219120000",
    "notes": "Submitted via LinkedIn Easy Apply",
    "platform": "linkedin",
    "applied_date": "2026-02-19",
}

SAMPLE_RESULT_FAILED = {
    "status": "Failed",
    "application_id": "",
    "notes": "Timeout",
    "platform": "linkedin",
    "applied_date": "2026-02-19",
}


@pytest.fixture(autouse=True)
def reset_scheduler_module():
    """Ensure scheduler module is imported fresh without side effects."""
    import importlib
    import scheduler
    importlib.reload(scheduler)
    yield


class TestApplyToJobs:
    def test_no_pending_jobs_does_nothing(self):
        with patch("scheduler.sheets.read_jobs", return_value=[]) as mock_read, \
             patch("scheduler.browser_apply.apply") as mock_apply:
            import scheduler
            scheduler.apply_to_jobs()
            mock_read.assert_called_once_with(status_filter="Not Applied")
            mock_apply.assert_not_called()

    def test_applies_to_pending_jobs(self):
        with patch("scheduler.sheets.read_jobs", return_value=[SAMPLE_JOB_NOT_APPLIED]), \
             patch("scheduler.cover_letter.generate", return_value="Dear Acme Corp..."), \
             patch("scheduler.browser_apply.apply", return_value=SAMPLE_RESULT_SUCCESS), \
             patch("scheduler.sheets.mark_applied") as mock_mark, \
             patch("scheduler.database.log_application") as mock_db, \
             patch("scheduler.gmail_notify.send_application_email") as mock_email:
            import scheduler
            scheduler.apply_to_jobs()
            mock_mark.assert_called_once()
            mock_db.assert_called_once()
            mock_email.assert_called_once()

    def test_respects_max_applications_per_run(self):
        import config
        original = config.MAX_APPLICATIONS_PER_RUN
        config.MAX_APPLICATIONS_PER_RUN = 2

        jobs = [
            {**SAMPLE_JOB_NOT_APPLIED, "Job_ID": str(i), "_row_index": i + 2}
            for i in range(5)
        ]

        with patch("scheduler.sheets.read_jobs", return_value=jobs), \
             patch("scheduler.cover_letter.generate", return_value="letter"), \
             patch("scheduler.browser_apply.apply", return_value=SAMPLE_RESULT_SUCCESS), \
             patch("scheduler.sheets.mark_applied"), \
             patch("scheduler.database.log_application"), \
             patch("scheduler.gmail_notify.send_application_email"):
            import scheduler
            scheduler.apply_to_jobs()
            assert scheduler.browser_apply.apply.call_count == 2

        config.MAX_APPLICATIONS_PER_RUN = original

    def test_email_failure_does_not_stop_run(self):
        """A failure in send_application_email must not abort remaining jobs."""
        jobs = [
            {**SAMPLE_JOB_NOT_APPLIED, "Job_ID": "001"},
            {**SAMPLE_JOB_NOT_APPLIED, "Job_ID": "002", "Company": "Beta Ltd", "_row_index": 3},
        ]

        with patch("scheduler.sheets.read_jobs", return_value=jobs), \
             patch("scheduler.cover_letter.generate", return_value="letter"), \
             patch("scheduler.browser_apply.apply", return_value=SAMPLE_RESULT_SUCCESS), \
             patch("scheduler.sheets.mark_applied"), \
             patch("scheduler.database.log_application"), \
             patch("scheduler.gmail_notify.send_application_email", side_effect=Exception("SMTP error")):
            import scheduler
            # Should not raise even though email fails
            scheduler.apply_to_jobs()
            assert scheduler.browser_apply.apply.call_count == 2


class TestCheckStatuses:
    def test_no_applied_jobs_does_nothing(self):
        with patch("scheduler.sheets.read_jobs", return_value=[]) as mock_read, \
             patch("scheduler.status_tracker.check_job_status") as mock_check:
            import scheduler
            scheduler.check_statuses()
            mock_read.assert_called_once_with(status_filter="Applied")
            mock_check.assert_not_called()

    def test_updates_sheet_even_when_status_unchanged(self):
        check_result = {"new_status": "Applied", "check_date": "2026-02-21", "notes": ""}
        with patch("scheduler.sheets.read_jobs", return_value=[SAMPLE_JOB_APPLIED]), \
             patch("scheduler.status_tracker.check_job_status", return_value=check_result), \
             patch("scheduler.sheets.mark_status_changed") as mock_mark, \
             patch("scheduler.database.log_status_change") as mock_db, \
             patch("scheduler.gmail_notify.send_status_update_email") as mock_email:
            import scheduler
            scheduler.check_statuses()
            # Sheet should always be updated (Last_Checked)
            mock_mark.assert_called_once()
            # DB and email should NOT fire when status is unchanged
            mock_db.assert_not_called()
            mock_email.assert_not_called()

    def test_logs_and_emails_on_status_change(self):
        check_result = {"new_status": "Rejected", "check_date": "2026-02-21", "notes": ""}
        with patch("scheduler.sheets.read_jobs", return_value=[SAMPLE_JOB_APPLIED]), \
             patch("scheduler.status_tracker.check_job_status", return_value=check_result), \
             patch("scheduler.sheets.mark_status_changed"), \
             patch("scheduler.database.log_status_change") as mock_db, \
             patch("scheduler.gmail_notify.send_status_update_email") as mock_email:
            import scheduler
            scheduler.check_statuses()
            mock_db.assert_called_once_with(SAMPLE_JOB_APPLIED, "Applied", "Rejected")
            mock_email.assert_called_once()

    def test_respects_max_status_checks_per_run(self):
        import config
        original = config.MAX_STATUS_CHECKS_PER_RUN
        config.MAX_STATUS_CHECKS_PER_RUN = 2

        jobs = [
            {**SAMPLE_JOB_APPLIED, "Job_ID": str(i), "_row_index": i + 2}
            for i in range(5)
        ]
        check_result = {"new_status": "Applied", "check_date": "2026-02-21", "notes": ""}

        with patch("scheduler.sheets.read_jobs", return_value=jobs), \
             patch("scheduler.status_tracker.check_job_status", return_value=check_result) as mock_check, \
             patch("scheduler.sheets.mark_status_changed"):
            import scheduler
            scheduler.check_statuses()
            assert mock_check.call_count == 2

        config.MAX_STATUS_CHECKS_PER_RUN = original
