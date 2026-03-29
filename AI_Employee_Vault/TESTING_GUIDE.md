# Personal AI Employee — Complete Testing Guide
> **Covers:** Bronze · Silver · Gold · Platinum
> **Author:** Sumair Khan
> **Project:** GIAIC Personal AI Employee Hackathon 0

---

## How to Use This Guide

Each workflow has:
- **Command(s)** to run
- **Expected result** — what success looks like
- **Pass/Fail** — how to confirm it worked

Run them in order. Each tier builds on the previous.

---

# BRONZE TIER TESTS

---

## B1 — Setup Verification

**Purpose:** Confirm all Bronze requirements are installed and configured.

```bash
cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0"
.venv/bin/python3 scripts/verify.py
```

**Expected result:**
```
✓ Bronze Tier — COMPLETE
⚠ Silver Tier — partially complete (warnings are OK)
```

**Pass:** Both Bronze lines show ✓
**Fail:** Any ✗ — follow the fix instructions shown

---

## B2 — Vault Folder Structure

**Purpose:** Confirm all required Obsidian vault folders exist.

```bash
ls AI_Employee_Vault/
```

**Expected result:** These folders visible:
```
Inbox/  Needs_Action/  Done/  Drop_Zone/  Logs/
Plans/  Approved/  Rejected/  Accounting/  Briefings/
```

**Pass:** All folders present
**Fail:** Run `mkdir -p AI_Employee_Vault/<missing_folder>`

---

## B3 — File System Watcher

**Purpose:** Drop a file → watcher detects it → creates action file.

**Step 1 — Start the watcher (Terminal 1):**
```bash
.venv/bin/python3 scripts/filesystem_watcher.py
```

**Step 2 — Drop a test file (Terminal 2):**
```bash
echo "Test invoice for Client A — $500 due" > "AI_Employee_Vault/Drop_Zone/test_invoice.txt"
```

**Step 3 — Check result:**
```bash
ls AI_Employee_Vault/Needs_Action/ACTION_FILE_*.md
cat AI_Employee_Vault/Needs_Action/ACTION_FILE_*.md
```

**Expected result:** `ACTION_FILE_test_invoice_<timestamp>.md` created in `Needs_Action/`
**Pass:** File detected within 10 seconds, action file created
**Fail:** Nothing in Needs_Action — check watcher is running in Terminal 1

---

## B4 — Process Vault Items (Claude Code)

**Purpose:** Claude reads action files and processes them.

Open Claude Code and type:
```
Process pending vault items
```

**Expected result:** Claude reads `ACTION_FILE_*.md`, writes summary to `Inbox/`, moves original to `Done/`
**Pass:** File appears in `Done/`, summary in `Inbox/`
**Fail:** Vault folders missing or Claude can't find action files

---

# SILVER TIER TESTS

---

## S1 — Gmail Watcher (Detect Emails)

**Purpose:** Gmail watcher polls inbox and creates action files for new emails.

```bash
.venv/bin/python3 scripts/gmail_watcher.py --once
```

**Expected result:**
```
[INFO] GmailWatcher: Connected as: devsumair@gmail.com
[INFO] GmailWatcher: Found X new email(s)
[INFO] GmailWatcher: Action file created: ACTION_EMAIL_*.md
```

**Pass:** At least one `ACTION_EMAIL_*.md` appears in `Needs_Action/`
**Fail:**
- `token.json` missing → run `.venv/bin/python3 scripts/gmail_watcher.py --auth`
- 403 error → add Gmail as test user in Google Cloud Console

---

## S2 — Process Email Action Files

**Purpose:** Claude reads email action files and drafts responses.

```bash
# First, make sure you have emails in Needs_Action/
ls AI_Employee_Vault/Needs_Action/ACTION_EMAIL_*.md
```

Open Claude Code and type:
```
Process pending vault items
```

**Expected result:** Claude reads email summaries, creates plan, moves to `Done/`
**Pass:** Files processed, summaries written
**Fail:** No action files — run S1 first

---

## S3 — Send Email (HITL Approval Flow)

**Purpose:** Draft email reply → approve → send via Gmail API.

**Step 1 — Ask Claude to draft a reply:**
```
Reply to the email from [sender] saying "This is a test — the AI Employee is working perfectly"
```

**Step 2 — Claude creates approval file:**
```bash
ls AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_Email_*.md
```

