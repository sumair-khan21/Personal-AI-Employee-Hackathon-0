"""
web_ui.py — Professional AI Employee Dashboard (Redesigned)
Sidebar navigation with dedicated tabs per service.

Run: .venv/bin/python3 scripts/web_ui.py
URL: http://<VM-IP>:8080  |  Login: admin / DASHBOARD_PASSWORD
"""

import os, re, json, base64, secrets, shutil
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText

import uvicorn, jinja2
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build

# ── Paths ──────────────────────────────────────────────────────────────────────
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

# ── Auth ───────────────────────────────────────────────────────────────────────
security = HTTPBasic()

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, "admin") and \
         secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="AI Employee"'})
    return credentials.username

# ── Vault Helpers ──────────────────────────────────────────────────────────────
def parse_fm(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m: return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1); fm[k.strip()] = v.strip()
    return fm

def classify(name, fm):
    n = name.upper()
    if n.startswith("APPROVAL_REQUIRED_"): return "approval"
    t = fm.get("type","").lower()
    if t=="email"      or "EMAIL"    in n: return "email"
    if "linkedin" in t or "LINKEDIN" in n: return "linkedin"
    if "whatsapp" in t or "WHATSAPP" in n: return "whatsapp"
    if "odoo"     in t or "ODOO"     in n: return "odoo"
    if "facebook" in t or "FACEBOOK" in n: return "facebook"
    if "instagram"in t or "INSTAGRAM"in n: return "instagram"
    return "other"

def parse_file(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    fm   = parse_fm(text)
    kind = classify(path.name, fm)
    pm   = re.search(r"^> (.+)", text, re.MULTILINE)
    preview = pm.group(1)[:250] if pm else text.replace("---","")[:150]
    detected = fm.get("detected","")
    if not detected:
        detected = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "filename": path.name,
        "type":     kind,
        "from_":    fm.get("from", fm.get("source","System")),
        "subject":  fm.get("subject", path.stem.replace("_"," ")[:60]),
        "urgency":  fm.get("urgency","Normal"),
        "gmail_id": fm.get("gmail_id",""),
        "detected": detected[:16].replace("T"," "),
        "preview":  preview.strip(),
        "contact":  fm.get("contact",""),
    }

def get_pending(kind=None):
    if not NEEDS_ACTION_DIR.exists(): return []
    files = sorted(NEEDS_ACTION_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = [parse_file(f) for f in files]
    if kind: result = [r for r in result if r["type"]==kind]
    return result

def get_status():
    if not STATUS_FILE.exists(): return {}, ""
    data = json.loads(STATUS_FILE.read_text())
    secs = int(data.get("uptime_seconds",0))
    h,m  = divmod(secs//60, 60); d,h = divmod(h,24)
    uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    return data.get("watchers",{}), uptime

def safe_move(filename, dest):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    src = NEEDS_ACTION_DIR / filename
    if not src.exists():
        # Already moved (race condition) — treat as success
        return
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest / filename))

# ── Gmail ──────────────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.modify"]

def get_gmail():
    if not TOKEN_PATH.exists(): raise RuntimeError("token.json not found")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest()); TOKEN_PATH.write_text(creds.to_json())
    return build("gmail","v1",credentials=creds)

# ── App ────────────────────────────────────────────────────────────────────────
app  = FastAPI(title="AI Employee", docs_url=None, redoc_url=None)
_j   = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=False)

