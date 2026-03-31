"""
web_ui.py — FastAPI dashboard for Personal AI Employee Vault.

Run with:  .venv/bin/python3 scripts/web_ui.py
Access at: http://<VM-IP>:8080
Login:     admin / (DASHBOARD_PASSWORD from .env)
"""

import os, re, json, base64, secrets, shutil
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import uvicorn
import jinja2
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT     = Path(__file__).parent.parent
VAULT            = PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT / "Needs_Action"
APPROVED_DIR     = VAULT / "Approved"
DONE_DIR         = VAULT / "Done"
REJECTED_DIR     = VAULT / "Rejected"
LOGS_DIR         = VAULT / "Logs"
STATUS_FILE      = LOGS_DIR / "orchestrator_status.json"
ORCH_LOG         = LOGS_DIR / "orchestrator.log"
TOKEN_PATH       = PROJECT_ROOT / "token.json"

load_dotenv(PROJECT_ROOT / ".env")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")

# ── Auth ──────────────────────────────────────────────────────────────────────

security = HTTPBasic()

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, "admin")
    ok_pass = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="AI Employee"'})
    return credentials.username

# ── Vault Parser ──────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fm[k.strip()] = v.strip()
    return fm

def classify_file(name: str, fm: dict) -> str:
    n = name.upper()
    if n.startswith("APPROVAL_REQUIRED_"):
        return "approval"
    t = fm.get("type", "").lower()
    if t == "email"      or "EMAIL"    in n: return "email"
    if "linkedin"  in t  or "LINKEDIN" in n: return "linkedin"
    if "whatsapp"  in t  or "WHATSAPP" in n: return "whatsapp"
    if "odoo"      in t  or "ODOO"     in n: return "odoo"
    return "unknown"

def parse_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm   = parse_frontmatter(text)
    kind = classify_file(path.name, fm)

    preview_m = re.search(r"^> (.+)", text, re.MULTILINE)
    preview   = preview_m.group(1)[:200] if preview_m else text.replace("---","")[:150]

    detected = fm.get("detected", "")
    if not detected:
        detected = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "filename": path.name,
        "type":     kind,
        "from_":    fm.get("from", fm.get("source", "System")),
        "subject":  fm.get("subject", path.stem.replace("_", " ")[:60]),
        "urgency":  fm.get("urgency", "Normal"),
        "gmail_id": fm.get("gmail_id", ""),
        "detected": detected[:16].replace("T", " "),
        "preview":  preview.strip(),
    }

# ── Gmail ─────────────────────────────────────────────────────────────────────

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

def get_gmail():
    if not TOKEN_PATH.exists():
        raise RuntimeError("token.json not found")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest())
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)

# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Employee", docs_url=None, redoc_url=None)
_jinja = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=True)

WATCHER_NAMES = {
    "filesystem":    "Filesystem",
    "send_email":    "Email Sender",
    "gmail":         "Gmail",
    "linkedin_watch":"LinkedIn Watch",
    "linkedin_post": "LinkedIn Post",
    "odoo":          "Odoo",
    "facebook":      "Facebook",
    "instagram":     "Instagram",
    "whatsapp":      "WhatsApp",
}

GROUP_LABELS = {
    "email":    ("📧", "Emails"),
    "approval": ("⚠️", "Approvals"),
    "linkedin": ("💼", "LinkedIn"),
    "whatsapp": ("💬", "WhatsApp"),
    "odoo":     ("📊", "Odoo"),
    "unknown":  ("📋", "Other"),
}

def _safe_move(filename: str, dest_dir: Path):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    src = NEEDS_ACTION_DIR / filename
    if not src.exists():
        raise HTTPException(404, "File not found")
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest_dir / filename))

# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(user=Depends(require_auth)):
    status = {}
    uptime = ""
    if STATUS_FILE.exists():
        data = json.loads(STATUS_FILE.read_text())
        status = data.get("watchers", {})
        secs = int(data.get("uptime_seconds", 0))
        h, m = divmod(secs // 60, 60)
        d, h = divmod(h, 24)
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"

    pending = len(list(NEEDS_ACTION_DIR.glob("*.md"))) if NEEDS_ACTION_DIR.exists() else 0
    done    = len(list(DONE_DIR.glob("*.md")))         if DONE_DIR.exists()         else 0
    approved= len(list(APPROVED_DIR.glob("*.md")))     if APPROVED_DIR.exists()     else 0

    log_lines = ""
    if ORCH_LOG.exists():
        lines = ORCH_LOG.read_text(errors="replace").splitlines()
        log_lines = "\n".join(lines[-20:])

    watchers = []
    for k, v in status.items():
        s = v.get("status", "unknown")
        color = "green" if s in ("running","idle") else ("yellow" if s == "error" else "red")
        label = "Running" if s in ("running","idle") else s.capitalize()
        watchers.append({"name": WATCHER_NAMES.get(k, k), "status": label, "color": color, "pid": v.get("pid","")})

    return HTMLResponse(_jinja.from_string(HOME_HTML).render(
        watchers=watchers, pending=pending, done=done, approved=approved,
        log_lines=log_lines, uptime=uptime, now=datetime.now().strftime("%H:%M:%S")
    ))


@app.get("/inbox", response_class=HTMLResponse)
async def inbox(user=Depends(require_auth)):
    files = sorted(NEEDS_ACTION_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True) \
            if NEEDS_ACTION_DIR.exists() else []
    groups = {}
    for path in files:
        item = parse_file(path)
        groups.setdefault(item["type"], []).append(item)

    ordered = []
    for kind in ["email","approval","linkedin","whatsapp","odoo","unknown"]:
        if kind in groups:
            emoji, label = GROUP_LABELS[kind]
            ordered.append({"label": label, "emoji": emoji, "items": groups[kind]})

    return HTMLResponse(_jinja.from_string(INBOX_HTML).render(groups=ordered, total=len(files)))


@app.get("/compose", response_class=HTMLResponse)
async def compose(user=Depends(require_auth)):
    return HTMLResponse(_jinja.from_string(COMPOSE_HTML).render())


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(user=Depends(require_auth)):
    lines = ""
    if ORCH_LOG.exists():
        lines = "\n".join(ORCH_LOG.read_text(errors="replace").splitlines()[-100:])
    return HTMLResponse(_jinja.from_string(LOGS_HTML).render(log_lines=lines))


@app.get("/api/logs")
async def api_logs(user=Depends(require_auth)):
    if not ORCH_LOG.exists():
        return JSONResponse({"lines": ""})
    lines = "\n".join(ORCH_LOG.read_text(errors="replace").splitlines()[-100:])
    return JSONResponse({"lines": lines})


@app.get("/api/status")
async def api_status(user=Depends(require_auth)):
    if not STATUS_FILE.exists():
        return JSONResponse({"error": "Status file not found"}, status_code=404)
    return JSONResponse(json.loads(STATUS_FILE.read_text()))


@app.get("/api/inbox")
async def api_inbox(user=Depends(require_auth)):
    files = sorted(NEEDS_ACTION_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True) \
            if NEEDS_ACTION_DIR.exists() else []
    return JSONResponse([parse_file(f) for f in files])


@app.post("/api/action")
async def api_action(filename: str = Form(...), action: str = Form(...), user=Depends(require_auth)):
    dest = {"done": DONE_DIR, "approve": APPROVED_DIR, "reject": REJECTED_DIR}.get(action)
    if not dest:
        raise HTTPException(400, "Invalid action")
    _safe_move(filename, dest)
    return JSONResponse({"ok": True})


@app.post("/api/reply")
async def api_reply(gmail_id: str = Form(...), message: str = Form(...), filename: str = Form(...), user=Depends(require_auth)):
    try:
        svc  = get_gmail()
        orig = svc.users().messages().get(userId="me", id=gmail_id, format="metadata",
               metadataHeaders=["From","Subject","Message-ID"]).execute()
        h    = {x["name"]: x["value"] for x in orig["payload"]["headers"]}

        reply = MIMEText(message, "plain", "utf-8")
        reply["to"]          = h.get("From", "")
        reply["subject"]     = ("Re: " + h.get("Subject","")) if not h.get("Subject","").startswith("Re:") else h.get("Subject","")
        reply["In-Reply-To"] = h.get("Message-ID", "")
        reply["References"]  = h.get("Message-ID", "")

        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw, "threadId": orig["threadId"]}).execute()

        _safe_move(filename, DONE_DIR)
        return JSONResponse({"ok": True})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/send-email")
async def api_send_email(to: str = Form(...), subject: str = Form(...), body: str = Form(...), user=Depends(require_auth)):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"APPROVAL_REQUIRED_Email_{ts}.md"
    content = f"""---
to: {to}
subject: {subject}
type: approval_email
status: pending
created: {datetime.now().isoformat()}
---

# Approval Required: Email to {to}

**To:** {to}
**Subject:** {subject}

---

{body}

---
*Move to Approved/ to send. Move to Rejected/ to cancel.*
"""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    (NEEDS_ACTION_DIR / name).write_text(content, encoding="utf-8")
    return JSONResponse({"ok": True, "filename": name})

# ── HTML Templates ────────────────────────────────────────────────────────────

NAV = """
<nav class="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 shadow-lg">
  <span class="font-bold text-lg">🤖 AI Employee</span>
  <a href="/" class="hover:text-blue-300 text-sm">Dashboard</a>
  <a href="/inbox" class="hover:text-blue-300 text-sm">Inbox</a>
  <a href="/compose" class="hover:text-blue-300 text-sm">Compose</a>
  <a href="/logs" class="hover:text-blue-300 text-sm">Logs</a>
  <span class="ml-auto text-xs text-gray-400">{{ now if now is defined else "" }}</span>
</nav>"""

