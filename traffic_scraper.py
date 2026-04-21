# traffic_scraper.py
"""
Entry point for the Traffic Alert System.

Structure
---------
config.py     — constants, paths, Flask app, locks, clients
logger.py     — thread-safe safe_print()
db.py         — SQLite schema, CRUD operations
llm.py        — LLM description + severity generation
scrapers/
  chp.py      — California Highway Patrol scraper
  sdpd.py     — San Diego Police Department scraper
  sdfd.py     — San Diego Fire Department scraper
  sdso.py     — San Diego Sheriff's Office scraper
monitor.py    — background monitoring loop + geocoding orchestration
routes.py     — Flask API endpoints
traffic_scraper.py  ← you are here (entry point only)
"""

import threading

from config import app, BASE_DIR, DB_FILE, MAP_GENERATOR, TARGET_DIR
from logger import safe_print
from db import init_db
from monitor import monitor_traffic_data

# Register all Flask routes by importing the module
import routes  # noqa: F401


def run_scraper_and_server():
    """Initialise the database, start the scraper thread, then serve Flask."""
    import os

    init_db()

    scraper_thread = threading.Thread(target=monitor_traffic_data, daemon=True)
    scraper_thread.start()

    safe_print("Starting Flask server...")
    try:
        app.run(debug=False, host="127.0.0.1", port=5002, threaded=True)
    except Exception as e:
        safe_print(f"Server error: {e}")
        os._exit(1)
    except SystemExit:
        os._exit(1)


if __name__ == "__main__":
    import os

    safe_print("Traffic Alert System Starting...")
    safe_print(f"Base directory: {BASE_DIR}")
    safe_print(f"Map directory:  {TARGET_DIR}")
    safe_print(f"SQLite DB:      {DB_FILE}")
    if not os.path.exists(MAP_GENERATOR):
        safe_print(f"WARNING: Map generator not found at {MAP_GENERATOR}")

    try:
        run_scraper_and_server()
    except KeyboardInterrupt:
        os._exit(0)