def page(title, content, active):
    return HTMLResponse(_j.from_string(SHELL).render(
        title=title, content=content, active=active,
        now=datetime.now().strftime("%H:%M")
    ))

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(user=Depends(require_auth)):
    watchers, uptime = get_status()
    pending = len(list(NEEDS_ACTION_DIR.glob("*.md"))) if NEEDS_ACTION_DIR.exists() else 0
    done    = len(list(DONE_DIR.glob("*.md")))          if DONE_DIR.exists()          else 0
    approved= len(list(APPROVED_DIR.glob("*.md")))      if APPROVED_DIR.exists()      else 0
    log     = "\n".join((ORCH_LOG.read_text(errors="replace").splitlines()[-15:] if ORCH_LOG.exists() else []))

    services = [
        ("filesystem","Filesystem Watcher","🗂️"),("send_email","Email Sender","📤"),
        ("gmail","Gmail","📧"),("linkedin_watch","LinkedIn","💼"),
        ("linkedin_post","LinkedIn Post","📣"),("odoo","Odoo","📊"),
    ]
    watcher_cards = ""
    for key, label, emoji in services:
        w = watchers.get(key,{})
        s = w.get("status","unknown")
        color = "emerald" if s in ("running","idle") else ("amber" if s=="error" else "red")
        dot   = "bg-emerald-400" if color=="emerald" else ("bg-amber-400" if color=="amber" else "bg-red-400")
        badge = "bg-emerald-50 text-emerald-700 border-emerald-200" if color=="emerald" else \
                ("bg-amber-50 text-amber-700 border-amber-200" if color=="amber" else "bg-red-50 text-red-700 border-red-200")
        status_label = "Running" if s in ("running","idle") else s.capitalize()
        pid   = w.get("pid","")
        interval = w.get("interval_seconds","")
        interval_str = f"Every {interval//60}m" if interval else "Continuous"
        watcher_cards += f"""
        <div class="bg-white rounded-2xl border border-gray-100 p-4 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
          <div class="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-xl">{emoji}</div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-gray-800 text-sm">{label}</div>
            <div class="text-xs text-gray-400 mt-0.5">{interval_str}{f' · PID {pid}' if pid else ''}</div>
          </div>
          <span class="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border {badge}">
            <span class="w-1.5 h-1.5 rounded-full {dot}"></span>{status_label}
          </span>
        </div>"""

    content = f"""
    <div class="space-y-6">
      <!-- Stats -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-gradient-to-br from-red-500 to-rose-600 rounded-2xl p-5 text-white">
          <div class="text-3xl font-bold">{pending}</div>
          <div class="text-red-100 text-sm mt-1">Needs Action</div>
          <div class="text-red-200 text-xs mt-1">⚡ Requires attention</div>
        </div>
        <div class="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl p-5 text-white">
          <div class="text-3xl font-bold">{done}</div>
          <div class="text-emerald-100 text-sm mt-1">Completed</div>
          <div class="text-emerald-200 text-xs mt-1">✅ All done</div>
        </div>
        <div class="bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl p-5 text-white">
          <div class="text-3xl font-bold">{approved}</div>
          <div class="text-blue-100 text-sm mt-1">Approved</div>
          <div class="text-blue-200 text-xs mt-1">🚀 Ready to execute</div>
        </div>
      </div>

      <!-- Uptime -->
      <div class="bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-100 rounded-2xl p-4 flex items-center gap-3">
        <div class="w-10 h-10 bg-violet-100 rounded-xl flex items-center justify-center text-xl">⏱️</div>
        <div>
          <div class="text-sm font-semibold text-violet-800">System Uptime</div>
          <div class="text-violet-600 font-bold text-lg">{uptime}</div>
        </div>
        <div class="ml-auto text-xs text-violet-400">Auto-refreshes every 30s</div>
      </div>

      <!-- Watcher Grid -->
      <div>
        <h2 class="text-base font-semibold text-gray-700 mb-3">🔧 Active Services</h2>
        <div class="grid grid-cols-2 gap-3">{watcher_cards}</div>
      </div>

      <!-- Log -->
      <div>
        <h2 class="text-base font-semibold text-gray-700 mb-3">📋 Recent Activity</h2>
        <pre class="bg-gray-950 text-emerald-400 p-4 rounded-2xl text-xs font-mono leading-relaxed overflow-auto max-h-52">{log}</pre>
      </div>
    </div>
    <script>setTimeout(()=>location.reload(),30000)</script>"""
    return page("Dashboard", content, "dashboard")


@app.get("/gmail", response_class=HTMLResponse)
async def gmail_page(user=Depends(require_auth)):
    emails = get_pending("email")
    approvals = [f for f in get_pending("approval") if "Email" in f["filename"]]
    cards = _render_email_cards(emails)
    approval_cards = _render_approval_cards(approvals)
    content = f"""
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-800">📧 Gmail</h1>
          <p class="text-sm text-gray-500 mt-0.5">Monitor, read, reply and compose emails</p>
        </div>
        <a href="/compose" class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-xl flex items-center gap-2 transition-colors">
          ✍️ Compose
        </a>
      </div>

      <!-- Compose Quick Form -->
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between cursor-pointer" onclick="toggleSection('compose-quick')">
          <span class="font-semibold text-gray-700 text-sm">✍️ Quick Compose</span>
          <span class="text-gray-400 text-sm" id="compose-quick-icon">▼</span>
        </div>
        <div id="compose-quick" class="hidden p-5 space-y-3">
          <input id="qc-to" type="email" placeholder="To: recipient@example.com"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <input id="qc-subject" type="text" placeholder="Subject"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <textarea id="qc-body" rows="5" placeholder="Write your message..."
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
          <div class="flex gap-2">
            <button onclick="quickCompose()" class="bg-blue-600 hover:bg-blue-700 text-white text-sm px-5 py-2 rounded-xl font-medium transition-colors">📤 Send for Approval</button>
          </div>
          <div id="qc-status" class="text-sm"></div>
        </div>
      </div>

      <!-- Pending Emails -->
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">📬 Pending Emails</span>
          <span class="bg-red-100 text-red-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(emails)}</span>
        </div>
        <div class="divide-y divide-gray-50">{cards if cards else _empty("No pending emails")}</div>
      </div>

      <!-- Pending Approvals -->
      {f'<div class="bg-white rounded-2xl border border-amber-100 shadow-sm overflow-hidden"><div class="px-5 py-4 border-b border-amber-50 flex items-center gap-2"><span class="font-semibold text-gray-700 text-sm">⚠️ Pending Approvals</span><span class="bg-amber-100 text-amber-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(approvals)}</span></div><div class="divide-y divide-gray-50">{approval_cards}</div></div>' if approvals else ''}
    </div>
    {_reply_modal()}
    {_view_modal()}
    {_reply_script()}
    <script>
    function toggleSection(id){{
      const el=document.getElementById(id), icon=document.getElementById(id+'-icon');
      el.classList.toggle('hidden'); icon.textContent=el.classList.contains('hidden')?'▼':'▲';
    }}
    async function quickCompose(){{
      const to=document.getElementById('qc-to').value;
      const subject=document.getElementById('qc-subject').value;
      const body=document.getElementById('qc-body').value;
      if(!to||!subject||!body){{document.getElementById('qc-status').textContent='Please fill all fields.';return;}}
      const fd=new FormData(); fd.append('to',to); fd.append('subject',subject); fd.append('body',body);
      const r=await fetch('/api/send-email',{{method:'POST',body:fd}});
      if(r.ok){{document.getElementById('qc-status').innerHTML='<span class="text-emerald-600">✅ Queued for approval — check inbox.</span>';}}
    }}
    </script>"""
    return page("Gmail", content, "gmail")


