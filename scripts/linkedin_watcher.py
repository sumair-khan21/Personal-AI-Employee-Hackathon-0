"""
linkedin_watcher.py - LinkedIn Watcher + Auto-Poster for the AI Employee Vault (Silver Tier).

Two modes:
  1. WATCH mode  — monitors LinkedIn notifications for business leads/messages
  2. POST mode   — drafts and posts LinkedIn content (always via HITL approval first)

Uses Playwright with a persistent browser session so you only log in once.

Usage:
    # First-time login (opens headed browser for you to log in):
    python3 scripts/linkedin_watcher.py --login

    # Watch for new messages/notifications (continuous):
    python3 scripts/linkedin_watcher.py --watch

    # Watch once (for cron):
    python3 scripts/linkedin_watcher.py --watch --once

    # Post approved content (reads from Approved/ folder):
    python3 scripts/linkedin_watcher.py --post

Stop with Ctrl+C.
"""

import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher, setup_logging

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"

# Persistent browser session directory (gitignored)
SESSION_DIR = PROJECT_ROOT / ".linkedin-session"

# Keywords in LinkedIn messages that trigger action files
TRIGGER_KEYWORDS = {
    "pricing", "invoice", "proposal", "quote", "contract",
    "urgent", "asap", "hire", "project", "budget", "collaborate",
    "partnership", "interested", "inquiry", "demo", "meeting",
}

LINKEDIN_URL = "https://www.linkedin.com"


# ── Logging (standalone, not via BaseWatcher) ─────────────────────────────────
logger = setup_logging(VAULT_PATH, "LinkedInWatcher")


# ── Session helpers ───────────────────────────────────────────────────────────

def get_browser_context(playwright, headless: bool = True):
    """
    Launch a persistent Chromium context using the saved LinkedIn session.
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
    )
    return context


def is_logged_in(page) -> bool:
    """Check if the current page is a logged-in LinkedIn session."""
    try:
        page.wait_for_selector("nav[aria-label='Primary Navigation']", timeout=8000)
        return True
    except Exception:
        return False


# ── Login flow ────────────────────────────────────────────────────────────────

def run_login():
    """
    Open a headed browser so the user can log into LinkedIn manually.
    Session is persisted to .linkedin-session/ for future headless runs.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening LinkedIn in headed browser for manual login...")
    logger.info(f"Session will be saved to: {SESSION_DIR}")
    logger.info("Log in, then close the browser window when done.")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LINKEDIN_URL)

        # Wait until user navigates to the feed (confirms login)
        try:
            page.wait_for_url("**/feed/**", timeout=120_000)
            logger.info("Login detected! Session saved.")
        except Exception:
            logger.warning("Timed out waiting for login. Try again.")
        ctx.close()


# ── Watch mode ────────────────────────────────────────────────────────────────

def scrape_notifications(page) -> list[dict]:
    """
    Navigate to LinkedIn notifications and extract new ones.
    Returns list of notification dicts.
    """
    try:
        page.goto(f"{LINKEDIN_URL}/notifications/", timeout=15000)
        page.wait_for_selector(".notification-item, .artdeco-list__item", timeout=10000)
    except Exception as e:
        logger.warning(f"Could not load notifications: {e}")
        return []

    notifications = []
    items = page.query_selector_all(".artdeco-list__item, .notification-item")
    for item in items[:10]:  # process top 10 only
        try:
            text = item.inner_text().strip()
            link_el = item.query_selector("a")
            link = link_el.get_attribute("href") if link_el else ""
            if text:
                notifications.append({"text": text, "link": link or ""})
        except Exception:
            continue
    return notifications


def scrape_messages(page) -> list[dict]:
    """
    Navigate to LinkedIn messaging and extract unread messages
    containing trigger keywords.
    """
    try:
        page.goto(f"{LINKEDIN_URL}/messaging/", timeout=15000)
        page.wait_for_selector(
            ".msg-conversation-listitem, .msg-conversations-container",
            timeout=10000,
        )
    except Exception as e:
        logger.warning(f"Could not load messages: {e}")
        return []

    messages = []
    items = page.query_selector_all(".msg-conversation-listitem__link")
    for item in items[:10]:
        try:
            text = item.inner_text().strip().lower()
            if any(kw in text for kw in TRIGGER_KEYWORDS):
                messages.append({
                    "text": item.inner_text().strip(),
                    "link": item.get_attribute("href") or "",
                })
        except Exception:
            continue
    return messages


