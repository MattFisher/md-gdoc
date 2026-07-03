"""OAuth for a Workspace user; installed-app flow with cached token."""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_CONFIG = Path.home() / ".config" / "gdoc-sync"


def _credentials_path():
    return Path(os.environ.get("GDOC_SYNC_CREDENTIALS", _CONFIG / "credentials.json"))


def _token_path():
    return Path(os.environ.get("GDOC_SYNC_TOKEN", _CONFIG / "token.json"))


def get_credentials():
    token_path = _token_path()
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        cred_path = _credentials_path()
        if not cred_path.exists():
            raise SystemExit(
                f"No OAuth client secrets at {cred_path}. Create a Google Cloud "
                "OAuth desktop client and save its JSON there (or set "
                "GDOC_SYNC_CREDENTIALS)."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
        creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds
