---
name: schedule-tasks
description: |
  Set up cron jobs (Linux/Mac) or Task Scheduler (Windows) to run AI Employee
  tasks automatically on a schedule. Use to schedule watcher scripts, daily briefings,
  LinkedIn posts, or any recurring AI Employee workflow. Use when the user wants
  to automate a task to run at a specific time, set up a daily briefing, schedule
  a recurring job, or configure cron.
---

# Schedule Tasks — AI Employee Skill

Automate AI Employee workflows with cron (Linux/Mac) or Task Scheduler (Windows).

## Scheduled Task Types

| Schedule | Task | Trigger |
|----------|------|---------|
| Startup | Start all watchers | On login / machine boot |
| Daily 8AM | Monday CEO briefing | cron `0 8 * * *` |
| Every Monday 9AM | LinkedIn lead post | cron `0 9 * * 1` |
| Every 2 min | Gmail watcher | cron `*/2 * * * *` |
| Every 10 min | File system watcher | cron `*/10 * * * *` |
| Daily midnight | Cleanup Done/ older than 30d | cron `0 0 * * *` |

---

## Setup: Linux/Mac (cron)

### Open crontab editor

```bash
crontab -e
```

### Cron format

```
MIN HOUR DAY MONTH WEEKDAY command
 *   *    *    *      *     /path/to/command
```

### Recommended cron entries

```cron
# AI Employee — Scheduled Tasks
# Edit with: crontab -e

# Daily CEO briefing at 8:00 AM (Monday–Friday)
0 8 * * 1-5 cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0" && \
  .venv/bin/python3 scripts/run_briefing.py >> AI_Employee_Vault/Logs/cron.log 2>&1

# LinkedIn post every Monday at 9:00 AM
0 9 * * 1 cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0" && \
  .venv/bin/python3 scripts/linkedin_scheduler.py >> AI_Employee_Vault/Logs/cron.log 2>&1

# Gmail watcher — poll every 2 minutes
*/2 * * * * cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0" && \
  .venv/bin/python3 scripts/gmail_watcher.py --once >> AI_Employee_Vault/Logs/cron.log 2>&1

# File system watcher — keep alive (restarts if crashed)
@reboot cd "/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0" && \
  .venv/bin/python3 scripts/filesystem_watcher.py >> AI_Employee_Vault/Logs/cron.log 2>&1
```

### Install cron entries

```bash
# Add entries directly
(crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -

# Verify
crontab -l

# View cron logs
tail -f "AI_Employee_Vault/Logs/cron.log"
```

---

## Setup: Windows (Task Scheduler)

```powershell
# Daily CEO Briefing at 8:00 AM
$action = New-ScheduledTaskAction -Execute "python" `
  -Argument "scripts\run_briefing.py" `
  -WorkingDirectory "C:\path\to\project"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"
Register-ScheduledTask -TaskName "AIEmployee_Briefing" `
  -Action $action -Trigger $trigger -RunLevel Highest

# LinkedIn every Monday 9AM
$trigger2 = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 `
  -DaysOfWeek Monday -At "09:00AM"
Register-ScheduledTask -TaskName "AIEmployee_LinkedIn" `
  -Action $action -Trigger $trigger2 -RunLevel Highest
```

---

## Crontab File (save as scripts/crontab.txt)

```bash
# Generate the crontab template file
cat > scripts/crontab.txt << 'CRON'
# AI Employee Vault — Scheduled Tasks
# Install with: (crontab -l 2>/dev/null; cat scripts/crontab.txt) | crontab -

PROJECT="/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0"
PYTHON="$PROJECT/.venv/bin/python3"
LOG="$PROJECT/AI_Employee_Vault/Logs/cron.log"

# Daily CEO briefing Mon-Fri at 8AM
0 8 * * 1-5 cd "$PROJECT" && $PYTHON scripts/run_briefing.py >> $LOG 2>&1

# LinkedIn post every Monday 9AM
0 9 * * 1 cd "$PROJECT" && $PYTHON scripts/linkedin_scheduler.py >> $LOG 2>&1

# Gmail poll every 2 minutes
*/2 * * * * cd "$PROJECT" && $PYTHON scripts/gmail_watcher.py --once >> $LOG 2>&1

# Start filesystem watcher on reboot
@reboot cd "$PROJECT" && $PYTHON scripts/filesystem_watcher.py >> $LOG 2>&1
CRON
```

---

## Viewing & Managing Schedules

```bash
# List all scheduled tasks
crontab -l

# Remove all cron jobs (careful!)
crontab -r

# Check what ran recently
tail -50 "AI_Employee_Vault/Logs/cron.log"

# Check if watcher process is running
pgrep -a python3 | grep watcher
```

---

## `--once` Flag Pattern

For cron-compatible scripts that run once and exit (vs continuous loop):

```python
# In gmail_watcher.py, check_interval is irrelevant when called with --once
if "--once" in sys.argv:
    items = watcher.check_for_updates()
    for item in items:
        watcher.create_action_file(item)
    # exit — cron will re-run next cycle
else:
    watcher.run()  # continuous loop
```

---

## Vault Log for Schedule Events

All scheduled runs append to `Logs/cron.log`:
```
2026-03-04 08:00:01 [INFO] run_briefing: Starting Monday CEO Briefing
2026-03-04 08:00:03 [INFO] run_briefing: Plan created → Plans/General/Plan_CEOBriefing_20260304.md
2026-03-04 08:00:03 [INFO] run_briefing: Briefing complete.
```

---

## Triggering This Skill

User can say:
- "Schedule [task] to run at [time]"
- "Set up a daily briefing at 8AM"
- "Add a cron job for [script]"
- "Run the Gmail watcher every 2 minutes automatically"
- "Schedule LinkedIn posts for every Monday"
- "Show me my scheduled tasks"
