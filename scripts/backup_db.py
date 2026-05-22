#!/usr/bin/env python3
"""
Create a consistent SQLite backup of the traffic database.

The live database runs in WAL mode, so use SQLite's backup API instead of
copying the .db file directly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_FILE = ROOT_DIR / "traffic_data.db"
BACKUP_DIR = ROOT_DIR / "backups"
KEEP_BACKUPS = 3


def main() -> int:
    if not DB_FILE.exists():
        print(f"Database not found: {DB_FILE}", file=sys.stderr)
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_UTC")
    backup_path = BACKUP_DIR / f"traffic_data_{timestamp}.db"

    with sqlite3.connect(DB_FILE) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)

    print(f"Created backup: {backup_path}")
    prune_old_backups()
    return 0


def prune_old_backups() -> None:
    """Keep only the newest `KEEP_BACKUPS` SQLite backups."""
    backups = sorted(BACKUP_DIR.glob("traffic_data_*.db"))
    excess = backups[:-KEEP_BACKUPS]

    for old_backup in excess:
        old_backup.unlink(missing_ok=True)
        print(f"Removed old backup: {old_backup}")


if __name__ == "__main__":
    raise SystemExit(main())
