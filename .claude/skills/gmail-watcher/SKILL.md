---
name: gmail-watcher
description: |
  Monitor Gmail for important/unread emails and create structured action files
  in the AI Employee Vault. Requires Google API credentials. Creates ACTION_EMAIL_*.md
  files in Needs_Action/ for each new important email. Use when the user wants to
  start Gmail monitoring, check for new emails, or set up the Gmail watcher script.
---

# Gmail Watcher — AI Employee Skill

Monitor Gmail for important unread emails and route them into the vault workflow.

## Prerequisites

### 1. Google API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Gmail API**
4. Create **OAuth 2.0 credentials** → Download as `credentials.json`
5. Place `credentials.json` in project root (it is gitignored)

### 2. Install Dependencies

```bash
.venv/bin/pip install google-auth google-auth-oauthlib google-api-python-client
```

### 3. First-Time Auth (generates token.json)

```bash
.venv/bin/python3 scripts/gmail_watcher.py --auth
```

A browser window opens — sign in and grant Gmail read access.
`token.json` is saved automatically (also gitignored).

---

## Running the Watcher

```bash
.venv/bin/python3 scripts/gmail_watcher.py
```

Polls Gmail every **120 seconds** for unread important emails.

**Stop with:** `Ctrl+C`

---

## What It Does

For each new important unread email detected:

1. Creates `Needs_Action/ACTION_EMAIL_<id>_<timestamp>.md` with:
   - Sender, subject, received time
   - Email snippet/preview
   - Urgency classification (checks for priority keywords)
   - Suggested actions checklist
2. Marks email as processed (avoids duplicates across restarts)
3. Logs the event to `Logs/activity.log`
4. Updates `Dashboard.md` pending count

---

## Action File Format

```markdown
---
type: email
from: Client A <client@example.com>
subject: Invoice #1234 - Payment Overdue
received: 2026-03-04T10:30:00
urgency: High
status: pending
---

# Action Required: Email from Client A

🟡 Urgency: High

## Email Preview
Invoice #1234 is now overdue. Please arrange payment at your earliest...

## Suggested Actions
- [ ] Reply to sender
- [ ] Create payment approval request
- [ ] Archive after processing
```

---

## Credential Security

| File | Location | Gitignored |
|------|----------|-----------|
| `credentials.json` | Project root | Yes |
| `token.json` | Project root | Yes |
| `.env` | Project root | Yes |

**Never put credentials in `.md` files** (per Company_Handbook.md).

---

## Gmail Query Filter

Default filter: `is:unread is:important`

To customize, edit `scripts/gmail_watcher.py`:
```python
GMAIL_QUERY = "is:unread is:important"
# Examples:
# "is:unread from:client@example.com"
# "is:unread subject:invoice"
# "is:unread label:urgent"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `credentials.json not found` | Download from Google Cloud Console |
| `token.json expired` | Delete `token.json` and re-run `--auth` |
| `quota exceeded` | Increase poll interval to 300s |
| No emails appearing | Check Gmail query filter, verify label exists |

---

## Integration with process-vault

After the watcher creates action files, run:
```
Process pending vault items
```
Claude will read each `ACTION_EMAIL_*.md` and respond per `Company_Handbook.md`.

---

## Triggering This Skill

User can say:
- "Start Gmail watcher"
- "Set up Gmail monitoring"
- "Check my emails"
- "Monitor Gmail for important messages"
