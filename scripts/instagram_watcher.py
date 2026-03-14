"""
instagram_watcher.py - Instagram Auto-Poster for the AI Employee Vault.

Uses Playwright with a persistent browser session so you only log in once.
All posts go through HITL approval before publishing.

Instagram requires an image for every feed post.  If no image path is
provided the script auto-generates a 1080×1080 PNG from the post text
using Pillow (pip install Pillow).

Usage:
    # First-time login (opens headed browser for you to log in manually):
    python3 scripts/instagram_watcher.py --login

    # Post approved content (reads from Approved/ folder):
    python3 scripts/instagram_watcher.py --post

Stop with Ctrl+C.
"""

import sys
import re
import textwrap
from pathlib import Path
from datetime import datetime

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import setup_logging

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"

# Persistent browser session directory (gitignored)
SESSION_DIR = PROJECT_ROOT / ".instagram-session"

INSTAGRAM_URL = "https://www.instagram.com"

# ── Logging ───────────────────────────────────────────────────────────────────
logger = setup_logging(VAULT_PATH, "InstagramWatcher")


# ── Session helpers ───────────────────────────────────────────────────────────

def get_browser_context(playwright, headless: bool = True):
    """
    Launch a persistent Chromium context using the saved Instagram session.
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
    Check if the browser is currently on an authenticated Instagram session.
    Looks for the main navigation icons shown only when logged in.
    """
    try:
        page.wait_for_selector(
            # Instagram's persistent left-rail navigation or bottom nav bar
            "nav[role='navigation'], svg[aria-label='Home'], a[href='/']",
            timeout=8000,
        )
        # Make sure we are not stuck on a login/challenge page
        if "accounts/login" in page.url or "challenge" in page.url:
            return False
        return True
    except Exception:
        return False


# ── Login flow ────────────────────────────────────────────────────────────────

