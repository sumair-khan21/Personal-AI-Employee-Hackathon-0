# Personal AI Employee — Silver Tier

> **Hackathon:** GIAIC Personal AI Employee Hackathon 0: Building Autonomous FTEs in 2026
> **Tier:** Silver (Functional Assistant)
> **Tagline:** *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*
> **Author:** Sumair Khan

---

## What Is This?

A **Personal AI Employee** that runs 24/7 on your local machine. It monitors your Gmail inbox and LinkedIn, detects important messages, creates structured action files, drafts replies, and sends emails — all with your approval before any action is taken.

Built with **Claude Code** as the reasoning engine and **Obsidian** as the local dashboard. No cloud required. Everything stays on your machine.

---

## How It Works (Full Workflow)

```
┌─────────────────────────────────────────────────────────┐
│                   WATCHERS (Senses)                      │
│  filesystem_watcher.py   gmail_watcher.py               │
│  Monitors Drop_Zone/     Polls Gmail every 2min         │
│         │                        │                       │
│         └──────────┬─────────────┘                       │
│                    ▼                                      │
│         Creates ACTION_*.md in Needs_Action/             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                REASONING (Claude Code)                   │
│  Reads Company_Handbook.md for rules                    │
│  Reads Needs_Action/ for pending items                  │
│  Thinks → Creates Plan.md → Routes actions              │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐  ┌────────────────────────────────┐
│   SAFE ACTIONS   │  │    SENSITIVE ACTIONS (HITL)    │
│  Archive to Done/│  │  Creates APPROVAL_REQUIRED_*.md│
│  Write summaries │  │  Claude STOPS — waits for you  │
│  Update dashboard│  │  You move to Approved/ → sent  │
└──────────────────┘  └────────────────────────────────┘
                                │
                                ▼
                     ┌──────────────────┐
                     │  ACTION LAYER    │
                     │  send_email.py   │
                     │  Gmail API send  │
                     │  LinkedIn post   │
                     └──────────────────┘
```

---

## Project Structure

```
Personal AI Employee Hackathon 0/
│
├── AI_Employee_Vault/                  ← Obsidian Vault (open this in Obsidian)
│   ├── Dashboard.md                   ← Live status dashboard
│   ├── Company_Handbook.md            ← AI rules of engagement
│   │
│   ├── Drop_Zone/                     ← Drop any file here → watcher picks it up
│   ├── Inbox/                         ← Processed files + email summaries
│   ├── Needs_Action/                  ← ACTION_*.md files for Claude to process
│   ├── Done/                          ← Completed & archived items
│   │
│   ├── Plans/                         ← Claude-generated plan files
│   │   ├── Finance/
│   │   ├── Communications/
│   │   ├── Social/
│   │   └── General/                   ← CEO Briefings land here
│   │
│   ├── Pending_Approval/              ← Approval requests (reference)
│   ├── Approved/                      ← Move APPROVAL_REQUIRED files here to execute
│   ├── Rejected/                      ← Rejected actions (audit trail)
│   ├── Accounting/                    ← Financial records
│   ├── Briefings/                     ← Weekly CEO briefings
│   └── Logs/
│       ├── activity.log               ← All AI Employee activity
│       ├── cron.log                   ← Scheduled job logs
│       ├── gmail_processed.txt        ← Tracks processed email IDs
│       └── processed_files.txt        ← Tracks processed Drop_Zone files
│
├── scripts/
│   ├── base_watcher.py                ← Abstract base class (all watchers extend this)
│   ├── filesystem_watcher.py          ← Bronze: monitors Drop_Zone/ every 10s
│   ├── gmail_watcher.py               ← Silver: monitors Gmail every 2min
│   ├── linkedin_watcher.py            ← Silver: LinkedIn watcher + auto-poster
│   ├── send_email.py                  ← Silver: sends approved emails via Gmail API
│   ├── run_briefing.py                ← Silver: generates Monday CEO briefing
│   ├── crontab.txt                    ← Cron schedule template
│   └── verify.py                      ← Full setup verification (Bronze + Silver)
│
├── .claude/
│   └── skills/                        ← Claude Code Agent Skills
│       ├── process-vault/             ← Process Needs_Action/ items
│       ├── gmail-watcher/             ← Gmail monitoring guide
│       ├── linkedin-post/             ← LinkedIn draft → approve → post
│       ├── create-plan/               ← Reasoning loop → Plan.md
│       ├── hitl-approval/             ← HITL approval gatekeeper
│       ├── schedule-tasks/            ← Cron setup guide
│       ├── send-email/                ← Email send via Gmail API
│       └── browsing-with-playwright/  ← Browser automation guide
│
├── credentials.json                   ← Google OAuth client (gitignored)
├── token.json                         ← Gmail auth token (gitignored)
├── .linkedin-session/                 ← LinkedIn browser session (gitignored)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Watcher scripts |
| Claude Code | Latest | AI reasoning engine |
| Obsidian | v1.10.6+ (free) | Open `AI_Employee_Vault/` as vault |
| Google Cloud account | Free | Gmail API credentials |

---

## Installation

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd "Personal AI Employee Hackathon 0"
```

