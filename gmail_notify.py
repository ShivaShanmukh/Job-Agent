"""
gmail_notify.py — Send HTML email notifications via Gmail API.
Uses the same OAuth2 credentials as the Sheets integration.
"""

import base64
import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build

import config
import google_auth

logger = logging.getLogger(__name__)

_gmail_service = None


def _get_gmail_service():
    """Return a cached Gmail API service, authenticating on first call."""
    global _gmail_service
    if _gmail_service:
        return _gmail_service
    _gmail_service = build("gmail", "v1", credentials=google_auth.get_credentials())
    return _gmail_service


def _send(subject: str, html_body: str) -> None:
    """Internal helper — build MIME message and send via Gmail API."""
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would send email:\nSubject: %s\n%s", subject, html_body)
        return

    service = _get_gmail_service()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.USER_EMAIL
    msg["To"] = config.USER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info("Email sent: %s", subject)


def send_application_email(job: dict, result: dict) -> None:
    """Notify the user that an application was submitted (or failed)."""
    # All user-sourced values are escaped to prevent malformed HTML.
    company = html.escape(job.get("Company", ""))
    position = html.escape(job.get("Position", ""))
    platform = html.escape(job.get("platform", "").title())
    status = html.escape(result.get("status", ""))
    application_id = html.escape(result.get("application_id", "N/A"))
    applied_date = html.escape(result.get("applied_date", ""))
    notes = html.escape(result.get("notes", ""))

    status_color = "#27ae60" if result.get("status") == "Applied" else "#e74c3c"
    subject = f"Job Application: {job.get('Company')} \u2014 {job.get('Position')}"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#2c3e50;">&#128203; Job Application Update</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;">Company</td>
            <td style="padding:8px;">{company}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Position</td>
            <td style="padding:8px;">{position}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Status</td>
            <td style="padding:8px;color:{status_color};font-weight:bold;">{status}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Platform</td>
            <td style="padding:8px;">{platform}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Application ID</td>
            <td style="padding:8px;">{application_id}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Date</td>
            <td style="padding:8px;">{applied_date}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Notes</td>
            <td style="padding:8px;">{notes}</td></tr>
      </table>
      <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
        Sent by your Job Application Agent &#129302;
      </p>
    </body></html>
    """
    _send(subject, html_body)


def send_status_update_email(job: dict, old_status: str, new_status: str, check_date: str) -> None:
    """Notify the user that a job's status changed."""
    # All user-sourced values are escaped to prevent malformed HTML.
    company = html.escape(job.get("Company", ""))
    position = html.escape(job.get("Position", ""))
    old_status_escaped = html.escape(old_status)
    new_status_escaped = html.escape(new_status)
    check_date_escaped = html.escape(check_date)

    subject = f"Status Update: {job.get('Company')} \u2014 {job.get('Position')}"
    color_map = {
        "Interview Scheduled": "#27ae60",
        "Offer Received": "#8e44ad",
        "Rejected": "#e74c3c",
        "Under Review": "#f39c12",
    }
    new_color = color_map.get(new_status, "#2980b9")
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#2c3e50;">&#128276; Application Status Changed</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;">Company</td>
            <td style="padding:8px;">{company}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Position</td>
            <td style="padding:8px;">{position}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Previous Status</td>
            <td style="padding:8px;color:#7f8c8d;">{old_status_escaped}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">New Status</td>
            <td style="padding:8px;color:{new_color};font-weight:bold;">{new_status_escaped}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Last Checked</td>
            <td style="padding:8px;">{check_date_escaped}</td></tr>
      </table>
      <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
        Sent by your Job Application Agent &#129302;
      </p>
    </body></html>
    """
    _send(subject, html_body)


def send_test_email() -> None:
    """Send a test email to verify Gmail setup is working."""
    _send(
        subject="\u2705 Job Agent \u2014 Gmail Test",
        html_body="<h2>Gmail is working!</h2><p>Your Job Application Agent can send emails.</p>",
    )
    print(f"Test email sent to {config.USER_EMAIL}. Check your inbox!")