HOME_HTML = NAV + """
<script src="https://cdn.tailwindcss.com"></script>
<div class="p-6 max-w-6xl mx-auto space-y-8">

  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">Dashboard</h1>
    <span class="text-sm text-gray-500">Uptime: {{ uptime }} &nbsp;|&nbsp; Updated: {{ now }}</span>
  </div>

  <!-- Stats -->
  <div class="grid grid-cols-3 gap-4">
    <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
      <div class="text-3xl font-bold text-red-600">{{ pending }}</div>
      <div class="text-sm text-gray-600 mt-1">Needs Action</div>
    </div>
    <div class="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
      <div class="text-3xl font-bold text-green-600">{{ done }}</div>
      <div class="text-sm text-gray-600 mt-1">Done</div>
    </div>
    <div class="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
      <div class="text-3xl font-bold text-blue-600">{{ approved }}</div>
      <div class="text-sm text-gray-600 mt-1">Approved</div>
    </div>
  </div>

  <!-- Watchers -->
  <div>
    <h2 class="text-lg font-semibold mb-3">Watcher Status</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
      {% for w in watchers %}
      <div class="bg-white border rounded-xl p-3 flex items-center gap-3 shadow-sm">
        <span class="w-2.5 h-2.5 rounded-full
          {% if w.color == 'green' %}bg-green-500
          {% elif w.color == 'yellow' %}bg-yellow-500
          {% else %}bg-red-500{% endif %}"></span>
        <div>
          <div class="font-medium text-sm">{{ w.name }}</div>
          <div class="text-xs text-gray-500">{{ w.status }}{% if w.pid %} · PID {{ w.pid }}{% endif %}</div>
        </div>
      </div>
      {% else %}
      <div class="text-gray-400 text-sm col-span-3">No watcher data available.</div>
      {% endfor %}
    </div>
  </div>

  <!-- Activity Log -->
  <div>
    <h2 class="text-lg font-semibold mb-3">Recent Activity</h2>
    <pre class="bg-gray-900 text-green-300 p-4 rounded-xl text-xs font-mono overflow-auto h-56">{{ log_lines }}</pre>
  </div>

</div>
<script>setTimeout(() => location.reload(), 30000)</script>
"""

INBOX_HTML = NAV + """
<script src="https://cdn.tailwindcss.com"></script>

<!-- Reply Modal -->
<div id="modal" class="hidden fixed inset-0 bg-black/60 flex items-center justify-center z-50">
  <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg mx-4">
    <h3 class="font-bold text-lg mb-3">✉️ Reply</h3>
    <input type="hidden" id="m-gmail-id">
    <input type="hidden" id="m-filename">
    <textarea id="m-body" rows="8" placeholder="Type your reply..."
      class="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
    <div class="flex gap-3 mt-4">
      <button onclick="submitReply()"
        class="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700">Send Reply</button>
      <button onclick="closeModal()"
        class="bg-gray-100 px-5 py-2 rounded-lg text-sm hover:bg-gray-200">Cancel</button>
    </div>
    <div id="m-status" class="text-sm mt-2"></div>
  </div>
</div>

<div class="p-6 max-w-4xl mx-auto space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">Inbox</h1>
    <span class="bg-red-100 text-red-700 text-sm font-medium px-3 py-1 rounded-full">{{ total }} pending</span>
  </div>

  {% if total == 0 %}
  <div class="text-center py-20 text-gray-400">
    <div class="text-5xl mb-4">✅</div>
    <div class="text-lg">All clear — no pending items</div>
  </div>
  {% endif %}

  {% for group in groups %}
  <div>
    <h2 class="text-base font-semibold text-gray-700 mb-2">{{ group.emoji }} {{ group.label }} ({{ group.items|length }})</h2>
    <div class="space-y-3">
    {% for item in group.items %}
    <div id="card-{{ loop.index }}-{{ group.label }}" class="bg-white border rounded-xl p-4 shadow-sm">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-xs font-medium px-2 py-0.5 rounded-full
          {% if item.urgency == 'High' or item.urgency == 'Critical' %}bg-red-100 text-red-700
          {% else %}bg-green-100 text-green-700{% endif %}">
          {{ item.urgency }}
        </span>
        <span class="text-sm font-medium text-gray-800">{{ item.from_ }}</span>
        <span class="ml-auto text-xs text-gray-400">{{ item.detected }}</span>
      </div>
      <div class="font-semibold text-sm text-gray-900 mb-1">{{ item.subject }}</div>
      <div class="text-xs text-gray-500 mb-3 line-clamp-2">{{ item.preview }}</div>
      <div class="flex flex-wrap gap-2">
        {% if item.gmail_id %}
        <button onclick="openModal('{{ item.filename }}','{{ item.gmail_id }}')"
          class="bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-blue-700">✉️ Reply</button>
        {% endif %}
        <button onclick="doAction('{{ item.filename }}','approve',this)"
          class="bg-green-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-green-700">✅ Approve</button>
        <button onclick="doAction('{{ item.filename }}','done',this)"
          class="bg-gray-200 text-gray-700 text-xs px-3 py-1.5 rounded-lg hover:bg-gray-300">Done</button>
        <button onclick="doAction('{{ item.filename }}','reject',this)"
          class="bg-red-100 text-red-700 text-xs px-3 py-1.5 rounded-lg hover:bg-red-200">❌ Reject</button>
      </div>
    </div>
    {% endfor %}
    </div>
  </div>
  {% endfor %}
</div>

<script>
function openModal(filename, gmailId) {
  document.getElementById('m-filename').value = filename;
  document.getElementById('m-gmail-id').value = gmailId;
  document.getElementById('m-body').value = '';
  document.getElementById('m-status').textContent = '';
  document.getElementById('modal').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}
async function submitReply() {
  const gmailId  = document.getElementById('m-gmail-id').value;
  const filename = document.getElementById('m-filename').value;
  const message  = document.getElementById('m-body').value.trim();
  if (!message) return;
  document.getElementById('m-status').textContent = 'Sending...';
  const fd = new FormData();
  fd.append('gmail_id', gmailId);
  fd.append('filename', filename);
  fd.append('message',  message);
  const r = await fetch('/api/reply', {method:'POST', body: fd});
  if (r.ok) {
    closeModal();
    location.reload();
  } else {
    const e = await r.json();
    document.getElementById('m-status').textContent = 'Error: ' + (e.detail || 'Unknown error');
  }
}
async function doAction(filename, action, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  const fd = new FormData();
  fd.append('filename', filename);
  fd.append('action',   action);
  const r = await fetch('/api/action', {method:'POST', body: fd});
  if (r.ok) {
    btn.closest('[id^=card-]').remove();
  } else {
    btn.textContent = 'Error';
  }
}
</script>
"""

