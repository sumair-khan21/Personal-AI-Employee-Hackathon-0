"""
audit_logger.py - Structured JSON audit logger for all AI Employee actions.

Writes one JSON log file per calendar day to:
    AI_Employee_Vault/Logs/YYYY-MM-DD.json

Each log entry captures who did what, to whom, with what parameters,
whether approval was required, and what the outcome was.

CLI flags:
  --summary   Print today's action summary to terminal
  --cleanup   Delete log files older than 90 days
"""

import sys
import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta, date

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
LOGS_DIR = VAULT_PATH / "Logs"


# ---------------------------------------------------------------------------
# Core logging
# ---------------------------------------------------------------------------

def _get_log_path(date_str=None):
    """
    Return the Path for the JSON log file for a given date.

    Args:
        date_str: ISO date string 'YYYY-MM-DD'. Defaults to today.

    Returns:
        pathlib.Path for the log file.
    """
    if date_str is None:
        date_str = date.today().isoformat()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{date_str}.json"


def _read_log(log_path):
    """
    Load and return the list of entries from a JSON log file.

    Args:
        log_path: Path to the JSON log file.

    Returns:
        List of entry dicts. Returns [] if file does not exist or is corrupt.
    """
    if not log_path.exists():
        return []
    try:
        content = log_path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[audit_logger] WARNING: Could not read {log_path}: {e}", file=sys.stderr)
        return []


def _write_log(log_path, entries):
    """
    Serialise and write the entries list to the JSON log file.

    Args:
        log_path: Path to the JSON log file.
        entries:  List of entry dicts to write.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def log_action(
    action_type,
    target,
    parameters,
    approval_status,
    approved_by,
    result,
    actor="claude_code",
):
    """
    Append a single structured audit entry to today's JSON log file.

    Args:
        action_type:     Short string identifying the action, e.g. 'email_send'.
        target:          The primary object/recipient of the action, e.g. 'client@example.com'.
        parameters:      Dict of additional context (subject, amount, etc.).
        approval_status: One of 'approved', 'pending', 'rejected', 'not_required'.
        approved_by:     Who approved — e.g. 'human', 'auto', 'none'.
        result:          Outcome string — 'success', 'failure', 'skipped', etc.
        actor:           System or user that performed the action. Default 'claude_code'.

    Returns:
        The new log entry dict that was appended.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "parameters": parameters if isinstance(parameters, dict) else {},
        "approval_status": approval_status,
        "approved_by": approved_by,
        "result": result,
        "session_id": str(uuid.uuid4()),
    }

    log_path = _get_log_path()
    entries = _read_log(log_path)
    entries.append(entry)
    _write_log(log_path, entries)
    return entry


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def get_today_log():
    """
    Return all audit entries logged today.

    Returns:
        List of entry dicts for today (may be empty).
    """
    return _read_log(_get_log_path())


def get_log_summary(date_str=None):
    """
    Produce a summary of all audit entries for a given day.

    Args:
        date_str: ISO date string 'YYYY-MM-DD'. Defaults to today.

    Returns:
        Dict with keys:
            total_actions   (int)
            by_type         (dict mapping action_type -> count)
            by_result       (dict mapping result -> count)
            approvals_needed (int — entries where approval_status != 'not_required')
            approvals_given  (int — entries where approval_status == 'approved')
    """
    entries = _read_log(_get_log_path(date_str))

    by_type = {}
    by_result = {}
    approvals_needed = 0
    approvals_given = 0

    for e in entries:
        atype = e.get("action_type", "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1

        res = e.get("result", "unknown")
        by_result[res] = by_result.get(res, 0) + 1

        if e.get("approval_status") != "not_required":
            approvals_needed += 1
        if e.get("approval_status") == "approved":
            approvals_given += 1

    return {
        "total_actions": len(entries),
        "by_type": by_type,
        "by_result": by_result,
        "approvals_needed": approvals_needed,
        "approvals_given": approvals_given,
    }


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def cleanup_old_logs(retention_days=90):
    """
    Delete JSON log files that are older than retention_days days.

    Args:
        retention_days: Number of days to keep logs. Default 90.

    Returns:
        List of Path objects for deleted files.
    """
    if not LOGS_DIR.exists():
        return []

    cutoff = date.today() - timedelta(days=retention_days)
    deleted = []

    for log_file in sorted(LOGS_DIR.glob("*.json")):
        stem = log_file.stem  # e.g. '2025-11-01'
        try:
            file_date = date.fromisoformat(stem)
        except ValueError:
            # Not a dated log file — skip
            continue
        if file_date < cutoff:
            try:
                log_file.unlink()
                deleted.append(log_file)
                print(f"[audit_logger] Deleted old log: {log_file.name}")
            except OSError as e:
                print(f"[audit_logger] WARNING: Could not delete {log_file}: {e}", file=sys.stderr)

    return deleted


# ---------------------------------------------------------------------------
# Pretty-print CLI helper
# ---------------------------------------------------------------------------

def print_summary(date_str=None):
    """
    Pretty-print the audit summary for a given day to stdout.

    Args:
        date_str: ISO date string 'YYYY-MM-DD'. Defaults to today.
    """
    label = date_str if date_str else date.today().isoformat()
    summary = get_log_summary(date_str)

    print(f"\n=== AI Employee Audit Summary — {label} ===")
    print(f"  Total actions    : {summary['total_actions']}")
    print(f"  Approvals needed : {summary['approvals_needed']}")
    print(f"  Approvals given  : {summary['approvals_given']}")

    if summary["by_type"]:
        print("\n  Actions by type:")
        for atype, count in sorted(summary["by_type"].items()):
            print(f"    {atype:<30} {count}")

    if summary["by_result"]:
        print("\n  Results:")
        for res, count in sorted(summary["by_result"].items()):
            print(f"    {res:<30} {count}")

    print("=" * 46 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Entry point — parse CLI args and dispatch."""
    parser = argparse.ArgumentParser(description="AI Employee Audit Logger")
    parser.add_argument("--summary", action="store_true", help="Print today's action summary")
    parser.add_argument("--date", type=str, default=None, help="Date for --summary (YYYY-MM-DD)")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete log files older than 90 days",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=90,
        help="Retention period in days for --cleanup (default: 90)",
    )
    args = parser.parse_args()

    if not args.summary and not args.cleanup:
        parser.print_help()
        sys.exit(0)

    if args.summary:
        print_summary(args.date)

    if args.cleanup:
        deleted = cleanup_old_logs(args.retention_days)
        if deleted:
            print(f"[audit_logger] Removed {len(deleted)} old log file(s).")
        else:
            print("[audit_logger] No old log files to remove.")


if __name__ == "__main__":
    main()
