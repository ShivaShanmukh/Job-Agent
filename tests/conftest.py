"""
conftest.py — Pytest configuration.
Sets fake environment variables before any test imports config,
so tests work without a real .env file.
"""

import os
import pytest
from pathlib import Path


def pytest_configure(config):
    """Set fake env vars at the very start of the test session."""
    os.environ.setdefault("GOOGLE_SHEET_ID", "fake_sheet_id_for_testing")
    os.environ.setdefault("USER_EMAIL", "test@example.com")
    os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    os.environ.setdefault("RESUME_URL", "https://example.com/resume.pdf")
    os.environ.setdefault("RESUME_LOCAL_PATH", "resume.pdf")
    os.environ.setdefault("LINKEDIN_EMAIL", "test@example.com")
    os.environ.setdefault("LINKEDIN_PASSWORD", "testpassword")
    os.environ.setdefault("INDEED_EMAIL", "test@example.com")
    os.environ.setdefault("INDEED_PASSWORD", "testpassword")
    os.environ.setdefault("DRY_RUN", "true")
