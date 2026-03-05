"""
verify.py - Full verification script for the AI Employee Vault (Bronze + Silver).

Usage:
    python3 scripts/verify.py           # check all tiers
    python3 scripts/verify.py --bronze  # Bronze checks only
    python3 scripts/verify.py --silver  # Silver checks only
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VAULT = PROJECT_ROOT / "AI_Employee_Vault"

PASS = "✓"
FAIL = "✗"
WARN = "⚠"

results = []
warnings = []


def check(label: str, condition: bool, fix: str = "") -> bool:
    symbol = PASS if condition else FAIL
    status = "PASS" if condition else "FAIL"
    results.append((symbol, label, status, fix))
    return condition


def warn(label: str, message: str):
    warnings.append((WARN, label, message))
    results.append((WARN, label, "WARN", message))


def header(title: str):
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


# ══════════════════════════════════════════════════════════════
# BRONZE CHECKS
# ══════════════════════════════════════════════════════════════

def run_bronze_checks() -> bool:
    all_passed = True

    header("BRONZE 1. Vault Folder Structure")
    for folder in ["Inbox", "Needs_Action", "Done", "Drop_Zone", "Logs"]:
        ok = (VAULT / folder).is_dir()
        check(f"Folder exists: AI_Employee_Vault/{folder}/", ok,
              f"mkdir -p AI_Employee_Vault/{folder}")
        if not ok:
            all_passed = False

    header("BRONZE 2. Required Vault Files")
    for fname in ["Dashboard.md", "Company_Handbook.md"]:
        ok = (VAULT / fname).is_file()
        check(f"File exists: AI_Employee_Vault/{fname}", ok)
        if not ok:
            all_passed = False

    header("BRONZE 3. Watcher Scripts")
    for script in ["scripts/base_watcher.py", "scripts/filesystem_watcher.py", "scripts/verify.py"]:
        ok = (PROJECT_ROOT / script).is_file()
        check(f"Script exists: {script}", ok)
        if not ok:
            all_passed = False

    header("BRONZE 4. Python Dependencies")
    try:
        import watchdog  # noqa: F401
        check("watchdog package installed", True)
    except ImportError:
        check("watchdog package installed", False, ".venv/bin/pip install watchdog")
        all_passed = False

    header("BRONZE 5. Watcher Import Test")
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from base_watcher import BaseWatcher  # noqa: F401
        check("base_watcher.py imports successfully", True)
    except Exception as e:
        check(f"base_watcher.py imports ({e})", False)
        all_passed = False

    try:
        from filesystem_watcher import FileSystemWatcher  # noqa: F401
        check("filesystem_watcher.py imports successfully", True)
    except Exception as e:
        check(f"filesystem_watcher.py imports ({e})", False)
        all_passed = False

    header("BRONZE 6. Write Tests")
    for path, label in [
        (VAULT / "Drop_Zone" / ".verify_test", "Drop_Zone/ is writable"),
        (VAULT / "Logs" / ".verify_test.log", "Logs/ directory is writable"),
    ]:
        try:
            path.write_text("ok")
            path.unlink()
            check(label, True)
        except Exception as e:
            check(f"{label} ({e})", False)
            all_passed = False

    header("BRONZE 7. Security")
    gitignore = PROJECT_ROOT / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        check(".gitignore exists", True)
        check("credentials.json is gitignored", "credentials.json" in content,
              "Add 'credentials.json' to .gitignore")
        check("token.json is gitignored", "token.json" in content,
              "Add 'token.json' to .gitignore")
    else:
        check(".gitignore exists", False, "Create .gitignore")
        all_passed = False

    return all_passed


# ══════════════════════════════════════════════════════════════
# SILVER CHECKS
# ══════════════════════════════════════════════════════════════

def run_silver_checks() -> bool:
    all_passed = True

    header("SILVER 1. Silver Vault Folders")
    silver_folders = [
        "Plans/Finance", "Plans/Communications", "Plans/Social", "Plans/General",
        "Pending_Approval", "Approved", "Rejected", "Accounting", "Briefings",
    ]
    for folder in silver_folders:
        ok = (VAULT / folder).is_dir()
        check(f"Folder exists: AI_Employee_Vault/{folder}/", ok,
              f"mkdir -p AI_Employee_Vault/{folder}")
        if not ok:
            all_passed = False

    header("SILVER 2. Silver Scripts")
    silver_scripts = [
        "scripts/gmail_watcher.py",
        "scripts/linkedin_watcher.py",
        "scripts/run_briefing.py",
        "scripts/crontab.txt",
    ]
    for script in silver_scripts:
        ok = (PROJECT_ROOT / script).is_file()
        check(f"Script exists: {script}", ok)
        if not ok:
            all_passed = False

    header("SILVER 3. Google API Dependencies")
    for pkg, name in [
        ("google.oauth2.credentials", "google-auth"),
        ("google_auth_oauthlib.flow", "google-auth-oauthlib"),
        ("googleapiclient.discovery", "google-api-python-client"),
    ]:
        try:
            __import__(pkg)
            check(f"{name} installed", True)
        except ImportError:
            check(f"{name} installed", False, f".venv/bin/pip install {name}")
            all_passed = False

    header("SILVER 4. Playwright")
    try:
        import subprocess
        result = subprocess.run(["playwright", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            check(f"Playwright installed globally ({version})", True)
        else:
            check("Playwright installed globally", False, "pip install playwright && playwright install chromium")
            all_passed = False
    except FileNotFoundError:
        check("Playwright installed globally", False, "pip install playwright && playwright install chromium")
        all_passed = False

    header("SILVER 5. Gmail Script Import Test")
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gmail_watcher", PROJECT_ROOT / "scripts" / "gmail_watcher.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        check("gmail_watcher.py imports successfully", True)
    except Exception as e:
        check(f"gmail_watcher.py imports ({e})", False)
        all_passed = False

    header("SILVER 6. LinkedIn Script Import Test")
    try:
        spec = importlib.util.spec_from_file_location(
            "linkedin_watcher", PROJECT_ROOT / "scripts" / "linkedin_watcher.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        check("linkedin_watcher.py imports successfully", True)
    except Exception as e:
        check(f"linkedin_watcher.py imports ({e})", False)
        all_passed = False

    header("SILVER 7. Credentials & Auth")
    creds_ok = (PROJECT_ROOT / "credentials.json").exists()
    token_ok  = (PROJECT_ROOT / "token.json").exists()
    check("credentials.json exists", creds_ok,
          "Download from Google Cloud Console → APIs & Services → Credentials")
    if not creds_ok:
        all_passed = False

    if not token_ok:
        warn("token.json not found",
             "Run: .venv/bin/python3 scripts/gmail_watcher.py --auth")
    else:
        check("token.json exists (Gmail auth completed)", True)

    header("SILVER 8. LinkedIn Session")
    session_ok = (PROJECT_ROOT / ".linkedin-session").is_dir()
    if not session_ok:
        warn(".linkedin-session/ not found",
             "Run: .venv/bin/python3 scripts/linkedin_watcher.py --login")
    else:
        check(".linkedin-session/ exists (LinkedIn auth completed)", True)

    header("SILVER 9. Agent Skills")
    silver_skills = [
        ".claude/skills/gmail-watcher/SKILL.md",
        ".claude/skills/linkedin-post/SKILL.md",
        ".claude/skills/create-plan/SKILL.md",
        ".claude/skills/hitl-approval/SKILL.md",
        ".claude/skills/schedule-tasks/SKILL.md",
        ".claude/skills/send-email/SKILL.md",
    ]
    for skill in silver_skills:
        ok = (PROJECT_ROOT / skill).is_file()
        check(f"Skill exists: {skill}", ok)
        if not ok:
            all_passed = False

    return all_passed


# ══════════════════════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════════════════════

def print_results(bronze_ok: bool, silver_ok: bool, run_silver: bool):
    print(f"\n{'═' * 55}")
    print("  Results")
    print(f"{'═' * 55}")
    for symbol, label, status, fix in results:
        print(f"  {symbol}  {label}")
        if status == "FAIL" and fix:
            print(f"       Fix: {fix}")
        elif status == "WARN":
            print(f"       Note: {fix}")

    print(f"\n{'═' * 55}")
    if bronze_ok:
        print("  ✓ Bronze Tier — COMPLETE")
    else:
        print("  ✗ Bronze Tier — incomplete (see fixes above)")

    if run_silver:
        if silver_ok:
            print("  ✓ Silver Tier — COMPLETE")
        else:
            print("  ⚠ Silver Tier — partially complete (warnings are OK)")

    print(f"{'═' * 55}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    bronze_only = "--bronze" in args
    silver_only = "--silver" in args
    run_silver  = not bronze_only

    bronze_ok = run_bronze_checks() if not silver_only else True
    silver_ok = run_silver_checks() if run_silver else True

    print_results(bronze_ok, silver_ok, run_silver)

    # Exit 0 if bronze passes (silver warnings are acceptable)
    sys.exit(0 if bronze_ok else 1)
