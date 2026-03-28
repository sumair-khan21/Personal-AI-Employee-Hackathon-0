# Platinum Tier — Personal AI Employee Hackathon 0

## Context
Gold Tier is complete and fully tested locally. Platinum moves the AI Employee from a laptop-dependent process to a 24/7 cloud-resident autonomous agent using 100% free tools. Nothing is rewritten — the existing orchestrator, watchers, vault, and Odoo Docker stack all migrate as-is. Three new capabilities are added: cloud hosting (Oracle Always Free), health monitoring, and WhatsApp send.

---

## Phase 1: Oracle Cloud Always Free VM

### Goal
Get a free cloud VM running with all dependencies installed, ready to host the AI Employee 24/7 without keeping the laptop on.

### Step-by-Step

**1. Create Oracle Cloud Account**
- Go to cloud.oracle.com → Sign Up for Always Free
- Home region: `ap-mumbai-1` (closest to Pakistan)
- Credit card required for identity only (not charged)

**2. Create the VM**
- Compute > Instances > Create Instance
- Name: `ai-employee`
- Image: **Canonical Ubuntu 22.04** (change from Oracle Linux)
- Shape: `VM.Standard.E2.1.Micro` (confirm "Always Free eligible" badge)
- Allow public IP assignment
- SSH Keys: paste your public key

```bash
# Generate SSH key on local machine (if needed)
ssh-keygen -t ed25519 -C "ai-employee-oracle" -f ~/.ssh/oracle_ai_employee
cat ~/.ssh/oracle_ai_employee.pub   # paste this into Oracle console
```

**3. Open Ports (Oracle VCN Security List)**
- Networking > VCN > Security Lists > Default > Add Ingress Rules:
  - TCP port 22 from 0.0.0.0/0 (SSH)
  - TCP port 8069 from your-home-IP only (Odoo, Phase 3)

**4. First SSH + OS Firewall**
```bash
# Connect from local machine
ssh -i ~/.ssh/oracle_ai_employee ubuntu@<VM_PUBLIC_IP>

# On VM — open firewall
sudo ufw allow 22/tcp
sudo ufw allow 8069/tcp
sudo ufw enable
```

**5. Install All Dependencies on VM**
```bash
sudo apt-get update && sudo apt-get upgrade -y

# Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Git, Docker, Docker Compose
sudo apt-get install -y git docker.io docker-compose
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker ubuntu

# Playwright system deps (Chromium)
sudo apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libexpat1 libxcb1 libxkbcommon0 libatspi2.0-0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2

# Node.js 20 (for MCP servers in Phase 7)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Syncthing (for Phase 2 vault sync)
curl -s https://syncthing.net/release-key.txt | sudo tee /etc/apt/trusted.gpg.d/syncthing.asc
echo "deb https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list
sudo apt-get update && sudo apt-get install -y syncthing
```

**6. Clone Repo onto VM**
```bash
# On VM
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/<your-username>/<your-repo>.git "Personal AI Employee Hackathon 0"
cd "Personal AI Employee Hackathon 0"
```

For private repo — add a deploy key:
```bash
ssh-keygen -t ed25519 -C "oracle-vm-deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub  # Add in GitHub > Settings > Deploy Keys
```

**7. Setup Python Venv on VM**
```bash
cd ~/projects/Personal\ AI\ Employee\ Hackathon\ 0
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
.venv/bin/playwright install-deps chromium
```

**8. Copy Secrets to VM** (gitignored files — must copy manually)
```bash
# On LOCAL machine
VM="ubuntu@<VM_PUBLIC_IP>"
KEY="~/.ssh/oracle_ai_employee"
PROJ="/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0"
DEST="~/projects/Personal AI Employee Hackathon 0"

scp -i $KEY "$PROJ/.env"             $VM:"$DEST/.env"
scp -i $KEY "$PROJ/credentials.json" $VM:"$DEST/credentials.json"
scp -i $KEY "$PROJ/token.json"       $VM:"$DEST/token.json"
```

### Phase 1 Checklist
- [ ] Oracle account created, VM status = **Running**
- [ ] `ssh -i ~/.ssh/oracle_ai_employee ubuntu@<VM_PUBLIC_IP>` connects
- [ ] `python3.11 --version` → 3.11.x
- [ ] `docker --version` → 24.x or higher
- [ ] `node --version` → v20.x
- [ ] `.venv/bin/playwright --version` → returns version
- [ ] `.env`, `credentials.json`, `token.json` present on VM
- [ ] VM Public IP saved: _______________

### How to Test Phase 1
```bash
# Test 1 — SSH round-trip
ssh -i ~/.ssh/oracle_ai_employee ubuntu@<VM_PUBLIC_IP> \
  "hostname && python3.11 --version && docker --version"

# Test 2 — Script imports work
ssh -i ~/.ssh/oracle_ai_employee ubuntu@<VM_PUBLIC_IP> \
  "cd ~/projects/Personal\ AI\ Employee\ Hackathon\ 0 && \
   .venv/bin/python3 -c 'from scripts.orchestrator import WATCHERS; print(len(WATCHERS), \"watchers registered\")'"
# Expected: 6 watchers registered

# Test 3 — Vault dirs present
ssh -i ~/.ssh/oracle_ai_employee ubuntu@<VM_PUBLIC_IP> \
  "ls ~/projects/Personal\ AI\ Employee\ Hackathon\ 0/AI_Employee_Vault/"
# Expected: Needs_Action  Done  Logs  Accounting  Plans  ...
```

---

## Phases 2–8 — Summary (detail provided on "next")

| Phase | What Gets Built | Key Files |
|-------|----------------|-----------|
| **2** | Git sync (code) + Syncthing (vault) — live sync between local Obsidian and VM | `scripts/sync_vault.sh`, systemd syncthing unit |
| **3** | Odoo + Docker migrated to VM (second Always Free instance) | `docker/docker-compose.yml` updated paths |
| **4** | Orchestrator as systemd service — survives reboots, auto-starts on VM | `systemd/ai-employee.service`, session rsync script |
| **5** | `health_monitor.py` — checks watcher PIDs, reads `orchestrator_status.json`, emails alert via Gmail API if anything dies | `scripts/health_monitor.py` |
| **6** | `whatsapp_send.py` — HITL-gated WhatsApp message sender via Playwright | `scripts/whatsapp_send.py` |
| **7** | Real MCP server configs wired into `.mcp.json` (filesystem, gmail, brave-search) | `.mcp.json` |
| **8** | Platinum README, architecture diagram, final `verify.py` with Platinum checks | `README.md`, `scripts/verify.py` |

### Key Constraint: RAM Budget
- Oracle Always Free = 1GB RAM per VM
- AI Employee scripts (orchestrator + all watchers) ≈ 150–300MB
- Odoo 17 + PostgreSQL 15 ≈ 600–800MB minimum
- **Solution:** Use 2 Always Free VMs — VM1 for AI Employee scripts, VM2 for Odoo+Docker

### Critical Files (referenced in all phases)
- `scripts/orchestrator.py` — WATCHERS registry; paths updated to VM absolute paths in Phase 4
- `docker/docker-compose.yml` — Odoo stack; volume paths + port bindings updated in Phase 3
- `scripts/whatsapp_watcher.py` — Phase 6 `whatsapp_send.py` extends same `SESSION_DIR` and Playwright pattern
- `scripts/audit_logger.py` — Phase 5 health monitor reads this to detect dead watchers
- `scripts/crontab.txt` — replaced by systemd units in Phase 4 (paths change from `/home/sumair/...` to `/home/ubuntu/...`)
