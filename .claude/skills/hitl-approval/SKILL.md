---
name: hitl-approval
description: |
  Human-in-the-Loop approval workflow for sensitive AI Employee actions.
  Creates APPROVAL_REQUIRED_*.md files in Needs_Action/ for payments, emails,
  social posts, and other irreversible actions. Monitors the vault for approvals
  and executes only after human sign-off. Use when Claude needs to request
  approval, check approval status, list pending approvals, or execute an
  approved action.
---

# HITL Approval — AI Employee Skill

The Human-in-the-Loop approval system. Claude proposes — you decide — Claude executes.

## Core Principle

> Claude will **never** take an irreversible action without explicit human approval.
> This skill is the gatekeeper for all sensitive operations.

---

## Approval-Required Actions

| Action Type | Trigger Condition | File Prefix |
|-------------|------------------|-------------|
| Payment | Any payment or bank transfer | `APPROVAL_REQUIRED_Payment_` |
| Email send | Sending email to external party | `APPROVAL_REQUIRED_Email_` |
| LinkedIn post | Publishing social media content | `APPROVAL_REQUIRED_LinkedIn_` |
| File deletion | Deleting any file permanently | `APPROVAL_REQUIRED_Delete_` |
| External API | Calling any paid/external service | `APPROVAL_REQUIRED_API_` |
| WhatsApp reply | Sending message to a contact | `APPROVAL_REQUIRED_WhatsApp_` |

---

## Creating an Approval Request

Claude creates the approval file automatically. You can also trigger manually:

```
Request approval for: [describe action]
```

### Approval File Format

```
Needs_Action/APPROVAL_REQUIRED_<Category>_<Description>_<YYYYMMDD_HHMMSS>.md
```

```markdown
---
type: approval_required
category: Payment
description: Pay Client A - Invoice #1234
amount: 500.00
currency: USD
urgency: Critical
status: awaiting_approval
created: 2026-03-04T10:30:00
expires: 2026-03-05T10:30:00
---

# APPROVAL REQUIRED: Payment — Client A

🔴 Urgency: Critical | Expires: 2026-03-05

## What Claude Wants to Do
Send payment of **$500.00** to Client A for Invoice #1234.

## Why
Invoice #1234 detected as overdue in urgent_invoice.txt (Inbox/).

## Exact Action That Will Be Taken
1. Log into payment portal
2. Create payment: $500.00 → Client A (Account: XXXX)
3. Submit payment with reference "Invoice #1234"
4. Screenshot confirmation
5. Log to Logs/activity.log

## Risk Assessment
- ⚠️ Irreversible once submitted
- ⚠️ Verify bank details before approving

## To APPROVE
Move this file to: `Done/`
Claude will then execute the payment automatically.

## To REJECT
Delete this file. Claude will not proceed.

## To EDIT
Edit the details above, then move to `Done/`.
```

---

## Checking Pending Approvals

```bash
# List all pending approval files
ls "AI_Employee_Vault/Needs_Action/APPROVAL_REQUIRED_"*.md 2>/dev/null \
  || echo "No pending approvals"
```

Claude will also summarize pending approvals when asked:
```
What approvals are waiting for me?
```

---

## Vault Folder Structure for HITL

```
AI_Employee_Vault/
├── Needs_Action/
│   └── APPROVAL_REQUIRED_*.md   ← Awaiting your review
├── Done/
│   └── APPROVED_*.md            ← Moved here after you approve
└── Logs/
    └── activity.log             ← All approval events logged
```

> Note: Create an `Approved/` and `Rejected/` subfolder if you want separate tracking:
> ```bash
> mkdir -p "AI_Employee_Vault/Approved" "AI_Employee_Vault/Rejected"
> ```

---

## Approval Execution Flow

```
[Claude detects sensitive action needed]
         ↓
[Creates APPROVAL_REQUIRED_*.md in Needs_Action/]
         ↓
[Claude STOPS — does nothing further]
         ↓
[You review the file in Obsidian]
         ↓
        / \
    YES    NO
     ↓      ↓
 [Move to  [Delete
  Done/]    file]
     ↓
[Claude detects file moved]
     ↓
[Claude executes the approved action]
     ↓
[Logs result to activity.log]
```

---

## Monitoring for Approval (Watcher Integration)

The filesystem watcher can be extended to detect approvals:

```python
# In filesystem_watcher.py — detect when APPROVAL_REQUIRED files move to Done/
def check_for_approvals(self) -> list:
    approved = []
    for f in (self.vault_path / "Done").glob("APPROVAL_REQUIRED_*.md"):
        if f.name not in self.processed_approvals:
            approved.append(f)
    return approved
```

Or simply ask Claude to check:
```
Check if any approvals have been granted
```

---

## Expiry Policy

Approval files expire after **24 hours** by default (set in file frontmatter).

Expired approvals:
- Are moved to `Done/` with status `expired`
- Are logged as expired in `activity.log`
- Claude will NOT execute an expired approval

---

## Security Notes

- Approval files contain **no credentials** — only descriptions of actions
- All approvals and rejections are logged immutably
- Claude cannot self-approve — it only reads the `Done/` folder for confirmation

---

## Triggering This Skill

User can say:
- "What approvals are waiting?"
- "Show me pending HITL items"
- "Request approval for [action]"
- "Check if my approval was processed"
- "List sensitive actions waiting for review"
