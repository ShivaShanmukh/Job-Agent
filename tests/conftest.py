"""
conftest.py — Pytest configuration.
Sets fake environment variables before any test imports config,
so tests work without a real .env file.

Also stubs out the Google API native-extension imports (googleapiclient,
google.auth, google_auth_oauthlib) so tests run correctly in environments
where the cryptography C extension may not be available (e.g. some Linux CI
setups). This mirrors the mocking that test_sheets.py already applies at
the service level, just extended to also cover the import-time chain.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ─── Project root on sys.path ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Stub Google API modules before any project file is imported ──────────────
# These stubs prevent the broken cryptography/cffi chain from being triggered
# at import time. Each module's actual API calls are mocked per-test.
_google_stubs = [
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "google",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
]
for _mod in _google_stubs:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


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


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    """
    Session-scoped temporary SQLite database path.
    Created once for the entire test session and cleaned up automatically
    by pytest's tmp_path_factory when the session ends.
    """
    return tmp_path_factory.mktemp("db") / "test_job_history.db"


@pytest.fixture(scope="session", autouse=True)
def configure_test_db(tmp_db_path):
    """
    Point config.DB_PATH at the temp database for the entire session.
    Runs once before any test, ensuring all DB imports get the test path.
    """
    import config
    config.DB_PATH = tmp_db_path
