# config.py
"""
Shared configuration: paths, API keys, HTTP constants, and Flask app instance.
All other modules import from here to avoid circular dependencies.
"""

import os
import threading
from datetime import datetime

import pytz
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

from geocoding import GeocodingCache

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR   = os.path.join(BASE_DIR, "traffic-app", "maps")
DB_FILE      = os.path.join(BASE_DIR, "traffic_data.db")
MAP_GENERATOR = os.path.join(BASE_DIR, "generate_map.py")

os.makedirs(TARGET_DIR, exist_ok=True)

# ── Feature flags ────────────────────────────────────────────────────────────
TESTMODE = os.environ.get("TESTMODE", "False").lower() == "true"

# LLM enrichment: Mistral handles the immediate response, then Gemini refines
# incidents together after a short collection window.
BATCH_LLM_ENABLED = os.environ.get("BATCH_LLM_ENABLED", "True").lower() == "true"
BATCH_LLM_MODEL = os.environ.get(
    "BATCH_LLM_MODEL", "google/gemini-2.5-flash-lite"
)
BATCH_LLM_INTERVAL_SECONDS = max(
    1, int(os.environ.get("BATCH_LLM_INTERVAL_SECONDS", "300"))
)
BATCH_LLM_MAX_ITEMS = max(1, int(os.environ.get("BATCH_LLM_MAX_ITEMS", "100")))

# San Diego traffic sources use the local Pacific clock, including daylight time.
PACIFIC = pytz.timezone("America/Los_Angeles")
# Backward-compatible alias for existing imports; now DST-aware.
PST = PACIFIC


def now_pst():
    """Return the current time in San Diego's Pacific timezone."""
    return datetime.now(PST)


def ensure_pst(dt):
    """Attach/convert a datetime to San Diego's Pacific timezone."""
    if dt.tzinfo is None:
        return PST.localize(dt)
    return dt.astimezone(PST)


def pst_date_str(dt=None):
    """Format a datetime as a Pacific time date string."""
    return ensure_pst(dt or now_pst()).strftime("%Y-%m-%d")


def pst_timestamp_str(dt=None):
    """Format a datetime as a Pacific time timestamp string."""
    return ensure_pst(dt or now_pst()).strftime("%Y-%m-%d %H:%M:%S")

# ── External API URLs ────────────────────────────────────────────────────────
CHP_SCRAPE_URL  = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"
SDPD_SCRAPE_URL = "https://webapps.sandiego.gov/sdpdonline"
SDFD_API_URL    = "https://webapps.sandiego.gov/SDFireDispatch/api/v1/Incidents"
SDSO_API_URL    = os.environ.get("SDSO_API_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "12"))

# ── HTTP headers shared by all scrapers ─────────────────────────────────────
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}
PARAMS = {"ddlComCenter": "BCCC"}

# ── Cookie settings ──────────────────────────────────────────────────────────
COOKIE_NAME    = "traffic_app_uuid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year
COOKIE_SECURE  = os.environ.get("COOKIE_SECURE", str(not TESTMODE)).lower() == "true"

# ── Public API guardrails ────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "TRAFFIC_APP_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
API_DEFAULT_RATE_LIMIT = os.environ.get("API_DEFAULT_RATE_LIMIT", "300 per minute")
API_READ_RATE_LIMIT    = os.environ.get("API_READ_RATE_LIMIT", "120 per minute")
API_WRITE_RATE_LIMIT   = os.environ.get("API_WRITE_RATE_LIMIT", "20 per minute")
_default_trust_proxy = "true" if os.environ.get("TRAFFIC_APP_HOST", "127.0.0.1") in {"127.0.0.1", "localhost", "::1"} else "false"
TRUST_PROXY_HEADERS    = os.environ.get("TRUST_PROXY_HEADERS", _default_trust_proxy).lower() == "true"

# ── OpenAI / OpenRouter client ───────────────────────────────────────────────
GPT_KEY = os.getenv("GPT_KEY")
llm_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=GPT_KEY,
)

# ── Geocoding cache (shared across modules) ──────────────────────────────────
geo_cache = GeocodingCache(DB_FILE)

# ── Thread locks ─────────────────────────────────────────────────────────────
db_lock    = threading.Lock()
print_lock = threading.Lock()

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "traffic-app", "dist"))
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
CORS(
    app,
    resources={
        r"/api/*": {"origins": ALLOWED_ORIGINS},
        r"/maps/*": {"origins": ALLOWED_ORIGINS},
    },
)
