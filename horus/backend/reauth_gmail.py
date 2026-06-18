"""Run this once from a terminal to refresh the Gmail OAuth token."""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

DIR = Path(__file__).parent
CREDENTIALS_FILE = DIR / "credentials.json"
TOKEN_FILE = DIR / "gmail_token.json"

if not CREDENTIALS_FILE.exists():
    print("ERROR: credentials.json not found.")
    print("Download it from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → Desktop app")
    raise SystemExit(1)

if TOKEN_FILE.exists():
    TOKEN_FILE.unlink()
    print("Deleted old token.")

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=0)
TOKEN_FILE.write_text(creds.to_json())
print(f"Gmail re-authenticated. Token saved to {TOKEN_FILE}")