COMPOSE_HTML = NAV + """
<script src="https://cdn.tailwindcss.com"></script>
<div class="p-6 max-w-2xl mx-auto">
  <h1 class="text-2xl font-bold mb-6">✍️ Compose Email</h1>
  <div class="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-6 text-sm text-blue-800">
    Email will be queued for approval — it won't send until you approve it in Inbox.
  </div>
  <form id="compose-form" class="space-y-4">
    <div>
      <label class="block text-sm font-medium mb-1">To</label>
      <input name="to" type="email" required placeholder="recipient@example.com"
        class="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">Subject</label>
      <input name="subject" type="text" required placeholder="Subject"
        class="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">Message</label>
      <textarea name="body" rows="12" required placeholder="Write your email..."
        class="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
    </div>
    <button type="submit"
      class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-medium">
      📤 Send for Approval
    </button>
  </form>
  <div id="success" class="hidden mt-4 bg-green-50 border border-green-200 rounded-xl p-4 text-green-800 text-sm">
    ✅ Email queued! Check <a href="/inbox" class="underline">Inbox</a> to approve and send.
  </div>
</div>
<script>
document.getElementById('compose-form').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const r  = await fetch('/api/send-email', {method:'POST', body: fd});
  if (r.ok) {
    e.target.reset();
    document.getElementById('success').classList.remove('hidden');
  }
});
</script>
"""

LOGS_HTML = NAV + """
<script src="https://cdn.tailwindcss.com"></script>
<div class="p-6 max-w-6xl mx-auto">
  <div class="flex items-center justify-between mb-4">
    <h1 class="text-2xl font-bold">📋 Orchestrator Logs</h1>
    <span class="text-xs text-gray-400">Auto-refreshes every 10s</span>
  </div>
  <pre id="log-box"
    class="bg-gray-900 text-green-300 p-4 rounded-xl text-xs font-mono overflow-auto h-[75vh] whitespace-pre-wrap">{{ log_lines }}</pre>
</div>
<script>
const box = document.getElementById('log-box');
box.scrollTop = box.scrollHeight;
setInterval(async () => {
  const r = await fetch('/api/logs');
  const d = await r.json();
  box.textContent = d.lines;
  box.scrollTop = box.scrollHeight;
}, 10000);
</script>
"""

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    print(f"Dashboard: http://{args.host}:{args.port}  |  Login: admin / {DASHBOARD_PASSWORD}")
    uvicorn.run("web_ui:app", host=args.host, port=args.port, app_dir=str(Path(__file__).parent))
