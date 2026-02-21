"""
status_tracker.py — Checks the current status of applied jobs.

Currently implements a scraping-based check for LinkedIn.
Extend check_job_status() for other platforms as needed.
"""

import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)

# Possible statuses returned by platforms / set manually
KNOWN_STATUSES = [
    "Applied",
    "Under Review",
    "Interview Scheduled",
    "Offer Received",
    "Rejected",
    "Withdrawn",
]


def check_job_status(job: dict) -> dict:
    """
    Check the current status of an applied job.

    Returns:
        dict with keys: new_status (str), check_date (str), notes (str)
    """
    url = job.get("Job_URL", "").lower()
    check_date = datetime.utcnow().strftime("%Y-%m-%d")

    if "linkedin.com" in url:
        return _check_linkedin(job, check_date)
    else:
        logger.info(
            "No automated status check for %s — keeping current status.",
            job.get("Job_URL"),
        )
        return {
            "new_status": job.get("Status", "Applied"),
            "check_date": check_date,
            "notes": "No automated status check available for this platform.",
        }


def _check_linkedin(job: dict, check_date: str) -> dict:
    """
    Open LinkedIn's Applied Jobs page and find the status for this job.

    Navigates to the correct applied-jobs endpoint (not saved-jobs) and
    searches for the company name in context before interpreting status
    keywords, reducing false positives from unrelated jobs on the page.

    Falls back to keeping the current status if not found.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    if config.DRY_RUN:
        logger.info(
            "[DRY RUN] Would check LinkedIn status for %s @ %s",
            job.get("Position"),
            job.get("Company"),
        )
        return {
            "new_status": job.get("Status", "Applied"),
            "check_date": check_date,
            "notes": "Dry run — no actual status check performed.",
        }

    company = job.get("Company", "")
    position = job.get("Position", "")
    application_id = job.get("Application_ID", "")

    logger.info("Checking LinkedIn status for %s @ %s", position, company)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Log in
            page.goto("https://www.linkedin.com/login", timeout=30000)
            page.wait_for_selector("#username", timeout=10000)
            page.fill("#username", config.LINKEDIN_EMAIL)
            page.fill("#password", config.LINKEDIN_PASSWORD)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle", timeout=15000)

            # Navigate to the Applied Jobs page (not saved-jobs)
            page.goto("https://www.linkedin.com/my-items/applied-jobs/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Locate the card for this specific company to scope keyword matching.
            # LinkedIn renders each application as a list item containing the company name.
            new_status = job.get("Status", "Applied")  # default: no change
            company_lower = company.lower()

            # Try to find a card element containing the company name
            cards = page.locator("li").all()
            matched_text = ""
            for card in cards:
                card_text = card.inner_text().lower()
                if company_lower in card_text:
                    matched_text = card_text
                    break

            if matched_text:
                # Only interpret status keywords within the matched card's text
                if "rejected" in matched_text:
                    new_status = "Rejected"
                elif "interview" in matched_text or "assessment" in matched_text:
                    new_status = "Interview Scheduled"
                elif "viewed" in matched_text or "under review" in matched_text:
                    new_status = "Under Review"
                elif "offer" in matched_text:
                    new_status = "Offer Received"
            else:
                logger.info(
                    "Could not find application card for %s on LinkedIn — keeping current status.",
                    company,
                )

            browser.close()
            return {
                "new_status": new_status,
                "check_date": check_date,
                "notes": f"Status checked via LinkedIn Applied Jobs. Application ID: {application_id}",
            }

        except PWTimeout as e:
            logger.error("Status check timeout for %s @ %s: %s", position, company, e)
            browser.close()
            return {
                "new_status": job.get("Status", "Applied"),
                "check_date": check_date,
                "notes": f"Check failed (timeout): {e}",
            }
        except Exception as e:
            logger.error("Status check error for %s @ %s: %s", position, company, e)
            try:
                browser.close()
            except Exception:
                pass
            return {
                "new_status": job.get("Status", "Applied"),
                "check_date": check_date,
                "notes": f"Check failed: {e}",
            }
