"""
whatsapp_watcher.py - WhatsApp Web watcher for the AI Employee Vault (Gold Tier).

Uses Playwright with a persistent browser session so you only scan the QR code once.

Usage:
    # First-time setup (headed browser — scan the QR code with your phone):
    python3 scripts/whatsapp_watcher.py --login

    # Watch for new messages continuously:
    python3 scripts/whatsapp_watcher.py --watch

    # Watch once (for orchestrator/cron):
    python3 scripts/whatsapp_watcher.py --watch --once

Stop with Ctrl+C.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import setup_logging

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"

# Persistent browser session directory (gitignored)
SESSION_DIR = PROJECT_ROOT / ".whatsapp-session"

WHATSAPP_URL = "https://web.whatsapp.com"
WATCH_INTERVAL = 30  # seconds between polls in continuous mode

# Keywords that trigger an ACTION file
TRIGGER_KEYWORDS = [
    "urgent", "asap", "invoice", "payment", "help", "important",
]

# ── Logging ───────────────────────────────────────────────────────────────────
logger = setup_logging(VAULT_PATH, "WhatsAppWatcher")


# ── Browser context ───────────────────────────────────────────────────────────

def get_browser_context(playwright, headless: bool = True):
    """
    Launch a persistent Chromium context using the saved WhatsApp session.
    If no session exists yet, run --login first.
    """
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        str(SESSION_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    return context


def _is_logged_in(page) -> bool:
    """
    Return True if WhatsApp Web is in the main chat view (not the QR screen).
    Detects both the classic QR landing and the "Use WhatsApp on your phone" interstitial.
    """
    try:
        # If the main app canvas / side panel is present → logged in
        page.wait_for_selector(
            "#app, #side, [data-testid='chat-list'], [data-testid='default-user']",
            timeout=8000,
        )
        # Make sure we are NOT on the QR page
        qr_el = page.query_selector(
            "canvas[aria-label='Scan me!'], [data-testid='qrcode'], "
            "div[data-ref], ._19vUU"
        )
        return qr_el is None
    except Exception:
        return False


def _detect_qr_screen(page) -> bool:
    """Return True if the QR code / 'Use WhatsApp on your phone' screen is showing."""
    try:
        page.wait_for_selector(
            "canvas[aria-label='Scan me!'], [data-testid='qrcode'], "
            "div[data-ref], ._19vUU, [data-icon='logo-ct']",
            timeout=5000,
        )
        return True
    except Exception:
        return False


# ── Login flow ─────────────────────────────────────────────────────────────────

def run_login():
    """
    Open a headed browser, navigate to WhatsApp Web, and wait for the user
    to scan the QR code. The session is saved to .whatsapp-session/.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening WhatsApp Web in headed browser for QR scan setup...")
    logger.info(f"Session will be saved to: {SESSION_DIR}")
    logger.info("-" * 60)
    logger.info("INSTRUCTIONS:")
    logger.info("  1. Your phone must be on the same Wi-Fi as this machine.")
    logger.info("  2. Open WhatsApp on your phone.")
    logger.info("  3. Go to: Settings > Linked Devices > Link a Device.")
    logger.info("  4. Scan the QR code that appears in the browser window.")
    logger.info("  5. Wait until the chats load, then close the browser window.")
    logger.info("-" * 60)

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)

            # Detect QR screen immediately
            if _detect_qr_screen(page):
                logger.info("QR code is visible — please scan it with your phone now.")
            else:
                logger.info("Loaded WhatsApp Web — waiting for QR or session...")

            # Wait up to 3 minutes for the user to scan and chats to load
            try:
                page.wait_for_selector(
                    "#side, [data-testid='chat-list'], [data-testid='default-user']",
                    timeout=180_000,
                )
                logger.info("Login successful! WhatsApp session saved.")
            except Exception:
                logger.warning(
                    "Timed out waiting for login. "
                    "Please re-run --login and scan the QR within 3 minutes."
                )
        finally:
            ctx.close()


# ── Scrape messages ────────────────────────────────────────────────────────────

def scrape_messages(page) -> list[dict]:
    """
    Scrape unread messages from the WhatsApp Web chat list.
    Only returns messages that contain at least one TRIGGER_KEYWORD.

    Returns a list of dicts:
        {contact, message, timestamp, is_unread}
    """
    try:
        page.wait_for_selector(
            "[data-testid='chat-list'], #pane-side",
            timeout=15000,
        )
    except Exception as e:
        logger.warning(f"Could not find chat list: {e}")
        return []

    messages = []

    # Try multiple selectors for individual chat rows (WhatsApp changes these often)
    chat_selectors = [
        "#pane-side div[role='row']",       # current WhatsApp Web (2025+)
        "[data-testid='cell-frame-container']",
        "div[role='listitem']",
        "._21S-L",
        ".zoWT4",
    ]

    chat_items = []
    for sel in chat_selectors:
        chat_items = page.query_selector_all(sel)
        if chat_items:
            logger.info(f"Found {len(chat_items)} chats using selector: {sel}")
            break

    if not chat_items:
        logger.info("No chat items found in the list.")
        return []

    for item in chat_items[:30]:
        try:
            full_text = item.inner_text().strip()
            if not full_text:
                continue

            # Determine if this chat has an unread badge
            unread_badge = item.query_selector(
                "[data-testid='icon-unread-count'], "
                "._15G96, "          # unread count bubble
                "span.P6z4j, "
                "span[aria-label*='unread']"
            )
            is_unread = unread_badge is not None

            # Extract contact name (first line of the cell text)
            lines = [l.strip() for l in full_text.splitlines() if l.strip()]
            contact   = lines[0] if lines else "Unknown"
            message   = " ".join(lines[1:]) if len(lines) > 1 else full_text
            timestamp = lines[-1] if len(lines) > 2 else ""

            # Filter by trigger keywords (case-insensitive)
            msg_lower = message.lower()
            if not any(kw in msg_lower for kw in TRIGGER_KEYWORDS):
                continue

            messages.append(
                {
                    "contact":   contact,
                    "message":   message,
                    "timestamp": timestamp,
                    "is_unread": is_unread,
                }
            )

        except Exception:
            continue

    logger.info(
        f"Scraped {len(messages)} keyword-matching message(s) from {len(chat_items)} chat(s)."
    )
    return messages


