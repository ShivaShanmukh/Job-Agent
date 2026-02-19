"""
gmail_notify.py — Send HTML email notifications via Gmail API.
Uses the same OAuth2 credentials as the Sheets integration.
"""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

_gmail_service = None


def _get_gmail_service():
    global _gmail_service
    if _gmail_service:
        return _gmail_service

    creds = None
    if config.TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(config.TOKEN_PATH), config.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_PATH, config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        config.TOKEN_PATH.write_text(creds.to_json())

    _gmail_service = build("gmail", "v1", credentials=creds)
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
    status_color = "#27ae60" if result.get("status") == "Applied" else "#e74c3c"
    subject = f"Job Application: {job.get('Company')} — {job.get('Position')}"
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#2c3e50;">📋 Job Application Update</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;">Company</td>
            <td style="padding:8px;">{job.get('Company', '')}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Position</td>
            <td style="padding:8px;">{job.get('Position', '')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Status</td>
            <td style="padding:8px;color:{status_color};font-weight:bold;">{result.get('status', '')}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Platform</td>
            <td style="padding:8px;">{job.get('platform', '').title()}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Application ID</td>
            <td style="padding:8px;">{result.get('application_id', 'N/A')}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Date</td>
            <td style="padding:8px;">{result.get('applied_date', '')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Notes</td>
            <td style="padding:8px;">{result.get('notes', '')}</td></tr>
      </table>
      <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
        Sent by your Job Application Agent 🤖
      </p>
    </body></html>
    """
    _send(subject, html)


def send_status_update_email(job: dict, old_status: str, new_status: str, check_date: str) -> None:
    """Notify the user that a job's status changed."""
    subject = f"Status Update: {job.get('Company')} — {job.get('Position')}"
    color_map = {
        "Interview Scheduled": "#27ae60",
        "Offer Received": "#8e44ad",
        "Rejected": "#e74c3c",
        "Under Review": "#f39c12",
    }
    new_color = color_map.get(new_status, "#2980b9")
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#2c3e50;">🔔 Application Status Changed</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;">Company</td>
            <td style="padding:8px;">{job.get('Company', '')}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">Position</td>
            <td style="padding:8px;">{job.get('Position', '')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Previous Status</td>
            <td style="padding:8px;color:#7f8c8d;">{old_status}</td></tr>
        <tr style="background:#f8f9fa;"><td style="padding:8px;font-weight:bold;">New Status</td>
            <td style="padding:8px;color:{new_color};font-weight:bold;">{new_status}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Last Checked</td>
            <td style="padding:8px;">{check_date}</td></tr>
      </table>
      <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
        Sent by your Job Application Agent 🤖
      </p>
    </body></html>
    """
    _send(subject, html)


def send_test_email() -> None:
    """Send a test email to verify Gmail setup is working."""
    _send(
        subject="✅ Job Agent — Gmail Test",
        html_body="<h2>Gmail is working!</h2><p>Your Job Application Agent can send emails.</p>",
    )
    print(f"Test email sent to {config.USER_EMAIL}. Check your inbox!")