def run_login():
    """
    Open a headed browser so the user can log into Instagram manually.
    Handles the "Save login info?" dialog automatically if it appears.
    Session is persisted to .instagram-session/ for future runs.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening Instagram in headed browser for manual login...")
    logger.info(f"Session will be saved to: {SESSION_DIR}")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(INSTAGRAM_URL)

        print("\nLog into Instagram in the browser, then press Enter here...")
        input()

        # Give the page a moment to settle
        page.wait_for_timeout(2000)

        # Dismiss "Save login info?" dialog if present
        try:
            save_btn = page.wait_for_selector(
                "button:has-text('Save'), button[type='button']:has-text('Save Info')",
                timeout=5000,
            )
            if save_btn:
                save_btn.click()
                logger.info("Clicked 'Save login info' dialog.")
                page.wait_for_timeout(1500)
        except Exception:
            pass  # Dialog not present — that's fine

        # Dismiss "Turn on Notifications?" if present
        try:
            not_now = page.wait_for_selector(
                "button:has-text('Not Now'), button:has-text('Not now')",
                timeout=4000,
            )
            if not_now:
                not_now.click()
                logger.info("Dismissed notifications dialog.")
                page.wait_for_timeout(1000)
        except Exception:
            pass

        if is_logged_in(page):
            logger.info("Login confirmed! Session saved to .instagram-session/")
        else:
            logger.warning(
                "Could not confirm login. "
                "If you completed login the session may still be saved — try --post."
            )

        ctx.close()


# ── Image helpers ─────────────────────────────────────────────────────────────

def create_text_image(text: str, output_path: Path) -> Path:
    """
    Create a 1080×1080 white PNG with the post text rendered in black,
    word-wrapped at ~40 characters per line, centred on the canvas.
    Requires Pillow (pip install Pillow).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error(
            "Pillow is required to generate text images. "
            "Install it with: pip install Pillow"
        )
        raise

    img_size = 1080
    img = Image.new("RGB", (img_size, img_size), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Wrap text at ~38 chars per line (accounts for padding)
    wrapped_lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            wrapped_lines.extend(textwrap.wrap(paragraph, width=38))
        else:
            wrapped_lines.append("")  # preserve blank lines

    # Try to load a system font; fall back to default
    font = None
    font_size = 48
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/System/Library/Fonts/Helvetica.ttc",  # macOS fallback
    ]
    for candidate in font_candidates:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, font_size)
                break
            except Exception:
                continue

    if font is None:
        # Pillow built-in bitmap font — smaller but always available
        font = ImageFont.load_default()
        font_size = 20  # approximate for layout calculation

    line_height = font_size + 12
    total_height = len(wrapped_lines) * line_height
    y_start = (img_size - total_height) // 2

    for i, line in enumerate(wrapped_lines):
        # Measure line width for horizontal centering
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
        except AttributeError:
            # Older Pillow versions
            text_width, _ = draw.textsize(line, font=font)

        x = (img_size - text_width) // 2
        y = y_start + i * line_height
        draw.text((x, y), line, fill=(30, 30, 30), font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")
    logger.info(f"Text image created: {output_path.name}")
    return output_path


# ── Post mode ─────────────────────────────────────────────────────────────────

def post_to_instagram(post_text: str, image_path: Path | None = None) -> bool:
    """
    Use Playwright to post approved content to Instagram.
    If no image_path is provided a text image is auto-generated with PIL.
    Returns True on success.
    """
    from playwright.sync_api import sync_playwright

    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Ensure we have an image (Instagram feed posts require one)
    if image_path is None or not Path(image_path).exists():
        logger.info("No image provided — generating text image with PIL...")
        image_path = logs_dir / f"instagram_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        create_text_image(post_text, image_path)

    logger.info("Opening Instagram to post approved content...")
    logger.info(f"Image: {image_path}")

    with sync_playwright() as p:
        ctx = get_browser_context(p, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(INSTAGRAM_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if not is_logged_in(page):
                logger.error(
                    "Not logged in to Instagram. "
                    "Run: python3 scripts/instagram_watcher.py --login"
                )
                return False

            # ── Step 1: Click the "+" (Create) button ─────────────────────
            create_btn = None
            create_selectors = [
                "svg[aria-label='New post']",
                "a[href='/create/style/']",
                # The Create nav item contains an SVG; its parent <a> is clickable
                "a:has(svg[aria-label='New post'])",
                # Fallback: look for the "+" icon by aria-label on the nav link
                "[aria-label='New post']",
                "[aria-label='Create']",
            ]
            for sel in create_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=5000)
                    if el:
                        create_btn = el
                        logger.info(f"Found Create button: {sel}")
                        break
                except Exception:
                    continue

            if not create_btn:
                debug_path = logs_dir / f"instagram_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(
                    f"Could not find Create ('+') button. Debug screenshot: {debug_path.name}"
                )
                return False

            create_btn.click()
            page.wait_for_timeout(2000)

            # ── Step 1b: Click "Post" from the Create submenu ─────────────
            # After clicking Create, Instagram shows a submenu in the left
            # rail with plain <a> links: "Post", "Story", "Reel", "AI".
            # Use JS to find the "Post" link by text and click it.
            page.wait_for_timeout(1500)
            post_clicked = page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                const link = links.find(a => {
                    const t = (a.innerText || a.textContent || '').trim();
                    return t === 'Post';
                });
                if (link) { link.click(); return true; }
                return false;
            }""")
            if post_clicked:
                logger.info("Clicked 'Post' in Create submenu.")
                page.wait_for_timeout(3000)
            else:
                logger.warning("Could not find 'Post' link in submenu.")

            # ── Step 2: Upload the image ───────────────────────────────────
            file_input = None

            # Try 1: direct hidden file input (present on /create/style/ page)
            for sel in ["input[type='file'][accept*='image']", "input[type='file']"]:
                try:
                    el = page.wait_for_selector(sel, timeout=5000)
                    if el:
                        file_input = el
                        logger.info(f"Found file input: {sel}")
                        break
                except Exception:
                    continue

            # Try 2: "Select from computer" button → file chooser
            if not file_input:
                try:
                    select_btn = page.wait_for_selector(
                        "button:has-text('Select from computer'), "
                        "button:has-text('Select From Computer'), "
                        "button:has-text('Select from device'), "
                        "button:has-text('Select from')",
                        timeout=6000,
                    )
                    if select_btn:
                        logger.info("Found 'Select from computer' button, using file chooser...")
                        with page.expect_file_chooser(timeout=5000) as fc_info:
                            select_btn.click()
                        fc_info.value.set_files(str(image_path))
                        logger.info("File uploaded via file chooser.")
                        page.wait_for_timeout(3000)
                        file_input = True  # handled
                except Exception as e:
                    logger.info(f"File chooser approach failed: {e}")

            # Try 3: JS text search for any upload-like button
            if not file_input:
                try:
                    clicked = page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
                        const btn = btns.find(b => {
                            const t = (b.innerText || b.textContent || '').toLowerCase();
                            return t.includes('select from') || t.includes('from computer') || t.includes('from device') || t.includes('upload');
                        });
                        if (btn) { btn.click(); return btn.textContent.trim(); }
                        return null;
                    }""")
                    if clicked:
                        logger.info(f"Clicked upload button via JS: '{clicked}'")
                        page.wait_for_timeout(1500)
                        try:
                            file_input = page.wait_for_selector("input[type='file']", timeout=4000)
                        except Exception:
                            pass
                except Exception:
                    pass

            if not file_input:
                debug_path = logs_dir / f"instagram_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(
                    f"Could not find file input. Debug screenshot: {debug_path.name}"
                )
                return False

            # Only call set_input_files if we got a real element (not True from file chooser)
            if file_input is not True:
                file_input.set_input_files(str(image_path))
                logger.info("File set via input element.")
            page.wait_for_timeout(3000)

            # ── Step 3: Next → Next (crop/filter steps) ───────────────────
            for step_label in ["Next", "Next"]:
                try:
                    btn = page.wait_for_selector(
                        f"button:has-text('{step_label}'), "
                        f"div[role='button']:has-text('{step_label}')",
                        timeout=8000,
                    )
                    if btn:
                        page.evaluate("el => el.click()", btn)
                        logger.info(f"Clicked '{step_label}'")
                        page.wait_for_timeout(2500)
                except Exception as step_err:
                    logger.warning(f"Step '{step_label}' not found: {step_err}")

            # ── Step 4: Type caption on the final caption screen ──────────
            try:
                caption_area = page.wait_for_selector(
                    "textarea[aria-label*='caption'], "
                    "div[contenteditable='true'][aria-label*='caption'], "
                    "div[role='textbox']",
                    timeout=6000,
                )
                if caption_area:
                    caption_area.click()
                    page.wait_for_timeout(500)
                    page.keyboard.type(post_text, delay=15)
                    page.wait_for_timeout(1000)
                    logger.info("Caption typed.")
            except Exception as cap_err:
                logger.warning(f"Could not type caption: {cap_err}")

            # ── Step 5: Click the blue Share button in the dialog header ─
            # The publish "Share" button is in the top-right of the modal
            # header row — NOT the Share icon in the bottom toolbar.
            # Use JS to find the last/rightmost "Share" button in the dialog.
            share_clicked = False
            try:
                share_clicked = page.evaluate("""() => {
                    // Look inside the create-post dialog header for the Share button
                    const allBtns = Array.from(document.querySelectorAll(
                        'div[role="dialog"] div[role="button"], '
                        + 'div[role="dialog"] button'
                    ));
                    // The publish button text is exactly "Share"
                    const shareBtns = allBtns.filter(b => {
                        const t = (b.innerText || b.textContent || '').trim();
                        return t === 'Share';
                    });
                    if (shareBtns.length > 0) {
                        // Click the LAST one — it's in the top-right header
                        shareBtns[shareBtns.length - 1].click();
                        return true;
                    }
                    return false;
                }""")
                if share_clicked:
                    logger.info("Clicked 'Share' (publish) button via JS.")
                else:
                    logger.warning("JS Share button search returned false.")
            except Exception as e:
                logger.warning(f"Share button JS failed: {e}")

            if not share_clicked:
                debug_path = logs_dir / f"instagram_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(debug_path))
                logger.error(f"Could not click Share. Debug: {debug_path.name}")
                return False

            # ── Step 6: Wait for "Post shared" / feed redirect ────────────
            # Instagram shows "Your post has been shared." or navigates to feed
            published = False
            try:
                page.wait_for_selector(
                    "span:has-text('Post shared'), "
                    "span:has-text('Your post has been shared'), "
                    "[aria-label='Post shared']",
                    timeout=15000,
                )
                published = True
                logger.info("Instagram confirmed: Post shared!")
            except Exception:
                # Fallback: if URL changed back to feed, post went through
                page.wait_for_timeout(5000)
                if "instagram.com/p/" in page.url or page.url in [
                    "https://www.instagram.com/",
                    "https://www.instagram.com",
                ]:
                    published = True
                    logger.info("Post published (navigated back to feed).")

            # Confirmation screenshot
            confirm_path = logs_dir / f"instagram_posted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(confirm_path))
            logger.info(f"Confirmation screenshot: {confirm_path.name}")

            if not published:
                logger.warning(
                    "Could not confirm post — check screenshot to verify manually."
                )

            return True

        except Exception as e:
            logger.error(f"Instagram post failed: {e}")
            try:
                debug_path = logs_dir / f"instagram_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
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
    Scan Approved/ folder for Instagram post approval files.
    Returns the first one found as {file, content}, or None.
    """
    approved_dir = VAULT_PATH / "Approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    for f in sorted(approved_dir.glob("APPROVAL_REQUIRED_Instagram_*.md")):
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


def draft_post_for_approval(topic: str, post_text: str, image_path: str = "") -> Path:
    """
    Write an APPROVAL_REQUIRED file for an Instagram post into Needs_Action/.
    Move the file to Approved/ to trigger posting.
    Optionally include an image_path that the poster will use.
    """
    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"APPROVAL_REQUIRED_Instagram_{timestamp}.md"
    path = needs_action / filename

    image_line = f"image_path: {image_path}" if image_path else "image_path: (auto-generate)"

    content = f"""---
