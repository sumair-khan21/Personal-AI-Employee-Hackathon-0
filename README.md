# Personal AI Employee — Gold Tier

> **Hackathon:** GIAIC Personal AI Employee Hackathon 0: Building Autonomous FTEs in 2026
> **Tier:** Gold (Autonomous Business Assistant)
> **Tagline:** *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*
> **Author:** Sumair Khan

---

## What Is This?

A **Personal AI Employee** that runs 24/7 on your local machine. It monitors Gmail, LinkedIn, Facebook, Instagram, WhatsApp, and Odoo accounting — detects important signals, creates structured action files, drafts replies and social posts, tracks invoices, and executes approved actions — all with your sign-off before anything irreversible happens.

Built with **Claude Code** as the reasoning engine, **Obsidian** as the local dashboard, **Playwright** for browser automation, and **Odoo Community** for accounting. No paid APIs. Everything stays on your machine.

---

## How It Works (Full Workflow)

```
┌──────────────────────────────────────────────────────────────┐
│                    WATCHERS (Senses)                          │
│  filesystem  gmail  linkedin  facebook  instagram             │
│  whatsapp    odoo   send_email                                │
│         │                                                     │
│         └──────────────────┬──────────────────               │
│                             ▼                                 │
│              Creates ACTION_*.md in Needs_Action/             │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Brain)                         │
│  orchestrator.py manages all watchers as subprocesses        │
│  Ralph Wiggum loop: watchdog on Needs_Action/ + Done/        │
│  Auto-restarts crashed watchers                              │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│               REASONING (Claude Code)                         │
│  Reads Company_Handbook.md for rules                         │
│  Reads Needs_Action/ for pending items                       │
│  Thinks → Creates Plan.md → Routes actions                   │
└─────────────────────────────┬────────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
┌──────────────────────┐    ┌─────────────────────────────────┐
│    SAFE ACTIONS      │    │    SENSITIVE ACTIONS (HITL)     │
│  Archive to Done/    │    │  Creates APPROVAL_REQUIRED_*.md │
│  Write summaries     │    │  Claude STOPS — waits for you   │
│  Update dashboard    │    │  Move to Approved/ → executes   │
└──────────────────────┘    └─────────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │      ACTION LAYER        │
                              │  send_email.py (Gmail)   │
                              │  linkedin_watcher --post │
                              │  facebook_watcher --post │
                              │  instagram_watcher --post│
                              │  odoo_watcher (XML-RPC)  │
                              └─────────────────────────┘
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
│   ├── Drop_Zone/                     ← Drop any file → watcher picks it up
│   ├── Inbox/                         ← Processed files + email summaries
│   ├── Needs_Action/                  ← ACTION_*.md files to process
│   ├── Done/                          ← Completed & archived items
│   │
│   ├── Plans/                         ← Claude-generated plan files
│   │   ├── Finance/
│   │   ├── Communications/
│   │   ├── Social/
│   │   └── General/                   ← CEO Briefings land here
│   │
│   ├── Pending_Approval/              ← Approval requests (reference)
│   ├── Approved/                      ← Move APPROVAL_REQUIRED files here
│   ├── Rejected/                      ← Rejected actions (audit trail)
│   ├── Accounting/                    ← Odoo weekly audit reports
│   ├── Briefings/                     ← Weekly CEO briefings
│   └── Logs/
│       ├── activity.log               ← All AI Employee activity
│       ├── cron.log                   ← Scheduled job logs
│       ├── YYYY-MM-DD.json            ← Daily JSON audit trail
│       └── orchestrator_status.json  ← Live orchestrator status
│
├── scripts/
│   ├── base_watcher.py                ← Abstract base class
│   ├── filesystem_watcher.py          ← Bronze: monitors Drop_Zone/
│   ├── gmail_watcher.py               ← Silver: monitors Gmail every 2min
│   ├── linkedin_watcher.py            ← Silver: LinkedIn watcher + poster
│   ├── send_email.py                  ← Silver: sends approved emails
│   ├── run_briefing.py                ← Silver: Monday CEO briefing
│   ├── facebook_watcher.py            ← Gold: Facebook poster via Playwright
│   ├── instagram_watcher.py           ← Gold: Instagram poster via Playwright
│   ├── whatsapp_watcher.py            ← Gold: WhatsApp message monitor
│   ├── odoo_watcher.py                ← Gold: Odoo accounting via XML-RPC
│   ├── orchestrator.py                ← Gold: master process manager
│   ├── audit_logger.py                ← Gold: JSON audit trail
│   ├── crontab.txt                    ← Cron schedule template
│   └── verify.py                      ← Setup verification
│
├── docker/
│   └── docker-compose.yml             ← Odoo 17 + PostgreSQL 15
│
├── .claude/
│   └── skills/                        ← Claude Code Agent Skills
│       ├── process-vault/
│       ├── gmail-watcher/
│       ├── linkedin-post/
│       ├── create-plan/
│       ├── hitl-approval/
│       ├── schedule-tasks/
│       ├── send-email/
│       └── browsing-with-playwright/
│
├── credentials.json                   ← Google OAuth client (gitignored)
├── token.json                         ← Gmail auth token (gitignored)
├── .env                               ← Odoo credentials (gitignored)
├── .linkedin-session/                 ← LinkedIn browser session (gitignored)
├── .facebook-session/                 ← Facebook browser session (gitignored)
├── .instagram-session/                ← Instagram browser session (gitignored)
├── .whatsapp-session/                 ← WhatsApp browser session (gitignored)
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
| Docker | Latest | Odoo Community (accounting) |
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

### Step 4 — Start Odoo (accounting)

```bash
cd docker && docker compose up -d && cd ..
# Wait ~30 seconds, then open http://localhost:8069
```

### Step 5 — Run verification

```bash
.venv/bin/python3 scripts/verify.py
```

---

## One-time Auth Setup

### Gmail

```bash
# 1. Place credentials.json (Google OAuth) in project root
# 2. Authenticate:
.venv/bin/python3 scripts/gmail_watcher.py --auth
```

### LinkedIn

```bash
.venv/bin/python3 scripts/linkedin_watcher.py --login
```

### Facebook

```bash
.venv/bin/python3 scripts/facebook_watcher.py --login
```

### Instagram

```bash
.venv/bin/python3 scripts/instagram_watcher.py --login
```

### WhatsApp

```bash
.venv/bin/python3 scripts/whatsapp_watcher.py --login
# Scan the QR code with your phone
```

### Odoo

Create `.env` in project root:
```
ODOO_URL=http://localhost:8069
ODOO_DB=odoo
ODOO_USERNAME=your@email.com
ODOO_PASSWORD=your_password
```

---

## Running the Application

### Option A — Master Orchestrator (Recommended)

Runs all watchers automatically, restarts on crash, Ralph Wiggum loop active:

```bash
.venv/bin/python3 scripts/orchestrator.py
```

### Option B — Individual watchers

```bash
.venv/bin/python3 scripts/filesystem_watcher.py
.venv/bin/python3 scripts/gmail_watcher.py
.venv/bin/python3 scripts/linkedin_watcher.py --watch
.venv/bin/python3 scripts/whatsapp_watcher.py --watch
```

### Option C — Cron (fully automated)

```bash
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -
crontab -l
```

Cron schedule:
| Job | Schedule |
|-----|----------|
| Gmail watcher | Every 2 minutes |
| LinkedIn watcher | Every 10 minutes |
| LinkedIn / Facebook / Instagram post | Every 5 minutes |
| WhatsApp watcher | Every 5 minutes |
| Odoo accounting audit | Every hour |
| CEO Briefing | Mon–Fri at 8:00 AM |
| Filesystem + send_email | On reboot (continuous) |

---

## Daily Workflow

### 1. Drop a file

```bash
cp invoice.pdf "AI_Employee_Vault/Drop_Zone/"
```

### 2. Gmail detected — process it

```bash
.venv/bin/python3 scripts/gmail_watcher.py --once
```

### 3. Ask Claude Code to reason

```
Process pending vault items
```

### 4. Review & approve actions

Open `Needs_Action/APPROVAL_REQUIRED_*.md` in Obsidian → move to `Approved/`

### 5. Social media posts

```bash
# LinkedIn
.venv/bin/python3 scripts/linkedin_watcher.py --post