**Step 3 — Review and approve:**
```bash
# Open the file in Obsidian, review it, then move to Approved/
mv AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_Email_*.md \
   AI_Employee_Vault/Approved/
```

**Step 4 — Send the email:**
```bash
.venv/bin/python3 scripts/send_email.py
```

**Expected result:**
```
[INFO] EmailSender: Email sent successfully to [recipient]
```

**Pass:** Email arrives in recipient's inbox, file moves to `Done/`
**Fail:** Check Gmail API scope — delete `token.json` and re-run `--auth`

---

## S4 — LinkedIn Post (Full HITL Flow)

**Purpose:** Draft LinkedIn post → approve → auto-post via Playwright.

**Step 1 — Draft the post (ask Claude Code):**
```
Draft a LinkedIn post about my AI Employee hackathon project
```

**Step 2 — Check approval file created:**
```bash
ls AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_LinkedIn_*.md
```

**Step 3 — Approve:**
```bash
mv AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_LinkedIn_*.md \
   AI_Employee_Vault/Approved/
```

**Step 4 — Post it:**
```bash
.venv/bin/python3 scripts/linkedin_watcher.py --post
```

**Expected result:**
```
[INFO] LinkedInWatcher: Post published successfully
[INFO] LinkedInWatcher: Archived to Done/POSTED_LinkedIn_*.md
```

**Pass:** Post visible on LinkedIn profile, screenshot in `Logs/`
**Fail:** Session expired → run `.venv/bin/python3 scripts/linkedin_watcher.py --login`

---

## S5 — Create Plan (Reasoning Loop)

**Purpose:** Claude reads vault context and creates a structured Plan.md.

Open Claude Code and type:
```
Create a plan for managing my inbox this week
```

**Expected result:** New file created at `AI_Employee_Vault/Plans/General/Plan_*.md` with checkboxes and action items.

**Pass:** Plan file exists with structured content
**Fail:** No plans folder — run `mkdir -p AI_Employee_Vault/Plans/General`

---

## S6 — Monday CEO Briefing

**Purpose:** Auto-generate weekly business briefing.

```bash
.venv/bin/python3 scripts/run_briefing.py
```

**Expected result:**
```
Briefing written: AI_Employee_Vault/Plans/General/Plan_CEOBriefing_<date>.md
```

**Pass:** Briefing file created with vault summary
**Fail:** Missing Plans/General folder

---

## S7 — Cron Jobs (Automated Scheduling)

**Purpose:** Verify all scheduled tasks are installed.

```bash
crontab -l
```

**Expected result:** Should show all scheduled jobs including:
- Gmail every 2 min
- LinkedIn every 10 min
- CEO Briefing Mon-Fri 8AM
- Facebook/Instagram/WhatsApp every 5 min
- Odoo every hour

**Install if missing:**
```bash
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -
```

**Pass:** All jobs listed
**Fail:** Empty crontab — run the install command above

---

# GOLD TIER TESTS

---

## G1 — Facebook Post (Full HITL Flow)

**Purpose:** Draft Facebook post → approve → auto-post via Playwright.

**Step 1 — Create and approve draft:**
```bash
python3 - << 'EOF'
import sys, shutil
sys.path.insert(0, "scripts")
from facebook_watcher import draft_post_for_approval
path = draft_post_for_approval("AI Employee Hackathon", """My AI Employee works 24/7 — no salary, no breaks.

Built for the GIAIC Personal AI Employee Hackathon:
✅ Gmail monitoring & auto-replies
✅ LinkedIn, Facebook & Instagram posting
✅ Odoo invoice tracking
✅ WhatsApp monitoring
✅ Human approval for every sensitive action

#AIEmployee #GIAIC #BuildInPublic #ClaudeCode""")
dest = path.parent.parent / "Approved" / path.name
shutil.move(str(path), str(dest))
print(f"Ready: {dest.name}")
EOF
```

**Step 2 — Post it:**
```bash
.venv/bin/python3 scripts/facebook_watcher.py --post
```

**Expected result:**
```
[INFO] FacebookWatcher: Post published successfully
[INFO] FacebookWatcher: Archived to Done/POSTED_Facebook_*.md
```

**Pass:** Post visible on Facebook, screenshot in `Logs/`
**Fail:** Session expired → run `.venv/bin/python3 scripts/facebook_watcher.py --login`

