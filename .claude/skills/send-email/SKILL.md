---
name: send-email
description: |
  MCP server skill for sending emails via Gmail. Drafts email content, creates
  an APPROVAL_REQUIRED file for human review, then sends only after approval.
  Uses gmail-mcp or Google Gmail API as the external action MCP server.
  Use when the user wants to send an email, draft a reply, respond to a client,
  or set up the email MCP server for external action capability.
---

# Send Email — AI Employee Skill (MCP Server)

Send emails via Gmail using the email MCP server — with mandatory HITL approval.

## Architecture

```
Claude drafts email
       ↓
APPROVAL_REQUIRED_Email_*.md created
       ↓
Human approves (moves to Done/)
       ↓
Email MCP server sends the email
       ↓
Confirmation logged to activity.log
```

**Emails are NEVER sent without explicit approval** (Company_Handbook.md rule).

---

## MCP Server Options

### Option A: gmail-mcp (Recommended)

```bash
# Install
npm install -g @gptscript-ai/gmail-mcp
# or
npx @anthropic-ai/email-mcp
```

Configure in `~/.claude.json` or project `.mcp.json`:

```json
{
  "mcpServers": {
    "email": {
      "command": "npx",
      "args": ["@gptscript-ai/gmail-mcp"],
      "env": {
        "GMAIL_CREDENTIALS_PATH": "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0/credentials.json",
        "GMAIL_TOKEN_PATH": "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0/token.json"
      }
    }
  }
}
```

### Option B: Direct Gmail API (Python script)

```bash
# Install dependencies
.venv/bin/pip install google-auth google-auth-oauthlib google-api-python-client
```

Script: `scripts/send_email.py`

```python
"""send_email.py — Send an email via Gmail API after HITL approval."""
import sys
import base64
import json
from pathlib import Path
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def send_email(to: str, subject: str, body: str, token_path: str = "token.json"):
    creds = Credentials.from_authorized_user_file(token_path)
    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return result["id"]

if __name__ == "__main__":
    data = json.loads(sys.argv[1])
    msg_id = send_email(data["to"], data["subject"], data["body"])
    print(f"Email sent. Message ID: {msg_id}")
```

---

## Workflow: Drafting & Sending an Email

### Step 1 — Provide context to Claude

```
Draft a reply to Client A about their invoice #1234.
Be professional and apologize for the delay.
```

### Step 2 — Claude creates approval file

Claude writes to `Needs_Action/APPROVAL_REQUIRED_Email_<desc>_<timestamp>.md`:

```markdown
---
type: approval_required
category: email
to: client@example.com
subject: Re: Invoice #1234 - Payment Update
status: awaiting_approval
created: 2026-03-04T10:30:00
---

# APPROVAL REQUIRED: Send Email to Client A

## Draft Email

**To:** client@example.com
**Subject:** Re: Invoice #1234 — Payment Update

---

Dear Client A,

Thank you for your patience regarding Invoice #1234.
I wanted to confirm that we are processing the payment today
and you should receive confirmation within 24 hours.

Please don't hesitate to reach out with any questions.

Best regards,
Sumair

---

## To APPROVE
Move this file to `Done/` — Claude will send the email immediately.

## To EDIT
Edit the email body above, then move to `Done/`.

## To REJECT
Delete this file. No email will be sent.
```

### Step 3 — Human approves

Move the file to `Done/`.

### Step 4 — Claude sends the email

Via MCP server or direct Gmail API:

```bash
# Via Python script
.venv/bin/python3 scripts/send_email.py \
  '{"to": "client@example.com", "subject": "Re: Invoice #1234", "body": "..."}'

# Log result
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Email sent to client@example.com — Subject: Re: Invoice #1234" \
  >> "AI_Employee_Vault/Logs/activity.log"
```

---

## Credential Security

| File | Location | Gitignored |
|------|----------|-----------|
| `credentials.json` | Project root | Yes |
| `token.json` | Project root | Yes |
| `.env` | Project root | Yes |
| `.gitignore` | Project root | No (committed) |

`.gitignore` must include:
```
credentials.json
token.json
.env
*.key
*.pem
```

---

## MCP Server Config File

Save as `.mcp.json` in project root (gitignored):

```json
{
  "mcpServers": {
    "email": {
      "command": "npx",
      "args": ["@gptscript-ai/gmail-mcp"],
      "env": {
        "GMAIL_CREDENTIALS_PATH": "./credentials.json",
        "GMAIL_TOKEN_PATH": "./token.json"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "env": {
        "ROOT_PATH": "./AI_Employee_Vault"
      }
    }
  }
}
```

Add `.mcp.json` to `.gitignore` if it contains sensitive paths.

---

## Testing the Email MCP Server

```bash
# Verify MCP server responds
npx @gptscript-ai/gmail-mcp --test

# Send a test email to yourself
.venv/bin/python3 scripts/send_email.py \
  '{"to": "your@email.com", "subject": "AI Employee Test", "body": "Hello from your AI Employee!"}'
```

---

## Triggering This Skill

User can say:
- "Send an email to [person] about [topic]"
- "Draft a reply to [email]"
- "Set up the email MCP server"
- "Reply to Client A's invoice"
- "Compose an email for [purpose]"