type: approval_required
category: instagram_post
topic: {topic}
{image_line}
status: awaiting_approval
created: {datetime.now().isoformat()}
---

# APPROVAL REQUIRED: Instagram Post

## Topic
{topic}

## Draft Content

{post_text}

## Image
{image_path if image_path else "*(Will be auto-generated as a text image if not provided)*"}

## Goal
Share engaging content on Instagram to grow audience and brand visibility.

## To APPROVE
Move this file to `Approved/` — the instagram_watcher will then post it.

## To EDIT
Edit the draft above, then move to `Approved/`.

## To REJECT
Delete this file.

---
*Claude Code will NOT post until this file is in Approved/*
"""
    path.write_text(content, encoding="utf-8")
    logger.info(f"Instagram draft created for approval: {filename}")
    return path


# ── Run post mode ─────────────────────────────────────────────────────────────

def run_post_mode():
    """
    Check Approved/ for Instagram posts and publish them.
    Archives the approval file to Done/ after success.
    """
    approved = read_approved_post()
    if not approved:
        logger.info("No approved Instagram posts found in Approved/ folder.")
        return

    f = approved["file"]
    post_text = extract_post_text(approved["content"])

    if not post_text:
        logger.error(f"Could not extract post text from {f.name}")
        return

    # Check if the approval file specifies a custom image path
    image_path: Path | None = None
    img_match = re.search(r"image_path:\s*(.+)", approved["content"])
    if img_match:
        img_val = img_match.group(1).strip()
        if img_val and not img_val.startswith("("):
            candidate = Path(img_val)
            if candidate.exists():
                image_path = candidate
                logger.info(f"Using specified image: {image_path}")
            else:
                logger.warning(
                    f"Specified image not found ({img_val}) — will auto-generate."
                )

    logger.info(f"Found approved post: {f.name}")
    logger.info(f"Post preview: {post_text[:120]}...")

    success = post_to_instagram(post_text, image_path)

    if success:
        done_dir = VAULT_PATH / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = done_dir / f"POSTED_Instagram_{timestamp}.md"
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