@app.get("/linkedin", response_class=HTMLResponse)
async def linkedin_page(user=Depends(require_auth)):
    notifications = get_pending("linkedin")
    approvals = [f for f in get_pending("approval") if "LinkedIn" in f["filename"]]
    content = f"""
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-800">💼 LinkedIn</h1>
          <p class="text-sm text-gray-500 mt-0.5">Notifications, drafts and post management</p>
        </div>
      </div>

      <!-- Draft Post -->
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between cursor-pointer" onclick="toggleSection('li-draft')">
          <span class="font-semibold text-gray-700 text-sm">✍️ Draft a Post</span>
          <span class="text-gray-400 text-sm" id="li-draft-icon">▼</span>
        </div>
        <div id="li-draft" class="hidden p-5 space-y-3">
          <textarea id="li-body" rows="6" placeholder="What do you want to share on LinkedIn?"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
          <button onclick="draftLinkedIn()" class="bg-blue-700 hover:bg-blue-800 text-white text-sm px-5 py-2 rounded-xl font-medium transition-colors">📝 Save Draft for Approval</button>
          <div id="li-status" class="text-sm"></div>
        </div>
      </div>

      <!-- Notifications -->
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">🔔 Notifications</span>
          <span class="bg-red-100 text-red-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(notifications)}</span>
        </div>
        <div class="divide-y divide-gray-50">{_render_generic_cards(notifications) if notifications else _empty("No new notifications")}</div>
      </div>

      <!-- Pending Post Approvals -->
      {f'<div class="bg-white rounded-2xl border border-amber-100 shadow-sm overflow-hidden"><div class="px-5 py-4 border-b border-amber-50 flex items-center gap-2"><span class="font-semibold text-gray-700 text-sm">⚠️ Posts Awaiting Approval</span><span class="bg-amber-100 text-amber-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(approvals)}</span></div><div class="divide-y divide-gray-50">{_render_approval_cards(approvals)}</div></div>' if approvals else ''}
    </div>
    <script>
    function toggleSection(id){{const el=document.getElementById(id),icon=document.getElementById(id+'-icon');el.classList.toggle('hidden');icon.textContent=el.classList.contains('hidden')?'▼':'▲';}}
    async function draftLinkedIn(){{
      const body=document.getElementById('li-body').value.trim();
      if(!body)return;
      const fd=new FormData(); fd.append('content',body); fd.append('platform','linkedin');
      const r=await fetch('/api/draft-post',{{method:'POST',body:fd}});
      if(r.ok){{document.getElementById('li-status').innerHTML='<span class="text-emerald-600">✅ Draft saved — check inbox to approve.</span>';document.getElementById('li-body').value='';}}
    }}
    </script>"""
    content += _view_modal() + _reply_script()
    return page("LinkedIn", content, "linkedin")


@app.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(user=Depends(require_auth)):
    messages = get_pending("whatsapp")
    content = f"""
    <div class="space-y-6">
      <div>
        <h1 class="text-xl font-bold text-gray-800">💬 WhatsApp</h1>
        <p class="text-sm text-gray-500 mt-0.5">Incoming messages and chat monitoring</p>
      </div>
      <div class="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800 flex gap-3">
        <span class="text-lg">⚠️</span>
        <span>WhatsApp replies require manual approval per Company Handbook. Review each message carefully before actioning.</span>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">💬 Pending Messages</span>
          <span class="bg-red-100 text-red-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(messages)}</span>
        </div>
        <div class="divide-y divide-gray-50">{_render_generic_cards(messages) if messages else _empty("No new WhatsApp messages")}</div>
      </div>
    </div>"""
    content += _view_modal() + _reply_script()
    return page("WhatsApp", content, "whatsapp")


