"""
send_email.py - Gmail sender for the AI Employee Vault (Silver Tier MCP action).

Watches Approved/ for APPROVAL_REQUIRED_Email_*.md files and sends them
via Gmail API. This is the "hands" of the AI Employee for email actions.

Usage:
    # Send all approved emails (run once):
    python3 scripts/send_email.py

    # Watch Approved/ continuously (auto-send on approval):
    python3 scripts/send_email.py --watch

    # Send a specific approval file:
    python3 scripts/send_email.py --file "AI_Employee_Vault/Approved/APPROVAL_REQUIRED_Email_*.md"
"""

import sys
import re
import base64
import time
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import setup_logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent
VAULT        = PROJECT_ROOT / "AI_Employee_Vault"
TOKEN_PATH   = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

logger = setup_logging(VAULT, "SendEmail")


# ── Gmail service ─────────────────────────────────────────────────────────────

def get_service():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            "token.json not found. Run: .venv/bin/python3 scripts/gmail_watcher.py --auth"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())

    if not creds.valid:
        raise RuntimeError("Gmail credentials invalid. Re-run --auth.")

    # Check send scope is present
    if "https://www.googleapis.com/auth/gmail.send" not in (creds.scopes or []):
        raise RuntimeError(
            "token.json missing send scope.\n"
            "Delete token.json and re-run: .venv/bin/python3 scripts/gmail_watcher.py --auth"
        )

    return build("gmail", "v1", credentials=creds)


# ── Parse approval file ───────────────────────────────────────────────────────

def parse_approval_file(path: Path) -> dict | None:
    """
    Extract to, subject, and body from an APPROVAL_REQUIRED_Email_*.md file.

    Expected frontmatter fields: to, subject
    Email body is between the --- separator line and the ## To APPROVE section.
    """
    content = path.read_text(encoding="utf-8")

    # Extract frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        logger.error(f"No frontmatter found in {path.name}")
        return None

    fm = {}
    for line in fm_match.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fm[k.strip()] = v.strip()

    to      = fm.get("to", "")
    subject = fm.get("subject", "")

    if not to or not subject:
        logger.error(f"Missing 'to' or 'subject' in {path.name}")
        return None

    # Extract email body — between the --- divider and ## To APPROVE
    body_match = re.search(
        r"---\n\n(.*?)\n\n---",
        content,
        re.DOTALL,
    )
    if not body_match:
        logger.error(f"Could not extract email body from {path.name}")
        return None

    body = body_match.group(1).strip()

    return {"to": to, "subject": subject, "body": body, "file": path}


# ── Send email ────────────────────────────────────────────────────────────────

def send_email(service, to: str, subject: str, body: str) -> str:
    """Send email via Gmail API. Returns message ID."""
    message = MIMEText(body, "plain", "utf-8")
    message["to"]      = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return result["id"]


# ── Process one approval file ─────────────────────────────────────────────────

def process_approval(path: Path, service) -> bool:
    """Parse, send, archive. Returns True on success."""
    parsed = parse_approval_file(path)
    if not parsed:
        return False

    to      = parsed["to"]
    subject = parsed["subject"]
    body    = parsed["body"]

    logger.info(f"Sending email → To: {to} | Subject: {subject}")

    try:
        msg_id = send_email(service, to, subject, body)
        logger.info(f"Email sent successfully. Gmail message ID: {msg_id}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

    # Archive to Done/ with sent confirmation
    done_dir = VAULT / "Done"
    done_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest     = done_dir / f"SENT_Email_{ts}.md"

    sent_content = path.read_text(encoding="utf-8")
    sent_content += f"\n\n---\n**SENT:** {datetime.now().isoformat()}\n**Gmail ID:** {msg_id}\n**Status:** SUCCESS\n"
    dest.write_text(sent_content, encoding="utf-8")
    path.unlink()

    # Log
    log = VAULT / "Logs" / "activity.log"
    with log.open("a") as f:
        f.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] SendEmail: "
            f"Sent to {to} | Subject: {subject} | Gmail ID: {msg_id}\n"
        )

    logger.info(f"Archived to Done/{dest.name}")
    return True


# ── Scan Approved/ ────────────────────────────────────────────────────────────

def scan_and_send(service) -> int:
    """Scan Approved/ for email approval files and send them. Returns count sent."""
    approved_dir = VAULT / "Approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    files = list(approved_dir.glob("APPROVAL_REQUIRED_Email_*.md"))
    if not files:
        logger.info("No approved emails found in Approved/")
        return 0

    sent = 0
    for f in files:
        logger.info(f"Processing approved email: {f.name}")
        if process_approval(f, service):
            sent += 1

    return sent


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    try:
        service = get_service()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    profile = service.users().getProfile(userId="me").execute()
    logger.info(f"Gmail connected as: {profile['emailAddress']}")

    if "--file" in args:
        idx  = args.index("--file")
        path = Path(args[idx + 1])
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
        process_approval(path, service)

    elif "--watch" in args:
        logger.info("Watching Approved/ for email approvals (interval=10s). Ctrl+C to stop.")
        try:
            while True:
                scan_and_send(service)
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Stopped.")

    else:
        # Default: run once
        count = scan_and_send(service)
        if count:
            logger.info(f"Sent {count} email(s).")
        else:
            logger.info("Nothing to send.")


if __name__ == "__main__":
    main()
