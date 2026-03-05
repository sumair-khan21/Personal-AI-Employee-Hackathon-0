"""
base_watcher.py - Abstract base class for all AI Employee Watchers.

All watcher implementations (filesystem, gmail, whatsapp) extend this class.
"""

import time
import logging
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime

# Configure logging to both file and stdout
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(vault_path: Path, logger_name: str) -> logging.Logger:
    log_dir = vault_path / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "activity.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # File handler (persistent)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


class BaseWatcher(ABC):
    """
    Abstract base for all Watcher scripts.
    Subclasses implement check_for_updates() and create_action_file().
    """

    def __init__(self, vault_path: str, check_interval: int = 10):
        self.vault_path = Path(vault_path).resolve()
        self.needs_action = self.vault_path / "Needs_Action"
        self.inbox = self.vault_path / "Inbox"
        self.done = self.vault_path / "Done"
        self.check_interval = check_interval

        # Ensure required folders exist
        for folder in [self.needs_action, self.inbox, self.done]:
            folder.mkdir(parents=True, exist_ok=True)

        self.logger = setup_logging(self.vault_path, self.__class__.__name__)

    @abstractmethod
    def check_for_updates(self) -> list:
        """
        Poll for new items to process.
        Returns a list of items (dicts or objects) to be acted upon.
        """
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """
        Given a detected item, create a .md action file in /Needs_Action/.
        Returns the path of the created file.
        """
        pass

    def update_dashboard(self):
        """Update the pending count in Dashboard.md."""
        dashboard = self.vault_path / "Dashboard.md"
        if not dashboard.exists():
            return
        try:
            content = dashboard.read_text(encoding="utf-8")
            pending = len(list(self.needs_action.glob("*.md")))
            done = len(list(self.done.glob("*.md")))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Update counts
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("- **Pending items in /Needs_Action:**"):
                    line = f"- **Pending items in /Needs_Action:** {pending}"
                elif line.startswith("- **Items in /Done:**"):
                    line = f"- **Items in /Done:** {done}"
                elif line.startswith("> **Last Updated:**"):
                    line = f"> **Last Updated:** {now}"
                new_lines.append(line)
            dashboard.write_text("\n".join(new_lines), encoding="utf-8")
        except Exception as e:
            self.logger.warning(f"Could not update Dashboard.md: {e}")

    def run(self):
        """Main loop — polls for updates at check_interval seconds."""
        self.logger.info(f"Starting {self.__class__.__name__} (interval={self.check_interval}s)")
        self.logger.info(f"Vault path: {self.vault_path}")
        self.logger.info("Press Ctrl+C to stop.")

        try:
            while True:
                try:
                    items = self.check_for_updates()
                    for item in items:
                        path = self.create_action_file(item)
                        self.logger.info(f"Action file created: {path.name}")
                    if items:
                        self.update_dashboard()
                except Exception as e:
                    self.logger.error(f"Error during update cycle: {e}")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.logger.info(f"{self.__class__.__name__} stopped by user.")
