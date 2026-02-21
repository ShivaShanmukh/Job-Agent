"""
sheets.py — Google Sheets integration.
Reads job listings and writes back status updates.
"""

import logging
from googleapiclient.discovery import build

import config
import google_auth

logger = logging.getLogger(__name__)

_service = None  # lazy-loaded


def _get_service():
    """Return a cached Sheets API service, authenticating on first call."""
    global _service
    if _service:
        return _service
    _service = build("sheets", "v4", credentials=google_auth.get_credentials())
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
    Update specific columns in a given sheet row in a single batch request.

    Args:
        row_index: The 1-based row number in the sheet (including the header row).
        fields:    Dict mapping column letter → value, e.g. {'D': 'Applied', 'E': '2026-02-19'}
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would update row %d with %s", row_index, fields)
        return

    service = _get_service()
    data = [
        {
            "range": f"{config.SHEET_NAME}!{col_letter}{row_index}",
            "values": [[value]],
        }
        for col_letter, value in fields.items()
    ]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        body={"valueInputOption": "RAW", "data": data},
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