@app.get("/facebook", response_class=HTMLResponse)
async def facebook_page(user=Depends(require_auth)):
    approvals = [f for f in get_pending("approval") if "Facebook" in f["filename"]]
    content = f"""
    <div class="space-y-6">
      <div>
        <h1 class="text-xl font-bold text-gray-800">📘 Facebook</h1>
        <p class="text-sm text-gray-500 mt-0.5">Post drafting and scheduling</p>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between cursor-pointer" onclick="toggleSection('fb-draft')">
          <span class="font-semibold text-gray-700 text-sm">✍️ Draft a Post</span>
          <span class="text-gray-400 text-sm" id="fb-draft-icon">▼</span>
        </div>
        <div id="fb-draft" class="hidden p-5 space-y-3">
          <textarea id="fb-body" rows="6" placeholder="What's on your mind?"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
          <button onclick="draftPost('fb','facebook')" class="bg-blue-700 hover:bg-blue-800 text-white text-sm px-5 py-2 rounded-xl font-medium transition-colors">📝 Save Draft for Approval</button>
          <div id="fb-status" class="text-sm"></div>
        </div>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">⚠️ Posts Awaiting Approval</span>
          <span class="bg-amber-100 text-amber-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(approvals)}</span>
        </div>
        <div class="divide-y divide-gray-50">{_render_approval_cards(approvals) if approvals else _empty("No pending posts")}</div>
      </div>
    </div>
    <script>
    function toggleSection(id){{const el=document.getElementById(id),icon=document.getElementById(id+'-icon');el.classList.toggle('hidden');icon.textContent=el.classList.contains('hidden')?'▼':'▲';}}
    async function draftPost(prefix,platform){{
      const body=document.getElementById(prefix+'-body').value.trim();
      if(!body)return;
      const fd=new FormData(); fd.append('content',body); fd.append('platform',platform);
      const r=await fetch('/api/draft-post',{{method:'POST',body:fd}});
      if(r.ok){{document.getElementById(prefix+'-status').innerHTML='<span class="text-emerald-600">✅ Draft saved — check inbox to approve.</span>';document.getElementById(prefix+'-body').value='';}}
    }}
    </script>"""
    content += _view_modal() + _reply_script()
    return page("Facebook", content, "facebook")


@app.get("/instagram", response_class=HTMLResponse)
async def instagram_page(user=Depends(require_auth)):
    approvals = [f for f in get_pending("approval") if "Instagram" in f["filename"]]
    content = f"""
    <div class="space-y-6">
      <div>
        <h1 class="text-xl font-bold text-gray-800">📸 Instagram</h1>
        <p class="text-sm text-gray-500 mt-0.5">Post drafting and image content management</p>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between cursor-pointer" onclick="toggleSection('ig-draft')">
          <span class="font-semibold text-gray-700 text-sm">✍️ Draft a Post</span>
          <span class="text-gray-400 text-sm" id="ig-draft-icon">▼</span>
        </div>
        <div id="ig-draft" class="hidden p-5 space-y-3">
          <textarea id="ig-body" rows="4" placeholder="Caption for your post..."
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500 resize-none"></textarea>
          <input id="ig-tags" type="text" placeholder="Hashtags: #ai #automation"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500">
          <button onclick="draftPost('ig','instagram')" class="bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white text-sm px-5 py-2 rounded-xl font-medium transition-colors">📝 Save Draft for Approval</button>
          <div id="ig-status" class="text-sm"></div>
        </div>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">⚠️ Posts Awaiting Approval</span>
          <span class="bg-amber-100 text-amber-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(approvals)}</span>
        </div>
        <div class="divide-y divide-gray-50">{_render_approval_cards(approvals) if approvals else _empty("No pending posts")}</div>
      </div>
    </div>
    <script>
    function toggleSection(id){{const el=document.getElementById(id),icon=document.getElementById(id+'-icon');el.classList.toggle('hidden');icon.textContent=el.classList.contains('hidden')?'▼':'▲';}}
    async function draftPost(prefix,platform){{
      const body=document.getElementById(prefix+'-body').value.trim();
      const tags=prefix==='ig'?(document.getElementById('ig-tags')||{{value:''}}).value:'';
      if(!body)return;
      const fd=new FormData(); fd.append('content',body+(tags?' '+tags:'')); fd.append('platform',platform);
      const r=await fetch('/api/draft-post',{{method:'POST',body:fd}});
      if(r.ok){{document.getElementById(prefix+'-status').innerHTML='<span class="text-emerald-600">✅ Draft saved — check inbox to approve.</span>';document.getElementById(prefix+'-body').value='';}}
    }}
    </script>"""
    content += _view_modal() + _reply_script()
    return page("Instagram", content, "instagram")


