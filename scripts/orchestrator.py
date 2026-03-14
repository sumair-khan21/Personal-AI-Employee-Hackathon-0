"""
orchestrator.py - Master Orchestrator for the Personal AI Employee Vault (Gold Tier).

Runs all watchers as managed subprocesses, implements the Ralph Wiggum loop
(monitors Needs_Action/ and Done/ for autonomous task awareness), writes a
live status JSON, and restarts crashed watchers automatically.

Ralph Wiggum loop:
    When a new ACTION_*.md appears in Needs_Action/ → log it.
    When a file lands in Done/ → log completion.
    This creates a continuous autonomous awareness loop.

Usage:
    # Start all watchers:
    python3 scripts/orchestrator.py

    # Print current status:
    python3 scripts/orchestrator.py --status

    # Graceful stop (same as Ctrl+C on the running process):
    python3 scripts/orchestrator.py --stop

Stop with Ctrl+C.
"""

import sys
import os
import json
import time
import signal
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import schedule
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Project setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import setup_logging

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"
SCRIPTS_DIR  = Path(__file__).parent

NEEDS_ACTION_DIR = VAULT_PATH / "Needs_Action"
DONE_DIR         = VAULT_PATH / "Done"
LOGS_DIR         = VAULT_PATH / "Logs"
STATUS_FILE      = LOGS_DIR / "orchestrator_status.json"
PID_FILE         = LOGS_DIR / "orchestrator.pid"

# Python interpreter inside the venv — use path directly (don't resolve symlinks)
_venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable

# ── Logging ───────────────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("Orchestrator")
logger.setLevel(logging.INFO)

_fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "%Y-%m-%d %H:%M:%S",
)

_fh = logging.FileHandler(LOGS_DIR / "orchestrator.log", encoding="utf-8")
_fh.setFormatter(_fmt)

_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)

logger.addHandler(_fh)
logger.addHandler(_ch)


# ── Watcher definitions ───────────────────────────────────────────────────────

class WatcherDef:
    """Describes one managed watcher subprocess."""

    def __init__(self, name: str, cmd: list[str], mode: str, interval: int = 0):
        """
        name     — human-readable identifier
        cmd      — command list passed to subprocess.Popen
        mode     — "continuous" (persistent) | "scheduled" (run every `interval` seconds)
        interval — only for scheduled mode; seconds between runs
        """
        self.name     = name
        self.cmd      = cmd
        self.mode     = mode          # "continuous" | "scheduled"
        self.interval = interval      # seconds (scheduled mode only)
        self.process: subprocess.Popen | None = None
        self.pid: int | None = None
        self.restarts: int = 0
        self.last_start: datetime | None = None
        self.status: str = "stopped"  # running | stopped | error


# Watcher registry
WATCHERS: list[WatcherDef] = [
    WatcherDef(
        name="filesystem",
        cmd=[PYTHON, str(SCRIPTS_DIR / "filesystem_watcher.py")],
        mode="continuous",
    ),
    WatcherDef(
        name="send_email",
        cmd=[PYTHON, str(SCRIPTS_DIR / "send_email.py"), "--watch"],
        mode="continuous",
    ),
    WatcherDef(
        name="gmail",
        cmd=[PYTHON, str(SCRIPTS_DIR / "gmail_watcher.py"), "--once"],
        mode="scheduled",
        interval=120,
    ),
    WatcherDef(
        name="linkedin_watch",
        cmd=[PYTHON, str(SCRIPTS_DIR / "linkedin_watcher.py"), "--watch", "--once"],
        mode="scheduled",
        interval=600,
    ),
    WatcherDef(
        name="linkedin_post",
        cmd=[PYTHON, str(SCRIPTS_DIR / "linkedin_watcher.py"), "--post"],
        mode="scheduled",
        interval=300,
    ),
    WatcherDef(
        name="odoo",
        cmd=[PYTHON, str(SCRIPTS_DIR / "odoo_watcher.py"), "--once"],
        mode="scheduled",
        interval=3600,
    ),
]

# ── Global state ──────────────────────────────────────────────────────────────
_start_time = datetime.now(timezone.utc)
_shutdown_event = threading.Event()


# ── Ralph Wiggum loop — vault event handler ───────────────────────────────────

class VaultEventHandler(FileSystemEventHandler):
    """
    Watchdog event handler for Needs_Action/ and Done/.
    Logs every new ACTION_*.md that appears and every completion.
    """

    def __init__(self, watch_dir: Path, label: str):
        super().__init__()
        self.watch_dir = watch_dir
        self.label     = label

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix == ".md":
            if self.label == "Needs_Action":
                logger.info(f"[Ralph Wiggum] New action detected: {p.name}")
            else:
                logger.info(f"[Ralph Wiggum] Task completed: {p.name}")

    def on_moved(self, event):
        """Also catch files moved into Done/ (common vault workflow)."""
        if event.is_directory:
            return
        dest = Path(event.dest_path)
        if dest.parent == DONE_DIR and dest.suffix == ".md":
            logger.info(f"[Ralph Wiggum] Task moved to Done: {dest.name}")


