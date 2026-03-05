"""
filesystem_watcher.py - File System Watcher for the AI Employee Vault.

Monitors the Drop_Zone/ folder for new files and creates structured
action files in Needs_Action/ for Claude Code to process.

Usage:
    python3 scripts/filesystem_watcher.py

Stop with Ctrl+C.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add scripts/ dir to path so base_watcher can be imported
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

# Vault path relative to project root
VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"

# Priority keywords that escalate urgency
PRIORITY_KEYWORDS = {"urgent", "asap", "invoice", "payment", "deadline", "overdue", "important"}

# Supported file types and their human-readable labels
SUPPORTED_TYPES = {
    ".pdf": "PDF Document",
    ".csv": "CSV Data File",
    ".txt": "Text File",
    ".docx": "Word Document",
    ".md": "Markdown File",
    ".xlsx": "Excel Spreadsheet",
    ".json": "JSON Data",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
}


def detect_urgency(filename: str) -> tuple[str, str]:
    """
    Returns (urgency_label, urgency_emoji) based on filename keywords.
    """
    name_lower = filename.lower()
    if any(kw in name_lower for kw in PRIORITY_KEYWORDS):
        return "High", "🟡"
    return "Normal", "🟢"


class FileSystemWatcher(BaseWatcher):
    """
    Watches the Drop_Zone/ folder for new files.
    When a file is detected:
      1. Creates a structured .md action file in /Needs_Action/
      2. Moves the original file to /Inbox/ for safe keeping
      3. Logs the event
    """

    def __init__(self, vault_path: Path, check_interval: int = 10):
        super().__init__(str(vault_path), check_interval)
        self.drop_zone = self.vault_path / "Drop_Zone"
        self.drop_zone.mkdir(parents=True, exist_ok=True)
        self.processed = self._load_processed_ids()

    def _processed_log_path(self) -> Path:
        return self.vault_path / "Logs" / "processed_files.txt"

    def _load_processed_ids(self) -> set:
        """Load the set of already-processed file names to avoid duplicates."""
        log = self._processed_log_path()
        if log.exists():
            return set(log.read_text(encoding="utf-8").splitlines())
        return set()

    def _save_processed_id(self, filename: str):
        """Persist a processed filename so we don't re-process on restart."""
        log = self._processed_log_path()
        with log.open("a", encoding="utf-8") as f:
            f.write(filename + "\n")
        self.processed.add(filename)

    def check_for_updates(self) -> list:
        """Scan Drop_Zone/ for new files not yet processed."""
        new_files = []
        for file in self.drop_zone.iterdir():
            if file.is_file() and file.name not in self.processed:
                new_files.append(file)
        return new_files

    def create_action_file(self, file: Path) -> Path:
        """
        Create a structured Markdown action file in /Needs_Action/.
        Then move the original file to /Inbox/ for safe keeping.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = file.stem.replace(" ", "_")
        action_filename = f"ACTION_{safe_name}_{timestamp}.md"
        action_path = self.needs_action / action_filename

        file_type = SUPPORTED_TYPES.get(file.suffix.lower(), "Unknown File Type")
        file_size = file.stat().st_size
        urgency_label, urgency_emoji = detect_urgency(file.name)

        content = f"""---
type: file_drop
original_name: {file.name}
file_type: {file_type}
size_bytes: {file_size}
detected: {datetime.now().isoformat()}
urgency: {urgency_label}
status: pending
---

# Action Required: {file.name}

{urgency_emoji} **Urgency:** {urgency_label}

## File Details

| Field | Value |
|-------|-------|
| Original name | `{file.name}` |
| Type | {file_type} |
| Size | {file_size:,} bytes |
| Detected | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |
| Stored in | `Inbox/{file.name}` |

## Suggested Actions

- [ ] Review file content
- [ ] Summarize and extract key information
- [ ] Route to appropriate folder or respond to sender
- [ ] Move this file to `/Done/` when complete

## Notes

*(Claude Code: read the file at `AI_Employee_Vault/Inbox/{file.name}` and process according to Company_Handbook.md)*
"""

        action_path.write_text(content, encoding="utf-8")

        # Move original file to Inbox for safe storage
        dest = self.inbox / file.name
        # Handle name collisions
        if dest.exists():
            dest = self.inbox / f"{file.stem}_{timestamp}{file.suffix}"
        shutil.move(str(file), str(dest))

        self._save_processed_id(file.name)
        self.logger.info(f"Processed '{file.name}' → action file: {action_filename}, stored at Inbox/{dest.name}")
        return action_path


def main():
    watcher = FileSystemWatcher(vault_path=VAULT_PATH, check_interval=10)
    watcher.run()


if __name__ == "__main__":
    main()