@app.get("/odoo", response_class=HTMLResponse)
async def odoo_page(user=Depends(require_auth)):
    alerts = get_pending("odoo")
    content = f"""
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-800">📊 Odoo Accounting</h1>
          <p class="text-sm text-gray-500 mt-0.5">Invoice alerts, overdue tracking and audit reports</p>
        </div>
        <a href="http://92.4.74.176:8069" target="_blank"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-xl flex items-center gap-2 transition-colors">
          🔗 Open Odoo
        </a>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
          <span class="font-semibold text-gray-700 text-sm">🚨 Accounting Alerts</span>
          <span class="bg-red-100 text-red-600 text-xs font-bold px-2 py-0.5 rounded-full">{len(alerts)}</span>
        </div>
        <div class="divide-y divide-gray-50">{_render_generic_cards(alerts) if alerts else _empty("✅ No overdue invoices — all clear!")}</div>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50">
          <span class="font-semibold text-gray-700 text-sm">📁 Audit Reports</span>
        </div>
        <div class="p-5">{"".join(f'<div class="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0"><span class="text-gray-400 text-xs font-mono">{f.name}</span><span class="ml-auto text-xs text-gray-400">{datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d")}</span></div>' for f in sorted((VAULT/"Accounting").glob("*.md"), reverse=True)[:10]) if (VAULT/"Accounting").exists() else _empty("No audit reports yet")}</div>
      </div>
    </div>"""
    content += _view_modal() + _reply_script()
    return page("Odoo", content, "odoo")


@app.get("/compose", response_class=HTMLResponse)
async def compose_page(user=Depends(require_auth)):
    content = """
    <div class="space-y-6 max-w-2xl">
      <div>
        <h1 class="text-xl font-bold text-gray-800">✍️ Compose Email</h1>
        <p class="text-sm text-gray-500 mt-0.5">New emails require approval before sending</p>
      </div>
      <div class="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700 flex gap-3">
        <span>🔒</span>
        <span>This email will be queued in <strong>Inbox → Approvals</strong>. It won't send until you approve it.</span>
      </div>
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">To</label>
          <input id="c-to" type="email" placeholder="recipient@example.com"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Subject</label>
          <input id="c-subject" type="text" placeholder="Email subject"
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Message</label>
          <textarea id="c-body" rows="12" placeholder="Write your message here..."
            class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
        </div>
        <button onclick="sendCompose()"
          class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-xl transition-colors">
          📤 Send for Approval
        </button>
        <div id="c-status" class="text-sm text-center"></div>
      </div>
    </div>
    <script>
    async function sendCompose(){
      const to=document.getElementById('c-to').value;
      const subject=document.getElementById('c-subject').value;
      const body=document.getElementById('c-body').value;
      if(!to||!subject||!body){document.getElementById('c-status').textContent='Please fill all fields.';return;}
      const fd=new FormData(); fd.append('to',to); fd.append('subject',subject); fd.append('body',body);
      const r=await fetch('/api/send-email',{method:'POST',body:fd});
      if(r.ok){
        document.getElementById('c-status').innerHTML='<span class="text-emerald-600">✅ Email queued for approval — check Gmail inbox.</span>';
        document.getElementById('c-to').value='';
        document.getElementById('c-subject').value='';
        document.getElementById('c-body').value='';
      }
    }
    </script>"""
    return page("Compose", content, "compose")


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(user=Depends(require_auth)):
    lines = "\n".join(ORCH_LOG.read_text(errors="replace").splitlines()[-150:]) if ORCH_LOG.exists() else ""
    content = f"""
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-800">📋 System Logs</h1>
          <p class="text-sm text-gray-500 mt-0.5">Live orchestrator activity — auto-refreshes every 10s</p>
        </div>
        <button onclick="clearScroll()" class="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-3 py-1.5 rounded-lg">⬇ Scroll to bottom</button>
      </div>
      <pre id="log-box" class="bg-gray-950 text-emerald-400 p-5 rounded-2xl text-xs font-mono leading-relaxed overflow-auto h-[78vh] whitespace-pre-wrap">{lines}</pre>
    </div>
    <script>
    const box=document.getElementById('log-box');
    box.scrollTop=box.scrollHeight;
    function clearScroll(){{box.scrollTop=box.scrollHeight;}}
    setInterval(async()=>{{
      const r=await fetch('/api/logs');
      const d=await r.json();
      box.textContent=d.lines;
      box.scrollTop=box.scrollHeight;
    }},10000);
    </script>"""
    return page("Logs", content, "logs")


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def api_logs(user=Depends(require_auth)):
    lines = "\n".join(ORCH_LOG.read_text(errors="replace").splitlines()[-150:]) if ORCH_LOG.exists() else ""
    return JSONResponse({"lines": lines})

@app.get("/api/status")
async def api_status(user=Depends(require_auth)):
    if not STATUS_FILE.exists(): return JSONResponse({"error":"not found"},status_code=404)
    return JSONResponse(json.loads(STATUS_FILE.read_text()))

@app.post("/api/action")
async def api_action(filename: str=Form(...), action: str=Form(...), user=Depends(require_auth)):
    dest = {"done":DONE_DIR,"approve":APPROVED_DIR,"reject":REJECTED_DIR}.get(action)
    if not dest: raise HTTPException(400,"Invalid action")
    safe_move(filename, dest)
    return JSONResponse({"ok":True})

