"""
browser_apply.py — Playwright-based browser automation for LinkedIn and Indeed.
Simulates a real user clicking through Easy Apply forms.

Platform-specific configuration (URLs, selectors) is declared as a dict so
adding a new platform is a matter of adding an entry to PLATFORM_CONFIG rather
than duplicating the entire apply flow.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

import config

logger = logging.getLogger(__name__)


# ─── Platform configuration ───────────────────────────────────────────────────
# Each entry describes how to log in and identify apply/submit/next buttons.
# The shared _apply_flow() function uses these selectors.

PLATFORM_CONFIG = {
    "linkedin": {
        "login_url": "https://www.linkedin.com/login",
        "username_selector": "#username",
        "password_selector": "#password",
        "submit_selector": "button[type=submit]",
        "checkpoint_patterns": ["checkpoint", "challenge"],
        "checkpoint_wait_url": "**/feed/**",
        "apply_button_selector": "button:has-text('Easy Apply'), .jobs-apply-button",
        "form_submit_selector": "button:has-text('Submit application')",
        "form_next_selector": "button:has-text('Next'), button:has-text('Review')",
        "platform_name": "linkedin",
        "applied_note": "Submitted via LinkedIn Easy Apply",
        "headless": False,  # headless=False lets user solve CAPTCHA/2FA interactively
    },
    "indeed": {
        "login_url": "https://secure.indeed.com/account/login",
        "username_selector": "#ifl-InputFormField-3",
        "password_selector": "#ifl-InputFormField-7, input[type=password]",
        "submit_selector": "button[type=submit]",
        "checkpoint_patterns": [],
        "checkpoint_wait_url": None,
        "apply_button_selector": "button:has-text('Apply now'), #indeedApplyButton, .jobsearch-IndeedApplyButton-newDesign",
        "form_submit_selector": "button:has-text('Submit'), button:has-text('Submit your application')",
        "form_next_selector": "button:has-text('Continue'), button:has-text('Next')",
        "platform_name": "indeed",
        "applied_note": "Submitted via Indeed Apply",
        "headless": False,
        "two_step_login": True,  # Indeed splits email + password across two screens
    },
}


# ─── Shared helpers ───────────────────────────────────────────────────────────

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


# ─── Shared browser session context manager ───────────────────────────────────

@contextmanager
def platform_session(platform: str) -> Generator[dict, None, None]:
    """
    Context manager that opens a browser, logs into the given platform,
    and yields a session dict for use with apply_with_session().

    Yields:
        dict with keys: page, browser, cfg (platform config), context
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    cfg = PLATFORM_CONFIG[platform]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg["headless"])
        context = browser.new_context()
        page = context.new_page()

        try:
            _login(page, cfg)
            yield {"page": page, "browser": browser, "context": context, "cfg": cfg}
        finally:
            try:
                browser.close()
            except Exception:
                pass


def _login(page, cfg: dict) -> None:
    """Log into a platform using the given config."""
    from playwright.sync_api import TimeoutError as PWTimeout

    page.goto(cfg["login_url"], timeout=30000)

    if cfg.get("two_step_login"):
        # Indeed: email first, then continue, then password
        page.wait_for_selector(cfg["username_selector"], timeout=10000)
        page.fill(cfg["username_selector"], config.INDEED_EMAIL)
        page.locator("button:has-text('Continue'), button[type=submit]").first.click()
        page.wait_for_selector(cfg["password_selector"], timeout=10000)
        page.fill(cfg["password_selector"], config.INDEED_PASSWORD)
        page.locator(cfg["submit_selector"]).first.click()
    else:
        # LinkedIn: email + password on same screen
        page.wait_for_selector(cfg["username_selector"], timeout=10000)
        page.fill(cfg["username_selector"], config.LINKEDIN_EMAIL)
        page.fill(cfg["password_selector"], config.LINKEDIN_PASSWORD)
        page.click(cfg["submit_selector"])

    page.wait_for_load_state("networkidle", timeout=15000)

    # Handle CAPTCHA / 2FA checkpoint (LinkedIn)
    if cfg["checkpoint_patterns"]:
        if any(p in page.url for p in cfg["checkpoint_patterns"]):
            logger.warning(
                "Security check detected on %s. Please complete it in the browser window.",
                cfg["platform_name"],
            )
            page.wait_for_url(cfg["checkpoint_wait_url"], timeout=120000)


# ─── Shared form-fill flow ────────────────────────────────────────────────────

