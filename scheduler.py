"""
scheduler.py — APScheduler-based job scheduler.
Replaces the two n8n Cron triggers:
  1. Apply to new jobs  → weekdays at APPLY_HOUR:APPLY_MINUTE
  2. Check job statuses → every STATUS_CHECK_INTERVAL_DAYS days at STATUS_CHECK_HOUR:00
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import sheets
import cover_letter
import browser_apply
import status_tracker
import gmail_notify
import database

logger = logging.getLogger(__name__)


# ─── Job 1: Apply to pending jobs ─────────────────────────────────────────────

def apply_to_jobs() -> None:
    """
    Main application workflow — mirrors the n8n daily-trigger flow.
    Reads 'Not Applied' jobs, applies to each, updates sheet, sends email.

    Jobs are grouped by platform so each platform needs only one browser
    login per run, reducing CAPTCHA risk.
    """
    logger.info("=" * 60)
    logger.info("Starting application run at %s", datetime.utcnow().isoformat())

    pending_jobs = sheets.read_jobs(status_filter="Not Applied")
    if not pending_jobs:
        logger.info("No pending jobs found. Nothing to do.")
        return

    # Limit per-run for safety
    batch = pending_jobs[: config.MAX_APPLICATIONS_PER_RUN]
    logger.info("Processing %d job(s) (limit=%d).", len(batch), config.MAX_APPLICATIONS_PER_RUN)

    # Group by platform so we can reuse browser sessions (reduces login churn)
    from collections import defaultdict
    by_platform: dict[str, list[dict]] = defaultdict(list)
    for job in batch:
        url = job.get("Job_URL", "").lower()
        if "linkedin.com" in url:
            by_platform["linkedin"].append(job)
        elif "indeed.com" in url:
            by_platform["indeed"].append(job)
        else:
            by_platform["generic"].append(job)

    for platform, jobs in by_platform.items():
        logger.info("─ Platform: %s (%d job(s))", platform, len(jobs))
        _apply_platform_batch(platform, jobs)

    logger.info("Application run complete.")
    logger.info("=" * 60)


def _apply_platform_batch(platform: str, jobs: list[dict]) -> None:
    """
    Apply to all jobs for a single platform using one shared browser session.
    Falls back to per-job apply() for generic/unsupported platforms or dry-run.
    """
    if platform == "generic" or config.DRY_RUN:
        # Dry-run and generic both use the standalone apply() which handles both cases
        for job in jobs:
            company = job.get("Company", "?")
            position = job.get("Position", "?")
            logger.info("─ Applying: %s @ %s", position, company)
            result = browser_apply.apply(job, cover_letter.generate(job))
            _process_single_job(job, result)
        return

    # Open one shared browser session for this platform
    with browser_apply.platform_session(platform) as session:
        for job in jobs:
            company = job.get("Company", "?")
            position = job.get("Position", "?")
            logger.info("─ Applying: %s @ %s", position, company)

            letter = cover_letter.generate(job)
            result = browser_apply.apply_with_session(session, job, letter)
            _process_single_job(job, result)


def _process_single_job(job: dict, result: dict) -> None:
    """Update sheet, log to DB, and send email for one completed application."""
    sheets.mark_applied(
        job,
        application_id=result["application_id"],
        notes=result["notes"],
        applied_date=result["applied_date"],
    )
    database.log_application(job, result)

    try:
        gmail_notify.send_application_email(job, result)
    except Exception as e:
        logger.warning("Could not send email notification: %s", e)

    logger.info(
        "  Result: %s | ID: %s | Notes: %s",
        result["status"],
        result["application_id"],
        result["notes"],
    )


# ─── Job 2: Check status of applied jobs ──────────────────────────────────────

def check_statuses() -> None:
    """
    Status-tracking workflow — mirrors the n8n every-N-days status check.
    Reads 'Applied' jobs, checks each status, updates sheet if changed, sends email.
    Capped at MAX_STATUS_CHECKS_PER_RUN to prevent unbounded browser sessions.
    """
    logger.info("=" * 60)
    logger.info("Starting status check at %s", datetime.utcnow().isoformat())

    applied_jobs = sheets.read_jobs(status_filter="Applied")
    if not applied_jobs:
        logger.info("No applied jobs to check.")
        return

    # Cap per-run to avoid excessive logins and CAPTCHA risk
    batch = applied_jobs[: config.MAX_STATUS_CHECKS_PER_RUN]
    logger.info(
        "Checking status of %d job(s) (limit=%d).",
        len(batch),
        config.MAX_STATUS_CHECKS_PER_RUN,
    )

    for job in batch:
        company = job.get("Company", "?")
        position = job.get("Position", "?")
        old_status = job.get("Status", "Applied")

        # Check for status update
        check_result = status_tracker.check_job_status(job)
        new_status = check_result["new_status"]
        check_date = check_result["check_date"]

        # Update sheet's Last_Checked regardless
        sheets.mark_status_changed(job, new_status, check_date)

        if new_status != old_status:
            logger.info("  Status change: %s → %s for %s @ %s", old_status, new_status, position, company)

            # Log to database
            database.log_status_change(job, old_status, new_status)

            # Send notification email
            try:
                gmail_notify.send_status_update_email(job, old_status, new_status, check_date)
            except Exception as e:
                logger.warning("Could not send status update email: %s", e)
        else:
            logger.info("  No change for %s @ %s (still: %s)", position, company, old_status)

    logger.info("Status check complete.")
    logger.info("=" * 60)


# ─── Scheduler setup ──────────────────────────────────────────────────────────

def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")

    # Weekdays at APPLY_HOUR:APPLY_MINUTE
    scheduler.add_job(
        apply_to_jobs,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=config.APPLY_HOUR,
            minute=config.APPLY_MINUTE,
        ),
        id="apply_to_jobs",
        name="Apply to pending jobs",
        replace_existing=True,
        misfire_grace_time=3600,  # if machine was off, run within 1h window
    )

    # Every STATUS_CHECK_INTERVAL_DAYS days at STATUS_CHECK_HOUR:00 UTC.
    # Uses CronTrigger (not IntervalTrigger) so the hour is respected as a
    # wall-clock time rather than an offset from the first run.
    start = datetime.utcnow() + timedelta(days=config.STATUS_CHECK_INTERVAL_DAYS)
    scheduler.add_job(
        check_statuses,
        trigger=CronTrigger(
            day=f"*/{config.STATUS_CHECK_INTERVAL_DAYS}",
            hour=config.STATUS_CHECK_HOUR,
            minute=0,
            start_date=start,
        ),
        id="check_statuses",
        name="Check applied job statuses",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    return scheduler
