# AI Employee — Complete Workflow Guide

> Your personal reference for running and using the AI Employee system daily.

---

## Quick Start (Every Day)

```bash
cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0"

# Start all watchers
.venv/bin/python3 scripts/filesystem_watcher.py &   # Drop_Zone monitor
.venv/bin/python3 scripts/gmail_watcher.py &         # Gmail monitor

# Then open Claude Code and say:
# "Process pending vault items"
```

---

## Workflow 1 — File Drop

**Use when:** You have a document, invoice, CSV, or any file to process.

```
1. Copy/move file into:
   AI_Employee_Vault/Drop_Zone/

2. Watcher detects it within 10 seconds

3. Creates: Needs_Action/ACTION_<filename>_<timestamp>.md

4. Original file moved to: Inbox/<filename>

5. Tell Claude: "Process pending vault items"

6. Claude reads, summarizes, routes the file

7. Action file moved to: Done/
```

**Test it:**
```bash
echo "Invoice from Client A - $500 overdue" > \
  "AI_Employee_Vault/Drop_Zone/invoice_clientA.txt"
```

---

## Workflow 2 — Gmail Monitoring

**Use when:** You want Claude to monitor your inbox and handle emails.

```
1. Run once (manual):
   .venv/bin/python3 scripts/gmail_watcher.py --once

   Or continuous (auto-polls every 2 min):
   .venv/bin/python3 scripts/gmail_watcher.py

2. For each important unread email, creates:
   Needs_Action/ACTION_EMAIL_<id>_<timestamp>.md

3. Tell Claude: "Process pending vault items"

4. Claude classifies each email:
   - Normal → summarizes, archives to Done/
   - Payment/sensitive → creates APPROVAL_REQUIRED_*.md

5. You review and decide
```

**Check what was detected:**
```bash
ls "AI_Employee_Vault/Needs_Action/ACTION_EMAIL_"*.md
tail -20 "AI_Employee_Vault/Logs/activity.log"
```

---

## Workflow 3 — Reply to an Email

**Use when:** Claude needs to send an email on your behalf.

```
1. Tell Claude:
   "Draft a reply to [person] about [topic]"

2. Claude creates:
   Needs_Action/APPROVAL_REQUIRED_Email_<desc>_<date>.md
   (contains full draft — To, Subject, Body)

3. Claude STOPS — reviews the draft in Obsidian

4. You edit if needed, then:
   mv "AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_Email_*.md" \
      "AI_Employee_Vault/Approved/"

5. Send it:
   .venv/bin/python3 scripts/send_email.py

6. Email sent via Gmail API → archived to Done/
```

---

## Workflow 4 — LinkedIn Post

**Use when:** You want to post business content to generate leads.

```
1. Tell Claude:
   "Draft a LinkedIn post about [topic/service]"

2. Claude creates:
   Needs_Action/APPROVAL_REQUIRED_LinkedIn_<timestamp>.md
   (contains full post draft)

3. Review and edit in Obsidian

4. Move to Approved/:
   mv "AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_LinkedIn_*.md" \
      "AI_Employee_Vault/Approved/"

5. Post it:
   .venv/bin/python3 scripts/linkedin_watcher.py --post

6. Post goes live → screenshot saved to Logs/ → archived to Done/
```

---

## Workflow 5 — Create a Plan

**Use when:** You want Claude to reason through pending items and create an action plan.

```
1. Tell Claude:
   "Create a plan for [topic]"
   or
   "What's my action plan for today?"

2. Claude reads:
   - Company_Handbook.md (rules)
   - All Needs_Action/ items
   - Dashboard.md (big picture)

3. Reasons through each item and writes:
   Plans/<Domain>/Plan_<Topic>_<date>.md

4. Plan contains:
   - Situation summary
   - Recommended actions (checkboxes)
   - Risk flags
   - Items needing approval
   - Timeline
```

---

## Workflow 6 — Monday CEO Briefing

**Use when:** Start of week review of everything — revenue, tasks, bottlenecks.

```
1. Run manually:
   .venv/bin/python3 scripts/run_briefing.py

   Or it runs automatically via cron every Mon–Fri at 8AM

2. Output:
   Plans/General/Plan_CEOBriefing_<date>.md

3. Briefing contains:
   - Pending items count
   - Completed this week
   - Approvals waiting for you
   - Recent activity log
   - Priorities for the week
```

---

