"""
linkedin_debug.py - Discovers current LinkedIn selectors by inspecting live DOM.
Run: .venv/bin/python3 scripts/linkedin_debug.py
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from linkedin_watcher import get_browser_context, VAULT_PATH
from playwright.sync_api import sync_playwright

LOG = VAULT_PATH / "Logs"

with sync_playwright() as p:
    ctx = get_browser_context(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    # ── Feed page ─────────────────────────────────────────────
    print("Loading feed (waiting for JS to render)...")
    page.goto("https://www.linkedin.com/feed/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(4000)
    page.screenshot(path=str(LOG / "debug_feed.png"))
    print("Feed screenshot saved.")

    # Find "Start a post" button text/aria
    btns = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, [role=button]'))
            .filter(b => b.innerText || b.getAttribute('aria-label'))
            .map(b => ({
                tag: b.tagName,
                text: (b.innerText || '').trim().slice(0, 60),
                aria: b.getAttribute('aria-label') || '',
                cls: b.className.slice(0, 80)
            }))
            .filter(b => b.text || b.aria)
            .slice(0, 30)
    }""")
    print("\n── Feed Buttons ──")
    for b in btns:
        print(f"  [{b['tag']}] aria='{b['aria']}' text='{b['text']}' class='{b['cls'][:50]}'")

    # ── Notifications page ────────────────────────────────────
    print("\nLoading notifications (waiting for JS)...")
    page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    page.screenshot(path=str(LOG / "debug_notifications.png"))
    print("Notifications screenshot saved.")

    # Find notification list items
    items = page.evaluate("""() => {
        const selectors = [
            'li', 'article', '[data-urn]', '[id*="notification"]',
            '[class*="notification"]', '[class*="nt-card"]',
            '[class*="list-item"]', '[class*="feed-shared"]'
        ];
        let found = [];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 0 && els.length < 50) {
                found.push({
                    selector: sel,
                    count: els.length,
                    sample_class: els[0].className.slice(0, 80),
                    sample_text: (els[0].innerText || '').trim().slice(0, 60)
                });
            }
        }
        return found;
    }""")
    print("\n── Notification Candidates ──")
    for item in items:
        print(f"  sel='{item['selector']}' count={item['count']} class='{item['sample_class'][:50]}' text='{item['sample_text']}'")

    # Save full results
    results = {"buttons": btns, "notification_items": items}
    (LOG / "debug_selectors.json").write_text(json.dumps(results, indent=2))
    print(f"\nFull results saved to: {LOG / 'debug_selectors.json'}")

    ctx.close()
    print("Done.")
