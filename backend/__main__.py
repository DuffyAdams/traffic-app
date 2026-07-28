"""
Entry point for the Traffic Alert System.

Run with ``python -m backend``.
"""

import os
import threading

from .config import app, BASE_DIR, DB_FILE
from .logging_utils import safe_print
from .db import init_db
from .monitor import monitor_traffic_data

# Register all Flask routes by importing the module
from . import routes  # noqa: F401


def run_scraper_and_server():
    """Initialise the database, start the scraper thread, then serve Flask."""
    init_db()

    scraper_thread = threading.Thread(
        target=monitor_traffic_data,
        name="traffic-monitor",
        daemon=True,
    )
    scraper_thread.start()

    host = os.environ.get("TRAFFIC_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("TRAFFIC_APP_PORT", "5002"))

    safe_print("Starting Flask server...")
    app.run(debug=False, host=host, port=port, threaded=True)


def main():
    """Start the production scraper and API process."""
    safe_print("Traffic Alert System Starting...")
    safe_print(f"Base directory: {BASE_DIR}")
    safe_print(f"SQLite DB:      {DB_FILE}")

    try:
        run_scraper_and_server()
    except KeyboardInterrupt:
        safe_print("Traffic Alert System stopped.")


if __name__ == "__main__":
    main()
