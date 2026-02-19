"""
main.py — Entry point for the Job Application Agent.

Usage:
  python main.py                  Start the scheduler (runs continuously)
  python main.py --dry-run        Preview what would happen (no actual applications)
  python main.py --run-now        Apply to pending jobs right now (don't wait for schedule)
  python main.py --check-now      Check statuses right now (don't wait for schedule)
  python main.py --test-email     Send a test email to verify Gmail setup
  python main.py --list-jobs      Print all pending jobs from the sheet
"""

import argparse
import io
import logging
import sys

# ─── Logging (force UTF-8 on Windows stdout) ──────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job Application Automation Agent (free, no n8n required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true", help="Log actions without applying")
    parser.add_argument("--run-now", action="store_true", help="Apply to pending jobs immediately")
    parser.add_argument("--check-now", action="store_true", help="Check applied job statuses immediately")
    parser.add_argument("--test-email", action="store_true", help="Send a test email and exit")
    parser.add_argument("--list-jobs", action="store_true", help="Print pending jobs and exit")
    args = parser.parse_args()

    # Apply --dry-run flag to config at runtime
    if args.dry_run:
        import config
        config.DRY_RUN = True
        logger.info("DRY RUN mode active — no applications will be submitted.")

    # Import modules (after config is potentially patched)
    import config
    import database
    import sheets
    import scheduler as sched_module
    import gmail_notify

    # Always initialise the local database
    database.init_db()

    # ── One-shot commands ─────────────────────────────────────────────────────

    if args.test_email:
        logger.info("Sending test email to %s …", config.USER_EMAIL)
        gmail_notify.send_test_email()
        return

    if args.list_jobs:
        jobs = sheets.read_jobs(status_filter="Not Applied")
        if not jobs:
            print("No pending jobs found in the sheet.")
        else:
            print(f"\n{'='*70}")
            print(f"{'Company':<30} {'Position':<30} {'Priority':<10}")
            print(f"{'='*70}")
            for j in jobs:
                print(f"{j.get('Company',''):<30} {j.get('Position',''):<30} {j.get('Priority',''):<10}")
            print(f"{'='*70}\n")
        return

    if args.run_now:
        logger.info("Running application workflow now …")
        sched_module.apply_to_jobs()
        return

    if args.check_now:
        logger.info("Running status check workflow now …")
        sched_module.check_statuses()
        return

    # ── Continuous scheduler ──────────────────────────────────────────────────
    scheduler = sched_module.build_scheduler()

    print("\n" + "=" * 60)
    print("  Job Application Agent - Running")
    print("=" * 60)
    print(f"  Apply jobs   : weekdays at {config.APPLY_HOUR:02d}:{config.APPLY_MINUTE:02d} UTC")
    print(f"  Check status : every {config.STATUS_CHECK_INTERVAL_DAYS} day(s) at {config.STATUS_CHECK_HOUR:02d}:00 UTC")
    print(f"  Dry run mode : {config.DRY_RUN}")
    print(f"  Max per run  : {config.MAX_APPLICATIONS_PER_RUN}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent stopped by user.")


if __name__ == "__main__":
    main()