def create_linkedin_action_file(item: dict, item_type: str) -> Path:
    """Create an action file in Needs_Action/ for a LinkedIn notification/message."""
    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ACTION_LINKEDIN_{item_type.upper()}_{timestamp}.md"
    action_path = needs_action / filename

    text = item.get("text", "")
    link = item.get("link", "")
    urgency = "High" if any(kw in text.lower() for kw in {"urgent", "asap", "hire", "budget"}) else "Normal"
    emoji = "🟡" if urgency == "High" else "🟢"

    content = f"""---
type: linkedin_{item_type}
source: LinkedIn
urgency: {urgency}
status: pending
detected: {datetime.now().isoformat()}
---

# Action Required: LinkedIn {item_type.title()}

{emoji} **Urgency:** {urgency}

## Content

> {text}

## Link

{f'[Open on LinkedIn](https://www.linkedin.com{link})' if link else '*(no direct link)*'}

## Suggested Actions

- [ ] Review the {item_type} on LinkedIn
- [ ] If it's a lead/inquiry → run `create-plan` skill to draft a response plan
- [ ] If reply needed → run `send-email` or `hitl-approval` skill
- [ ] If it's a post opportunity → run `linkedin-post` skill
- [ ] Move this file to `/Done/` when complete

---
*(Claude Code: process per Company_Handbook.md — do NOT reply without approval)*
"""
    action_path.write_text(content, encoding="utf-8")
    logger.info(f"LinkedIn action file created: {filename}")
    return action_path


def watch_once(processed_texts: set) -> set:
    """Single watch cycle — returns updated processed_texts set."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            if not is_logged_in(page):
                page.goto(LINKEDIN_URL)
                if not is_logged_in(page):
                    logger.error(
                        "Not logged in to LinkedIn. "
                        "Run: python3 scripts/linkedin_watcher.py --login"
                    )
                    return processed_texts

            new_items = []

            # Scrape notifications
            for notif in scrape_notifications(page):
                key = notif["text"][:80]
                if key not in processed_texts:
                    new_items.append(("notification", notif))
                    processed_texts.add(key)

            # Scrape keyword-triggered messages
            for msg in scrape_messages(page):
                key = msg["text"][:80]
                if key not in processed_texts:
                    new_items.append(("message", msg))
                    processed_texts.add(key)

            if new_items:
                logger.info(f"Found {len(new_items)} new LinkedIn item(s).")
                for item_type, item in new_items:
                    create_linkedin_action_file(item, item_type)
            else:
                logger.info("No new LinkedIn items.")

        finally:
            ctx.close()

    return processed_texts


# ── Post mode ─────────────────────────────────────────────────────────────────

def read_approved_post() -> dict | None:
    """
    Scan Approved/ folder for LinkedIn post approval files.
    Returns the first one found, or None.
    """
    approved_dir = VAULT_PATH / "Approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    for f in approved_dir.glob("APPROVAL_REQUIRED_LinkedIn_*.md"):
        content = f.read_text(encoding="utf-8")
        return {"file": f, "content": content}
    return None


def extract_post_text(approval_content: str) -> str:
    """
    Extract the post body from the approval file.
    Looks for content between '## Draft Content' and next '## ' heading.
    """
    match = re.search(
        r"## Draft Content\s*\n(.*?)(?=\n## |\Z)", approval_content, re.DOTALL
    )
    if match:
        return match.group(1).strip()
    # Fallback: return everything after the frontmatter
    parts = approval_content.split("---", 2)
    return parts[-1].strip() if len(parts) >= 3 else approval_content.strip()


def post_to_linkedin(post_text: str) -> bool:
    """
    Use Playwright to post approved content to LinkedIn.
    Uses robust multi-selector approach to handle LinkedIn UI changes.
    Returns True on success.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening LinkedIn to post approved content...")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)  # headed so you can verify
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(f"{LINKEDIN_URL}/feed/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if not is_logged_in(page):
                logger.error("Not logged in. Run --login first.")
                return False

            # ── Step 1: Click "Start a post" ─────────────────────────────
            # Try multiple known selectors for LinkedIn's post button
            start_btn = None
            start_selectors = [
                "button[aria-label*='Start a post']",
                "button[aria-label*='Create a post']",
                "div[data-placeholder*='Start a post']",
                ".share-box-feed-entry__trigger",
                "button.share-box-feed-entry__trigger",
                "[data-control-name='share.sharebox_open']",
                "div.share-box-feed-entry__top-bar button",
            ]
            for sel in start_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=4000)
                    if el:
                        start_btn = el
                        logger.info(f"Found start-post button: {sel}")
                        break
                except Exception:
                    continue

            if not start_btn:
                # Take a debug screenshot to inspect the page
                debug_path = VAULT_PATH / "Logs" / f"linkedin_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(f"Could not find 'Start a post' button. Debug screenshot: {debug_path.name}")
                return False

            start_btn.click()
            page.wait_for_timeout(2000)

            # ── Step 2: Type into the post editor ────────────────────────
            editor = None
            editor_selectors = [
                "div[role='textbox']",
                ".ql-editor",
                "div[contenteditable='true']",
                ".share-creation-state__text-editor",
                "[data-placeholder*='What do you want to talk about']",
                "[data-placeholder*='Share your thoughts']",
            ]
            for sel in editor_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=4000)
                    if el:
                        editor = el
                        logger.info(f"Found editor: {sel}")
                        break
                except Exception:
                    continue

            if not editor:
                debug_path = VAULT_PATH / "Logs" / f"linkedin_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(f"Could not find post editor. Debug screenshot: {debug_path.name}")
                return False

            editor.click()
            page.wait_for_timeout(500)
            # Use keyboard typing for better compatibility
            page.keyboard.type(post_text, delay=20)
            page.wait_for_timeout(1500)

            # Draft screenshot for audit
            draft_path = VAULT_PATH / "Logs" / f"linkedin_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(draft_path))
            logger.info(f"Draft screenshot saved: {draft_path.name}")

            # ── Step 3: Click Post button ─────────────────────────────────
            post_btn = None
            post_selectors = [
                "button[aria-label='Post']",
                "button.share-actions__primary-action",
                "button[aria-label*='Post now']",
                "div.share-actions__primary-action button",
                "button.artdeco-button--primary[type='submit']",
                # Last resort: any primary button in the share modal
                ".share-box-footer__primary-btn",
            ]
            for sel in post_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=4000)
                    if el and el.is_enabled():
                        post_btn = el
                        logger.info(f"Found post button: {sel}")
                        break
                except Exception:
                    continue

            if not post_btn:
                debug_path = VAULT_PATH / "Logs" / f"linkedin_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(f"Could not find Post button. Debug screenshot: {debug_path.name}")
                return False

            post_btn.click()
            page.wait_for_timeout(4000)

            # Confirmation screenshot
            confirm_path = VAULT_PATH / "Logs" / f"linkedin_posted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(confirm_path))
            logger.info(f"Post confirmation screenshot: {confirm_path.name}")
            return True

        except Exception as e:
            logger.error(f"LinkedIn post failed: {e}")
            try:
                debug_path = VAULT_PATH / "Logs" / f"linkedin_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.info(f"Debug screenshot: {debug_path.name}")
            except Exception:
                pass
            return False
        finally:
            ctx.close()