# ── Action file creator ────────────────────────────────────────────────────────

def create_whatsapp_action_file(vault_path: Path, message_data: dict) -> Path:
    """
    Create Needs_Action/ACTION_WHATSAPP_<contact>_<timestamp>.md
    with message details and suggested actions.
    """
    needs_action = vault_path / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    now       = datetime.now()
    ts_str    = now.strftime("%Y%m%d_%H%M%S")
    contact   = message_data.get("contact", "Unknown")
    # Sanitise contact name for use in filename
    safe_contact = "".join(c if c.isalnum() or c in "-_" else "_" for c in contact)[:30]
    filename  = f"ACTION_WHATSAPP_{safe_contact}_{ts_str}.md"
    path      = needs_action / filename

    message   = message_data.get("message", "")
    timestamp = message_data.get("timestamp", "")
    is_unread = message_data.get("is_unread", False)

    urgency = "High" if any(kw in message.lower() for kw in {"urgent", "asap", "payment"}) else "Normal"
    badge   = "Unread" if is_unread else "Read"
    emoji   = "🔴" if urgency == "High" else "🟡"

    content = f"""---
type: whatsapp_message
source: WhatsApp
contact: {contact}
urgency: {urgency}
read_status: {badge}
status: pending
detected: {now.isoformat()}
---

# Action Required: WhatsApp Message from {contact}

{emoji} **Urgency:** {urgency}  |  **Status:** {badge}

## Message

> {message}

{"**Received:** " + timestamp if timestamp else ""}

## Contact

**{contact}** (via WhatsApp Web)

## Suggested Actions

- [ ] Open WhatsApp and read the full conversation with **{contact}**
- [ ] If it's a payment/invoice query → run `hitl-approval` skill
- [ ] If a reply is needed → run `send-email` skill or reply directly
- [ ] If it's a lead/opportunity → run `create-plan` skill to draft a response plan
- [ ] Move this file to `/Done/` when complete

---
*(Claude Code: do NOT reply without reviewing in Company_Handbook.md — always HITL first)*
"""
    path.write_text(content, encoding="utf-8")
    logger.info(f"WhatsApp action file created: {filename}")
    return path


# ── Single watch cycle ─────────────────────────────────────────────────────────

def watch_once(processed_texts: set) -> set:
    """
    Run one scrape cycle using the saved headless session.
    Returns an updated processed_texts set (deduplication across cycles).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(WHATSAPP_URL, wait_until="domcontentloaded", timeout=30000)

            # Small pause to let the page hydrate
            page.wait_for_timeout(4000)

            # Check for QR / "Use WhatsApp on your phone" screen
            if _detect_qr_screen(page):
                logger.error(
                    "WhatsApp Web is showing the QR / 'Use WhatsApp on your phone' screen. "
                    "Session has expired or was never saved. "
                    "Re-run: python3 scripts/whatsapp_watcher.py --login"
                )
                return processed_texts

            if not _is_logged_in(page):
                page.goto(WHATSAPP_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                if not _is_logged_in(page):
                    logger.error(
                        "Not logged in to WhatsApp Web. "
                        "Run: python3 scripts/whatsapp_watcher.py --login"
                    )
                    return processed_texts

            messages = scrape_messages(page)

            new_count = 0
            for msg in messages:
                # Deduplicate using contact + message snippet
                key = f"{msg['contact']}::{msg['message'][:80]}"
                if key not in processed_texts:
                    create_whatsapp_action_file(VAULT_PATH, msg)
                    processed_texts.add(key)
                    new_count += 1

            if new_count:
                logger.info(f"Created {new_count} new WhatsApp action file(s).")
            else:
                logger.info("No new keyword-matching WhatsApp messages.")

        finally:
            ctx.close()

    return processed_texts


# ── Main watch loop ────────────────────────────────────────────────────────────

def run_watch(continuous: bool = True):
    """
    Main watch loop.

    If continuous=True  → polls every WATCH_INTERVAL seconds (--watch).
    If continuous=False → single cycle only (--watch --once).
    """
    if continuous:
        logger.info(
            f"WhatsApp watcher starting (interval={WATCH_INTERVAL}s). "
            "Press Ctrl+C to stop."
        )
    else:
        logger.info("WhatsApp watcher running in --once mode.")

    processed_texts: set = set()

    try:
        processed_texts = watch_once(processed_texts)

        if not continuous:
            return

        while True:
            time.sleep(WATCH_INTERVAL)
            processed_texts = watch_once(processed_texts)

    except KeyboardInterrupt:
        logger.info("WhatsApp watcher stopped by user.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--login" in args:
        run_login()
        return

    if "--watch" in args:
        continuous = "--once" not in args
        run_watch(continuous=continuous)
        return

    # No valid argument
    print(__doc__)
    print("\nError: specify --login or --watch [--once]")
    sys.exit(1)


if __name__ == "__main__":
    main()
