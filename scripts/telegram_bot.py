"""
telegram_bot.py — Telegram notification + action bot for the Personal AI Employee.

Watches Needs_Action/ with watchdog. When a new .md file appears, sends a
formatted Telegram card with inline buttons. Handles Reply/Approve/Reject/Done.

Usage:
    .venv/bin/python3 scripts/telegram_bot.py

First-time setup:
    1. Create bot via @BotFather on Telegram, copy token
    2. Add TELEGRAM_BOT_TOKEN to .env
    3. Run this script, open Telegram, send /start to your bot
    4. Chat ID is saved automatically — notifications start immediately
"""

import asyncio
import base64
import logging
import os
import re
import shutil
import sys
import threading
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT     = Path(__file__).parent.parent
VAULT_PATH       = PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_PATH / "Needs_Action"
APPROVED_DIR     = VAULT_PATH / "Approved"
REJECTED_DIR     = VAULT_PATH / "Rejected"
DONE_DIR         = VAULT_PATH / "Done"
LOGS_DIR         = VAULT_PATH / "Logs"
TOKEN_PATH       = PROJECT_ROOT / "token.json"
CHAT_ID_FILE     = LOGS_DIR / "telegram_chat_id.txt"

# ConversationHandler state
WAITING_FOR_REPLY = 1

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv(PROJECT_ROOT / ".env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("TelegramBot")

# ── Chat ID ───────────────────────────────────────────────────────────────────

def get_chat_id() -> int | None:
    env_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if env_id.lstrip("-").isdigit():
        return int(env_id)
    if CHAT_ID_FILE.exists():
        raw = CHAT_ID_FILE.read_text().strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
    return None

# ── File Parser ───────────────────────────────────────────────────────────────

def parse_action_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")

    fm = {}
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                fm[k.strip()] = v.strip()

    name = path.name
    file_type = fm.get("type", "")
    if not file_type:
        if name.startswith("ACTION_EMAIL"):
            file_type = "email"
        elif name.startswith("APPROVAL_REQUIRED"):
            file_type = "approval"
        elif name.startswith("ACTION_LINKEDIN"):
            file_type = "linkedin_notification"
        elif name.startswith("ACTION_ODOO"):
            file_type = "odoo"
        elif name.startswith("ACTION_WHATSAPP"):
            file_type = "whatsapp_message"
        else:
            file_type = "generic"

    preview = ""
    preview_match = re.search(r"## Preview\s*\n+> (.+?)(?:\n|$)", content)
    if preview_match:
        preview = preview_match.group(1).strip()
    else:
        bq = re.search(r"^> (.+)", content, re.MULTILINE)
        if bq:
            preview = bq.group(1).strip()

    return {
        "file_type":   file_type,
        "filename":    name,
        "path":        path,
        "from_":       fm.get("from", ""),
        "subject":     fm.get("subject", ""),
        "urgency":     fm.get("urgency", "Normal"),
        "preview":     preview[:280] if preview else "(no preview)",
        "raw_content": content,
        "frontmatter": fm,
        "gmail_id":    fm.get("gmail_id", ""),
    }

# ── Telegram Message Builders ─────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def build_card(info: dict) -> tuple[str, InlineKeyboardMarkup]:
    ft = info["file_type"]
    urgency = info["urgency"]
    u_emoji = "🟡" if urgency == "High" else ("🔴" if urgency == "Critical" else "🟢")

    if ft == "email":
        text = (
            f"📧 *New Email*\n"
            f"{u_emoji} {_esc(urgency)}\n\n"
            f"*From:* {_esc(info['from_'])}\n"
            f"*Subject:* {_esc(info['subject'])}\n\n"
            f"_{_esc(info['preview'])}_\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✉️ Reply", callback_data=f"reply|{info['filename']}"),
            InlineKeyboardButton("✅ Done",  callback_data=f"done|{info['filename']}"),
        ]])

    elif ft == "approval":
        body_start = info["raw_content"].find("---\n", 4) + 4
        body = info["raw_content"][body_start:body_start + 500].strip()
        text = (
            f"⚠️ *Approval Required*\n\n"
            f"{_esc(body[:400])}\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve|{info['filename']}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject|{info['filename']}"),
        ]])

    elif "linkedin" in ft:
        text = (
            f"💼 *LinkedIn Notification*\n\n"
            f"_{_esc(info['preview'])}_\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done|{info['filename']}"),
        ]])

    elif ft == "odoo":
        text = (
            f"📊 *Odoo Accounting Alert*\n\n"
            f"_{_esc(info['preview'])}_\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done|{info['filename']}"),
        ]])

    elif "whatsapp" in ft:
        text = (
            f"💬 *WhatsApp Message*\n"
            f"{u_emoji} {_esc(urgency)}\n\n"
            f"*From:* {_esc(info['frontmatter'].get('contact', 'Unknown'))}\n\n"
            f"_{_esc(info['preview'])}_\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done|{info['filename']}"),
        ]])

    else:
        text = (
            f"📋 *Action Required*\n\n"
            f"_{_esc(info['preview'])}_\n\n"
            f"`{_esc(info['filename'])}`"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done|{info['filename']}"),
        ]])

    return text, keyboard