@app.post("/api/reply")
async def api_reply(gmail_id: str=Form(...), message: str=Form(...), filename: str=Form(...), user=Depends(require_auth)):
    try:
        svc  = get_gmail()
        orig = svc.users().messages().get(userId="me",id=gmail_id,format="metadata",
               metadataHeaders=["From","Subject","Message-ID"]).execute()
        h    = {x["name"]:x["value"] for x in orig["payload"]["headers"]}
        msg  = MIMEText(message,"plain","utf-8")
        msg["to"]          = h.get("From","")
        msg["subject"]     = "Re: "+h.get("Subject","") if not h.get("Subject","").startswith("Re:") else h.get("Subject","")
        msg["In-Reply-To"] = h.get("Message-ID","")
        msg["References"]  = h.get("Message-ID","")
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me",body={"raw":raw,"threadId":orig["threadId"]}).execute()
        safe_move(filename, DONE_DIR)
        return JSONResponse({"ok":True})
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post("/api/send-email")
async def api_send_email(to: str=Form(...), subject: str=Form(...), body: str=Form(...), user=Depends(require_auth)):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"APPROVAL_REQUIRED_Email_{ts}.md"
    (NEEDS_ACTION_DIR/name).write_text(
        f"---\nto: {to}\nsubject: {subject}\ntype: approval_email\nstatus: pending\ncreated: {datetime.now().isoformat()}\n---\n\n"
        f"# Approval Required: Email to {to}\n\n**To:** {to}\n**Subject:** {subject}\n\n---\n\n{body}\n\n---\n*Move to Approved/ to send.*\n",
        encoding="utf-8")
    return JSONResponse({"ok":True,"filename":name})

@app.post("/api/draft-post")
async def api_draft_post(content: str=Form(...), platform: str=Form(...), user=Depends(require_auth)):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    plat = platform.capitalize()
    name = f"APPROVAL_REQUIRED_{plat}_{ts}.md"
    (NEEDS_ACTION_DIR/name).write_text(
        f"---\ntype: approval_required\ncategory: {platform}_post\nstatus: awaiting_approval\ncreated: {datetime.now().isoformat()}\n---\n\n"
        f"# APPROVAL REQUIRED: {plat} Post\n\n## Draft Content\n\n---\n\n{content}\n\n---\n\n## To Approve\nMove this file to `Approved/`\n\n## To Cancel\nDelete this file.\n",
        encoding="utf-8")
    return JSONResponse({"ok":True,"filename":name})

# ── Card Renderers ─────────────────────────────────────────────────────────────

def _empty(msg):
    return f'<div class="px-5 py-10 text-center text-gray-400 text-sm">{msg}</div>'

def _urgency_badge(urgency):
    if urgency in ("High","Critical"):
        return f'<span class="bg-red-100 text-red-600 text-xs font-medium px-2 py-0.5 rounded-full">{urgency}</span>'
    return f'<span class="bg-emerald-100 text-emerald-600 text-xs font-medium px-2 py-0.5 rounded-full">{urgency}</span>'

def _action_btn(label, onclick, style="gray"):
    styles = {
        "blue":  "bg-blue-600 hover:bg-blue-700 text-white",
        "green": "bg-emerald-600 hover:bg-emerald-700 text-white",
        "red":   "bg-red-100 hover:bg-red-200 text-red-700",
        "gray":  "bg-gray-100 hover:bg-gray-200 text-gray-700",
    }
    return f'<button onclick="{onclick}" class="text-xs font-medium px-3 py-1.5 rounded-lg {styles.get(style,"bg-gray-100 text-gray-700")} transition-colors">{label}</button>'

def _render_email_cards(emails):
    if not emails: return ""
    html = ""
    for item in emails:
        fid = item["filename"].replace(".","_")
        # Read full body from file for the view modal
        try:
            full_text = (NEEDS_ACTION_DIR / item["filename"]).read_text(encoding="utf-8", errors="replace")
            # Extract body section
            body_match = re.search(r"## Body.*?\n\n(.*?)(?:\n## |\Z)", full_text, re.DOTALL)
            full_body = body_match.group(1).strip() if body_match else item["preview"]
            # Clean up invisible chars
            full_body = re.sub(r'[\u034f\u00ad\u200b-\u200d\ufeff]', '', full_body)
            full_body = full_body[:2000]
        except Exception:
            full_body = item["preview"]

        # Escape for JS string (avoid breaking onclick)
        escaped_body = full_body.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
        escaped_from = item['from_'].replace('"', '&quot;')
        escaped_subj = item['subject'].replace('"', '&quot;')

        html += f"""
        <div id="card-{fid}" class="p-4 hover:bg-gray-50 transition-colors">
          <div class="flex items-start gap-3">
            <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-sm flex-shrink-0">📧</div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                {_urgency_badge(item['urgency'])}
                <span class="text-sm font-semibold text-gray-800 truncate">{item['from_']}</span>
                <span class="ml-auto text-xs text-gray-400 flex-shrink-0">{item['detected']}</span>
              </div>
              <div class="text-sm text-gray-700 font-medium mt-0.5">{item['subject']}</div>
              <div class="text-xs text-gray-400 mt-1 line-clamp-2">{item['preview']}</div>
              <div class="flex gap-2 mt-3 flex-wrap">
                {_action_btn("👁 View", f"openViewModal(`{escaped_from}`,`{escaped_subj}`,`{item['detected']}`,`{escaped_body}`)", "gray")}
                {_action_btn("✉️ Reply", f"openModal('{item['filename']}','{item['gmail_id']}')", "blue") if item['gmail_id'] else ""}
                {_action_btn("✅ Done", f"doAction('{item['filename']}','done',this)", "green")}
                {_action_btn("❌ Reject", f"doAction('{item['filename']}','reject',this)", "red")}
              </div>
            </div>
          </div>
        </div>"""
    return html

