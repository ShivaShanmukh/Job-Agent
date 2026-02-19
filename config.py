"""
config.py — Loads all settings from .env file.
Edit .env (copied from .env.example) to configure the agent.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(Path(__file__).parent / ".env")


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Copy .env.example to .env and fill in your values."
        )
    return value


# ─── Google ───────────────────────────────────────────────────────────────────
GOOGLE_SHEET_ID: str = _require("GOOGLE_SHEET_ID")
USER_EMAIL: str = _require("USER_EMAIL")
GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# ─── Resume ───────────────────────────────────────────────────────────────────
RESUME_URL: str = os.getenv("RESUME_URL", "")
RESUME_LOCAL_PATH: str = os.getenv("RESUME_LOCAL_PATH", "")

# ─── LinkedIn ─────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")

# ─── Indeed ───────────────────────────────────────────────────────────────────
INDEED_EMAIL: str = os.getenv("INDEED_EMAIL", "")
INDEED_PASSWORD: str = os.getenv("INDEED_PASSWORD", "")

# ─── Scheduler ────────────────────────────────────────────────────────────────
APPLY_HOUR: int = int(os.getenv("APPLY_HOUR", "9"))
APPLY_MINUTE: int = int(os.getenv("APPLY_MINUTE", "0"))
STATUS_CHECK_INTERVAL_DAYS: int = int(os.getenv("STATUS_CHECK_INTERVAL_DAYS", "2"))
STATUS_CHECK_HOUR: int = int(os.getenv("STATUS_CHECK_HOUR", "10"))

# ─── Behaviour ────────────────────────────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"
MAX_APPLICATIONS_PER_RUN: int = int(os.getenv("MAX_APPLICATIONS_PER_RUN", "5"))

# ─── Derived ──────────────────────────────────────────────────────────────────
SHEET_NAME = "Jobs"
SHEET_RANGE = "A:J"
DB_PATH = Path(__file__).parent / "job_history.db"
TOKEN_PATH = Path(__file__).parent / "token.json"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]
