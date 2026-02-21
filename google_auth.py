"""
google_auth.py — Shared Google OAuth2 authentication helper.
Both sheets.py and gmail_notify.py use this to obtain credentials,
so the token refresh / interactive-flow logic lives in one place.
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

import config


def get_credentials() -> Credentials:
    """
    Load, refresh, or acquire Google OAuth2 credentials.

    1. If token.json exists, load it.
    2. If valid, return as-is.
    3. If expired but refresh-able, refresh in-place and persist.
    4. Otherwise, run the local-server OAuth flow and persist.

    Returns:
        A valid Credentials object with the scopes in config.GOOGLE_SCOPES.
    """
    creds: Credentials | None = None
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

    return creds
