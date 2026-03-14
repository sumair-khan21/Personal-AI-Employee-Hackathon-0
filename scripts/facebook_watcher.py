"""
facebook_watcher.py - Facebook Auto-Poster for the AI Employee Vault.

Uses Playwright with a persistent browser session so you only log in once.
All posts go through HITL approval before publishing.

Usage:
    # First-time login (opens headed browser for you to log in manually):
    python3 scripts/facebook_watcher.py --login

    # Post approved content (reads from Approved/ folder):
    python3 scripts/facebook_watcher.py --post

Stop with Ctrl+C.
"""

import sys
import re
import time
from pathlib import Path
from datetime import datetime

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import setup_logging

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"

# Persistent browser session directory (gitignored)
SESSION_DIR = PROJECT_ROOT / ".facebook-session"

FACEBOOK_URL = "https://www.facebook.com"

# ── Logging ───────────────────────────────────────────────────────────────────
logger = setup_logging(VAULT_PATH, "FacebookWatcher")


# ── Session helpers ───────────────────────────────────────────────────────────

def get_browser_context(playwright, headless: bool = True):
    """
    Launch a persistent Chromium context using the saved Facebook session.
    If no session exists yet, run --login first.
    """
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        str(SESSION_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        args=["--disable-blink-features=AutomationControlled"],
    )
    return context


def is_logged_in(page) -> bool:
    """
    Check if the browser is currently logged into Facebook.
    Looks for the home feed or profile navigation elements.
    """
    try:
        # Facebook feed/home shows a navigation bar with aria-label
        page.wait_for_selector(
            "[aria-label='Facebook'], [role='navigation'], div[data-pagelet='LeftRail']",
            timeout=8000,
        )
        # Confirm we are NOT on the login page
        if "login" in page.url or "checkpoint" in page.url:
            return False
        return True
    except Exception:
        return False


# ── Login flow ────────────────────────────────────────────────────────────────

def run_login():
    """
    Open a headed browser so the user can log into Facebook manually.
    Session is persisted to .facebook-session/ for future runs.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening Facebook in headed browser for manual login...")
    logger.info(f"Session will be saved to: {SESSION_DIR}")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(FACEBOOK_URL)

        print("\nLog into Facebook in the browser, then press Enter here...")
        input()

        # Give the page a moment to settle after the user presses Enter
        page.wait_for_timeout(2000)

        if is_logged_in(page):
            logger.info("Login confirmed! Session saved to .facebook-session/")
        else:
            logger.warning(
                "Could not confirm login. "
                "If you completed login, the session may still be saved — try --post."
            )

        ctx.close()


# ── Post mode ─────────────────────────────────────────────────────────────────

def post_to_facebook(post_text: str) -> bool:
    """
    Use Playwright to post approved content to Facebook.
    Uses headless=False so the user can visually verify the post.
    Returns True on success.
    """
    from playwright.sync_api import sync_playwright

    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Opening Facebook to post approved content...")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(FACEBOOK_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if not is_logged_in(page):
                logger.error(
                    "Not logged in to Facebook. "
                    "Run: python3 scripts/facebook_watcher.py --login"
                )
                return False

            # ── Dismiss any blocking dialogs (password save, notifications) ─
            for dismiss_sel in [
                "[aria-label='Close']",
                "div[aria-label='Close']",
                "[data-testid='close-button']",
                "div[role='button'][aria-label='Close']",
            ]:
                try:
                    el = page.query_selector(dismiss_sel)
                    if el and el.is_visible():
                        el.click()
                        logger.info(f"Dismissed dialog: {dismiss_sel}")
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue

            # Also press Escape to dismiss any overlay
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

            # ── Step 1: Open the "What's on your mind?" composer ─────────
            # Use JS to find the composer by its placeholder text
            composer_opened = False
            try:
                page.evaluate("""() => {
                    const all = Array.from(document.querySelectorAll('[role=button]'));
                    const btn = all.find(el =>
                        el.textContent.toLowerCase().includes("what") &&
                        el.textContent.toLowerCase().includes("mind")
                    );
                    if (btn) btn.click();
                }""")
                page.wait_for_timeout(2500)
                modal = page.query_selector("div[role='dialog']")
                if modal:
                    composer_opened = True
                    logger.info("Opened post composer via JS text search")
            except Exception:
                pass

            # Fallback selectors if JS didn't work
            if not composer_opened:
                for sel in [
                    "[aria-label*=\"What's on your mind\"]",
                    "[data-testid='status-attachment-mentions-input']",
                ]:
                    try:
                        el = page.wait_for_selector(sel, timeout=4000)
                        if el and el.is_visible():
                            el.click()
                            page.wait_for_timeout(2500)
                            if page.query_selector("div[role='dialog']"):
                                composer_opened = True
                                logger.info(f"Opened post composer: {sel}")
                                break
                    except Exception:
                        continue

            if not composer_opened:
                debug_path = logs_dir / f"facebook_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(f"Could not open post composer. Debug screenshot: {debug_path.name}")
                return False

            # ── Step 2: Type post text into the active editor ─────────────
            # After clicking the composer button Facebook opens a modal dialog
            # The text editor inside the modal is a contenteditable div
            editor = None
            editor_selectors = [
                "div[contenteditable='true'][role='textbox']",
                "div[contenteditable='true']",
                # Dialog-specific selectors
                "[data-testid='tce-text-area'] div[contenteditable='true']",
                "div[aria-label*='post'] div[contenteditable='true']",
            ]
            for sel in editor_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=5000)
                    if el:
                        editor = el
                        logger.info(f"Found post editor: {sel}")
                        break
                except Exception:
                    continue

            if not editor:
                debug_path = logs_dir / f"facebook_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(
                    f"Could not find post editor. Debug screenshot: {debug_path.name}"
                )
                return False

            editor.click()
            page.wait_for_timeout(500)
            page.keyboard.type(post_text, delay=20)
            page.wait_for_timeout(1500)

            # Draft screenshot for audit trail
            draft_path = logs_dir / f"facebook_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(draft_path))
            logger.info(f"Draft screenshot saved: {draft_path.name}")

            # ── Step 3: Click the Post button ────────────────────────────
            post_btn = None
            post_btn_selectors = [
                "div[aria-label='Post'][role='button']",
                "button[type='submit'][aria-label*='Post']",
                # Dialog footer primary action
                "div[data-testid='react-composer-post-button']",
                "div[aria-label='Post']",
            ]
            for sel in post_btn_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=5000)
                    if el and el.is_enabled():
                        post_btn = el
                        logger.info(f"Found Post button: {sel}")
                        break
                except Exception:
                    continue

            if not post_btn:
                debug_path = logs_dir / f"facebook_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(
                    f"Could not find Post button. Debug screenshot: {debug_path.name}"
                )
                return False

            post_btn.click()
            page.wait_for_timeout(5000)

            # Confirmation screenshot
            confirm_path = logs_dir / f"facebook_posted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(confirm_path))
            logger.info(f"Post confirmation screenshot: {confirm_path.name}")
            return True

        except Exception as e:
            logger.error(f"Facebook post failed: {e}")
            try:
                debug_path = logs_dir / f"facebook_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.info(f"Debug screenshot saved: {debug_path.name}")
            except Exception:
                pass
            return False
        finally:
            ctx.close()


# ── Approval file helpers ─────────────────────────────────────────────────────

def read_approved_post() -> dict | None:
    """
    Scan Approved/ folder for Facebook post approval files.
    Returns the first one found as {file, content}, or None.
    """
    approved_dir = VAULT_PATH / "Approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    for f in sorted(approved_dir.glob("APPROVAL_REQUIRED_Facebook_*.md")):
        content = f.read_text(encoding="utf-8")
        return {"file": f, "content": content}
    return None


def extract_post_text(content: str) -> str:
    """
    Extract the post body from the approval file.
    Looks for content between '## Draft Content' and the next '## ' heading (or EOF).
    """
    match = re.search(
        r"## Draft Content\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if match:
        return match.group(1).strip()
    # Fallback: return everything after the YAML frontmatter
    parts = content.split("---", 2)
    return parts[-1].strip() if len(parts) >= 3 else content.strip()


def draft_post_for_approval(topic: str, post_text: str) -> Path:
    """
    Write an APPROVAL_REQUIRED file for a Facebook post into Needs_Action/.
    Move the file to Approved/ to trigger posting.
    """
    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"APPROVAL_REQUIRED_Facebook_{timestamp}.md"
    path = needs_action / filename

    content = f"""---