# Facebook
.venv/bin/python3 scripts/facebook_watcher.py --post

# Instagram
.venv/bin/python3 scripts/instagram_watcher.py --post
```

### 6. Odoo accounting check

```bash
.venv/bin/python3 scripts/odoo_watcher.py --once
# Creates WeeklyAudit_*.md in Accounting/ and ACTION_ODOO_*.md in Needs_Action/
```

### 7. WhatsApp monitoring

```bash
.venv/bin/python3 scripts/whatsapp_watcher.py --watch --once
# Creates ACTION_WHATSAPP_*.md for messages with urgent/payment keywords
```

### 8. Monday CEO Briefing

```bash
.venv/bin/python3 scripts/run_briefing.py
```

---

## Claude Code Commands (Agent Skills)

| Say this to Claude | What happens |
|--------------------|-------------|
| `Process pending vault items` | Reads & routes all Needs_Action/ items |
| `Create a plan for [topic]` | Reasoning loop → Plan.md |
| `Draft a LinkedIn post about [topic]` | Creates LinkedIn approval file |
| `Draft a Facebook post about [topic]` | Creates Facebook approval file |
| `Draft an Instagram post about [topic]` | Creates Instagram approval file |
| `Draft a reply to [email]` | Creates email approval file |
| `What approvals are waiting?` | Lists all APPROVAL_REQUIRED files |
| `Monday morning briefing` | Generates CEO briefing |
| `Schedule [task] at [time]` | Sets up cron job |

---

## Human-in-the-Loop (HITL) Approval Flow

Claude **never** takes sensitive actions without your sign-off:

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
Script executes and logs to Done/
```

