"""
scheduler.py — APScheduler-based job scheduler.
Replaces the two n8n Cron triggers:
  1. Apply to new jobs  → weekdays at APPLY_HOUR:APPLY_MINUTE
  2. Check job statuses → every STATUS_CHECK_INTERVAL_DAYS days at STATUS_CHECK_HOUR
"""

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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

    for job in batch:
        company = job.get("Company", "?")
        position = job.get("Position", "?")
        logger.info("─ Applying: %s @ %s", position, company)

        # 1. Generate personalised cover letter
        letter = cover_letter.generate(job)

        # 2. Apply via the appropriate platform
        result = browser_apply.apply(job, letter)

        # 3. Update Google Sheet
        sheets.mark_applied(
            job,
            application_id=result["application_id"],
            notes=result["notes"],
            applied_date=result["applied_date"],
        )

        # 4. Log to local SQLite database
        database.log_application(job, result)

        # 5. Send email notification
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

    logger.info("Application run complete.")
    logger.info("=" * 60)


# ─── Job 2: Check status of applied jobs ──────────────────────────────────────

def check_statuses() -> None:
    """
    Status-tracking workflow — mirrors the n8n every-2-days status check.
    Reads 'Applied' jobs, checks each status, updates sheet if changed, sends email.
    """
    logger.info("=" * 60)
    logger.info("Starting status check at %s", datetime.utcnow().isoformat())

    applied_jobs = sheets.read_jobs(status_filter="Applied")
    if not applied_jobs:
        logger.info("No applied jobs to check.")
        return

    logger.info("Checking status of %d applied job(s).", len(applied_jobs))

    for job in applied_jobs:
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

    # Every N days at STATUS_CHECK_HOUR
    scheduler.add_job(
        check_statuses,
        trigger=IntervalTrigger(days=config.STATUS_CHECK_INTERVAL_DAYS, hours=config.STATUS_CHECK_HOUR),
        id="check_statuses",
        name="Check applied job statuses",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    return scheduler
