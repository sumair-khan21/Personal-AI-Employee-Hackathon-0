"""
odoo_watcher.py - Odoo 17 XML-RPC integration for the Personal AI Employee.

Reads accounting data from Odoo, generates audit reports and action files
in the AI Employee Vault.

CLI flags:
  --once     Run audit once and exit
  --summary  Print accounting summary to terminal
  --invoices List all open invoices
  --watch    Continuous mode, polls every 3600 seconds
"""

import sys
import time
import argparse
import xmlrpc.client
from pathlib import Path
from datetime import datetime, date

# Allow sibling imports (base_watcher)
sys.path.insert(0, str(Path(__file__).parent))

from base_watcher import setup_logging

try:
    from dotenv import load_dotenv
except ImportError:
    print("python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

import os

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
POLL_INTERVAL = 3600  # 1 hour

logger = setup_logging(VAULT_PATH, "OdooWatcher")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_odoo_connection():
    """
    Connect to Odoo via XML-RPC using credentials from .env file.

    Reads ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD from .env at
    the project root.

    Returns:
        Tuple of (uid, models_proxy, common_proxy, creds_dict) on success.
        Returns (None, None, None, None) if connection fails.
    """
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    url = os.getenv("ODOO_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo")
    username = os.getenv("ODOO_USERNAME", "")
    password = os.getenv("ODOO_PASSWORD", "")

    if not username or not password:
        logger.error("ODOO_USERNAME or ODOO_PASSWORD not set in .env")
        return None, None, None, None

    creds = {"db": db, "username": username, "password": password}

    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        # Verify the server is reachable
        common.version()
        uid = common.authenticate(db, username, password, {})
        if not uid:
            logger.error("Odoo authentication failed — check username/password in .env")
            return None, None, None, None

        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        logger.info(f"Connected to Odoo at {url} as uid={uid}")
        return uid, models, common, creds

    except Exception as e:
        logger.warning(f"Could not connect to Odoo ({url}): {e}")
        return None, None, None, None


# ---------------------------------------------------------------------------
# Data retrieval helpers
# ---------------------------------------------------------------------------

def get_invoices(models, uid, creds, state="open"):
    """
    Fetch customer invoices from account.move.

    Args:
        models:  XML-RPC object proxy
        uid:     Authenticated user ID
        creds:   Dict with 'db' and 'password' keys
        state:   Invoice state filter — 'open' (posted/unpaid) or 'draft', etc.
                 Pass 'all' to skip state filter.

    Returns:
        List of dicts: id, name, partner_name, amount_total, currency,
        state, invoice_date, invoice_date_due, payment_state.
        Returns [] on error.
    """
    db = creds["db"]
    password = creds["password"]

    domain = [("move_type", "=", "out_invoice")]
    if state != "all":
        domain.append(("state", "=", state))

    fields = [
        "name", "partner_id", "amount_total", "currency_id",
        "state", "invoice_date", "invoice_date_due", "payment_state",
    ]

    try:
        records = models.execute_kw(
            db, uid, password,
            "account.move", "search_read",
            [domain],
            {"fields": fields, "order": "invoice_date_due asc"},
        )
    except Exception as e:
        logger.warning(f"get_invoices failed: {e}")
        return []

    invoices = []
    for r in records:
        invoices.append({
            "id": r["id"],
            "name": r.get("name", ""),
            "partner_name": r["partner_id"][1] if r.get("partner_id") else "",
            "amount_total": r.get("amount_total", 0.0),
            "currency": r["currency_id"][1] if r.get("currency_id") else "USD",
            "state": r.get("state", ""),
            "invoice_date": r.get("invoice_date") or "",
            "invoice_date_due": r.get("invoice_date_due") or "",
            "payment_state": r.get("payment_state", ""),
        })
    return invoices


def get_overdue_invoices(models, uid, creds):
    """
    Fetch invoices that are past their due date and not fully paid.

    Args:
        models:  XML-RPC object proxy
        uid:     Authenticated user ID
        creds:   Dict with 'db' and 'password' keys

    Returns:
        List of invoice dicts (same format as get_invoices). Returns [] on error.
    """
    db = creds["db"]
    password = creds["password"]
    today_str = date.today().isoformat()

    domain = [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("payment_state", "!=", "paid"),
        ("invoice_date_due", "<", today_str),
    ]

    fields = [
        "name", "partner_id", "amount_total", "currency_id",
        "state", "invoice_date", "invoice_date_due", "payment_state",
    ]

    try:
        records = models.execute_kw(
            db, uid, password,
            "account.move", "search_read",
            [domain],
            {"fields": fields, "order": "invoice_date_due asc"},
        )
    except Exception as e:
        logger.warning(f"get_overdue_invoices failed: {e}")
        return []

    invoices = []
    for r in records:
        invoices.append({
            "id": r["id"],
            "name": r.get("name", ""),
            "partner_name": r["partner_id"][1] if r.get("partner_id") else "",
            "amount_total": r.get("amount_total", 0.0),
            "currency": r["currency_id"][1] if r.get("currency_id") else "USD",
            "state": r.get("state", ""),
            "invoice_date": r.get("invoice_date") or "",
            "invoice_date_due": r.get("invoice_date_due") or "",
            "payment_state": r.get("payment_state", ""),
        })
    return invoices


def get_customers(models, uid, creds):
    """
    Fetch customer records from res.partner (customer_rank > 0).

    Args:
        models:  XML-RPC object proxy
        uid:     Authenticated user ID
        creds:   Dict with 'db' and 'password' keys

    Returns:
        List of dicts: id, name, email, phone. Returns [] on error.
    """
    db = creds["db"]
    password = creds["password"]

    domain = [("customer_rank", ">", 0), ("active", "=", True)]
    fields = ["name", "email", "phone"]

    try:
        records = models.execute_kw(
            db, uid, password,
            "res.partner", "search_read",
            [domain],
            {"fields": fields, "order": "name asc"},
        )
    except Exception as e:
        logger.warning(f"get_customers failed: {e}")
        return []

    return [
        {
            "id": r["id"],
            "name": r.get("name", ""),
            "email": r.get("email") or "",
            "phone": r.get("phone") or "",
        }
        for r in records
    ]


def create_invoice(models, uid, creds, partner_id, amount, description, due_date):
    """
    Create a draft customer invoice in Odoo.

    Args:
        models:      XML-RPC object proxy
        uid:         Authenticated user ID
        creds:       Dict with 'db' and 'password' keys
        partner_id:  Odoo res.partner ID for the customer
        amount:      Invoice line amount (float)
        description: Invoice line name / description
        due_date:    Due date string in 'YYYY-MM-DD' format

    Returns:
        New invoice ID (int) on success, or None on error.
    """
    db = creds["db"]
    password = creds["password"]

    invoice_vals = {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "invoice_date_due": due_date,
        "invoice_line_ids": [
            (0, 0, {
                "name": description,
                "quantity": 1.0,
                "price_unit": amount,
            })
        ],
    }

    try:
        invoice_id = models.execute_kw(
            db, uid, password,
            "account.move", "create",
            [invoice_vals],
        )
        logger.info(f"Created draft invoice id={invoice_id} for partner_id={partner_id}")
        return invoice_id
    except Exception as e:
        logger.warning(f"create_invoice failed: {e}")
        return None


def get_accounting_summary(models, uid, creds):
    """
    Build a high-level accounting summary from Odoo data.

    Args:
        models:  XML-RPC object proxy
        uid:     Authenticated user ID
        creds:   Dict with 'db' and 'password' keys

    Returns:
        Dict with keys: total_invoiced, total_paid, total_overdue,
        invoice_count, overdue_count. All monetary values are floats.
        Returns a zeroed dict on error.
    """
    empty = {
        "total_invoiced": 0.0,
        "total_paid": 0.0,
        "total_overdue": 0.0,
        "invoice_count": 0,
        "overdue_count": 0,
    }

    try:
        all_invoices = get_invoices(models, uid, creds, state="all")
        overdue = get_overdue_invoices(models, uid, creds)

        posted = [i for i in all_invoices if i["state"] == "posted"]
        paid_invoices = [i for i in posted if i["payment_state"] == "paid"]

        total_invoiced = sum(i["amount_total"] for i in posted)
        total_paid = sum(i["amount_total"] for i in paid_invoices)
        total_overdue = sum(i["amount_total"] for i in overdue)

        return {
            "total_invoiced": round(total_invoiced, 2),
            "total_paid": round(total_paid, 2),
            "total_overdue": round(total_overdue, 2),
            "invoice_count": len(posted),
            "overdue_count": len(overdue),
        }
    except Exception as e:
        logger.warning(f"get_accounting_summary failed: {e}")
        return empty


# ---------------------------------------------------------------------------
# Vault file writers
# ---------------------------------------------------------------------------

def create_accounting_action_file(vault_path, summary):
    """
    Write an action file to Needs_Action/ summarising the Odoo accounting state.

    Args:
        vault_path: Path to the AI_Employee_Vault directory
        summary:    Dict returned by get_accounting_summary()

    Returns:
        Path of the created file.
    """
    vault_path = Path(vault_path)
    needs_action = vault_path / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ACTION_ODOO_Accounting_{ts}.md"
    filepath = needs_action / filename

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = f"""# ACTION REQUIRED — Odoo Accounting Alert
**Generated:** {now_str}
**Source:** OdooWatcher

---

## Accounting Summary

| Metric | Value |
|--------|-------|
| Total Invoiced | ${summary['total_invoiced']:,.2f} |
| Total Paid | ${summary['total_paid']:,.2f} |
| Total Overdue | ${summary['total_overdue']:,.2f} |
| Invoice Count | {summary['invoice_count']} |
| Overdue Count | {summary['overdue_count']} |

## Action Required

{summary['overdue_count']} invoice(s) are overdue totalling **${summary['total_overdue']:,.2f}**.

Please review the weekly audit report in `Accounting/` and follow up with customers.

---
*Auto-generated by OdooWatcher. Move to Done/ when resolved.*
"""

    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Action file created: {filepath}")
    return filepath


def run_weekly_audit(vault_path):
    """
    Run a full weekly accounting audit: fetch summary + overdue invoices,
    write a detailed report to Accounting/WeeklyAudit_<date>.md, and
    create a Needs_Action file if there are overdue invoices.

    Args:
        vault_path: Path to the AI_Employee_Vault directory

    Returns:
        Path of the audit report file, or None if Odoo is unreachable.
    """
    vault_path = Path(vault_path)
    accounting_dir = vault_path / "Accounting"
    accounting_dir.mkdir(parents=True, exist_ok=True)

    uid, models, common, creds = get_odoo_connection()
    if uid is None:
        logger.warning("Skipping weekly audit — Odoo unavailable.")
        return None

    summary = get_accounting_summary(models, uid, creds)
    overdue = get_overdue_invoices(models, uid, creds)

    today_str = date.today().isoformat()
    report_path = accounting_dir / f"WeeklyAudit_{today_str}.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build overdue table
    if overdue:
        overdue_table = (
            "| Invoice | Customer | Amount | Due Date | Payment State |\n"
            "|---------|----------|--------|----------|---------------|\n"
        )
        for inv in overdue:
            overdue_table += (
                f"| {inv['name']} | {inv['partner_name']} "
                f"| {inv['currency']} {inv['amount_total']:,.2f} "
                f"| {inv['invoice_date_due']} "
                f"| {inv['payment_state']} |\n"
            )
    else:
        overdue_table = "_No overdue invoices. Great job!_\n"

    report_content = f"""# Weekly Accounting Audit — {today_str}
**Generated:** {now_str}
**Source:** OdooWatcher (automated)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Invoiced | ${summary['total_invoiced']:,.2f} |
| Total Paid | ${summary['total_paid']:,.2f} |
| Total Overdue | ${summary['total_overdue']:,.2f} |
| Invoice Count | {summary['invoice_count']} |
| Overdue Count | {summary['overdue_count']} |

## Overdue Invoices

{overdue_table}

## Recommendations

{'- **URGENT:** Follow up on ' + str(summary['overdue_count']) + ' overdue invoice(s) immediately.' if overdue else '- All invoices are current. No action required.'}
- Review aging report in Odoo for detailed breakdown.
- Ensure all new invoices have correct due dates set.

---
*Auto-generated by the AI Employee OdooWatcher.*
"""

    report_path.write_text(report_content, encoding="utf-8")
    logger.info(f"Weekly audit report written: {report_path}")

    # Create action file only when there are overdue invoices
    if overdue:
        create_accounting_action_file(vault_path, summary)

    return report_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(summary):
    """Print accounting summary to terminal in a readable format."""
    print("\n=== Odoo Accounting Summary ===")
    print(f"  Total Invoiced : ${summary['total_invoiced']:>12,.2f}")
    print(f"  Total Paid     : ${summary['total_paid']:>12,.2f}")
    print(f"  Total Overdue  : ${summary['total_overdue']:>12,.2f}")
    print(f"  Invoice Count  : {summary['invoice_count']}")
    print(f"  Overdue Count  : {summary['overdue_count']}")
    print("================================\n")


def print_invoices(invoices):
    """Print invoice list to terminal."""
    if not invoices:
        print("No invoices found.")
        return
    print(f"\n{'#':<5} {'Invoice':<20} {'Customer':<30} {'Amount':>12} {'Due Date':<12} {'Status'}")
    print("-" * 100)
    for i, inv in enumerate(invoices, 1):
        print(
            f"{i:<5} {inv['name']:<20} {inv['partner_name']:<30} "
            f"{inv['currency']} {inv['amount_total']:>10,.2f}  "
            f"{inv['invoice_date_due']:<12} {inv['payment_state']}"
        )
    print(f"\nTotal: {len(invoices)} invoice(s)\n")


def main():
    """Entry point — parse CLI args and dispatch."""
    parser = argparse.ArgumentParser(description="Odoo 17 Accounting Watcher for AI Employee")
    parser.add_argument("--once", action="store_true", help="Run weekly audit once and exit")
    parser.add_argument("--summary", action="store_true", help="Print accounting summary to terminal")
    parser.add_argument("--invoices", action="store_true", help="List all open invoices")
    parser.add_argument("--watch", action="store_true", help="Continuous mode, runs every 3600s")
    args = parser.parse_args()

    if not any([args.once, args.summary, args.invoices, args.watch]):
        parser.print_help()
        sys.exit(0)

    if args.summary or args.invoices:
        uid, models, common, creds = get_odoo_connection()
        if uid is None:
            print("ERROR: Could not connect to Odoo. Check .env and that Odoo is running.")
            sys.exit(1)
        if args.summary:
            summary = get_accounting_summary(models, uid, creds)
            print_summary(summary)
        if args.invoices:
            invoices = get_invoices(models, uid, creds, state="open")
            print_invoices(invoices)
        return

    if args.once:
        run_weekly_audit(VAULT_PATH)
        return

    if args.watch:
        logger.info(f"OdooWatcher running in continuous mode (interval={POLL_INTERVAL}s)")
        logger.info("Press Ctrl+C to stop.")
        try:
            while True:
                run_weekly_audit(VAULT_PATH)
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("OdooWatcher stopped by user.")


if __name__ == "__main__":
    main()
