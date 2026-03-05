---
name: process-vault
description: |
  Process pending action files in the AI Employee Vault.
  Reads Needs_Action/ for .md action files, processes each file according
  to Company_Handbook.md rules, writes summaries to Inbox/, and moves
  completed items to Done/. Use when the user asks to process vault items,
  check pending actions, or run the AI employee workflow.
---

# Process Vault — AI Employee Skill

Process pending items in the AI Employee Vault using Claude Code.

## Vault Location

```
AI_Employee_Vault/
├── Company_Handbook.md   ← Read this FIRST for rules of engagement
├── Dashboard.md          ← Update this LAST with new counts
├── Needs_Action/         ← Scan for ACTION_*.md files
├── Inbox/                ← Processed source files live here
└── Done/                 ← Move completed action files here
```

## Workflow

### Step 1 — Read the Rules

```bash
cat "AI_Employee_Vault/Company_Handbook.md"
```

Internalize the rules before processing any items.

### Step 2 — List Pending Items

```bash
ls -la "AI_Employee_Vault/Needs_Action/"
```

### Step 3 — Process Each Action File

For each `ACTION_*.md` file in `Needs_Action/`:

1. Read the action file metadata (type, urgency, original filename)
2. Read the source file from `Inbox/` if it exists
3. Summarize the content
4. Write a summary report to `Inbox/<name>_SUMMARY.md`
5. Move the action file to `Done/`

**Example processing command:**
```bash
# Read action file
cat "AI_Employee_Vault/Needs_Action/ACTION_filename_timestamp.md"

# Read source file
cat "AI_Employee_Vault/Inbox/original_file.txt"

# Write summary
cat > "AI_Employee_Vault/Inbox/original_file_SUMMARY.md" << 'EOF'
# Summary: original_file.txt
...summary content...
EOF

# Move action file to Done
mv "AI_Employee_Vault/Needs_Action/ACTION_filename_timestamp.md" \
   "AI_Employee_Vault/Done/"
```

### Step 4 — Handle APPROVAL_REQUIRED Items

If an action file starts with `APPROVAL_REQUIRED_`:
- **DO NOT process automatically**
- Report it to the user
- Wait for the user to manually move it to `Done/` after review

### Step 5 — Update Dashboard

After processing all items, update `Dashboard.md` counts:
- Pending items in /Needs_Action
- Items in /Done
- Last Updated timestamp

## Urgency Handling

| Urgency | Action |
|---------|--------|
| 🔴 Critical | Report immediately to user before processing others |
| 🟡 High | Process first in the queue |
| 🟢 Normal | Process in order |

## Rules from Company_Handbook.md (Summary)

- Never take irreversible actions without approval
- Log everything to `Logs/activity.log`
- Privacy first — no external services without approval
- Credentials never in .md files

## Triggering This Skill

User can say:
- "Process pending vault items"
- "Check /Needs_Action"
- "Run the AI employee workflow"
- "What's in my Needs_Action folder?"
