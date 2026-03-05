---
name: linkedin-post
description: |
  Automatically draft and post content to LinkedIn to generate business sales leads.
  Uses Playwright browser automation to log into LinkedIn and publish posts.
  Always requires HITL approval before posting — never posts without human review.
  Use when the user wants to post on LinkedIn, schedule a LinkedIn update, draft
  business content, or generate leads via social media.
---

# LinkedIn Post — AI Employee Skill

Draft and publish LinkedIn posts to generate business sales leads, with mandatory human approval.

## Workflow

```
1. Claude drafts post content
2. Writes APPROVAL_REQUIRED_LinkedIn_*.md to Needs_Action/
3. STOPS — waits for human review
4. Human approves → moves file to Done/
5. Claude uses Playwright to post on LinkedIn
6. Screenshots confirmation, logs result
```

**LinkedIn posts NEVER go live without Sumair's explicit approval.**

---

## Step 1 — Draft Post Content

Claude writes a draft based on your business context from `Company_Handbook.md`.

Post types to choose from:
- **Value post**: Share an insight or tip relevant to your business
- **Lead magnet**: Offer something free in exchange for engagement
- **Social proof**: Share a client win or testimonial
- **Announcement**: New service, product, or update

Provide context to Claude:
```
Draft a LinkedIn post about [topic/service]. Tone: professional. Goal: generate leads.
```

---

## Step 2 — Approval File Created

Claude creates:
```
Needs_Action/APPROVAL_REQUIRED_LinkedIn_<timestamp>.md
```

Format:
```markdown
---
type: approval_required
category: linkedin_post
status: awaiting_approval
created: 2026-03-04T10:00:00
---

# APPROVAL REQUIRED: LinkedIn Post

## Draft Content

[Full post text here]

## Target Audience
[Who this post targets]

## Goal
[Lead generation / brand awareness / announcement]

## To Approve
Move this file to Done/ — Claude will then post to LinkedIn.

## To Edit
Edit the post content above, then move to Done/.

## To Cancel
Delete this file.
```

---

## Step 3 — Post to LinkedIn (After Approval)

Uses `browsing-with-playwright` skill to automate LinkedIn:

```bash
# Start Playwright MCP server
bash scripts/start-server.sh

# Navigate to LinkedIn
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_navigate \
  -p '{"url": "https://www.linkedin.com"}'

# Take snapshot to find post creation button
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'

# Click "Start a post"
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_click \
  -p '{"element": "Start a post button", "ref": "<ref-from-snapshot>"}'

# Type post content
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_type \
  -p '{"element": "Post text area", "ref": "<ref>", "text": "<approved-content>"}'

# Click Post button
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_click \
  -p '{"element": "Post button", "ref": "<ref>"}'

# Screenshot confirmation
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_take_screenshot \
  -p '{"type": "png"}'
```

---

## LinkedIn Session Management

LinkedIn requires login. Use a **persistent browser context** to stay logged in:

```bash
# First time: log in manually with headed browser
npx @playwright/mcp@latest --port 8808 --shared-browser-context \
  --user-data-dir ~/.linkedin-session

# Subsequent runs: session is reused (no re-login needed)
npx @playwright/mcp@latest --port 8808 --shared-browser-context \
  --user-data-dir ~/.linkedin-session
```

**Store session directory path in `.env`** — never hardcode it.

---

## Post Scheduling (via cron)

To post at a specific time, use the `schedule-tasks` skill.

Example cron (post every Monday at 9 AM):
```
0 9 * * 1 cd /path/to/project && .venv/bin/python3 scripts/linkedin_scheduler.py
```

---

## Vault Integration

| File | Purpose |
|------|---------|
| `Needs_Action/APPROVAL_REQUIRED_LinkedIn_*.md` | Draft awaiting approval |
| `Done/POSTED_LinkedIn_*.md` | Confirmed posted content + screenshot path |
| `Logs/activity.log` | All LinkedIn activity logged |

---

## Security Rules

- LinkedIn credentials are **never** stored in `.md` files
- Session cookies live in `~/.linkedin-session/` (gitignored)
- All posts go through HITL approval — no auto-posting
- Screenshot of every post saved as evidence

---

## Triggering This Skill

User can say:
- "Post on LinkedIn"
- "Draft a LinkedIn post about [topic]"
- "Schedule a LinkedIn update"
- "Generate leads via LinkedIn"
- "Create a social media post for my business"