---

## G2 — Instagram Post (Full HITL Flow)

**Purpose:** Draft Instagram post → approve → auto-post with PIL image.

**Step 1 — Create and approve draft:**
```bash
python3 - << 'EOF'
import sys, shutil
sys.path.insert(0, "scripts")
from instagram_watcher import draft_post_for_approval
path = draft_post_for_approval("AI Employee Hackathon", """My AI Employee clocked in at 3AM while I was asleep.

No salary. No complaints. Just results.

Built for the GIAIC Personal AI Employee Hackathon:
- Monitors Gmail 24/7 and drafts replies
- Posts to LinkedIn, Facebook & Instagram on approval
- Tracks invoices via Odoo

#AIEmployee #GIAIC #BuildInPublic #ClaudeCode #PakistanTech""")
dest = path.parent.parent / "Approved" / path.name
shutil.move(str(path), str(dest))
print(f"Ready: {dest.name}")
EOF
```

**Step 2 — Post it:**
```bash
.venv/bin/python3 scripts/instagram_watcher.py --post
```

**Expected result:**
```
[INFO] InstagramWatcher: Text image created: instagram_image_*.png
[INFO] InstagramWatcher: File uploaded via file chooser
[INFO] InstagramWatcher: Clicked 'Share' to publish
[INFO] InstagramWatcher: Post published (navigated back to feed)
[INFO] InstagramWatcher: Post published and archived to Done/POSTED_Instagram_*.md
```

**Pass:** Post visible on Instagram profile (`instagram.com/devsumair`), screenshot in `Logs/`
**Fail:** Session expired → run `.venv/bin/python3 scripts/instagram_watcher.py --login`

---

## G3 — WhatsApp Watcher

**Purpose:** Scan all WhatsApp chats for urgent/payment keywords.

**Step 1 — Run the watcher:**
```bash
.venv/bin/python3 scripts/whatsapp_watcher.py --watch --once
```

**Expected result:**
```
[INFO] WhatsAppWatcher: Found 69 chats using selector: #pane-side div[role='row']
[INFO] WhatsAppWatcher: Scraped 0 keyword-matching message(s) from 69 chat(s)
```

**Pass:** Chat list found (69 chats scanned), no crash
**Fail:** "Could not find chat list" → session expired, run `--login` and re-scan QR code

**To trigger a test action file — send yourself a WhatsApp message with the word "urgent" then run again:**
```bash
.venv/bin/python3 scripts/whatsapp_watcher.py --watch --once
# Creates: Needs_Action/ACTION_WHATSAPP_*.md
```

---

## G4 — Odoo Accounting Watcher

**Purpose:** Connect to Odoo, check invoices, generate weekly audit.

**Step 1 — Make sure Odoo Docker is running:**
```bash
docker ps
# Should show: odoo_app and odoo_postgres
```

**Step 2 — Start Odoo if not running:**
```bash
cd docker && docker compose up -d && cd ..
```

**Step 3 — Run the watcher:**
```bash
.venv/bin/python3 scripts/odoo_watcher.py --once
```

**Expected result:**
```
[INFO] OdooWatcher: Connected to Odoo at http://localhost:8069 as uid=2
[INFO] OdooWatcher: Weekly audit report written: Accounting/WeeklyAudit_<date>.md
[INFO] OdooWatcher: Action file created: Needs_Action/ACTION_ODOO_Accounting_*.md
```

**Pass:** Both files created
**Fail:** Connection refused → start Docker first

---

## G5 — Master Orchestrator

**Purpose:** One command starts ALL watchers with auto-restart.

```bash
.venv/bin/python3 scripts/orchestrator.py
```

**Expected result within 60 seconds:**
```
[INFO] Orchestrator: [Ralph Wiggum] Watching Needs_Action/ for changes
[INFO] Orchestrator: [Ralph Wiggum] Watching Done/ for changes
[INFO] Orchestrator: [filesystem] Started (pid=XXXXX)
[INFO] Orchestrator: [send_email] Started (pid=XXXXX)
[INFO] Orchestrator: [gmail] Scheduled every 120s
[INFO] Orchestrator: [linkedin_watch] Scheduled every 600s
[INFO] Orchestrator: [linkedin_post] Scheduled every 300s
[INFO] Orchestrator: [odoo] Scheduled every 3600s
[INFO] Orchestrator: All watchers launched. Press Ctrl+C to stop
```