# ── Continuous watcher management ─────────────────────────────────────────────

def _start_continuous(wd: WatcherDef):
    """Launch a continuous watcher subprocess and record its PID."""
    try:
        proc = subprocess.Popen(
            wd.cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        wd.process  = proc
        wd.pid      = proc.pid
        wd.status   = "running"
        wd.last_start = datetime.now(timezone.utc)
        logger.info(f"[{wd.name}] Started (pid={proc.pid})")
    except FileNotFoundError as e:
        wd.status = "error"
        logger.warning(f"[{wd.name}] Could not start — script not found: {e}")
    except Exception as e:
        wd.status = "error"
        logger.error(f"[{wd.name}] Failed to start: {e}")


def _watchdog_loop(wd: WatcherDef):
    """Thread: keeps a continuous watcher alive, restarts on crash."""
    _start_continuous(wd)
    while not _shutdown_event.is_set():
        time.sleep(5)
        if _shutdown_event.is_set():
            break
        if wd.process and wd.process.poll() is not None:
            exit_code = wd.process.returncode
            # Exit code 1 = config/auth error — back off, don't spam restarts
            if exit_code == 1:
                wd.status = "error"
                logger.warning(
                    f"[{wd.name}] Exited with code 1 (auth/config error). "
                    f"Waiting 300s before retry..."
                )
                for _ in range(60):  # wait 300s in 5s steps
                    if _shutdown_event.is_set():
                        break
                    time.sleep(5)
            wd.restarts += 1
            if not _shutdown_event.is_set():
                logger.warning(f"[{wd.name}] Restarting... (restart #{wd.restarts})")
                _start_continuous(wd)
    # Shutdown — terminate the child
    if wd.process and wd.process.poll() is None:
        logger.info(f"[{wd.name}] Stopping (pid={wd.pid})...")
        wd.process.terminate()
        try:
            wd.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            wd.process.kill()
    wd.status = "stopped"
    logger.info(f"[{wd.name}] Stopped.")


# ── Scheduled watcher runner ──────────────────────────────────────────────────

def _run_scheduled(wd: WatcherDef):
    """Run a scheduled watcher once and wait for it to finish."""
    if _shutdown_event.is_set():
        return
    logger.info(f"[{wd.name}] Running scheduled job...")
    try:
        proc = subprocess.Popen(
            wd.cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        wd.process    = proc
        wd.pid        = proc.pid
        wd.status     = "running"
        wd.last_start = datetime.now(timezone.utc)
        proc.wait()
        wd.status = "idle"
        logger.info(f"[{wd.name}] Scheduled job finished (exit={proc.returncode}).")
    except FileNotFoundError:
        wd.status = "error"
        logger.warning(f"[{wd.name}] Script not found — skipping scheduled run.")
    except Exception as e:
        wd.status = "error"
        logger.error(f"[{wd.name}] Scheduled job error: {e}")


def _scheduler_loop():
    """Thread: drives the `schedule` library until shutdown."""
    while not _shutdown_event.is_set():
        schedule.run_pending()
        time.sleep(1)


# ── Status file ───────────────────────────────────────────────────────────────

def _write_status():
    """Write a live JSON status snapshot every 60 seconds."""
    while not _shutdown_event.is_set():
        try:
            now = datetime.now(timezone.utc)
            uptime = int((now - _start_time).total_seconds())

            watchers_info = {}
            for wd in WATCHERS:
                watchers_info[wd.name] = {
                    "status":   wd.status,
                    "pid":      wd.pid,
                    "restarts": wd.restarts,
                    "mode":     wd.mode,
                }
                if wd.mode == "scheduled":
                    watchers_info[wd.name]["interval_seconds"] = wd.interval

            needs_action_count = len(list(NEEDS_ACTION_DIR.glob("*.md"))) if NEEDS_ACTION_DIR.exists() else 0
            done_count         = len(list(DONE_DIR.glob("*.md")))         if DONE_DIR.exists()         else 0

            status = {
                "timestamp":          now.strftime("%Y-%m-%dT%H:%M:%S"),
                "watchers":           watchers_info,
                "needs_action_count": needs_action_count,
                "done_count":         done_count,
                "uptime_seconds":     uptime,
            }

            STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not write status file: {e}")

        # Sleep in small increments so we can exit quickly on shutdown
        for _ in range(60):
            if _shutdown_event.is_set():
                break
            time.sleep(1)


# ── Vault observer setup ──────────────────────────────────────────────────────

def _start_vault_observers() -> list[Observer]:
    """Start watchdog observers on Needs_Action/ and Done/."""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    observers = []
    for folder, label in [(NEEDS_ACTION_DIR, "Needs_Action"), (DONE_DIR, "Done")]:
        obs = Observer()
        obs.schedule(VaultEventHandler(folder, label), str(folder), recursive=False)
        obs.start()
        observers.append(obs)
        logger.info(f"[Ralph Wiggum] Watching {folder.name}/ for changes.")
    return observers


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_orchestrator():
    """Start all watchers, observers, scheduler, and status writer."""
    logger.info("=" * 60)
    logger.info("Personal AI Employee Orchestrator starting...")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Vault path:   {VAULT_PATH}")
    logger.info("=" * 60)

    # Write PID file so --stop can find us
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    # ── 1. Start vault observers (Ralph Wiggum loop) ──────────────────────────
    observers = _start_vault_observers()

    # ── 2. Start continuous watchers in watchdog threads ─────────────────────
    threads: list[threading.Thread] = []
    for wd in WATCHERS:
        if wd.mode == "continuous":
            t = threading.Thread(target=_watchdog_loop, args=(wd,), daemon=True, name=f"wd-{wd.name}")
            t.start()
            threads.append(t)
            logger.info(f"[{wd.name}] Watchdog thread started.")

    # ── 3. Register scheduled jobs ────────────────────────────────────────────
    for wd in WATCHERS:
        if wd.mode == "scheduled":
            # Run immediately on start, then on schedule
            _run_scheduled(wd)
            schedule.every(wd.interval).seconds.do(_run_scheduled, wd)
            logger.info(f"[{wd.name}] Scheduled every {wd.interval}s.")

    # Scheduler thread
    sched_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
    sched_thread.start()

    # ── 4. Status writer thread ───────────────────────────────────────────────
    status_thread = threading.Thread(target=_write_status, daemon=True, name="status-writer")
    status_thread.start()

    logger.info("All watchers launched. Press Ctrl+C to stop.")
    logger.info(f"Live status: {STATUS_FILE}")

    # ── 5. Wait for SIGINT / --stop ───────────────────────────────────────────
    def _sigint_handler(sig, frame):
        logger.info("SIGINT received — shutting down gracefully...")
        _shutdown_event.set()

    signal.signal(signal.SIGINT,  _sigint_handler)
    signal.signal(signal.SIGTERM, _sigint_handler)

    try:
        while not _shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown_event.set()

    # ── 6. Graceful shutdown ──────────────────────────────────────────────────
    logger.info("Stopping vault observers...")
    for obs in observers:
        obs.stop()
    for obs in observers:
        obs.join(timeout=5)

    logger.info("Waiting for watcher threads to finish...")
    for t in threads:
        t.join(timeout=10)

    # Clean up PID file
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    logger.info("Orchestrator stopped. Goodbye.")


# ── --status command ──────────────────────────────────────────────────────────

def print_status():
    """Print the current orchestrator_status.json to stdout."""
    if not STATUS_FILE.exists():
        print("No status file found. Is the orchestrator running?")
        print(f"Expected: {STATUS_FILE}")
        return

    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    print(f"\nOrchestrator Status — {data.get('timestamp', 'unknown')}")
    print(f"  Uptime:           {data.get('uptime_seconds', 0)}s")
    print(f"  Needs Action:     {data.get('needs_action_count', 0)} items")
    print(f"  Done:             {data.get('done_count', 0)} items")
    print()
    print("  Watchers:")
    for name, info in data.get("watchers", {}).items():
        pid_str = f"pid={info['pid']}" if info.get("pid") else "no pid"
        print(
            f"    {name:<20} {info.get('status','?'):<10} "
            f"{pid_str}  restarts={info.get('restarts', 0)}"
        )


# ── --stop command ────────────────────────────────────────────────────────────

def stop_orchestrator():
    """Send SIGTERM to the running orchestrator process."""
    if not PID_FILE.exists():
        print("PID file not found. Is the orchestrator running?")
        return

    pid_str = PID_FILE.read_text(encoding="utf-8").strip()
    try:
        pid = int(pid_str)
        os.kill(pid, signal.SIGTERM)
        print(f"SIGTERM sent to orchestrator (pid={pid}).")
    except (ValueError, ProcessLookupError):
        print(f"Could not signal pid={pid_str}. Process may have already stopped.")
    except PermissionError:
        print(f"Permission denied sending signal to pid={pid_str}.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--status" in args:
        print_status()
        return

    if "--stop" in args:
        stop_orchestrator()
        return

    run_orchestrator()


if __name__ == "__main__":
    main()