Actions that always require approval:
- Sending any email
- Posting to LinkedIn / Facebook / Instagram
- Any payment action
- Deleting files

---

## Security

| Protection | Implementation |
|-----------|---------------|
| Credentials never in code | All secrets gitignored |
| No auto-send | Every action requires `Approved/` move |
| Local-first | All vault data stays on your machine |
| JSON audit trail | Every action logged to `Logs/YYYY-MM-DD.json` |
| No secrets in `.md` files | Enforced by `Company_Handbook.md` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: playwright` | `.venv/bin/pip install playwright && .venv/bin/playwright install chromium` |
| Gmail 403 access_denied | Add your email as test user in Google Cloud OAuth consent screen |
| Gmail API disabled | Enable Gmail API at console.developers.google.com |
| token.json insufficient scope | Delete `token.json` and re-run `--auth` |
| LinkedIn/Facebook/Instagram not logged in | Re-run the `--login` command for that script |
| WhatsApp session expired | Re-run `--login` and scan QR again |
| Odoo connection refused | `cd docker && docker compose up -d` |
| Odoo auth failure | Reset password via PostgreSQL (see docker/README) |

---

## Tier Declaration

**Tier: Gold ✓**

| Requirement | Status |
|------------|--------|
| All Bronze + Silver requirements | ✅ Complete |
| Accounting integration (Odoo) | ✅ `odoo_watcher.py` via XML-RPC |
| Facebook posting | ✅ `facebook_watcher.py` via Playwright |
| Instagram posting | ✅ `instagram_watcher.py` via Playwright |
| WhatsApp monitoring | ✅ `whatsapp_watcher.py` via Playwright |
| Master orchestrator | ✅ `orchestrator.py` with Ralph Wiggum loop |
| JSON audit trail | ✅ `audit_logger.py` — daily YYYY-MM-DD.json |
| Docker deployment | ✅ `docker/docker-compose.yml` — Odoo 17 + PostgreSQL 15 |
| All AI as Agent Skills | ✅ 8 skills in `.claude/skills/` |

---

## Submission

- **GitHub:** [your-repo-url]
- **Demo video:** 5–10 minutes showing end-to-end Gold tier workflows
- **Tier:** Gold

---

*Built for GIAIC · Personal AI Employee Hackathon 0 · 2026*
*Stack: Claude Code · Python · Gmail API · Playwright · Odoo · Docker · Obsidian*