**Pass:** All watchers launched, Ralph Wiggum loop active
**Fail:** Check individual watcher errors in `Logs/orchestrator.log`

---

## G6 — Audit Logger

**Purpose:** Verify JSON audit trail is working.

```bash
.venv/bin/python3 scripts/audit_logger.py --summary
```

**Expected result:**
```
=== AI Employee Audit Summary — YYYY-MM-DD ===
  Total actions    : X
  Approvals needed : X
  Approvals given  : X
```

**Check today's log file:**
```bash
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json
```

**Pass:** Summary displays, JSON file exists
**Fail:** Empty — run some workflows first then check again

---

## G7 — Ralph Wiggum Loop (Real-Time Awareness)

**Purpose:** Verify the orchestrator detects new files instantly.

**Step 1 — Start orchestrator:**
```bash
.venv/bin/python3 scripts/orchestrator.py
```

**Step 2 — In another terminal, drop a test file:**
```bash
echo "# Test Action" > "AI_Employee_Vault/Needs_Action/ACTION_TEST_$(date +%Y%m%d_%H%M%S).md"
```

**Expected result (in orchestrator terminal within 2 seconds):**
```
[INFO] Orchestrator: [Ralph Wiggum] New action detected: ACTION_TEST_*.md
```

**Pass:** Detection logged within 2 seconds
**Fail:** Watchdog not installed — run `.venv/bin/pip install watchdog`

---

# PLATINUM TIER TESTS

---

## P1 — Oracle Cloud VM Running 24/7

**Purpose:** Verify the AI Employee is live on Oracle Cloud.

```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 "sudo systemctl status ai-employee --no-pager"
```

**Expected result:**
```
● ai-employee.service - AI Employee Orchestrator
   Active: active (running) since ...
   Main PID: XXXXX (python3)
```

**Pass:** `active (running)` shown
**Fail:** Run `sudo systemctl start ai-employee`

---

## P2 — Odoo Running on Cloud

**Purpose:** Verify Odoo Docker containers are live on Oracle VM.

```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 "sudo docker ps"
```

**Expected result:**
```
NAMES           STATUS
odoo_app        Up X hours
odoo_postgres   Up X hours
```

**Access from browser:** `http://92.4.74.176:8069`

**Pass:** Both containers running, Odoo accessible in browser
**Fail:** `sudo docker start odoo_app odoo_postgres`

---

## P3 — Cloud Odoo Watcher

**Purpose:** Verify Odoo watcher works on cloud VM.

```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "cd ~/ai-employee && .venv/bin/python3 scripts/odoo_watcher.py --once"
```

**Expected result:**
```
[INFO] OdooWatcher: Connected to Odoo at http://localhost:8069 as uid=2
[INFO] OdooWatcher: Weekly audit report written: Accounting/WeeklyAudit_*.md
[INFO] OdooWatcher: Action file created: Needs_Action/ACTION_ODOO_Accounting_*.md
```

**Pass:** Connected and files created on cloud VM
**Fail:** Check `.env` credentials on VM

---

## P4 — Cloud Gmail Watcher

**Purpose:** Verify Gmail watcher running on cloud VM picks up emails.

```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "cd ~/ai-employee && .venv/bin/python3 scripts/gmail_watcher.py --once"
```

**Expected result:**
```
[INFO] GmailWatcher: Connected as: devsumair@gmail.com
[INFO] GmailWatcher: Found X new email(s)
```

**Pass:** Connected to Gmail from cloud
**Fail:** `token.json` missing on VM — upload from local:
```bash
scp -i ~/.ssh/oracle_ai_employee token.json ubuntu@92.4.74.176:~/ai-employee/
```

---

## P5 — Cloud Orchestrator Live Log

**Purpose:** Watch the orchestrator logs in real-time on cloud VM.

```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "tail -f ~/ai-employee/AI_Employee_Vault/Logs/orchestrator.log"
```

**Expected result:** Live log showing scheduled jobs running every 2 minutes (gmail), 10 minutes (linkedin), etc.

**Pass:** Logs updating continuously
**Fail:** Log empty → `sudo systemctl restart ai-employee`

---

## P6 — Auto-Restart on Reboot Test

**Purpose:** Verify orchestrator and Docker auto-start after VM reboot.

