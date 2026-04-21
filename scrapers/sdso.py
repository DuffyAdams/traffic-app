# scrapers/sdso.py
"""San Diego Sheriff's Office (SDSO) incident scraper with 5-minute result cache."""

import time
from datetime import datetime

import requests

from config import SDSO_API_URL, HEADERS
from logger import safe_print

# ── Module-level cache to throttle SDSO requests (max once per 5 min) ──────
_last_fetch: float = 0
_cache: list = []
_CACHE_TTL  = 300  # seconds


def scrape_sdso_incidents():
    """Return SDSO incidents, using a local cache if fetched within the last 5 minutes."""
    global _last_fetch, _cache

    if time.time() - _last_fetch < _CACHE_TTL:
        return _cache

    if not SDSO_API_URL:
        safe_print("SDSO: SDSO_API_URL not configured, skipping.")
        return []

    safe_print("Scraping SDSO incidents...")
    try:
        response = requests.get(SDSO_API_URL, headers=HEADERS)
        response.raise_for_status()
        data   = response.json()
        events = data.get("Events", [])

        incidents = []
        for item in events:
            event_id   = item.get("EventNumber", "")
            is_open    = item.get("IsOpen", False)
            dt_str     = item.get("DateTime", "")
            address    = item.get("Address", "")
            community  = item.get("Community", "")
            event_type = item.get("EventType", "")

            incident_id = f"SDSO-{event_id}"

            try:
                dt_obj   = datetime.strptime(dt_str, "%m/%d/%y %H:%M")
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                safe_print(f"SDSO: Date parse error for '{dt_str}': {e}")
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            details = []
            if item.get("ServiceArea"):
                details.append(f"Service Area: {item['ServiceArea']}")

            incidents.append({
                "No.":           incident_id,
                "Date":          date_val,
                "Timestamp":     time_val,
                "City":          "San Diego County",
                "Neighborhood":  community,
                "Location":      address,
                "Location Desc.": "",
                "Type":          event_type,
                "Details":       details,
                "Source":        "SDSO",
                "active":        1 if is_open else 0,
            })

        safe_print(f"SDSO: Found {len(incidents)} incidents.")
        _last_fetch = time.time()
        _cache      = incidents
        return incidents

    except Exception as e:
        safe_print(f"Error scraping SDSO: {e}")
        return []