# ── Watchdog → Asyncio Bridge ─────────────────────────────────────────────────

class VaultNotifyHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._queue = queue
        self._loop  = loop

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix == ".md" and not p.name.startswith("."):
            asyncio.run_coroutine_threadsafe(self._queue.put(p), self._loop)


async def notify_worker(queue: asyncio.Queue, bot: Bot):
    while True:
        path = await queue.get()
        await asyncio.sleep(1.0)  # let file finish writing

        chat_id = get_chat_id()
        if not chat_id:
            logger.warning("No chat ID. Send /start to your bot first.")
            queue.task_done()
            continue

        try:
            if not path.exists():
                queue.task_done()
                continue
            info = parse_action_file(path)
            text, keyboard = build_card(info)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
            logger.info(f"Notified: {path.name}")
        except Exception as e:
            logger.error(f"Notify failed for {path.name}: {e}")
        finally:
            queue.task_done()

# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_ID_FILE.write_text(str(chat_id))
    os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)
    await update.message.reply_text(
        f"✅ AI Employee connected\\!\n"
        f"Chat ID `{chat_id}` registered\\.\n\n"
        f"You'll receive notifications for all new inbox items\\.\n\n"
        f"Commands:\n"
        f"/status — pending items count\n"
        f"/pending — list all pending files",
        parse_mode="MarkdownV2",
    )
    logger.info(f"/start from chat_id={chat_id}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files     = list(NEEDS_ACTION_DIR.glob("*.md")) if NEEDS_ACTION_DIR.exists() else []
    emails    = sum(1 for f in files if f.name.startswith("ACTION_EMAIL"))
    approvals = sum(1 for f in files if f.name.startswith("APPROVAL_REQUIRED"))
    linkedin  = sum(1 for f in files if f.name.startswith("ACTION_LINKEDIN"))
    odoo      = sum(1 for f in files if f.name.startswith("ACTION_ODOO"))
    whatsapp  = sum(1 for f in files if f.name.startswith("ACTION_WHATSAPP"))
    other     = len(files) - emails - approvals - linkedin - odoo - whatsapp
    done      = len(list(DONE_DIR.glob("*.md"))) if DONE_DIR.exists() else 0

    await update.message.reply_text(
        f"*AI Employee Status*\n\n"
        f"Pending:\n"
        f"  📧 Emails: {emails}\n"
        f"  ⚠️ Approvals: {approvals}\n"
        f"  💼 LinkedIn: {linkedin}\n"
        f"  📊 Odoo: {odoo}\n"
        f"  💬 WhatsApp: {whatsapp}\n"
        f"  📋 Other: {other}\n\n"
        f"✅ Done: {done}",
        parse_mode="Markdown",
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send Telegram cards for all current Needs_Action files."""
    chat_id = update.effective_chat.id
    files = sorted(NEEDS_ACTION_DIR.glob("*.md")) if NEEDS_ACTION_DIR.exists() else []
    if not files:
        await update.message.reply_text("✅ No pending items.")
        return
    await update.message.reply_text(f"Sending {len(files)} pending item(s)...")
    for path in files:
        try:
            info = parse_action_file(path)
            text, keyboard = build_card(info)
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
            await asyncio.sleep(0.3)
        except Exception as e:
            await update.message.reply_text(f"Error for {path.name}: {e}")

# ── Button Callbacks ──────────────────────────────────────────────────────────

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 1)
    if len(parts) != 2:
        return
    action, filename = parts
    src = NEEDS_ACTION_DIR / filename

    if action == "reply":
        context.user_data["reply_file"] = filename
        await query.edit_message_text(
            f"✉️ Type your reply message\\.\n\n"
            f"_\\(or /cancel to abort\\)_",
            parse_mode="MarkdownV2",
        )
        return WAITING_FOR_REPLY

    dest_map = {"done": DONE_DIR, "approve": APPROVED_DIR, "reject": REJECTED_DIR}
    label_map = {"done": "Done", "approve": "Approved", "reject": "Rejected"}

    dest_dir = dest_map.get(action)
    label    = label_map.get(action, "Done")

    if not dest_dir:
        return

    if not src.exists():
        await query.edit_message_text("File already processed or not found\\.", parse_mode="MarkdownV2")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest_dir / filename))
    logger.info(f"Moved {filename} → {label}/")

    await query.edit_message_text(
        f"✅ Moved to {_esc(label)}\\/\n`{_esc(filename)}`",
        parse_mode="MarkdownV2",
    )

# ── Reply Conversation ────────────────────────────────────────────────────────

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _get_gmail_service():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError("token.json missing")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _send_gmail_reply(to: str, subject: str, body: str) -> str:
    svc = _get_gmail_service()
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"]      = to
    msg["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return result["id"]


async def receive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filename = context.user_data.get("reply_file")
    if not filename:
        await update.message.reply_text("Session expired. Tap Reply again.")
        return ConversationHandler.END

    reply_text = update.message.text
    src = NEEDS_ACTION_DIR / filename

    if not src.exists():
        await update.message.reply_text(f"File no longer in Needs_Action/.")
        return ConversationHandler.END

    info    = parse_action_file(src)
    to      = info["from_"]
    subject = info["subject"]

    if not to:
        await update.message.reply_text("No 'from' field in file — cannot determine recipient.")
        return ConversationHandler.END

    email_match = re.search(r"<(.+?)>", to)
    to_addr = email_match.group(1) if email_match else to

    try:
        msg_id = await asyncio.get_event_loop().run_in_executor(
            None, _send_gmail_reply, to_addr, subject, reply_text
        )
    except Exception as e:
        logger.error(f"Gmail send failed: {e}")
        await update.message.reply_text(f"Send failed: {e}")
        return ConversationHandler.END

    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dest = DONE_DIR / f"REPLIED_{filename}"
    shutil.move(str(src), str(dest))
    note = f"\n\n---\n**SENT via Telegram:** {datetime.now().isoformat()}\n**Gmail ID:** {msg_id}\n"
    dest.write_text(dest.read_text() + note, encoding="utf-8")

    logger.info(f"Reply sent → {to_addr} | {subject} | Gmail ID: {msg_id}")
    await update.message.reply_text(f"✅ Reply sent to {to_addr}\nMoved to Done/")
    return ConversationHandler.END


async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reply_file", None)
    await update.message.reply_text("Reply cancelled.")
    return ConversationHandler.END

# ── Startup: notify existing pending files ────────────────────────────────────

async def notify_existing(bot: Bot):
    chat_id = get_chat_id()
    if not chat_id or not NEEDS_ACTION_DIR.exists():
        return
    cutoff = datetime.now().timestamp() - (24 * 3600)
    files  = sorted(NEEDS_ACTION_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime)
    recent = [f for f in files if f.stat().st_mtime > cutoff]
    if not recent:
        return
    await bot.send_message(chat_id=chat_id, text=f"🤖 Bot started\n{len(recent)} pending item(s) from last 24h:")
    for path in recent:
        try:
            info = parse_action_file(path)
            text, keyboard = build_card(info)
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2", reply_markup=keyboard)
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.warning(f"Could not notify for {path.name}: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_button, pattern=r"^reply\|")],
        states={WAITING_FOR_REPLY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reply),
            CommandHandler("cancel", cancel_reply),
        ]},
        fallbacks=[CommandHandler("cancel", cancel_reply)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(reply_conv)
    app.add_handler(CallbackQueryHandler(handle_button, pattern=r"^(done|approve|reject)\|"))

    loop  = asyncio.get_event_loop()
    queue = asyncio.Queue()

    handler  = VaultNotifyHandler(queue, loop)
    observer = Observer()
    observer.schedule(handler, str(NEEDS_ACTION_DIR), recursive=False)
    observer.start()

    async def _post_init(application):
        asyncio.create_task(notify_worker(queue, application.bot))
        await notify_existing(application.bot)

    app.post_init = _post_init

    logger.info("Telegram bot running. Press Ctrl+C to stop.")
    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        observer.stop()
        observer.join()
        logger.info("Telegram bot stopped.")


if __name__ == "__main__":
    main()