```bash
# Check systemd is enabled
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "sudo systemctl is-enabled ai-employee && sudo systemctl is-enabled docker"
```

**Expected result:**
```
enabled
enabled
```

**Pass:** Both enabled
**Fail:** Run `sudo systemctl enable ai-employee docker`

---

## P7 — Full End-to-End Platinum Test

**Purpose:** Email arrives on cloud → detected → action file created → (would notify local for approval).

**Step 1 — Send a test email** to `devsumair@gmail.com` from any other account with subject "URGENT: Test from Platinum"

**Step 2 — Wait 2 minutes (Gmail polls every 2 min) or run manually:**
```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "cd ~/ai-employee && .venv/bin/python3 scripts/gmail_watcher.py --once"
```

**Step 3 — Check action file created on cloud:**
```bash
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 \
  "ls ~/ai-employee/AI_Employee_Vault/Needs_Action/ACTION_EMAIL_*.md | tail -3"
```

**Expected result:** New `ACTION_EMAIL_*.md` file created on the cloud VM

**Pass:** Email detected on cloud within 2 minutes, action file created
**Fail:** Check `token.json` is on VM and not expired

---

# QUICK REFERENCE — All Test Commands

```bash
# ── Bronze ─────────────────────────────────────────────────
.venv/bin/python3 scripts/verify.py                          # B1: Setup check
.venv/bin/python3 scripts/filesystem_watcher.py              # B3: File watcher

# ── Silver ─────────────────────────────────────────────────
.venv/bin/python3 scripts/gmail_watcher.py --once            # S1: Gmail poll
.venv/bin/python3 scripts/send_email.py                      # S3: Send approved email
.venv/bin/python3 scripts/linkedin_watcher.py --post         # S4: LinkedIn post
.venv/bin/python3 scripts/run_briefing.py                    # S6: CEO briefing

# ── Gold ───────────────────────────────────────────────────
.venv/bin/python3 scripts/facebook_watcher.py --post         # G1: Facebook post
.venv/bin/python3 scripts/instagram_watcher.py --post        # G2: Instagram post
.venv/bin/python3 scripts/whatsapp_watcher.py --watch --once # G3: WhatsApp scan
.venv/bin/python3 scripts/odoo_watcher.py --once             # G4: Odoo audit
.venv/bin/python3 scripts/orchestrator.py                    # G5: Start all watchers
.venv/bin/python3 scripts/audit_logger.py --summary          # G6: Audit summary

# ── Platinum (run on Oracle VM) ────────────────────────────
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 "sudo systemctl status ai-employee"
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 "sudo docker ps"
ssh -i ~/.ssh/oracle_ai_employee ubuntu@92.4.74.176 "tail -f ~/ai-employee/AI_Employee_Vault/Logs/orchestrator.log"
```

---

# SESSION RENEWAL (When Browser Sessions Expire)

Social media sessions expire after ~7-30 days. Re-login commands:

```bash
# LinkedIn
.venv/bin/python3 scripts/linkedin_watcher.py --login

# Facebook
.venv/bin/python3 scripts/facebook_watcher.py --login

# Instagram
.venv/bin/python3 scripts/instagram_watcher.py --login

# WhatsApp (scan QR with phone)
.venv/bin/python3 scripts/whatsapp_watcher.py --login

# Gmail (if token expires)
rm token.json
.venv/bin/python3 scripts/gmail_watcher.py --auth
```

**After re-login, upload new sessions to Oracle VM:**
```bash
scp -i ~/.ssh/oracle_ai_employee token.json ubuntu@92.4.74.176:~/ai-employee/
scp -i ~/.ssh/oracle_ai_employee -r .linkedin-session ubuntu@92.4.74.176:~/ai-employee/
scp -i ~/.ssh/oracle_ai_employee -r .facebook-session ubuntu@92.4.74.176:~/ai-employee/
scp -i ~/.ssh/oracle_ai_employee -r .instagram-session ubuntu@92.4.74.176:~/ai-employee/
scp -i ~/.ssh/oracle_ai_employee -r .whatsapp-session ubuntu@92.4.74.176:~/ai-employee/
```

---

*Built for GIAIC · Personal AI Employee Hackathon 0 · 2026*
*Stack: Claude Code · Python · Playwright · Odoo · Docker · Oracle Cloud · Obsidian*
