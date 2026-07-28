"""Run the beta web/API server without starting the scraper loop."""

import os

from .config import app
from .db import init_db
from .logging_utils import safe_print

# Register routes on the shared Flask app.
from . import routes  # noqa: F401


def main():
    init_db()
    host = os.environ.get("TRAFFIC_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("TRAFFIC_APP_PORT", "5003"))
    safe_print(f"Starting beta Flask server on {host}:{port}")
    app.run(debug=False, host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
