"""
browser_apply.py — Playwright-based browser automation for LinkedIn and Indeed.
Simulates a real user clicking through Easy Apply forms.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)


# ─── Shared helpers ──────────────────────────────────────────────────────────

def _timestamp_id() -> str:
    return "AUTO_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _make_result(success: bool, application_id: str, notes: str, platform: str) -> dict:
    return {
        "status": "Applied" if success else "Failed",
        "application_id": application_id,
        "notes": notes,
        "platform": platform,
        "applied_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }


# ─── LinkedIn Easy Apply ─────────────────────────────────────────────────────

def apply_linkedin(job: dict, cover_letter: str, resume_path: str) -> dict:
    """
    Navigate to a LinkedIn job URL and click through Easy Apply.
    Returns a result dict with status, application_id, notes.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    job_url = job.get("Job_URL", "")
    company = job.get("Company", "")
    position = job.get("Position", "")

    if config.DRY_RUN:
        logger.info("[DRY RUN] Would apply to %s @ %s via LinkedIn", position, company)
        return _make_result(True, _timestamp_id(), "Dry run — no actual application sent", "linkedin")

    logger.info("Opening LinkedIn for %s @ %s", position, company)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False lets you see what's happening
        context = browser.new_context()
        page = context.new_page()

        try:
            # ── Step 1: Log in ────────────────────────────────────────────────
            page.goto("https://www.linkedin.com/login", timeout=30000)
            page.fill("#username", config.LINKEDIN_EMAIL)
            page.fill("#password", config.LINKEDIN_PASSWORD)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle", timeout=15000)

            # Handle possible CAPTCHA / 2FA — open browser so user can solve it
            if "checkpoint" in page.url or "challenge" in page.url:
                logger.warning("LinkedIn security check detected. Please complete it in the browser window.")
                page.wait_for_url("**/feed/**", timeout=120000)  # wait up to 2 min

            # ── Step 2: Go to job page ────────────────────────────────────────
            page.goto(job_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # ── Step 3: Click Easy Apply ──────────────────────────────────────
            easy_apply_btn = page.locator("button:has-text('Easy Apply'), .jobs-apply-button")
            if not easy_apply_btn.first.is_visible(timeout=8000):
                return _make_result(False, "", "No Easy Apply button found — may require external application", "linkedin")

            easy_apply_btn.first.click()
            time.sleep(2)

            # ── Step 4: Fill in the form (multi-step) ─────────────────────────
            max_steps = 10
            for step in range(max_steps):
                # Upload resume if prompted
                resume_input = page.locator("input[type=file]")
                if resume_input.count() > 0 and Path(resume_path).exists():
                    resume_input.first.set_input_files(resume_path)
                    time.sleep(1)

                # Fill cover letter text area if present
                cover_area = page.locator("textarea").first
                if cover_area.is_visible(timeout=2000):
                    cover_area.fill(cover_letter)
                    time.sleep(0.5)

                # Next / Submit
                submit_btn = page.locator("button:has-text('Submit application')")
                next_btn = page.locator("button:has-text('Next'), button:has-text('Review')")

                if submit_btn.is_visible(timeout=2000):
                    submit_btn.click()
                    time.sleep(2)
                    logger.info("Application submitted for %s @ %s", position, company)
                    app_id = _timestamp_id()
                    browser.close()
                    return _make_result(True, app_id, "Submitted via LinkedIn Easy Apply", "linkedin")

                elif next_btn.is_visible(timeout=2000):
                    next_btn.first.click()
                    time.sleep(1.5)
                else:
                    break  # No recognisable button — bail out

            browser.close()
            return _make_result(False, "", "Could not complete Easy Apply form — check job manually", "linkedin")

        except PWTimeout as e:
            logger.error("LinkedIn apply timeout for %s: %s", job_url, e)
            browser.close()
            return _make_result(False, "", f"Timeout: {e}", "linkedin")
        except Exception as e:
            logger.error("LinkedIn apply error for %s: %s", job_url, e)
            try:
                browser.close()
            except Exception:
                pass
            return _make_result(False, "", f"Error: {e}", "linkedin")


# ─── Indeed Apply ─────────────────────────────────────────────────────────────

def apply_indeed(job: dict, cover_letter: str, resume_path: str) -> dict:
    """
    Navigate to an Indeed job URL and apply using Indeed's apply flow.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    job_url = job.get("Job_URL", "")
    company = job.get("Company", "")
    position = job.get("Position", "")

    if config.DRY_RUN:
        logger.info("[DRY RUN] Would apply to %s @ %s via Indeed", position, company)
        return _make_result(True, _timestamp_id(), "Dry run — no actual application sent", "indeed")

    logger.info("Opening Indeed for %s @ %s", position, company)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            # ── Step 1: Log in ────────────────────────────────────────────────
            page.goto("https://secure.indeed.com/account/login", timeout=30000)
            page.fill("#ifl-InputFormField-3", config.INDEED_EMAIL)
            continue_btn = page.locator("button:has-text('Continue'), button[type=submit]")
            continue_btn.first.click()
            time.sleep(2)

            password_field = page.locator("#ifl-InputFormField-7, input[type=password]")
            if password_field.is_visible(timeout=8000):
                password_field.fill(config.INDEED_PASSWORD)
                page.locator("button[type=submit]").first.click()
                page.wait_for_load_state("networkidle", timeout=15000)

            # ── Step 2: Navigate to job ───────────────────────────────────────
            page.goto(job_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # ── Step 3: Click Apply ───────────────────────────────────────────
            apply_btn = page.locator("button:has-text('Apply now'), #indeedApplyButton, .jobsearch-IndeedApplyButton-newDesign")
            if not apply_btn.first.is_visible(timeout=8000):
                return _make_result(False, "", "No Indeed Apply button found — may be external", "indeed")

            apply_btn.first.click()
            time.sleep(2)

            # Switch to any new page/tab if apply opened in new tab
            if len(context.pages) > 1:
                page = context.pages[-1]
                time.sleep(2)

            # ── Step 4: Fill application ──────────────────────────────────────
            max_steps = 10
            for _ in range(max_steps):
                # Upload resume if prompted
                resume_input = page.locator("input[type=file]")
                if resume_input.count() > 0 and Path(resume_path).exists():
                    resume_input.first.set_input_files(resume_path)
                    time.sleep(1)

                # Fill cover letter if prompted
                cover_area = page.locator("textarea").first
                if cover_area.is_visible(timeout=2000):
                    cover_area.fill(cover_letter)

                # Try to advance/submit
                submit_btn = page.locator("button:has-text('Submit'), button:has-text('Submit your application')")
                next_btn = page.locator("button:has-text('Continue'), button:has-text('Next')")

                if submit_btn.is_visible(timeout=2000):
                    submit_btn.click()
                    time.sleep(2)
                    app_id = _timestamp_id()
                    browser.close()
                    return _make_result(True, app_id, "Submitted via Indeed Apply", "indeed")
                elif next_btn.is_visible(timeout=2000):
                    next_btn.first.click()
                    time.sleep(1.5)
                else:
                    break

            browser.close()
            return _make_result(False, "", "Could not complete Indeed apply form", "indeed")

        except PWTimeout as e:
            logger.error("Indeed apply timeout for %s: %s", job_url, e)
            browser.close()
            return _make_result(False, "", f"Timeout: {e}", "indeed")
        except Exception as e:
            logger.error("Indeed apply error for %s: %s", job_url, e)
            try:
                browser.close()
            except Exception:
                pass
            return _make_result(False, "", f"Error: {e}", "indeed")


# ─── Router ───────────────────────────────────────────────────────────────────

def apply(job: dict, cover_letter: str) -> dict:
    """
    Route the application to the correct platform handler.
    Returns the result dict from whichever platform was used.
    """
    url = job.get("Job_URL", "").lower()
    resume = config.RESUME_LOCAL_PATH

    if "linkedin.com" in url:
        job["platform"] = "linkedin"
        return apply_linkedin(job, cover_letter, resume)
    elif "indeed.com" in url:
        job["platform"] = "indeed"
        return apply_indeed(job, cover_letter, resume)
    else:
        job["platform"] = "generic"
        logger.warning("No automation available for URL: %s  — skipping (manual apply needed)", url)
        return _make_result(False, "", "Unsupported platform — apply manually via Job_URL", "generic")
