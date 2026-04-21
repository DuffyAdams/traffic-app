# logger.py
"""Thread-safe logging utility."""

import sys
from config import print_lock


def safe_print(*args, **kwargs):
    """Thread-safe print wrapper."""
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()