## Workflow 7 — HITL Approval (Any Sensitive Action)

**The golden rule:** Claude creates a file and stops. You decide.

```
Sensitive action detected
        ↓
File created in Needs_Action/:
APPROVAL_REQUIRED_<Category>_<Description>_<timestamp>.md
        ↓
Open in Obsidian → review the action details
        ↓
   ┌────┴────┐
APPROVE    REJECT
   ↓          ↓
Move to    Delete
Approved/  the file
   ↓
Script executes
(email sent / post published / etc.)
   ↓
Archived to Done/ with confirmation
```

**Approval categories:**
| Prefix | Triggers |
|--------|---------|
| `APPROVAL_REQUIRED_Email_` | Sending any email |
| `APPROVAL_REQUIRED_LinkedIn_` | Posting to LinkedIn |
| `APPROVAL_REQUIRED_Payment_` | Any payment action |
| `APPROVAL_REQUIRED_Delete_` | Deleting any file |

---

## Workflow 8 — Automated Scheduling (Set & Forget)

**Install cron once:**
```bash
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -
```

**What runs automatically:**
| Time | Job |
|------|-----|
| Every 2 min | Gmail watcher (polls inbox) |
| Every 10 min | LinkedIn watcher (checks notifications) |
| Every 5 min | Email sender (checks Approved/) |
| Mon–Fri 8AM | CEO Briefing generated |
| On reboot | File system watcher restarts |

**Check logs:**
```bash
tail -f "AI_Employee_Vault/Logs/cron.log"
tail -f "AI_Employee_Vault/Logs/activity.log"
```

**Remove cron:**
```bash
crontab -r
```

---

## Folder Reference

| Folder | What goes in | What comes out |
|--------|-------------|----------------|
| `Drop_Zone/` | You drop files | Moved to Inbox/ + action file created |
| `Needs_Action/` | Watcher-created action files | Processed by Claude → Done/ |
| `Inbox/` | Original dropped/received files | Summaries written here |
| `Approved/` | You move APPROVAL_REQUIRED files here | Scripts execute the action |
| `Rejected/` | Rejected approvals | Audit trail |
| `Done/` | Completed everything | Archive |
| `Plans/` | Claude writes Plan.md files | Your action roadmap |
| `Briefings/` | CEO briefing outputs | Weekly review |
| `Logs/` | All activity | Never delete |

---

## Key Commands Reference

```bash
# ── Setup ──────────────────────────────────────────────────
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
.venv/bin/python3 scripts/verify.py

# ── Auth (one-time) ────────────────────────────────────────
.venv/bin/python3 scripts/gmail_watcher.py --auth
.venv/bin/python3 scripts/linkedin_watcher.py --login

# ── Start Watchers ─────────────────────────────────────────
.venv/bin/python3 scripts/filesystem_watcher.py        # Drop_Zone monitor
.venv/bin/python3 scripts/gmail_watcher.py             # Gmail continuous
.venv/bin/python3 scripts/gmail_watcher.py --once      # Gmail single poll
.venv/bin/python3 scripts/linkedin_watcher.py --watch  # LinkedIn continuous
.venv/bin/python3 scripts/linkedin_watcher.py --watch --once  # LinkedIn single

# ── Actions ────────────────────────────────────────────────
.venv/bin/python3 scripts/send_email.py                # Send approved emails
.venv/bin/python3 scripts/linkedin_watcher.py --post   # Post approved LinkedIn
.venv/bin/python3 scripts/run_briefing.py              # Generate CEO briefing

# ── Scheduling ─────────────────────────────────────────────
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -
crontab -l                                             # View schedule
crontab -r                                             # Remove all cron

# ── Monitoring ─────────────────────────────────────────────
tail -f "AI_Employee_Vault/Logs/activity.log"
tail -f "AI_Employee_Vault/Logs/cron.log"
ls "AI_Employee_Vault/Needs_Action/"
ls "AI_Employee_Vault/Approved/"
```

---

## Claude Code Prompts Cheat Sheet

```
"Process pending vault items"
"Create a plan for [topic]"
"Draft a reply to [person] about [topic]"
"Draft a LinkedIn post about [topic]"
"What approvals are waiting for me?"
"Monday morning briefing"
"Start Gmail watcher"
"Schedule Gmail watcher every 2 minutes"
"Check /Needs_Action"
```

---

*AI Employee Vault · Silver Tier · 2026*
