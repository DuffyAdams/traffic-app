# config.py
"""
Shared configuration: paths, API keys, HTTP constants, and Flask app instance.
All other modules import from here to avoid circular dependencies.
"""

import os
import threading

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

# ── External API URLs ────────────────────────────────────────────────────────
CHP_SCRAPE_URL  = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"
SDPD_SCRAPE_URL = "https://webapps.sandiego.gov/sdpdonline"
SDFD_API_URL    = "https://webapps.sandiego.gov/SDFireDispatch/api/v1/Incidents"
SDSO_API_URL    = os.environ.get("SDSO_API_URL")
HEALTHCHECK_URL = "https://hc-ping.com/7299c402-d91d-4d89-8f84-5e6b510631c0"

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
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/maps/*": {"origins": "*"}})
