import base64
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

_DIR = Path(__file__).parent
CREDENTIALS_FILE = _DIR / "credentials.json"
TOKEN_FILE = _DIR / "gmail_token.json"


def _svc():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "Gmail not connected. Download credentials.json from Google Cloud Console "
                    "(APIs & Services → Credentials → OAuth 2.0 Client ID → Desktop app) "
                    "and place it in the backend folder, then ask me to connect Gmail."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _headers(payload: dict) -> dict:
    return {h["name"]: h["value"] for h in payload.get("headers", [])}


def _body_text(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    if mime == "text/html":
        # fall through to parts first; html is last resort
        pass
    for part in payload.get("parts", []):
        text = _body_text(part)
        if text:
            return text
    # html fallback
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            import re
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", "", html)
    return ""


# ── Public API ────────────────────────────────────────────────────────────────

def search_emails(query: str, max_results: int = 25) -> list[dict]:
    """Search Gmail with standard query syntax. Returns metadata list."""
    svc = _svc()
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    msgs = resp.get("messages", [])
    results = []
    for m in msgs:
        full = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["Subject", "From", "To", "Date"],
        ).execute()
        hdrs = _headers(full.get("payload", {}))
        results.append({
            "id": full["id"],
            "thread_id": full["threadId"],
            "subject": hdrs.get("Subject", "(no subject)"),
            "from": hdrs.get("From", ""),
            "to": hdrs.get("To", ""),
            "date": hdrs.get("Date", ""),
            "snippet": full.get("snippet", ""),
        })
    return results


def read_email(message_id: str) -> dict:
    """Read the full content of an email by ID."""
    svc = _svc()
    m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    hdrs = _headers(m.get("payload", {}))
    body = _body_text(m.get("payload", {}))
    return {
        "id": m["id"],
        "thread_id": m["threadId"],
        "subject": hdrs.get("Subject", "(no subject)"),
        "from": hdrs.get("From", ""),
        "to": hdrs.get("To", ""),
        "date": hdrs.get("Date", ""),
        "body": body[:10000],
    }


def trash_emails(message_ids: list[str]) -> str:
    """Move specific emails to trash (recoverable)."""
    svc = _svc()
    for mid in message_ids:
        svc.users().messages().trash(userId="me", id=mid).execute()
    return f"Moved {len(message_ids)} email(s) to trash."


def bulk_trash(query: str, max_results: int = 500) -> str:
    """Move all emails matching a Gmail query to trash."""
    svc = _svc()
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    msgs = resp.get("messages", [])
    if not msgs:
        return f"No emails found matching '{query}'."
    ids = [m["id"] for m in msgs]
    for i in range(0, len(ids), 1000):
        svc.users().messages().batchModify(
            userId="me",
            body={"ids": ids[i:i + 1000], "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
        ).execute()
    return f"Moved {len(ids)} email(s) to trash matching '{query}'."


def send_email(to: str, subject: str, body: str, thread_id: str = None) -> str:
    """Send an email, optionally as a reply to an existing thread."""
    svc = _svc()
    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    svc.users().messages().send(userId="me", body=payload).execute()
    return f"Email sent to {to}."


def is_connected() -> bool:
    return CREDENTIALS_FILE.exists() or TOKEN_FILE.exists()
