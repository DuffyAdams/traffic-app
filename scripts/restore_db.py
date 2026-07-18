#!/usr/bin/env python3
"""
Restore the traffic database from a backup file.

If no backup path is provided, the newest backup in ./backups is used.
"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_FILE = ROOT_DIR / "traffic_data.db"
BACKUP_DIR = ROOT_DIR / "backups"


def pick_backup(path_arg: str | None) -> Path:
    if path_arg:
        candidate = Path(path_arg).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate

    backups = sorted(BACKUP_DIR.glob("traffic_data_*.db"))
    if not backups:
        raise FileNotFoundError(f"No backups found in {BACKUP_DIR}")
    return backups[-1]


def restore_from_backup(backup_path: Path) -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(backup_path)) as source, closing(
        sqlite3.connect(DB_FILE)
    ) as target:
        source.backup(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore the traffic database from a backup.")
    parser.add_argument(
        "backup",
        nargs="?",
        help="Optional backup file path. Defaults to the newest file in ./backups.",
    )
    args = parser.parse_args()

    try:
        backup_path = pick_backup(args.backup)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    restore_from_backup(backup_path)
    print(f"Restored database from: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