type: approval_required
category: facebook_post
topic: {topic}
status: awaiting_approval
created: {datetime.now().isoformat()}
---

# APPROVAL REQUIRED: Facebook Post

## Topic
{topic}

## Draft Content

{post_text}

## Goal
Share updates and engage with the audience on Facebook.

## To APPROVE
Move this file to `Approved/` — the facebook_watcher will then post it.

## To EDIT
Edit the draft above, then move to `Approved/`.

## To REJECT
Delete this file.

---
*Claude Code will NOT post until this file is in Approved/*
"""
    path.write_text(content, encoding="utf-8")
    logger.info(f"Facebook draft created for approval: {filename}")
    return path


# ── Run post mode ─────────────────────────────────────────────────────────────

def run_post_mode():
    """
    Check Approved/ for Facebook posts and publish them.
    Archives the approval file to Done/ after success.
    """
    approved = read_approved_post()
    if not approved:
        logger.info("No approved Facebook posts found in Approved/ folder.")
        return

    f = approved["file"]
    post_text = extract_post_text(approved["content"])

    if not post_text:
        logger.error(f"Could not extract post text from {f.name}")
        return

    logger.info(f"Found approved post: {f.name}")
    logger.info(f"Post preview: {post_text[:120]}...")

    success = post_to_facebook(post_text)

    if success:
        done_dir = VAULT_PATH / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = done_dir / f"POSTED_Facebook_{timestamp}.md"
        done_content = (
            approved["content"]
            + f"\n\n---\n**Posted:** {datetime.now().isoformat()}\n**Status:** SUCCESS\n"
        )
        dest.write_text(done_content, encoding="utf-8")
        f.unlink()
        logger.info(f"Post published and archived to Done/{dest.name}")
    else:
        logger.error("Post failed — approval file left in Approved/ for retry.")


# ── Main entry point ──────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--login" in args:
        run_login()
        return

    if "--post" in args:
        run_post_mode()
        return

    # No valid argument supplied
    print(__doc__)
    print("\nError: specify --login or --post")
    sys.exit(1)


if __name__ == "__main__":
    main()