def _fill_and_submit(page, cfg: dict, cover_letter_text: str, resume_path: str, job: dict) -> dict:
    """
    Navigate to the job URL, click Apply, and work through the multi-step form.
    Returns a result dict. Caller is responsible for browser cleanup.
    """
    platform = cfg["platform_name"]
    job_url = job.get("Job_URL", "")
    company = job.get("Company", "")
    position = job.get("Position", "")

    page.goto(job_url, timeout=30000)
    page.wait_for_load_state("networkidle", timeout=15000)

    # Click the apply button
    apply_btn = page.locator(cfg["apply_button_selector"])
    if not apply_btn.first.is_visible(timeout=8000):
        return _make_result(
            False, "", f"No apply button found — may require external application", platform
        )
    apply_btn.first.click()
    page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Switch to a new tab if the apply flow opened one (Indeed pattern)
    from playwright.sync_api import Page
    context = page.context
    if len(context.pages) > 1:
        page = context.pages[-1]
        page.wait_for_load_state("networkidle", timeout=10000)

    # Multi-step form loop
    max_steps = 10
    for _ in range(max_steps):
        # Upload resume if an upload input is visible
        resume_input = page.locator("input[type=file]")
        if resume_input.count() > 0 and Path(resume_path).exists():
            resume_input.first.set_input_files(resume_path)
            page.wait_for_load_state("domcontentloaded", timeout=5000)

        # Fill cover letter textarea if visible
        cover_area = page.locator("textarea").first
        if cover_area.is_visible(timeout=2000):
            cover_area.fill(cover_letter_text)

        # Check for submit button first, then next/continue
        submit_btn = page.locator(cfg["form_submit_selector"])
        next_btn = page.locator(cfg["form_next_selector"])

        if submit_btn.is_visible(timeout=2000):
            submit_btn.click()
            page.wait_for_load_state("networkidle", timeout=10000)
            logger.info("Application submitted for %s @ %s", position, company)
            return _make_result(True, _timestamp_id(), cfg["applied_note"], platform)

        elif next_btn.is_visible(timeout=2000):
            next_btn.first.click()
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        else:
            break  # No recognisable button — bail out

    return _make_result(False, "", "Could not complete apply form — check job manually", platform)


# ─── Public API ───────────────────────────────────────────────────────────────

def apply_with_session(session: dict, job: dict, cover_letter_text: str) -> dict:
    """
    Apply to a job using an already-open browser session (from platform_session()).
    Used by the scheduler to reuse a single login per platform per run.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    cfg = session["cfg"]
    page = session["page"]
    platform = cfg["platform_name"]
    job_url = job.get("Job_URL", "")

    try:
        return _fill_and_submit(page, cfg, cover_letter_text, config.RESUME_LOCAL_PATH, job)
    except PWTimeout as e:
        logger.error("Apply timeout for %s: %s", job_url, e)
        return _make_result(False, "", f"Timeout: {e}", platform)
    except Exception as e:
        logger.error("Apply error for %s: %s", job_url, e)
        return _make_result(False, "", f"Error: {e}", platform)


def apply(job: dict, cover_letter_text: str) -> dict:
    """
    Apply to a single job, opening and closing its own browser session.
    Used for one-shot calls (e.g., --run-now for a single job, generic platforms).

    Routes to the correct platform handler based on the job URL.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    url = job.get("Job_URL", "").lower()
    resume = config.RESUME_LOCAL_PATH

    if "linkedin.com" in url:
        platform = "linkedin"
    elif "indeed.com" in url:
        platform = "indeed"
    else:
        job["platform"] = "generic"
        logger.warning("No automation available for URL: %s — skipping (manual apply needed)", url)
        return _make_result(False, "", "Unsupported platform — apply manually via Job_URL", "generic")

    cfg = PLATFORM_CONFIG[platform]
    job["platform"] = platform

    if config.DRY_RUN:
        logger.info("[DRY RUN] Would apply to %s @ %s via %s", job.get("Position"), job.get("Company"), platform)
        return _make_result(True, _timestamp_id(), "Dry run — no actual application sent", platform)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg["headless"])
        context = browser.new_context()
        page = context.new_page()
        try:
            _login(page, cfg)
            result = _fill_and_submit(page, cfg, cover_letter_text, resume, job)
            browser.close()
            return result
        except PWTimeout as e:
            logger.error("Apply timeout for %s: %s", job.get("Job_URL"), e)
            browser.close()
            return _make_result(False, "", f"Timeout: {e}", platform)
        except Exception as e:
            logger.error("Apply error for %s: %s", job.get("Job_URL"), e)
            try:
                browser.close()
            except Exception:
                pass
            return _make_result(False, "", f"Error: {e}", platform)