### Step 2 — Create virtual environment and install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 3 — Install Playwright browser

```bash
.venv/bin/playwright install chromium
```

### Step 4 — Run verification

```bash
.venv/bin/python3 scripts/verify.py
```

Expected output:
```
  ✓ Bronze Tier — COMPLETE
  ✓ Silver Tier — COMPLETE
```

---

## Gmail Setup (One-time)

### 1. Create Google Cloud credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project
3. Enable **Gmail API** → APIs & Services → Enable APIs → search "Gmail API"
4. Create **OAuth 2.0 credentials** → Desktop app → Download as `credentials.json`
5. Place `credentials.json` in project root
6. Go to **OAuth consent screen** → Add your Gmail as a **Test user**

### 2. Authenticate

```bash
.venv/bin/python3 scripts/gmail_watcher.py --auth
```

A browser opens → sign in → grant all Gmail permissions → `token.json` saved automatically.

---

## LinkedIn Setup (One-time)

```bash
.venv/bin/python3 scripts/linkedin_watcher.py --login
```

A headed browser opens → log in to LinkedIn → close browser → session saved to `.linkedin-session/`.

---

## Running the Application

### Option A — Run each watcher manually

```bash
# Terminal 1: File System Watcher (Bronze)
.venv/bin/python3 scripts/filesystem_watcher.py

# Terminal 2: Gmail Watcher (Silver) — continuous mode
.venv/bin/python3 scripts/gmail_watcher.py

# Terminal 3: LinkedIn Watcher (Silver)
.venv/bin/python3 scripts/linkedin_watcher.py --watch
```

### Option B — Automate with cron (Recommended)

```bash
# Install all scheduled tasks at once
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -

# Verify cron is set
crontab -l
```

Cron schedule:
| Job | Schedule |
|-----|----------|
| Gmail watcher | Every 2 minutes |
| LinkedIn watcher | Every 10 minutes |
| CEO Briefing | Mon–Fri at 8:00 AM |
| LinkedIn auto-post | Every 5 minutes (checks Approved/) |
| File system watcher | On system reboot |

---

## Daily Workflow

### 1. Files dropped into Drop_Zone/

```bash
# Drop any file — watcher detects it automatically
cp invoice.pdf "AI_Employee_Vault/Drop_Zone/"

# Check what was created
ls "AI_Employee_Vault/Needs_Action/"
```

### 2. Gmail emails detected

```bash
# Poll once manually
.venv/bin/python3 scripts/gmail_watcher.py --once

# Check action files created
ls "AI_Employee_Vault/Needs_Action/ACTION_EMAIL_*.md"
```

### 3. Ask Claude Code to process everything

Open Claude Code and say:
```
Process pending vault items
```

Claude reads all `ACTION_*.md` files, applies `Company_Handbook.md` rules, and routes each item.

### 4. Review approvals

```bash
# See what needs your decision
ls "AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_*.md"
```

Open each file in Obsidian, review it, then:
- **Approve** → move file to `Approved/`
- **Reject** → delete the file

### 5. Send approved emails

