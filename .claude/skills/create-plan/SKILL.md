---
name: create-plan
description: |
  Claude reasoning loop that reads Needs_Action/ items, reasons through them,
  and creates structured Plan.md files in the vault with checkboxes for next steps.
  This is the core Silver tier reasoning capability — turns raw action items into
  actionable plans. Use when the user wants Claude to think through a problem,
  create a plan, make a task breakdown, or reason about what to do next.
---

# Create Plan — AI Employee Skill

Claude's reasoning loop: read context → think → create a structured Plan.md with checkboxes.

## What This Does

Transforms raw items from `Needs_Action/` into a clear, actionable `Plans/<domain>/Plan_<topic>_<date>.md` file with:
- Situation summary
- Recommended actions (checkboxes)
- Risk flags
- Items needing human approval
- Suggested timeline

---

## Vault Structure for Plans

```
AI_Employee_Vault/
├── Needs_Action/          ← Input: raw action items
├── Plans/                 ← Output: Plan.md files live here
│   ├── Finance/           ← e.g. Plans/Finance/Plan_Invoice_ClientA_20260304.md
│   ├── Communications/    ← e.g. Plans/Communications/Plan_EmailReply_20260304.md
│   ├── Social/            ← e.g. Plans/Social/Plan_LinkedIn_Post_20260304.md
│   └── General/           ← everything else
└── Needs_Action/
```

Create Plans/ subfolders if they don't exist:
```bash
mkdir -p "AI_Employee_Vault/Plans/Finance" \
         "AI_Employee_Vault/Plans/Communications" \
         "AI_Employee_Vault/Plans/Social" \
         "AI_Employee_Vault/Plans/General"
```

---

## Reasoning Loop Workflow

### Step 1 — Gather Context

```bash
# Read rules
cat "AI_Employee_Vault/Company_Handbook.md"

# Read all pending action items
ls "AI_Employee_Vault/Needs_Action/"
cat "AI_Employee_Vault/Needs_Action/ACTION_*.md"

# Read dashboard for big picture
cat "AI_Employee_Vault/Dashboard.md"
```

### Step 2 — Reason (Claude's internal process)

For each action item, Claude asks:
1. **What is this?** — classify the item (email, file, payment, task)
2. **How urgent is it?** — per Company_Handbook urgency levels
3. **What are my options?** — enumerate 2-3 possible responses
4. **What does the handbook say?** — apply rules of engagement
5. **Does this need approval?** — if yes, flag for HITL
6. **What's the best next step?** — choose the most appropriate action

### Step 3 — Write Plan.md

Claude writes to `AI_Employee_Vault/Plans/<domain>/Plan_<topic>_<date>.md`:

```markdown
---
type: plan
domain: Finance
topic: Invoice Client A - Payment Overdue
created: 2026-03-04
urgency: Critical
status: active
related_action: ACTION_urgent_invoice_20260304_112248.md
---

# Plan: Invoice Client A — Payment Overdue

## Situation Summary
Client A has sent an urgent notice that invoice #1234 is overdue.
The original file detected keywords: urgent, invoice, payment overdue.

## Reasoning
This is a Critical urgency item (payment overdue). Per Company_Handbook.md:
- Payments require APPROVAL_REQUIRED workflow
- Response time: Immediate
- Never execute payment without human sign-off

## Recommended Actions

### Immediate (Today)
- [ ] Review invoice details in Inbox/urgent_invoice.txt
- [ ] Confirm amount owed and due date
- [ ] Contact Client A to acknowledge receipt

### Requires Approval
- [ ] APPROVAL_REQUIRED: Process payment to Client A (amount TBD)
  → File: Needs_Action/APPROVAL_REQUIRED_Payment_ClientA_*.md

### Follow-up
- [ ] Confirm payment received by client
- [ ] Archive all related files to Done/

## Risk Flags
⚠️ Payment action blocked until Sumair approves APPROVAL_REQUIRED file.

## Suggested Timeline
| Action | By When |
|--------|---------|
| Acknowledge to Client A | Today |
| Payment approval decision | Today |
| Payment executed (if approved) | Within 24h |

## Notes
*(Add your notes here as you work through this plan)*
```

### Step 4 — Update Dashboard and Log

After creating the plan:
```bash
# Log
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Claude Code: Plan created → Plans/Finance/Plan_Invoice_ClientA_$(date +%Y%m%d).md" \
  >> "AI_Employee_Vault/Logs/activity.log"
```

Update `Dashboard.md` to reference the new plan.

---

## Plan Naming Convention

```
Plans/<Domain>/Plan_<Topic>_<YYYYMMDD>.md
```

Examples:
- `Plans/Finance/Plan_Invoice_ClientA_20260304.md`
- `Plans/Communications/Plan_EmailReply_Newsletter_20260304.md`
- `Plans/Social/Plan_LinkedIn_WeeklyPost_20260304.md`
- `Plans/General/Plan_WeeklyReview_20260304.md`

---

## Monday Morning CEO Briefing

A special plan type — comprehensive weekly review:

```bash
# Trigger manually or via cron every Monday 8AM
# Claude reads all of:
# - Needs_Action/ (pending items)
# - Done/ (completed this week)
# - Logs/activity.log (activity summary)
# Then writes:
# Plans/General/Plan_CEOBriefing_<date>.md
```

Weekly briefing plan includes:
- [ ] Items completed last week
- [ ] Items still pending
- [ ] Bottlenecks identified
- [ ] Revenue/business activity summary
- [ ] Priorities for this week

---

## Triggering This Skill

User can say:
- "Create a plan for [topic]"
- "Think through what to do about [item]"
- "Make a Plan.md for the pending items"
- "Run the reasoning loop"
- "What's my action plan for today?"
- "Monday morning briefing"