def _render_approval_cards(approvals):
    if not approvals: return ""
    html = ""
    for item in approvals:
        fid = item["filename"].replace(".","_")
        html += f"""
        <div id="card-{fid}" class="p-4 hover:bg-amber-50 transition-colors">
          <div class="flex items-start gap-3">
            <div class="w-8 h-8 bg-amber-100 rounded-full flex items-center justify-center text-sm flex-shrink-0">⚠️</div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-gray-800 truncate">{item['subject']}</span>
                <span class="ml-auto text-xs text-gray-400 flex-shrink-0">{item['detected']}</span>
              </div>
              <div class="text-xs text-gray-400 mt-1 line-clamp-2">{item['preview']}</div>
              <div class="flex gap-2 mt-3">
                {_action_btn("✅ Approve", f"doAction('{item['filename']}','approve',this)", "green")}
                {_action_btn("❌ Reject", f"doAction('{item['filename']}','reject',this)", "red")}
              </div>
            </div>
          </div>
        </div>"""
    return html

def _render_generic_cards(items):
    if not items: return ""
    html = ""
    for item in items:
        fid = item["filename"].replace(".","_")
        # Read full content for view modal
        try:
            full_text = (NEEDS_ACTION_DIR / item["filename"]).read_text(encoding="utf-8", errors="replace")
            # Remove frontmatter
            full_text = re.sub(r"^---\n.*?\n---\n", "", full_text, flags=re.DOTALL).strip()
            full_text = re.sub(r'[\u034f\u00ad\u200b-\u200d\ufeff]', '', full_text)
            full_text = full_text[:3000]
        except Exception:
            full_text = item["preview"]

        escaped_body = full_text.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
        escaped_from = (item['from_'] or item['contact'] or 'System').replace('"', '&quot;')
        escaped_subj = item['preview'][:80].replace('"', '&quot;')

        html += f"""
        <div id="card-{fid}" class="p-4 hover:bg-gray-50 transition-colors">
          <div class="flex items-start gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                {_urgency_badge(item['urgency'])}
                <span class="text-sm font-medium text-gray-700 truncate">{item['from_'] or item['contact'] or 'System'}</span>
                <span class="ml-auto text-xs text-gray-400 flex-shrink-0">{item['detected']}</span>
              </div>
              <div class="text-xs text-gray-400 mt-1 line-clamp-2">{item['preview']}</div>
              <div class="flex gap-2 mt-3">
                {_action_btn("👁 View", f"openViewModal(`{escaped_from}`,`{escaped_subj}`,`{item['detected']}`,`{escaped_body}`)", "gray")}
                {_action_btn("✅ Done", f"doAction('{item['filename']}','done',this)", "green")}
                {_action_btn("❌ Reject", f"doAction('{item['filename']}','reject',this)", "red")}
              </div>
            </div>
          </div>
        </div>"""
    return html

def _view_modal():
    return """
    <div id="view-modal" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div class="px-6 py-4 border-b border-gray-100 flex items-start justify-between flex-shrink-0">
          <div>
            <div id="v-from" class="text-sm font-semibold text-gray-800"></div>
            <div id="v-subject" class="text-base font-bold text-gray-900 mt-0.5"></div>
            <div id="v-date" class="text-xs text-gray-400 mt-0.5"></div>
          </div>
          <button onclick="closeViewModal()" class="text-gray-400 hover:text-gray-600 text-2xl leading-none ml-4 flex-shrink-0">&times;</button>
        </div>
        <div class="p-6 overflow-y-auto flex-1">
          <pre id="v-body" class="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed"></pre>
        </div>
      </div>
    </div>"""

def _reply_modal():
    return """
    <div id="reply-modal" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 class="font-bold text-gray-800">✉️ Reply to Email</h3>
          <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <div class="p-6 space-y-4">
          <input type="hidden" id="m-gmail-id">
          <input type="hidden" id="m-filename">
          <textarea id="m-body" rows="8" placeholder="Type your reply..."
            class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
          <div class="flex gap-3">
            <button onclick="submitReply()" class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-xl transition-colors text-sm">📤 Send Reply</button>
            <button onclick="closeModal()" class="px-5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-sm transition-colors">Cancel</button>
          </div>
          <div id="m-status" class="text-sm text-center"></div>
        </div>
      </div>
    </div>"""