def run_post_mode():
    """
    Check Approved/ for LinkedIn posts and publish them.
    Moves approval file to Done/ after success.
    """
    approved = read_approved_post()
    if not approved:
        logger.info("No approved LinkedIn posts found in Approved/ folder.")
        return

    f = approved["file"]
    post_text = extract_post_text(approved["content"])

    if not post_text:
        logger.error(f"Could not extract post text from {f.name}")
        return

    logger.info(f"Found approved post: {f.name}")
    logger.info(f"Post preview: {post_text[:100]}...")

    success = post_to_linkedin(post_text)

    if success:
        # Move to Done
        done_dir = VAULT_PATH / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)
        dest = done_dir / f"POSTED_LinkedIn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        done_content = approved["content"] + f"\n\n---\n**Posted:** {datetime.now().isoformat()}\n**Status:** SUCCESS\n"
        dest.write_text(done_content, encoding="utf-8")
        f.unlink()
        logger.info(f"Post published and archived to Done/{dest.name}")
    else:
        logger.error("Post failed — approval file left in Approved/ for retry.")


# ── Draft + approval helper ───────────────────────────────────────────────────

def draft_post_for_approval(topic: str, post_text: str):
    """
    Write an approval request file for a LinkedIn post.
    Claude Code calls this before any post goes live.
    """
    needs_action = VAULT_PATH / "Needs_Action"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"APPROVAL_REQUIRED_LinkedIn_{timestamp}.md"
    path = needs_action / filename

    content = f"""---
type: approval_required
category: linkedin_post
topic: {topic}
status: awaiting_approval
created: {datetime.now().isoformat()}
---

# APPROVAL REQUIRED: LinkedIn Post

## Topic
{topic}

## Draft Content

{post_text}

## Goal
Generate business leads and increase visibility.

## To APPROVE
Move this file to `Approved/` — the linkedin_watcher will then post it.

## To EDIT
Edit the draft above, then move to `Approved/`.

## To REJECT
Delete this file.

---
*Claude Code will NOT post until this file is in Approved/*
"""
    path.write_text(content, encoding="utf-8")
    logger.info(f"LinkedIn draft created for approval: {filename}")
    return path


# ── Main entry point ──────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--login" in args:
        run_login()
        return

    if "--post" in args:
        run_post_mode()
        return

    if "--watch" in args:
        if "--once" in args:
            logger.info("LinkedIn watcher running in --once mode")
            watch_once(set())
        else:
            logger.info("LinkedIn watcher starting (interval=60s). Press Ctrl+C to stop.")
            processed_texts: set = set()
            try:
                while True:
                    processed_texts = watch_once(processed_texts)
                    time.sleep(60)
            except KeyboardInterrupt:
                logger.info("LinkedIn watcher stopped by user.")
        return

    # No valid arg
    print(__doc__)
    print("\nError: specify --login, --watch, or --post")
    sys.exit(1)


if __name__ == "__main__":
    main()
