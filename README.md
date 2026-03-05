# Personal AI Employee — Bronze Tier

> **Hackathon:** Personal AI Employee Hackathon 0: Building Autonomous FTEs in 2026
> **Tier:** Bronze (Foundation — Minimum Viable Deliverable)
> **Tagline:** *Your life on autopilot. Local-first, agent-driven, human-in-the-loop.*

---

## What This Does

A **File System Watcher** monitors a `Drop_Zone/` folder inside your Obsidian vault. When you drop any file into it:

1. The watcher detects the file immediately
2. Creates a structured action file in `Needs_Action/`
3. Moves the original file to `Inbox/` for safe keeping
4. Updates `Dashboard.md` with the pending count
5. Logs all activity to `Logs/activity.log`

Claude Code then reads `Needs_Action/` and processes items according to `Company_Handbook.md`.

---

## Architecture

```
Personal AI Employee Hackathon 0/
├── AI_Employee_Vault/          ← Obsidian Vault
│   ├── Dashboard.md            ← Real-time status dashboard
│   ├── Company_Handbook.md     ← AI rules of engagement
│   ├── Drop_Zone/              ← Drop files here → watcher picks them up
│   ├── Inbox/                  ← Processed files stored here
│   ├── Needs_Action/           ← Action .md files for Claude Code
│   ├── Done/                   ← Completed items
│   └── Logs/
│       ├── activity.log        ← All watcher activity
│       └── processed_files.txt ← Tracks processed files (no duplicates)
├── scripts/
│   ├── base_watcher.py         ← Abstract base class for all watchers
│   ├── filesystem_watcher.py   ← File System Watcher (Bronze Tier)
│   └── verify.py               ← Setup verification script
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Watcher scripts |
| Obsidian | v1.10.6+ (free) | Open `AI_Employee_Vault/` as vault |
| Claude Code | Latest | AI reasoning engine |

### Install

```bash
# 1. Clone / navigate to project
cd "Personal AI Employee Hackathon 0"

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Verify setup
python3 scripts/verify.py
```

Expected output:
```
  ✓ All checks passed — Bronze Tier setup is complete!
```

---

## Running the Watcher

```bash
python3 scripts/filesystem_watcher.py
```

The watcher polls `Drop_Zone/` every **10 seconds**. Keep it running in a terminal while you work.

**To test it:**
```bash
echo "Urgent invoice from Client A" > "AI_Employee_Vault/Drop_Zone/urgent_invoice.txt"
```

Within 10 seconds you will see:
- A new `ACTION_urgent_invoice_<timestamp>.md` in `Needs_Action/`
- The original file moved to `Inbox/`
- A log entry in `Logs/activity.log`

**Stop with:** `Ctrl+C`

---

## Claude Code Integration

Once the watcher creates action files, ask Claude Code:

```
Check /Needs_Action and process pending items according to Company_Handbook.md
```

Claude will:
1. Read `Company_Handbook.md` for rules
2. Process each `ACTION_*.md` file
3. Summarize findings to `Inbox/`
4. Move completed items to `Done/`

---

## Human-in-the-Loop (HITL)

For sensitive actions, Claude creates:
```
Needs_Action/APPROVAL_REQUIRED_<description>_<timestamp>.md
```

Claude will **not** proceed until you review the file. After review, manually move it to `Done/` to confirm, or delete it to cancel.

---

## Security

- No credentials stored in `.md` files
- No external API calls in Bronze tier
- All data stays local on your machine
- `.gitignore` includes `.env` and `Logs/`

---

## Tier Declaration

**Tier: Bronze**

Completed deliverables:
- [x] Obsidian vault with `Dashboard.md` and `Company_Handbook.md`
- [x] Working File System Watcher script
- [x] Claude Code can read from and write to the vault
- [x] Folder structure: `/Inbox`, `/Needs_Action`, `/Done`
- [x] AI functionality implemented as an Agent Skill (`.claude/skills/process-vault/`)

---

## Demo Script

1. `python3 scripts/verify.py` — confirm setup
2. `python3 scripts/filesystem_watcher.py` — start watcher
3. Drop a file into `AI_Employee_Vault/Drop_Zone/`
4. Watch `Needs_Action/` populate automatically
5. Open Claude Code and say: "Process items in /Needs_Action"

---

*Built for GIAIC · Personal AI Employee Hackathon 0 · 2026*