def _reply_script():
    return """<script>
    function openViewModal(from,subject,date,body){
      document.getElementById('v-from').textContent='From: '+from;
      document.getElementById('v-subject').textContent=subject;
      document.getElementById('v-date').textContent=date;
      document.getElementById('v-body').textContent=body;
      document.getElementById('view-modal').classList.remove('hidden');
    }
    function closeViewModal(){document.getElementById('view-modal').classList.add('hidden');}
    function openModal(filename,gmailId){
      document.getElementById('m-filename').value=filename;
      document.getElementById('m-gmail-id').value=gmailId;
      document.getElementById('m-body').value='';
      document.getElementById('m-status').textContent='';
      document.getElementById('reply-modal').classList.remove('hidden');
    }
    function closeModal(){document.getElementById('reply-modal').classList.add('hidden');}
    async function submitReply(){
      const gmailId=document.getElementById('m-gmail-id').value;
      const filename=document.getElementById('m-filename').value;
      const message=document.getElementById('m-body').value.trim();
      if(!message)return;
      document.getElementById('m-status').textContent='Sending...';
      const fd=new FormData(); fd.append('gmail_id',gmailId); fd.append('filename',filename); fd.append('message',message);
      const r=await fetch('/api/reply',{method:'POST',body:fd});
      if(r.ok){closeModal();location.reload();}
      else{const e=await r.json();document.getElementById('m-status').textContent='Error: '+(e.detail||'Unknown');}
    }
    async function doAction(filename,action,btn){
      btn.disabled=true; btn.textContent='...';
      const fd=new FormData(); fd.append('filename',filename); fd.append('action',action);
      const r=await fetch('/api/action',{method:'POST',body:fd});
      if(r.ok){const id='card-'+filename.replace(/\./g,'_');const c=document.getElementById(id);if(c)c.remove();else location.reload();}
      else{btn.disabled=false;btn.textContent='Error';}
    }
    </script>"""

# ── Shell Layout ───────────────────────────────────────────────────────────────

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} — AI Employee</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
  .nav-link{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:10px;font-size:13px;font-weight:500;color:#6b7280;transition:all .15s;cursor:pointer;text-decoration:none;}
  .nav-link:hover{background:#f3f4f6;color:#111827;}
  .nav-link.active{background:#eff6ff;color:#2563eb;}
  .nav-link .icon{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;background:#f9fafb;}
  .nav-link.active .icon{background:#dbeafe;}
  ::-webkit-scrollbar{width:4px;height:4px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:4px}
</style>
</head>
<body class="bg-gray-50 min-h-screen">
<div class="flex min-h-screen">

  <!-- Sidebar -->
  <aside class="w-56 bg-white border-r border-gray-100 flex flex-col fixed top-0 left-0 h-full z-40 shadow-sm">
    <!-- Brand -->
    <div class="px-4 py-5 border-b border-gray-50">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white text-sm font-bold">AI</div>
        <div>
          <div class="font-bold text-gray-800 text-sm leading-tight">AI Employee</div>
          <div class="text-xs text-gray-400">Platinum Tier</div>
        </div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
      <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mb-2">Overview</div>
      <a href="/" class="nav-link {{ 'active' if active=='dashboard' else '' }}">
        <span class="icon">🏠</span> Dashboard
      </a>

      <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mt-4 mb-2">Services</div>
      <a href="/gmail" class="nav-link {{ 'active' if active=='gmail' else '' }}">
        <span class="icon">📧</span> Gmail
      </a>
      <a href="/linkedin" class="nav-link {{ 'active' if active=='linkedin' else '' }}">
        <span class="icon">💼</span> LinkedIn
      </a>
      <a href="/facebook" class="nav-link {{ 'active' if active=='facebook' else '' }}">
        <span class="icon">📘</span> Facebook
      </a>
      <a href="/instagram" class="nav-link {{ 'active' if active=='instagram' else '' }}">
        <span class="icon">📸</span> Instagram
      </a>
      <a href="/whatsapp" class="nav-link {{ 'active' if active=='whatsapp' else '' }}">
        <span class="icon">💬</span> WhatsApp
      </a>
      <a href="/odoo" class="nav-link {{ 'active' if active=='odoo' else '' }}">
        <span class="icon">📊</span> Odoo
      </a>

      <div class="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mt-4 mb-2">Tools</div>
      <a href="/compose" class="nav-link {{ 'active' if active=='compose' else '' }}">
        <span class="icon">✍️</span> Compose
      </a>
      <a href="/logs" class="nav-link {{ 'active' if active=='logs' else '' }}">
        <span class="icon">📋</span> Logs
      </a>
    </nav>

    <!-- Footer -->
    <div class="px-4 py-3 border-t border-gray-50">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
        <span class="text-xs text-gray-500">Live · {{ now }}</span>
      </div>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="ml-56 flex-1 p-6 overflow-auto">
    {{ content }}
  </main>

</div>
</body>
</html>"""

# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    print(f"Dashboard: http://{args.host}:{args.port}  |  Login: admin / {DASHBOARD_PASSWORD}")
    uvicorn.run("web_ui:app", host=args.host, port=args.port, app_dir=str(Path(__file__).parent))