```bash
# Sends all files in Approved/ that are email approvals
.venv/bin/python3 scripts/send_email.py

# Or watch Approved/ continuously
.venv/bin/python3 scripts/send_email.py --watch
```

### 6. Monday CEO Briefing

```bash
# Generate manually anytime
.venv/bin/python3 scripts/run_briefing.py

# Output: AI_Employee_Vault/Plans/General/Plan_CEOBriefing_<date>.md
```

### 7. Post to LinkedIn

Tell Claude Code:
```
Draft a LinkedIn post about [your topic]
```

Claude creates `APPROVAL_REQUIRED_LinkedIn_*.md` → you review → move to `Approved/` → LinkedIn watcher posts it:

```bash
.venv/bin/python3 scripts/linkedin_watcher.py --post
```

---

## Claude Code Commands (Agent Skills)

| Say this to Claude | What happens |
|--------------------|-------------|
| `Process pending vault items` | Reads & routes all Needs_Action/ items |
| `Create a plan for [topic]` | Reasoning loop → Plan.md created |
| `Draft a LinkedIn post about [topic]` | Creates approval file for LinkedIn |
| `Draft a reply to [email]` | Creates approval file for email reply |
| `What approvals are waiting?` | Lists all APPROVAL_REQUIRED files |
| `Start Gmail watcher` | Guides Gmail setup & monitoring |
| `Schedule [task] at [time]` | Sets up cron job |
| `Monday morning briefing` | Generates CEO briefing |

---

## Human-in-the-Loop (HITL) Approval Flow

Claude **never** takes sensitive actions without your explicit sign-off:

```
Claude detects sensitive action needed
            ↓
Creates APPROVAL_REQUIRED_<type>_<timestamp>.md
            ↓
Claude STOPS — does nothing further
            ↓
You open the file in Obsidian and review
            ↓
        Approve?
        YES → move to Approved/
        NO  → delete the file
            ↓
Claude/script executes and logs to Done/
```

Actions that always require approval:
- Sending any email
- Posting to LinkedIn
- Any payment action
- Deleting files

---

## Security

| Protection | Implementation |
|-----------|---------------|
| Credentials never in code | `credentials.json` and `token.json` gitignored |
| No auto-send | Every email requires `Approved/` move |
| Local-first | All vault data stays on your machine |
| Audit trail | Every action logged to `Logs/activity.log` |
| No secrets in `.md` files | Enforced by `Company_Handbook.md` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: playwright` | `.venv/bin/pip install playwright && .venv/bin/playwright install chromium` |
| Gmail 403 access_denied | Add your email as test user in Google Cloud → OAuth consent screen |
| Gmail API disabled | Enable Gmail API at console.developers.google.com |
| token.json insufficient scope | Delete `token.json` and re-run `--auth` |
| LinkedIn not logged in | Run `.venv/bin/python3 scripts/linkedin_watcher.py --login` |
| No emails detected | Check Gmail query filter in `gmail_watcher.py` (`GMAIL_QUERY`) |

---

## Tier Declaration

**Tier: Silver ✓**

| Requirement | Status |
|------------|--------|
| All Bronze requirements | ✅ Complete |
| Two or more Watcher scripts | ✅ filesystem + Gmail + LinkedIn |
| Auto-post on LinkedIn | ✅ `linkedin_watcher.py --post` |
| Claude reasoning loop → Plan.md | ✅ `create-plan` skill |
| One working MCP for external action | ✅ Gmail API send (`send_email.py`) |
| HITL approval workflow | ✅ `APPROVAL_REQUIRED_*` → `Approved/` |
| Basic scheduling via cron | ✅ `scripts/crontab.txt` |
| All AI as Agent Skills | ✅ 7 skills in `.claude/skills/` |

---

## Submission

- **GitHub:** [your-repo-url]
- **Demo video:** 5–10 minutes showing Gmail detection → Claude processing → email send
- **Tier:** Silver

---

*Built for GIAIC · Personal AI Employee Hackathon 0 · 2026*
*Stack: Claude Code · Python · Gmail API · Playwright · Obsidian*
