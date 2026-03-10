"""
gmail_watcher.py - Gmail Watcher for the AI Employee Vault (Silver Tier).

Monitors Gmail for important unread emails and creates structured action files
in Needs_Action/ for Claude Code to process.

Usage:
    # First-time auth (opens browser):
    python3 scripts/gmail_watcher.py --auth

    # Run continuously (polls every 120s):
    python3 scripts/gmail_watcher.py

    # Run once and exit (for cron):
    python3 scripts/gmail_watcher.py --once

Stop with Ctrl+C.
"""

import sys
import json
import base64
import re
from pathlib import Path
from datetime import datetime

# ── Google Auth imports ───────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"

CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH       = PROJECT_ROOT / "token.json"

# Gmail OAuth scopes — read + send + modify (mark as read)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Gmail search filter — tune here
GMAIL_QUERY = "is:unread in:inbox"

# Keywords that escalate urgency to High/Critical
PRIORITY_KEYWORDS = {"urgent", "asap", "invoice", "payment", "deadline", "overdue", "important"}


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    """
    Load existing token or run OAuth flow to get fresh credentials.
    Saves token.json for future runs.
    """
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh expired token automatically
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        return creds

    # Need a fresh login
    if not creds or not creds.valid:
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"credentials.json not found at {CREDENTIALS_PATH}\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
        print(f"Auth successful. Token saved to {TOKEN_PATH}")

    return creds


def run_auth():
    """Standalone auth command: python3 scripts/gmail_watcher.py --auth"""
    print("Starting Gmail OAuth flow...")
    creds = get_credentials()
    print(f"Authenticated successfully.")
    print(f"Token saved: {TOKEN_PATH}")
    # Quick test
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    print(f"Connected as: {profile['emailAddress']}")


# ── Watcher implementation ────────────────────────────────────────────────────

def detect_urgency(sender: str, subject: str, snippet: str) -> tuple[str, str]:
    """Returns (urgency_label, urgency_emoji) based on content."""
    text = f"{subject} {snippet}".lower()
    if any(kw in text for kw in PRIORITY_KEYWORDS):
        return "High", "🟡"
    return "Normal", "🟢"


def decode_body(payload: dict) -> str:
    """Extract readable text body from Gmail message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    # Trim to first 500 chars to keep action files readable
    return body[:500].strip() if body else ""


class GmailWatcher(BaseWatcher):
    """
    Watches Gmail for important unread emails.
    Creates ACTION_EMAIL_*.md files in Needs_Action/ for each new email.
    """

    def __init__(self, vault_path: Path, check_interval: int = 120):
        super().__init__(str(vault_path), check_interval)
        self.processed_ids = self._load_processed_ids()
        self.service = None  # initialized lazily on first run

    def _processed_log_path(self) -> Path:
        return self.vault_path / "Logs" / "gmail_processed.txt"

    def _load_processed_ids(self) -> set:
        log = self._processed_log_path()
        if log.exists():
            return set(log.read_text(encoding="utf-8").splitlines())
        return set()

    def _save_processed_id(self, msg_id: str):
        log = self._processed_log_path()
        with log.open("a", encoding="utf-8") as f:
            f.write(msg_id + "\n")
        self.processed_ids.add(msg_id)

    def _get_service(self):
        if self.service is None:
            creds = get_credentials()
            self.service = build("gmail", "v1", credentials=creds)
        return self.service

    def check_for_updates(self) -> list:
        """Query Gmail for new important unread messages."""
        try:
            svc = self._get_service()
            result = svc.users().messages().list(
                userId="me", q=GMAIL_QUERY, maxResults=20
            ).execute()
            messages = result.get("messages", [])
            new = [m for m in messages if m["id"] not in self.processed_ids]
            if new:
                self.logger.info(f"Found {len(new)} new email(s) to process.")
            return new
        except Exception as e:
            self.logger.error(f"Gmail API error: {e}")
            # Reset service so it re-authenticates next cycle
            self.service = None
            return []

    def create_action_file(self, message: dict) -> Path:
        """Fetch full message, classify urgency, write ACTION_EMAIL_*.md."""
        svc = self._get_service()
        msg = svc.users().messages().get(
            userId="me", id=message["id"], format="full"
        ).execute()

        # Extract headers
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender  = headers.get("From", "Unknown")
        subject = headers.get("Subject", "(No Subject)")
        date    = headers.get("Date", datetime.now().isoformat())
        snippet = msg.get("snippet", "")
        body    = decode_body(msg["payload"])

        urgency_label, urgency_emoji = detect_urgency(sender, subject, snippet)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id   = re.sub(r"[^a-zA-Z0-9]", "", message["id"])[:12]
        filename  = f"ACTION_EMAIL_{safe_id}_{timestamp}.md"
        action_path = self.needs_action / filename

        # Detect if payment/approval needed
        needs_approval = any(
            kw in f"{subject} {snippet}".lower()
            for kw in {"payment", "invoice", "transfer", "pay", "overdue"}
        )
        approval_note = (
            "\n> ⚠️ **Payment keyword detected** — see `hitl-approval` skill before replying.\n"
            if needs_approval else ""
        )

        content = f"""---
type: email
from: {sender}
subject: {subject}
date: {date}
gmail_id: {message['id']}
urgency: {urgency_label}
needs_approval: {str(needs_approval).lower()}
status: pending
detected: {datetime.now().isoformat()}
---

# Action Required: Email — {subject}

{urgency_emoji} **Urgency:** {urgency_label}
{approval_note}
## Email Details

| Field | Value |
|-------|-------|
| From | {sender} |
| Subject | {subject} |
| Received | {date} |
| Gmail ID | `{message['id']}` |

## Preview

> {snippet}

## Body (first 500 chars)

{body if body else '*(body not extracted — check Gmail directly)*'}

## Suggested Actions

- [ ] Read full email in Gmail
- [ ] Classify: reply needed / forward / archive
- [ ] If payment involved → run `hitl-approval` skill first
- [ ] Draft reply (use `send-email` skill)
- [ ] Move this file to `/Done/` when complete

---
*(Claude Code: process this email per Company_Handbook.md rules)*
"""
        action_path.write_text(content, encoding="utf-8")
        self._save_processed_id(message["id"])
        self.logger.info(f"Email action file created: {filename} | From: {sender} | Subject: {subject}")
        return action_path


def main():
    args = sys.argv[1:]

    if "--auth" in args:
        run_auth()
        return

    watcher = GmailWatcher(vault_path=VAULT_PATH, check_interval=120)

    if "--once" in args:
        # Single-run mode for cron jobs
        watcher.logger.info("Running in --once mode (cron)")
        try:
            items = watcher.check_for_updates()
            for item in items:
                path = watcher.create_action_file(item)
                watcher.logger.info(f"Created: {path.name}")
            if items:
                watcher.update_dashboard()
        except Exception as e:
            watcher.logger.error(f"--once run failed: {e}")
            sys.exit(1)
    else:
        watcher.run()


if __name__ == "__main__":
    main()
