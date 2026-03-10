---
type: plan
domain: Communications
topic: Inbox Management — Week of Mar 11, 2026
created: 2026-03-11
urgency: Normal
status: active
---

# Plan: Inbox Management — Week of Mar 11, 2026

## Situation Summary

Based on vault activity and Gmail inbox review:
- **1,193 unread emails** in inbox (johnalex21210@gmail.com)
- **29 items processed** in Done/ since system started
- **0 items pending** in Needs_Action/ as of today
- Gmail watcher is now polling `is:unread in:inbox` (fixed from `is:unread is:important`)
- 2 emails successfully sent this week via Gmail API
- 1 LinkedIn post published successfully

Key recurring patterns identified in inbox:
1. **Lovable payment failures** — 4+ emails, Rs 7,280.20 overdue (unresolved)
2. **GitHub token expiry alerts** — fine-grained token expired (action needed)
3. **LaundryWalaa/LaundryXpress** — order notifications (low priority, archive)
4. **Medium Daily Digest** — newsletters (low priority, unsubscribe or filter)
5. **Dev Sumair test emails** — testing workflow (no action)

---

## Reasoning

The inbox has 1,193 unread emails but the watcher only picks up new ones going forward (by tracking processed IDs). The backlog requires a one-time cleanup pass. The most critical unresolved item is the Lovable payment.

---

## Recommended Actions

### Critical — Do Today
- [ ] Resolve Lovable payment (Rs 7,280.20 overdue x4 attempts)
  → Log into Lovable.dev → Billing → Update payment method
  → Or cancel subscription if no longer needed
  → Then move `APPROVAL_REQUIRED_Payment_Lovable_*.md` to Done/

### High Priority — This Week
- [ ] Renew GitHub fine-grained personal access token
  → Go to GitHub Settings → Developer Settings → Personal Access Tokens
  → Regenerate expired token
- [ ] Reply to any client or business emails in inbox
  → Tell Claude: "Draft a reply to [sender] about [topic]"

### Routine — Daily
- [ ] Run Gmail watcher once a day (or let cron handle it)
  `.venv/bin/python3 scripts/gmail_watcher.py --once`
- [ ] Say "Process pending vault items" after each poll
- [ ] Review and approve any APPROVAL_REQUIRED files same day

### Inbox Hygiene — Do Once This Week
- [ ] Unsubscribe from Medium Daily Digest (or create Gmail filter to auto-archive)
- [ ] Create Gmail filter for LaundryWalaa/LaundryXpress → skip inbox, label "Apps"
- [ ] Archive all read promotional emails older than 30 days

### Ongoing Automation (Already Running)
- [x] Gmail watcher polls inbox continuously
- [x] Action files auto-created for new emails
- [x] HITL approval workflow active for payments and sends
- [x] Cron schedule installed for 24/7 operation

---

## Risk Flags

- Payment to Lovable is 4+ attempts overdue — service may be suspended soon
- GitHub token expiry may break CI/CD pipelines silently
- 1,193 unread emails means some important messages may be buried

---

## Suggested Timeline

| Action | By When | Owner |
|--------|---------|-------|
| Fix Lovable payment | Today | Sumair (manual) |
| Renew GitHub token | Today | Sumair (manual) |
| Daily Gmail poll | Every day | Cron (automated) |
| Inbox filter setup | This week | Sumair (5 min task) |
| Weekly vault review | Every Monday | Claude Code (automated briefing) |

---

## Notes

*(Add your notes here as you work through this plan)*

---
*Plan created by Claude Code AI Employee — 2026-03-11*
