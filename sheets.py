"""
sheets.py — Google Sheets integration.
Reads job listings and writes back status updates.
"""

import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import config

logger = logging.getLogger(__name__)

_service = None  # lazy-loaded


def _get_service():
    """Authenticate and return a Sheets API service (OAuth2, cached in token.json)."""
    global _service
    if _service:
        return _service

    creds = None
    token_path = config.TOKEN_PATH

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_PATH, config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    _service = build("sheets", "v4", credentials=creds)
    return _service


def read_jobs(status_filter: str | None = None) -> list[dict]:
    """
    Read all rows from the Jobs sheet.

    Args:
        status_filter: If provided, only return rows with this Status value.
                       e.g. 'Not Applied' or 'Applied'
    Returns:
        List of dicts, one per row.  Row index (1-based, including header) is
        added as '_row_index' for later updates.
    """
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=f"{config.SHEET_NAME}!{config.SHEET_RANGE}",
        )
        .execute()
    )

    values = result.get("values", [])
    if len(values) < 2:
        logger.warning("No data found in sheet (or only header row).")
        return []

    headers = values[0]
    jobs = []
    for row_num, row in enumerate(values[1:], start=2):  # row 1 = header
        # Pad short rows
        padded = row + [""] * (len(headers) - len(row))
        job = dict(zip(headers, padded))
        job["_row_index"] = row_num  # sheet row number (1-based)
        jobs.append(job)

    if status_filter:
        jobs = [j for j in jobs if j.get("Status", "").strip() == status_filter]

    logger.info("Read %d jobs (filter=%r) from sheet.", len(jobs), status_filter)
    return jobs


def update_job_row(row_index: int, fields: dict) -> None:
    """
    Update specific columns in a given sheet row.

    Args:
        row_index: The 1-based row number in the sheet (including the header row).
        fields:    Dict mapping column letter → value, e.g. {'D': 'Applied', 'E': '2026-02-19'}
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would update row %d with %s", row_index, fields)
        return

    service = _get_service()
    for col_letter, value in fields.items():
        range_notation = f"{config.SHEET_NAME}!{col_letter}{row_index}"
        service.spreadsheets().values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=range_notation,
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()

    logger.info("Updated row %d: %s", row_index, fields)


def mark_applied(job: dict, application_id: str, notes: str, applied_date: str) -> None:
    """Convenience wrapper to mark a job as Applied in the sheet."""
    update_job_row(
        job["_row_index"],
        {
            "D": "Applied",
            "E": applied_date,
            "F": applied_date,
            "G": application_id,
            "H": notes,
        },
    )


def mark_status_changed(job: dict, new_status: str, check_date: str) -> None:
    """Update Status and Last_Checked columns for a status-tracking pass."""
    update_job_row(
        job["_row_index"],
        {
            "D": new_status,
            "F": check_date,
        },
    )
